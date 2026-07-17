"""Run-artifact layout: ``data_dir/runs/<run_id>/`` with a JSON manifest + Parquet series.

The ``manifest.json`` is the byte-stable reproducibility artifact (sorted keys, ``allow_nan=False``
so non-finite values must already be ``null``); the equity curve and trade log ride alongside as
Parquet. The HTML tear sheet is written separately by the renderer and is not byte-pinned.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from alpha_cli import RUN_DIRS
from alpha_core import DataError

_RUN_ID_RE = re.compile(r"[0-9a-f]{16}")  # ids are 16 hex chars; reject before path-joining


def sanitize(value: Any) -> Any:
    """Non-finite floats → None so manifests stay valid under ``allow_nan=False``.

    The one shared manifest sanitizer (propfirm/optim/forecast all write manifests).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [sanitize(v) for v in value]
    return value


if TYPE_CHECKING:
    from alpha_backtest.results import Trade

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


def find_run_dir(data_dir: Path, run_id: str) -> Path | None:
    """The run's artifact directory across every run-type subdir, or ``None`` if absent.

    Searches ``RUN_DIRS`` for ``<run_id>/manifest.json`` (the marker that a run exists). The run id
    is validated to 16 hex chars first, so a caller-supplied id can never path-traverse out of the
    run store. Used by ``alpha risk`` and the workstation to resolve any run by id alone.
    """
    if _RUN_ID_RE.fullmatch(run_id) is None:
        return None
    for sub in RUN_DIRS:
        rdir = data_dir / sub / run_id
        if (rdir / "manifest.json").exists():
            return rdir
    return None


def write_run(
    rdir: Path,
    *,
    manifest: dict[str, Any],
    equity: Sequence[tuple[datetime, float]],
    trades: Sequence[Trade],
) -> None:
    """Write ``equity_curve.parquet`` + ``trades.parquet`` + ``manifest.json`` into ``rdir``.

    The manifest is written LAST (atomically): every reader treats ``manifest.json`` as the
    marker that a run exists, so a crash mid-write leaves an invisible partial directory, never a
    listed run with missing series.
    """
    rdir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"ts": [ts for ts, _ in equity], "equity": [v for _, v in equity]}).write_parquet(
        rdir / "equity_curve.parquet"
    )
    rows = [dataclasses.asdict(t) for t in trades]
    frame = pl.DataFrame(rows) if rows else pl.DataFrame(schema=_EMPTY_TRADES_SCHEMA)
    frame.write_parquet(rdir / "trades.parquet")
    tmp = rdir / "manifest.json.tmp"
    try:
        tmp.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
        )
        os.replace(tmp, rdir / "manifest.json")
    finally:
        tmp.unlink(missing_ok=True)


def read_manifest(rdir: Path) -> dict[str, Any]:
    """Load a run's ``manifest.json`` back into a dict."""
    result: dict[str, Any] = json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))
    return result


def read_equity(rdir: Path) -> list[tuple[datetime, float]]:
    """Load a run's ``equity_curve.parquet`` back into ``(timestamp, equity)`` pairs (ts order).

    The symmetric reader for :func:`write_run`'s equity column — used by ``alpha propfirm
    --from-run`` to recover a prior run's return stream without re-running the engine. Fails loud
    (``DataError``) if the run has no equity curve (e.g. an optim/portfolio run).
    """
    path = rdir / "equity_curve.parquet"
    if not path.exists():
        raise DataError(f"run at {rdir} has no equity_curve.parquet")
    frame = pl.read_parquet(path)
    return list(zip(frame["ts"].to_list(), frame["equity"].to_list(), strict=True))
