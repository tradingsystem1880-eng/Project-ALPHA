"""Run-artifact layout: ``data_dir/runs/<run_id>/`` with a JSON manifest + Parquet series.

The ``manifest.json`` is the byte-stable reproducibility artifact (sorted keys, ``allow_nan=False``
so non-finite values must already be ``null``); the equity curve and trade log ride alongside as
Parquet. The HTML tear sheet is written separately by the renderer and is not byte-pinned.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from alpha_execution.results import Trade

# schema for an EMPTY trade log (no rows to infer dtypes from); non-empty infers from the rows
_EMPTY_TRADES_SCHEMA: dict[str, pl.DataType] = {
    "instrument_id": pl.String(),
    "side": pl.String(),
    "quantity": pl.Float64(),
    "entry_price": pl.Float64(),
    "exit_price": pl.Float64(),
    "entry_ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "exit_ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "realized_pnl": pl.Float64(),
    "realized_return": pl.Float64(),
}


def run_dir(data_dir: Path, run_id: str) -> Path:
    """The artifact directory for a run: ``data_dir/runs/<run_id>``."""
    return data_dir / "runs" / run_id


def write_run(
    rdir: Path,
    *,
    manifest: dict[str, Any],
    equity: Sequence[tuple[datetime, float]],
    trades: Sequence[Trade],
) -> None:
    """Write ``manifest.json`` + ``equity_curve.parquet`` + ``trades.parquet`` into ``rdir``."""
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    pl.DataFrame({"ts": [ts for ts, _ in equity], "equity": [v for _, v in equity]}).write_parquet(
        rdir / "equity_curve.parquet"
    )
    rows = [dataclasses.asdict(t) for t in trades]
    frame = pl.DataFrame(rows) if rows else pl.DataFrame(schema=_EMPTY_TRADES_SCHEMA)
    frame.write_parquet(rdir / "trades.parquet")


def read_manifest(rdir: Path) -> dict[str, Any]:
    """Load a run's ``manifest.json`` back into a dict."""
    result: dict[str, Any] = json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))
    return result
