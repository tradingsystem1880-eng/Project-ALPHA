"""`alpha data` subcommands: pull, snapshot, verify, candles, symbols."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from inspect import Parameter, signature
from pathlib import Path

import typer

from alpha_cli.providers import (
    HistoricalAdapterFactory,
    historical_adapter_factories,
    provider_option_choices,
)
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.adapters.base import DataAdapter
from alpha_data.ingest import store_fetch_result
from alpha_data.pipeline import (
    promote_quarantined,
    rollback_interrupted_promotion,
    stage_and_promote,
)
from alpha_data.snapshot import create_snapshot, verify_snapshot
from alpha_data.store import ParquetStore

data_app = typer.Typer(help="Data ingestion, snapshots, and integrity.")

# adapter registry — tests monkeypatch this to inject offline fakes
_ADAPTERS: dict[str, HistoricalAdapterFactory] = historical_adapter_factories()
_CCXT_EXCHANGES = provider_option_choices("ccxt", "exchange")
_DEFAULT_CCXT_EXCHANGE = "coinbase"


def _store() -> ParquetStore:
    return ParquetStore(AlphaSettings().data_dir / "store")


def _snaps_root() -> Path:
    return AlphaSettings().data_dir / "snapshots"


def _candle_provenance(
    symbol: str,
    *,
    snapshot_id: str | None,
    knowledge_cutoff: datetime | None,
) -> dict[str, object]:
    data_root = AlphaSettings().data_dir
    root = data_root / "snapshots" / snapshot_id if snapshot_id else data_root / "store"
    store = ParquetStore(root)
    provenance = store.read_provenance(symbol)
    path = store._provenance_path(symbol)  # noqa: SLF001 -- CLI/store projection seam
    provenance_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    source = provenance.get("source") if provenance is not None else "unknown"
    dataset = provenance.get("dataset") if provenance is not None else None
    venue = dataset.get("venue") if isinstance(dataset, dict) else None
    timeframe = dataset.get("timeframe") if isinstance(dataset, dict) else "1D"
    receipt = provenance.get("receipt") if provenance is not None else None
    receipt_id = receipt.get("receipt_id") if isinstance(receipt, dict) else None
    quality_status = "legacy_unqualified"
    if isinstance(receipt_id, str) and isinstance(source, str):
        passed = data_root / "store" / "candidates" / source / receipt_id / "quality.json"
        reviewed = data_root / "store" / "quarantine" / source / receipt_id / "quality.json"
        quality_status = (
            "passed"
            if passed.is_file()
            else "owner_approved"
            if reviewed.is_file()
            else "qualified"
        )
    return {
        "source": source,
        "venue": venue,
        "timeframe": timeframe,
        "snapshot_id": snapshot_id,
        "provenance_sha256": provenance_hash,
        "receipt_id": receipt_id,
        "knowledge_cutoff": knowledge_cutoff.isoformat() if knowledge_cutoff is not None else None,
        "quality_status": quality_status,
    }


def _adapter(
    source: str,
    exchange: str,
    *,
    asset_class: str = "stock",
    venue: str = "US",
    calendar: str = "XNYS",
    currency: str = "USD",
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

    kwargs: dict[str, str] = {}
    if source == "ccxt":
        try:
            params = tuple(signature(factory).parameters.values())
        except (TypeError, ValueError):
            params = ()
        if any(param.name == "exchange" or param.kind is Parameter.VAR_KEYWORD for param in params):
            kwargs["exchange"] = exchange
    if source == "tiingo":
        choices = provider_option_choices("tiingo", "asset_class")
        if asset_class not in choices:
            raise typer.BadParameter(
                f"unknown Tiingo asset class {asset_class!r}; known: {list(choices)}",
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


@data_app.command()
def pull(
    symbol: str,
    source: str = "yfinance",
    exchange: str = typer.Option(_DEFAULT_CCXT_EXCHANGE, help="CCXT exchange: coinbase or binance"),
    asset_class: str = typer.Option("stock", help="Tiingo asset class: stock or etf"),
    venue: str = typer.Option("US", help="Tiingo MIC/provider venue identifier"),
    calendar: str = typer.Option("XNYS", help="Tiingo exchange calendar identifier"),
    currency: str = typer.Option("USD", help="Tiingo quote currency"),
    start: str = typer.Option(...),
    end: str = typer.Option(...),
) -> None:
    """Pull raw bars + corporate actions for SYMBOL and store them."""
    adapter = _adapter(
        source,
        exchange,
        asset_class=asset_class,
        venue=venue,
        calendar=calendar,
        currency=currency,
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
        store = _store()
        if (
            result.identity is not None
            or result.receipt is not None
            or result.raw_response is not None
        ):
            outcome = stage_and_promote(store, result, authoritative_source=adapter.name)
            detail = f", receipt {outcome.receipt_id} promoted"
        else:
            existing = store.read_provenance(result.symbol)
            if (
                existing is not None
                and existing.get("source") == "tiingo"
                and adapter.name != "tiingo"
            ):
                raise DataError(
                    f"{adapter.name} is audit-only for {result.symbol}; canonical Tiingo data "
                    "cannot be silently replaced"
                )
            store.clear_provenance(result.symbol)
            store_fetch_result(store, result)
            store.write_provenance(
                result.symbol,
                source=adapter.name,
                adapter_version=adapter.version,
                parser_version=adapter.parser_version,
            )
            detail = ""
    except DataError as exc:  # expected domain failure (no data, anti-bot gate, bad vendor row)
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        f"pulled {symbol} from {source}: {result.bars.height} bars, "
        f"{len(result.actions)} actions{detail}"
    )


@data_app.command("source-status")
def source_status(
    symbol: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show canonical provenance and pending candidate/quarantine receipts for SYMBOL."""
    store = _store()
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
) -> None:
    """Read one immutable candidate/quarantine quality report."""
    if any(part in provider or part in receipt_id for part in ("/", "\\", "..")):
        raise typer.BadParameter("provider/receipt id must be opaque path-safe values")
    roots = (
        _store().root / "candidates" / provider / receipt_id,
        _store().root / "quarantine" / provider / receipt_id,
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
def repair(
    provider: str,
    receipt_id: str,
    approve_differences: bool = typer.Option(
        False,
        "--approve-differences",
        help="owner-reviewed override for this exact quarantined receipt",
    ),
) -> None:
    """Promote one exact quarantined receipt after explicit owner review."""
    try:
        outcome = promote_quarantined(
            _store(),
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
) -> None:
    """Recover a canonical symbol after a process interruption during promotion."""
    try:
        rollback_interrupted_promotion(_store(), symbol=symbol, acknowledge=acknowledge)
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
) -> None:
    """Freeze the current store for SYMBOLS into an immutable, hashed snapshot."""
    adapter = _adapter(source, exchange)
    try:
        create_snapshot(
            _store(),
            _snaps_root(),
            snapshot_id,
            symbols,
            source=adapter.name,
            adapter_version=adapter.version,
            parser_version=adapter.parser_version,
            created_at=datetime.now(UTC),
        )
    except DataError as exc:  # e.g. a symbol with no bars in the store
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"snapshot {snapshot_id} created for {symbols}")


@data_app.command()
def candles(
    symbol: str,
    start: str = typer.Option(None, help="lower bound YYYY-MM-DD (inclusive)"),
    end: str = typer.Option(None, help="as-of cutoff YYYY-MM-DD (inclusive)"),
    snapshot: str = typer.Option(None, help="snapshot id for provenance"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Point-in-time OHLCV candles for SYMBOL (split-adjusted; ``--end`` is an as-of cutoff).

    Reads through the same look-ahead firewall a backtest uses, so a chart can never show a bar past
    its window nor a split not yet known at ``--end``.
    """
    from alpha_cli._runner import load_bars

    try:
        when = datetime.combine(date.fromisoformat(end), time.max, tzinfo=UTC) if end else None
        lower = date.fromisoformat(start) if start else None
    except ValueError as exc:
        raise typer.BadParameter(f"--start/--end must be YYYY-MM-DD: {exc}") from exc
    try:
        bars, snap = load_bars(
            symbol, data_dir=AlphaSettings().data_dir, snapshot_id=snapshot, as_of=when
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    rows = [
        {"t": b.ts.timestamp(), "o": b.open, "h": b.high, "l": b.low, "c": b.close, "v": b.volume}
        for b in bars
        if lower is None or b.ts.date() >= lower
    ]
    if json_out:
        cutoff = when or (bars[-1].ts if bars else None)
        typer.echo(
            json.dumps(
                {
                    "symbol": symbol,
                    "snapshot_id": snap,
                    "provenance": _candle_provenance(
                        symbol,
                        snapshot_id=snap,
                        knowledge_cutoff=cutoff,
                    ),
                    "bars": rows,
                }
            )
        )
    else:
        typer.echo(f"{symbol}: {len(rows)} candles")


@data_app.command()
def symbols(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """List every symbol with stored bars (the workstation's symbol picker reads this)."""
    stored = _store().list_symbols()
    if json_out:
        typer.echo(json.dumps({"symbols": stored}))
        return
    for sym in stored:
        typer.echo(sym)


@data_app.command()
def snapshots(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """List every immutable snapshot's manifest summary in deterministic id order."""
    root = _snaps_root()
    rows: list[dict[str, object]] = []
    if root.is_dir():
        for manifest_path in sorted(root.glob("*/manifest.json")):
            raw = manifest_path.read_bytes()
            try:
                manifest = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DataError(f"corrupt snapshot manifest at {manifest_path}") from exc
            if not isinstance(manifest, dict):
                raise DataError(f"corrupt snapshot manifest at {manifest_path}")
            symbols_entry = manifest.get("symbols")
            rows.append(
                {
                    "snapshot_id": manifest.get("snapshot_id"),
                    "created_at": manifest.get("created_at"),
                    "source": manifest.get("source"),
                    "adapter_version": manifest.get("adapter_version"),
                    "parser_version": manifest.get("parser_version"),
                    "symbols": (sorted(symbols_entry) if isinstance(symbols_entry, dict) else []),
                    "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    if json_out:
        typer.echo(json.dumps({"snapshots": rows}, sort_keys=True, allow_nan=False))
        return
    if not rows:
        typer.echo("no snapshots")
        return
    for row in rows:
        listed = row["symbols"]
        names = ",".join(str(item) for item in listed) if isinstance(listed, list) else ""
        typer.echo(f"{row['snapshot_id']} {row['source']} {names}")


@data_app.command()
def verify(snapshot_id: str) -> None:
    """Re-hash a snapshot and confirm it matches its manifest."""
    try:
        verify_snapshot(_snaps_root() / snapshot_id)
    except DataError as exc:  # missing snapshot or a hash mismatch (corruption)
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"snapshot {snapshot_id}: integrity OK")
