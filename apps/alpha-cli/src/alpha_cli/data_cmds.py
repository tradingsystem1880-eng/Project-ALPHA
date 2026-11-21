"""`alpha data` subcommands: pull, snapshot, verify, candles, symbols."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from inspect import Parameter, signature
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from alpha_cli.market_overview_cmds import run_market_overview
from alpha_cli.providers import (
    HistoricalAdapterFactory,
    historical_adapter_factories,
    provider_option_choices,
)
from alpha_cli.run_price_cmds import run_run_price
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.adapters.base import DataAdapter
from alpha_data.pipeline import (
    RestoreFailed,
    promote_quarantined,
    rollback_interrupted_promotion,
)
from alpha_data.pull_store import FreezeRefused, pull_into_store
from alpha_data.snapshot import (
    create_snapshot,
    resolve_snapshot_dir,
    snapshot_manifest_hash,
    snapshot_timeframe,
    verify_snapshot,
)
from alpha_data.snapshot_reuse import content_hash, read_manifests, shared_content, total_bytes
from alpha_data.store import ParquetStore
from alpha_data.timeframe import DAILY, BarTimeframe, parse_timeframe, store_dir

data_app = typer.Typer(help="Data ingestion, snapshots, and integrity.")

# adapter registry — tests monkeypatch this to inject offline fakes
_ADAPTERS: dict[str, HistoricalAdapterFactory] = historical_adapter_factories()
_CCXT_EXCHANGES = provider_option_choices("ccxt", "exchange")
_DEFAULT_CCXT_EXCHANGE = "coinbase"


_TIMEFRAME_HELP = (
    "bar timeframe: 1D (default) or 1m..59m, 1h..23h; sub-minute and tick data are excluded"
)


def _timeframe(text: str) -> BarTimeframe:
    try:
        return parse_timeframe(text)
    except DataError as exc:
        raise typer.BadParameter(str(exc), param_hint="--timeframe") from exc


def _store(timeframe: BarTimeframe = DAILY) -> ParquetStore:
    return ParquetStore(store_dir(AlphaSettings().data_dir, timeframe))


def _snaps_root() -> Path:
    return AlphaSettings().data_dir / "snapshots"


def _candle_provenance(
    symbol: str,
    *,
    snapshot_id: str | None,
    knowledge_cutoff: datetime | None,
    timeframe: BarTimeframe = DAILY,
    source_timeframe: BarTimeframe | None = None,
    session: str | None = None,
) -> dict[str, object]:
    data_root = AlphaSettings().data_dir
    stored = source_timeframe or timeframe
    root = data_root / "snapshots" / snapshot_id if snapshot_id else store_dir(data_root, stored)
    store = ParquetStore(root)
    provenance = store.read_provenance(symbol)
    path = store._provenance_path(symbol)
    provenance_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    source = provenance.get("source") if provenance is not None else "unknown"
    dataset = provenance.get("dataset") if provenance is not None else None
    venue = dataset.get("venue") if isinstance(dataset, dict) else None
    dataset_timeframe = (
        dataset.get("timeframe") if isinstance(dataset, dict) else timeframe.canonical
    )
    receipt = provenance.get("receipt") if provenance is not None else None
    receipt_id = receipt.get("receipt_id") if isinstance(receipt, dict) else None
    quality_status = "legacy_unqualified"
    if isinstance(receipt_id, str) and isinstance(source, str):
        if not isinstance(dataset_timeframe, str):
            raise DataError("dataset provenance must name a bar timeframe")
        quality_root = store_dir(data_root, parse_timeframe(dataset_timeframe))
        passed = quality_root / "candidates" / source / receipt_id / "quality.json"
        reviewed = quality_root / "quarantine" / source / receipt_id / "quality.json"
        quality_status = (
            "passed"
            if passed.is_file()
            else "owner_approved"
            if reviewed.is_file()
            else "qualified"
        )
    result: dict[str, object] = {
        "source": source,
        "venue": venue,
        "timeframe": dataset_timeframe,
        "snapshot_id": snapshot_id,
        "provenance_sha256": provenance_hash,
        "receipt_id": receipt_id,
        "knowledge_cutoff": knowledge_cutoff.isoformat() if knowledge_cutoff is not None else None,
        "quality_status": quality_status,
    }

    if not timeframe.is_daily or not stored.is_daily:
        from alpha_cli._runner import _calendar_for
        from alpha_data.sessions import default_session

        result["timeframe"] = timeframe.canonical
        result["session"] = session or default_session(_calendar_for(symbol, provenance))
    return result


def _adapter(
    source: str,
    exchange: str,
    *,
    asset_class: str = "stock",
    venue: str = "US",
    calendar: str = "XNYS",
    currency: str = "USD",
    timeframe: BarTimeframe = DAILY,
) -> DataAdapter:
    factory = _ADAPTERS.get(source)
    if factory is None:
        raise typer.BadParameter(f"unknown source {source!r}; known: {sorted(_ADAPTERS)}")
    if exchange not in _CCXT_EXCHANGES:
        raise typer.BadParameter(
            f"unknown CCXT exchange {exchange!r}; known: {list(_CCXT_EXCHANGES)}",
            param_hint="--exchange",
        )
    if source != "ccxt" and exchange != _DEFAULT_CCXT_EXCHANGE:
        raise typer.BadParameter("--exchange applies only when --source ccxt")

    if not timeframe.is_daily and source not in {"alpaca", "ccxt"}:
        raise typer.BadParameter(
            f"{source} provides daily bars only in ALPHA; use --source alpaca (stocks/ETFs) "
            "or --source ccxt (crypto) for intraday bars"
        )
    kwargs: dict[str, object] = {}
    if source in {"alpaca", "ccxt"}:
        params = tuple(signature(factory).parameters.values())
        if not timeframe.is_daily or any(
            param.name == "timeframe" or param.kind is Parameter.VAR_KEYWORD for param in params
        ):
            kwargs["timeframe"] = timeframe
    if source == "ccxt":
        try:
            params = tuple(signature(factory).parameters.values())
        except (TypeError, ValueError):
            params = ()
        if any(param.name == "exchange" or param.kind is Parameter.VAR_KEYWORD for param in params):
            kwargs["exchange"] = exchange
    if source in {"tiingo", "alpaca"}:
        choices = provider_option_choices(source, "asset_class")
        if asset_class not in choices:
            raise typer.BadParameter(
                f"unknown {source.capitalize()} asset class {asset_class!r}; "
                f"known: {list(choices)}",
                param_hint="--asset-class",
            )
        kwargs.update(
            asset_class=asset_class,
            venue=venue,
            calendar=calendar,
            currency=currency,
        )
    return factory(**kwargs)


#: Quote assets a compact CCXT symbol (``XRPUSDT``) may end with; longest first so ``USDT``
#: wins over ``USD``. Anything else must be written ``BASE/QUOTE`` -- never guessed.
_CCXT_QUOTES = ("USDT", "USDC", "USD", "BTC", "ETH", "EUR")


def normalize_symbol(symbol: str, source: str) -> str:
    """Canonical vendor symbol for SOURCE: ``XRP/USDT`` for ccxt, upper-case for the rest."""
    cleaned = symbol.strip().upper()
    if source != "ccxt":
        if not cleaned or " " in cleaned:
            raise typer.BadParameter(f"symbol {symbol!r} must be a single ticker such as AAPL")
        return cleaned
    accepted = (
        f"symbol {symbol!r} is not a CCXT pair; write BASE/QUOTE such as XRP/USDT "
        f"(also accepted: xrp-usdt, xrp_usdt, or XRPUSDT when the quote is one of "
        f"{', '.join(_CCXT_QUOTES)})"
    )
    cleaned = cleaned.replace("-", "/").replace("_", "/")
    if "/" in cleaned:
        base, sep, quote = cleaned.partition("/")
        if not base or not quote or "/" in quote or not (base + quote).isalnum():
            raise typer.BadParameter(accepted)
        return f"{base}/{quote}"
    for quote in _CCXT_QUOTES:
        base = cleaned.removesuffix(quote)
        # A compact base longer than six characters (XRPUSDT in "xrpusdtusd") is a typo, not a
        # pair; explicit BASE/QUOTE above has no such limit.
        if base != cleaned and base and base.isalnum() and len(base) <= 6:
            return f"{base}/{quote}"
    raise typer.BadParameter(accepted)


@data_app.command("first-bar")
def first_bar(
    symbol: str,
    source: str = "ccxt",
    exchange: str = typer.Option(_DEFAULT_CCXT_EXCHANGE, help="CCXT exchange: coinbase or binance"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Report when SYMBOL was first listed on a CCXT exchange (read-only; needs network)."""
    if source != "ccxt":
        raise typer.BadParameter(
            "first-bar is available only for --source ccxt", param_hint="--source"
        )
    symbol = normalize_symbol(symbol, source)
    probe = getattr(_adapter(source, exchange), "first_bar", None)
    if probe is None:
        raise typer.BadParameter(f"the {source} adapter cannot report a first bar")
    try:
        first: datetime = probe(symbol)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        payload = {
            "symbol": symbol,
            "exchange": exchange,
            "first_bar_ts": first.isoformat(),
            "timeframe": "1d",
        }
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(f"{symbol} on {exchange}: first daily bar {first.date()}")


@data_app.command("ticker")
def ticker(
    symbol: str,
    source: str = "ccxt",
    exchange: str = typer.Option(_DEFAULT_CCXT_EXCHANGE, help="CCXT exchange: coinbase or binance"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Report SYMBOL's current last-trade price on a CCXT venue (read-only; needs network)."""
    if source != "ccxt":
        raise typer.BadParameter(
            "ticker is available only for --source ccxt", param_hint="--source"
        )
    symbol = normalize_symbol(symbol, source)
    probe = getattr(_adapter(source, exchange), "ticker", None)
    if probe is None:
        raise typer.BadParameter(f"the {source} adapter cannot report a ticker")
    try:
        last, stamp = probe(symbol)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        payload = {"symbol": symbol, "exchange": exchange, "last": last, "ts": stamp.isoformat()}
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(f"{symbol} on {exchange}: last {last} at {stamp.isoformat()}")


def _refuse_unfrozen(
    exc: FreezeRefused, symbol: str, source: str, start: str, end: str
) -> NoReturn:
    """Say plainly that nothing was replaced and what to do next; exit 3 (a freeze failure)."""
    again = f"alpha data pull {symbol} --source {source} --start {start} --end {end}"
    step = f"Fix that, then run the same pull again: {again}"
    typer.echo(
        f"cannot replace the stored {symbol}: it could not be frozen first. {exc.reason}. "
        f"Nothing was changed. {step}",
        err=True,
    )
    raise typer.Exit(3)


@data_app.command()
def pull(
    symbol: str,
    source: str = "yfinance",
    exchange: str = typer.Option(_DEFAULT_CCXT_EXCHANGE, help="CCXT exchange: coinbase or binance"),
    asset_class: str = typer.Option("stock", help="Tiingo or Alpaca asset class: stock or etf"),
    venue: str = typer.Option("US", help="Tiingo or Alpaca MIC/provider venue identifier"),
    calendar: str = typer.Option("XNYS", help="Tiingo or Alpaca exchange calendar identifier"),
    currency: str = typer.Option("USD", help="Tiingo or Alpaca quote currency"),
    start: str = typer.Option(...),
    end: str = typer.Option(...),
    timeframe: str = typer.Option("1D", help=_TIMEFRAME_HELP),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Pull raw bars + corporate actions for SYMBOL and store them.

    The stored series is frozen as a snapshot first; a failed freeze stops the pull unchanged.
    """
    tf = _timeframe(timeframe)
    adapter = _adapter(
        source,
        exchange,
        asset_class=asset_class,
        venue=venue,
        calendar=calendar,
        currency=currency,
        timeframe=tf,
    )
    symbol = normalize_symbol(symbol, source)
    try:
        start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError as exc:
        raise typer.BadParameter(f"--start/--end must be YYYY-MM-DD: {exc}") from exc
    if end_date < start_date:
        raise typer.BadParameter(f"--end {end_date} precedes --start {start_date}")
    probe = getattr(adapter, "first_bar", None) if source == "ccxt" else None
    try:
        if probe is not None:
            first: datetime = probe(symbol)
            if start_date < first.date():
                raise DataError(
                    f"No data for {symbol} on {exchange} before {first.date()} (first listed). "
                    f"Start there? (--start {first.date()})"
                )
        result = adapter.fetch(symbol, start_date, end_date)
        store = _store(tf)
        existing = store.read_provenance(result.symbol)
        if existing is not None and existing.get("source") == "tiingo" and adapter.name != "tiingo":
            raise DataError(
                f"{adapter.name} is audit-only for {result.symbol}; canonical Tiingo data "
                "cannot be silently replaced"
            )
        # Alpaca (ADR-0047) never shares a price series with another source, in either direction.
        held_by = existing.get("source") if existing is not None else None
        has_bars = result.symbol in store.list_symbols()
        if adapter.name == "alpaca" and has_bars and held_by != "alpaca":
            raise DataError(
                f"{result.symbol} already holds {held_by or 'unlabelled'} data here; ALPHA never "
                "mixes two sources in one price series, so use a separate ALPHA_DATA_DIR for "
                "Alpaca (docs/operations/alpaca-stock-data.md)"
            )
        if held_by == "alpaca" and adapter.name != "alpaca":
            raise DataError(
                f"{result.symbol} holds Alpaca data here; ALPHA never mixes two sources in one "
                f"price series, so pull {adapter.name} into a separate ALPHA_DATA_DIR"
            )
        report = pull_into_store(
            store,
            _snaps_root(),
            result,
            source=adapter.name,
            adapter_version=adapter.version,
            parser_version=adapter.parser_version,
            now=datetime.now(UTC),
            timeframe=tf.canonical,
        )
    except FreezeRefused as exc:  # nothing was replaced; a distinct exit code tells the nightly
        _refuse_unfrozen(exc, symbol, source, start, end)
    except RestoreFailed as exc:  # reads of the symbol now refuse; exit 4 is blocking
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    except DataError as exc:  # expected domain failure (no data, anti-bot gate, bad vendor row)
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(
            json.dumps({**report.as_dict(), "fetched_bars": result.bars.height}, sort_keys=True)
        )
        return
    detail = f", receipt {report.receipt_id} promoted" if report.receipt_id else ""
    if adapter.name == "alpaca":
        detail += "; not yet confirmed (interim source, not the authoritative Tiingo source)"
    if not tf.is_daily:
        detail += f", timeframe {tf.canonical}"
    typer.echo(
        f"pulled {symbol} from {source}: {result.bars.height} bars, "
        f"{len(result.actions)} actions{detail}"
    )
    for line in report.lines():
        typer.echo(line)


@data_app.command("source-status")
def source_status(
    symbol: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
    timeframe: str = typer.Option("1D", help=_TIMEFRAME_HELP),
) -> None:
    """Show canonical provenance and pending candidate/quarantine receipts for SYMBOL."""
    store = _store(_timeframe(timeframe))
    try:
        provenance = store.read_provenance(symbol)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    candidates: list[str] = []
    quarantined: list[str] = []
    for provider_dir in (store.root / "candidates").glob("*"):
        for candidate in provider_dir.glob("*"):
            if (candidate / "provenance" / f"{symbol}.json").is_file():
                candidates.append(f"{provider_dir.name}:{candidate.name}")
    for provider_dir in (store.root / "quarantine").glob("*"):
        for candidate in provider_dir.glob("*"):
            if (candidate / "provenance" / f"{symbol}.json").is_file():
                quarantined.append(f"{provider_dir.name}:{candidate.name}")
    payload: dict[str, object] = {
        "symbol": symbol,
        "provenance": provenance,
        "promotion_pending": store.promotion_pending(symbol),
        "candidates": sorted(candidates),
        "quarantined": sorted(quarantined),
    }
    if json_out:
        typer.echo(json.dumps(payload, sort_keys=True, allow_nan=False))
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))


@data_app.command()
def audit(
    provider: str,
    receipt_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
    timeframe: str = typer.Option("1D", help=_TIMEFRAME_HELP),
) -> None:
    """Read one immutable candidate/quarantine quality report."""
    if any(part in provider or part in receipt_id for part in ("/", "\\", "..")):
        raise typer.BadParameter("provider/receipt id must be opaque path-safe values")
    roots = (
        _store(_timeframe(timeframe)).root / "candidates" / provider / receipt_id,
        _store(_timeframe(timeframe)).root / "quarantine" / provider / receipt_id,
    )
    quality = next(
        (root / "quality.json" for root in roots if (root / "quality.json").is_file()), None
    )
    if quality is None:
        raise typer.BadParameter(f"no quality report for {provider}:{receipt_id}")
    try:
        payload = json.loads(quality.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"corrupt quality report at {quality}") from exc
    typer.echo(
        json.dumps(
            payload,
            indent=None if json_out else 2,
            sort_keys=True,
            allow_nan=False,
        )
    )


@data_app.command()
def health(
    asset: str = typer.Argument(..., help="Daily symbol, optionally qualified as SYMBOL@STORE."),
    universe: Annotated[
        Path | None, typer.Option(help="Membership CSV or stored membership JSON.")
    ] = None,
    stored: bool = typer.Option(False, "--stored", help="Verify and read the saved report."),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Check daily bars for adjustment, timestamp, gap and survivorship faults."""
    from alpha_cli._data_health import run_health

    try:
        run_health(AlphaSettings().data_dir, asset, universe, stored, json_out)
    except (DataError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@data_app.command()
def repair(
    provider: str,
    receipt_id: str,
    approve_differences: bool = typer.Option(
        False,
        "--approve-differences",
        help="owner-reviewed override for this exact quarantined receipt",
    ),
    timeframe: str = typer.Option("1D", help=_TIMEFRAME_HELP),
) -> None:
    """Promote one exact quarantined receipt after explicit owner review."""
    try:
        outcome = promote_quarantined(
            _store(_timeframe(timeframe)),
            provider=provider,
            receipt_id=receipt_id,
            approve_differences=approve_differences,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        f"promoted reviewed receipt {outcome.provider}:{outcome.receipt_id} for {outcome.symbol}"
    )


@data_app.command("rollback-promotion")
def rollback_promotion(
    symbol: str,
    acknowledge: bool = typer.Option(
        False,
        "--acknowledge",
        help="restore the immutable pre-promotion backup for this exact symbol",
    ),
    timeframe: str = typer.Option("1D", help=_TIMEFRAME_HELP),
) -> None:
    """Recover a canonical symbol after a process interruption during promotion."""
    try:
        rollback_interrupted_promotion(
            _store(_timeframe(timeframe)), symbol=symbol, acknowledge=acknowledge
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"restored pre-promotion canonical bytes for {symbol}")


@data_app.command()
def snapshot(
    snapshot_id: str,
    symbols: list[str],
    source: str = "yfinance",
    exchange: str = typer.Option(
        _DEFAULT_CCXT_EXCHANGE, help="CCXT exchange provenance: coinbase or binance"
    ),
    timeframe: str = typer.Option("1D", help=_TIMEFRAME_HELP),
) -> None:
    """Freeze the current store for SYMBOLS into an immutable, hashed snapshot."""
    tf = _timeframe(timeframe)
    adapter = _adapter(source, exchange, timeframe=tf)
    try:
        create_snapshot(
            _store(tf),
            _snaps_root(),
            snapshot_id,
            symbols,
            source=adapter.name,
            adapter_version=adapter.version,
            parser_version=adapter.parser_version,
            created_at=datetime.now(UTC),
            timeframe=tf.canonical,
        )
    except DataError as exc:  # e.g. a symbol with no bars in the store
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"snapshot {snapshot_id} created for {symbols}")


@data_app.command()
def candles(
    symbol: str,
    start: str = typer.Option(None, help="inclusive lower bound: date or ISO instant with offset"),
    end: str = typer.Option(None, help="as-of cutoff: date or ISO instant with offset"),
    snapshot: str = typer.Option(None, help="snapshot id for provenance"),
    manifest_id: str = typer.Option(None, help="exact qualified bulk chart manifest"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
    expected_snapshot_hash: str | None = None,
    timeframe: str = typer.Option("1D", help=_TIMEFRAME_HELP),
    source_timeframe: str | None = typer.Option(
        None, "--from-timeframe", help="stored timeframe to resample from"
    ),
    session: str | None = typer.Option(None, help="regular, extended or continuous"),
) -> None:
    """Point-in-time OHLCV candles for SYMBOL (split-adjusted; ``--end`` is an as-of cutoff).

    Reads through the same look-ahead firewall a backtest uses, so a chart can never show a bar past
    its window nor a split not yet known at ``--end``.
    """
    from alpha_cli._runner import load_bars, parse_cutoff

    try:
        target = parse_timeframe(timeframe)
        stored = parse_timeframe(source_timeframe or timeframe)
        when = parse_cutoff(end)
        # Preserve the existing candle date window, including its last microsecond.
        if end is not None and len(end) == 10 and when is not None:
            when = when.replace(microsecond=999999)
        lower = parse_cutoff(start)
        if start is not None and len(start) == 10 and lower is not None:
            lower = datetime.combine(lower.date(), time.min, tzinfo=UTC)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    try:
        provenance = None
        if expected_snapshot_hash is not None:
            if (
                not snapshot
                or manifest_id
                or len(expected_snapshot_hash) != 64
                or any(character not in "0123456789abcdef" for character in expected_snapshot_hash)
            ):
                raise DataError("expected snapshot hash requires an exact canonical snapshot")
            snapshot_path = resolve_snapshot_dir(AlphaSettings().data_dir / "snapshots", snapshot)
            if snapshot_manifest_hash(snapshot_path) != expected_snapshot_hash:
                raise DataError("chart snapshot differs from the frozen report identity")
        if manifest_id:
            from alpha_cli._chart_data import load_chart_dataset
            from alpha_cli.crypto_data_cmds import _bulk_store

            if snapshot:
                raise DataError("choose a canonical snapshot or a bulk manifest, not both")
            bars, provenance = load_chart_dataset(
                _bulk_store(), manifest_id, symbol=symbol, as_of=when
            )
            snap = None
        else:
            root = (
                resolve_snapshot_dir(AlphaSettings().data_dir / "snapshots", snapshot)
                if snapshot
                else store_dir(AlphaSettings().data_dir, stored)
            )
            bars_path = ParquetStore(root)._bars_path(symbol)
            if not bars_path.exists():
                raise DataError(
                    f"bars for {symbol!r} not found at {bars_path}; "
                    "next: run alpha data pull --help to download the missing data"
                )
            from polars.exceptions import PolarsError

            try:
                bars, snap = load_bars(
                    symbol,
                    data_dir=AlphaSettings().data_dir,
                    snapshot_id=snapshot,
                    as_of=when,
                    timeframe=target.canonical,
                    source_timeframe=stored.canonical,
                    session=session,
                )
            except FileNotFoundError as exc:
                raise DataError(
                    f"bars for {symbol!r} not found at {bars_path}; "
                    "next: run alpha data pull --help to download the missing data"
                ) from exc
            except (OSError, PolarsError) as exc:
                raise DataError(
                    f"corrupt or unreadable bars for {symbol!r} at {bars_path}: {exc}"
                ) from exc
            if (
                expected_snapshot_hash is not None
                and snapshot_manifest_hash(snapshot_path) != expected_snapshot_hash
            ):
                raise DataError("chart snapshot changed while reading frozen report candles")
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    rows = [
        {"t": b.ts.timestamp(), "o": b.open, "h": b.high, "l": b.low, "c": b.close, "v": b.volume}
        for b in bars
        if lower is None or b.ts >= lower
    ]
    if json_out:
        cutoff = when or (bars[-1].ts if bars else None)
        typer.echo(
            json.dumps(
                {
                    "symbol": symbol,
                    "snapshot_id": snap,
                    "provenance": provenance
                    or _candle_provenance(
                        symbol,
                        snapshot_id=snap,
                        knowledge_cutoff=cutoff,
                        timeframe=target,
                        source_timeframe=stored,
                        session=session,
                    ),
                    "bars": rows,
                }
            )
        )
    else:
        typer.echo(f"{symbol}: {len(rows)} candles")


@data_app.command()
def symbols(
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
    with_actions: bool = typer.Option(
        False, "--with-actions", help="add per-symbol corporate-action knowledge-time counts"
    ),
    timeframe: str = typer.Option("1D", help=_TIMEFRAME_HELP),
) -> None:
    """List every symbol with stored bars (the workstation's symbol picker reads this).

    The JSON form also reports, per symbol, how many stored corporate actions carry an
    *estimated* knowledge time (no ``announce_date``: the two-clock model is running on the
    ex-date clock alone for them), so the single-clock state is visible rather than silent.
    """
    store = _store(_timeframe(timeframe))
    stored = store.list_symbols()
    if json_out:
        payload: dict[str, object] = {"symbols": stored}
        if with_actions:
            actions_report: dict[str, dict[str, int]] = {}
            for sym in stored:
                actions = store.read_actions(sym)
                actions_report[sym] = {
                    "actions": len(actions),
                    "knowledge_estimated": sum(a.knowledge_is_estimated for a in actions),
                }
            payload["actions"] = actions_report
        typer.echo(json.dumps(payload, sort_keys=True))
        return
    for sym in stored:
        typer.echo(sym)


@data_app.command()
def snapshots(
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
    with_content: bool = typer.Option(
        False, "--with-content", help="with --json: add content hashes and the total size"
    ),
) -> None:
    """List every immutable snapshot's manifest summary in deterministic id order.

    The plain list also shows each content hash and the snapshots that share it, and the total
    size on disk. `--json` keeps its shape (the workstation reads it) unless `--with-content`.
    """
    root = _snaps_root()
    manifests = read_manifests(root)
    shared = shared_content(manifests)
    rows: list[dict[str, object]] = []
    for _, raw, manifest in manifests:
        symbols_entry = manifest.get("symbols")
        held = symbols_entry if isinstance(symbols_entry, dict) else {}
        held_content = {
            name: {
                "sha256": content_hash(entry),
                "shared_with": [
                    other
                    for other in shared.get((name, content_hash(entry)), [])
                    if other != manifest.get("snapshot_id")
                ],
            }
            for name, entry in sorted(held.items())
            if isinstance(entry, dict)
        }
        rows.append(
            {
                "snapshot_id": manifest.get("snapshot_id"),
                "created_at": manifest.get("created_at"),
                "source": manifest.get("source"),
                "adapter_version": manifest.get("adapter_version"),
                "parser_version": manifest.get("parser_version"),
                "symbols": sorted(held),
                "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                "content": held_content,
            }
        )
    size = total_bytes(root)
    if json_out:
        if with_content:
            body: dict[str, object] = {"snapshots": rows, "total_bytes": size}
        else:
            body = {"snapshots": [{k: v for k, v in r.items() if k != "content"} for r in rows]}
        typer.echo(json.dumps(body, sort_keys=True, allow_nan=False))
        return
    if not rows:
        typer.echo("no snapshots")
        return
    for row in rows:
        listed = row["symbols"]
        names = ",".join(str(item) for item in listed) if isinstance(listed, list) else ""
        typer.echo(f"{row['snapshot_id']} {row['source']} {names}")
        content = row["content"]
        for name, info in content.items() if isinstance(content, dict) else []:
            twins = ", ".join(info["shared_with"]) or "none"
            typer.echo(f"  {name} content {info['sha256'][:12]} also held by: {twins}")
    typer.echo(
        f"{len(rows)} snapshots, {size / 1024:.0f} KB in total. "
        "They are never deleted automatically; removing old ones is the owner's decision."
    )


@data_app.command()
def verify(snapshot_id: str) -> None:
    """Re-hash a snapshot and confirm it matches its manifest."""
    try:
        snapshot_dir = _snaps_root() / snapshot_id
        verify_snapshot(snapshot_dir, timeframe=snapshot_timeframe(snapshot_dir))
    except DataError as exc:  # missing snapshot or a hash mismatch (corruption)
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"snapshot {snapshot_id}: integrity OK")


universe_app = typer.Typer(help="Point-in-time universe membership (survivorship-safe reads).")
data_app.add_typer(universe_app, name="universe")


@universe_app.command("import")
def universe_import(
    name: str,
    csv_path: Path,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Import symbol,effective_from,effective_to,delisting_return,reason rows as universe NAME."""
    from alpha_data.universe import parse_universe_csv

    try:
        rows = parse_universe_csv(csv_path.read_text(encoding="utf-8"))
        path = _store().write_universe(name, rows)
    except (OSError, DataError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    payload = {
        "name": name,
        "memberships": len(rows),
        "symbols": len({r.symbol for r in rows}),
        "removed": sum(r.effective_to is not None for r in rows),
        "path": str(path),
        "authority": "none",
    }
    if json_out:
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(
            f"universe {name}: {payload['memberships']} memberships, {payload['symbols']} symbols, "
            f"{payload['removed']} removed -> {path}"
        )


@universe_app.command("show")
def universe_show(
    name: str,
    as_of: str = typer.Option(
        ..., help="membership date YYYY-MM-DD (from inclusive, to exclusive)"
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List the members of universe NAME as of a date, including names that later left."""
    from alpha_core import members_as_of

    try:
        when = date.fromisoformat(as_of)
        rows = _store().read_universe(name)
    except (ValueError, DataError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    members = members_as_of(rows, when)
    later_removed = sorted(
        {r.symbol for r in rows if r.effective_to is not None and r.effective_to > when}
        & set(members)
    )
    payload = {
        "name": name,
        "as_of": when.isoformat(),
        "members": members,
        "count": len(members),
        "later_removed": later_removed,
        "authority": "none",
    }
    if json_out:
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(
            f"{name} as of {when}: {len(members)} members ({len(later_removed)} later removed)"
        )
        typer.echo(" ".join(members))


@data_app.command("market-overview")
def market_overview_command(
    store: str = typer.Option("1D", help="stored bar size: 1D (default), 1h, 5m, ..."),
    window: int = typer.Option(90, help="bars shown: 30, 90 or 365"),
    limit: int = typer.Option(15, help="how many assets (1..30)"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Read-only market overview of stored bars. Market view. Not a test result."""
    run_market_overview(store, window, limit, json_out)


@data_app.command("run-price")
def run_price_command(
    run_id: str = typer.Argument(..., help="a completed rule-test run id"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Stored price bars of a rule test, only when they hash to the run's recorded source."""
    run_run_price(run_id, json_out)


@data_app.command("chart-datasets")
def chart_datasets_command(json_out: bool = typer.Option(False, "--json")) -> None:
    """Discover qualified external archive chart datasets without hashing all artifacts."""
    from alpha_cli._chart_data import chart_datasets
    from alpha_cli.crypto_data_cmds import BulkVolumeUnconfigured, _bulk_store

    try:
        store = _bulk_store()
        store.verify_readable()
        result = {"datasets": chart_datasets(store), "authority": "none", "state": "available"}
    except BulkVolumeUnconfigured:
        result = {"datasets": [], "authority": "none", "state": "unconfigured"}
    except (DataError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(result))
    else:
        typer.echo(f"{len(result['datasets'])} archive chart datasets")
