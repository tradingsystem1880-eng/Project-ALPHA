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

import numpy as np
import polars as pl

from alpha_cli import RUN_DIRS
from alpha_core import DataError
from alpha_validation import FloatArray

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


def write_equity_curve(
    rdir: Path,
    *,
    baseline_ts: datetime,
    timestamps: Sequence[datetime],
    returns: Sequence[float],
) -> None:
    """Write a returns-level ``equity_curve.parquet`` (validate-run schema, base 1.0).

    Convention (see ``_portfolio``): ``returns[i]`` realizes at ``timestamps[i]``, so the stored
    curve is a leading ``(baseline_ts, 1.0)`` point followed by ``equity[i] = prod(1 + r[0..i])``
    at ``timestamps[i]`` — the same length-N+1, leading-1.0 shape as a gauntlet run's OOS curve.
    ``read_equity`` + ``to_returns`` therefore recovers the FULL return stream (``alpha propfirm
    --from-run`` / ``alpha risk scenario``). Deterministic: fixed column order, pinned dtypes,
    strictly-increasing rows by construction. Callers must write this BEFORE the manifest (the
    run-exists marker).
    """
    if len(timestamps) != len(returns):
        raise DataError(
            f"equity curve misaligned: {len(timestamps)} timestamps vs {len(returns)} returns"
        )
    if timestamps and baseline_ts >= timestamps[0]:
        raise DataError(
            f"baseline_ts {baseline_ts} must precede the first realization ts {timestamps[0]}"
        )
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1.0 + float(r)))
    frame = pl.DataFrame(
        {"ts": [baseline_ts, *timestamps], "equity": equity},
        schema={"ts": pl.Datetime(time_unit="us", time_zone="UTC"), "equity": pl.Float64()},
    )
    rdir.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(rdir / "equity_curve.parquet")


def write_nulls(rdir: Path, *, tiers: Sequence[tuple[str, Sequence[float]]]) -> None:
    """Write ``nulls.parquet`` — the raw per-tier null distributions behind a gauntlet run.

    One row per (tier, path): ``tier`` String, ``path_index`` Int64, ``statistic`` Float64,
    sorted by (tier, path_index) regardless of caller order. Statistics are finite by construction
    (the null generators fail loud on non-finite paths). Deterministic: fixed column order, pinned
    dtypes, no wall-clock. Callers must write this BEFORE the manifest (the run-exists marker).
    """
    names = [name for name, _ in tiers]
    if len(set(names)) != len(names):
        raise DataError(f"duplicate null tiers: {names}")
    tier_col: list[str] = []
    idx_col: list[int] = []
    stat_col: list[float] = []
    for name, stats in sorted(tiers, key=lambda pair: pair[0]):
        tier_col.extend([name] * len(stats))
        idx_col.extend(range(len(stats)))
        stat_col.extend(float(v) for v in stats)
    frame = pl.DataFrame(
        {"tier": tier_col, "path_index": idx_col, "statistic": stat_col},
        schema={"tier": pl.String(), "path_index": pl.Int64(), "statistic": pl.Float64()},
    )
    rdir.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(rdir / "nulls.parquet")


def write_trials(rdir: Path, *, matrix: FloatArray) -> None:
    """Write ``trials.parquet`` — the ``(n_oos × n_configs)`` OOS return matrix behind a sweep.

    One row per (trial, step): ``trial`` Int64 (config index, aligned with the manifest's
    ``configs``/``sharpes``), ``step`` Int64 (position in the concatenated walk-forward OOS
    stream), ``oos_return`` Float64, sorted by (trial, step). Deterministic: fixed column order,
    pinned dtypes, no wall-clock. Callers must write this BEFORE the manifest (the run-exists
    marker).
    """
    if matrix.ndim != 2:
        raise DataError(f"trials matrix must be 2-D (n_oos × n_configs), got shape {matrix.shape}")
    n_oos, n_configs = matrix.shape
    frame = pl.DataFrame(
        {
            "trial": np.repeat(np.arange(n_configs, dtype=np.int64), n_oos),
            "step": np.tile(np.arange(n_oos, dtype=np.int64), n_configs),
            "oos_return": np.ascontiguousarray(matrix.T).reshape(-1),
        },
        schema={"trial": pl.Int64(), "step": pl.Int64(), "oos_return": pl.Float64()},
    )
    rdir.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(rdir / "trials.parquet")


def write_propfirm_paths(
    rdir: Path,
    *,
    passed: Sequence[bool],
    busted: Sequence[bool],
    days_to_pass: Sequence[float],
    payout: Sequence[float],
) -> None:
    """Write ``propfirm_paths.parquet`` — a prop-firm run's per-path Monte-Carlo outcomes.

    One row per path, sorted by ``path_index`` Int64 (0..n-1): ``passed``/``busted`` Boolean,
    ``days_to_pass`` Float64 (NaN when the path never passed — this is Parquet, not the manifest,
    so NaN is representable) and ``payout`` Float64. Deterministic: fixed column order, pinned
    dtypes, no wall-clock. Callers must write this BEFORE the manifest (the run-exists marker).
    """
    n = len(passed)
    if not len(busted) == len(days_to_pass) == len(payout) == n:
        raise DataError(
            f"propfirm path arrays misaligned: {n}/{len(busted)}/{len(days_to_pass)}/{len(payout)}"
        )
    frame = pl.DataFrame(
        {
            "path_index": list(range(n)),
            "passed": list(passed),
            "busted": list(busted),
            "days_to_pass": [float(v) for v in days_to_pass],
            "payout": [float(v) for v in payout],
        },
        schema={
            "path_index": pl.Int64(),
            "passed": pl.Boolean(),
            "busted": pl.Boolean(),
            "days_to_pass": pl.Float64(),
            "payout": pl.Float64(),
        },
    )
    rdir.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(rdir / "propfirm_paths.parquet")


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
