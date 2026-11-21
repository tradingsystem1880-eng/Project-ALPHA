"""``alpha data run-price``: price bars of a run with no snapshot, only when they match its record.

A rule test reads the stored bars up to the research cut-off and records one source fingerprint
over them. This module reads the stored bars again, cuts them at that cut-off and at the run's
last date, and hashes them the way the run did. It returns the bars only when the two hashes are
equal. It never reads a bar at or after the cut-off. It computes no statistic.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import typer

from alpha_core import Bar, DataError

BARS_CHANGED = "bars_changed_since_run"
NOT_SAVED = "price_not_saved_with_run"
UNAVAILABLE = "price_unavailable"


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _map(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _recorded(manifest: Mapping[str, Any]) -> str | None:
    """The run's recorded source fingerprint when it is a 64-hex digest."""
    value = _text(manifest.get("source_fingerprint"))
    if value is None or len(value) != 64:
        return None
    try:
        int(value, 16)
    except ValueError:
        return None
    return value


def _last_date(manifest: Mapping[str, Any]) -> datetime | None:
    spine = _map(manifest.get("spine"))
    stamp = _text(_map(spine.get("data_period")).get("last_ts")) or _text(
        _map(manifest.get("metadata")).get("last_ts")
    )
    if stamp is None:
        return None
    try:
        last = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return last if last.tzinfo is not None else None


def _row(bar: Bar) -> dict[str, float]:
    return {
        "t": bar.ts.timestamp(),
        "o": bar.open,
        "h": bar.high,
        "l": bar.low,
        "c": bar.close,
        "v": bar.volume,
    }


def verified_bars(
    manifest: Mapping[str, Any], *, data_dir: Path
) -> tuple[str, list[dict[str, float]]]:
    """Return ``(status, rows)`` for a rule-test manifest; rows only when ``status`` is available.

    Statuses: ``available``; ``price_not_saved_with_run`` (no usable fingerprint, symbol, store or
    last date was recorded); ``bars_changed_since_run`` (the stored bars no longer hash to the
    record); ``price_unavailable`` (the stored bars could not be read).
    """
    recorded = _recorded(manifest)
    symbol = _text(_map(manifest.get("metadata")).get("symbol")) or _text(manifest.get("symbol"))
    store = _text(_map(manifest.get("spine")).get("store"))
    last = _last_date(manifest)
    if recorded is None or symbol is None or store is None or last is None:
        return NOT_SAVED, []
    from alpha_cli import _runner
    from alpha_cli.spine import reserve
    from alpha_cli.spine.stores import resolve_asset

    try:
        resolved = resolve_asset(f"{symbol}@{store}", data_dir=data_dir)
        bars, _ = _runner.load_bars(
            resolved.symbol, data_dir=resolved.data_dir, as_of=reserve.CUTOFF
        )
        dividends = _runner.load_dividends(
            resolved.symbol, data_dir=resolved.data_dir, as_of=reserve.CUTOFF
        )
    except DataError:
        return UNAVAILABLE, []
    edge = min(last, reserve.CUTOFF)
    kept = [bar for bar in bars if bar.ts <= edge]
    if _runner.source_fingerprint(kept, dividends=dividends) != recorded:
        return BARS_CHANGED, []
    return "available", [_row(bar) for bar in kept]


def run_run_price(run_id: str, json_out: bool) -> None:
    """Print ``{"status", "bars"}`` for one stored run; a bad run id is a CLI usage error."""
    from alpha_cli.run_store import find_run_dir, read_manifest, valid_run_id
    from alpha_core.config import AlphaSettings

    data_dir = AlphaSettings().data_dir
    folder = find_run_dir(data_dir, run_id) if valid_run_id(run_id) else None
    if folder is None:
        raise typer.BadParameter(f"unknown completed run {run_id!r}")
    status, rows = verified_bars(read_manifest(folder), data_dir=data_dir)
    if json_out:
        typer.echo(json.dumps({"status": status, "bars": rows}))
        return
    typer.echo(f"{status}: {len(rows)} bars")
