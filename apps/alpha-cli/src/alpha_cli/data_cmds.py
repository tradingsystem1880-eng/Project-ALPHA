"""`alpha data` subcommands: pull, snapshot, verify."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from pathlib import Path

import typer

from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.adapters.ccxt_adapter import CCXTAdapter
from alpha_data.adapters.stooq_adapter import StooqAdapter
from alpha_data.adapters.yfinance_adapter import YFinanceAdapter
from alpha_data.ingest import store_fetch_result
from alpha_data.snapshot import create_snapshot, verify_snapshot
from alpha_data.store import ParquetStore

data_app = typer.Typer(help="Data ingestion, snapshots, and integrity.")

# adapter registry — tests monkeypatch this to inject offline fakes
_ADAPTERS: dict[str, type] = {
    "yfinance": YFinanceAdapter,
    "ccxt": CCXTAdapter,
    "stooq": StooqAdapter,
}


def _store() -> ParquetStore:
    return ParquetStore(AlphaSettings().data_dir / "store")


def _snaps_root() -> Path:
    return AlphaSettings().data_dir / "snapshots"


@data_app.command()
def pull(
    symbol: str,
    source: str = "yfinance",
    start: str = typer.Option(...),
    end: str = typer.Option(...),
) -> None:
    """Pull raw bars + corporate actions for SYMBOL and store them."""
    adapter_cls = _ADAPTERS.get(source)
    if adapter_cls is None:
        raise typer.BadParameter(f"unknown source {source!r}; known: {sorted(_ADAPTERS)}")
    try:
        start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError as exc:
        raise typer.BadParameter(f"--start/--end must be YYYY-MM-DD: {exc}") from exc
    try:
        result = adapter_cls().fetch(symbol, start_date, end_date)
        store_fetch_result(_store(), result)
    except DataError as exc:  # expected domain failure (no data, anti-bot gate, bad vendor row)
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        f"pulled {symbol} from {source}: {result.bars.height} bars, {len(result.actions)} actions"
    )


@data_app.command()
def snapshot(snapshot_id: str, symbols: list[str], source: str = "yfinance") -> None:
    """Freeze the current store for SYMBOLS into an immutable, hashed snapshot."""
    adapter_cls = _ADAPTERS.get(source)
    if adapter_cls is None:
        raise typer.BadParameter(f"unknown source {source!r}; known: {sorted(_ADAPTERS)}")
    adapter = adapter_cls()
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
        typer.echo(json.dumps({"symbol": symbol, "snapshot_id": snap, "bars": rows}))
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
def verify(snapshot_id: str) -> None:
    """Re-hash a snapshot and confirm it matches its manifest."""
    try:
        verify_snapshot(_snaps_root() / snapshot_id)
    except DataError as exc:  # missing snapshot or a hash mismatch (corruption)
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"snapshot {snapshot_id}: integrity OK")
