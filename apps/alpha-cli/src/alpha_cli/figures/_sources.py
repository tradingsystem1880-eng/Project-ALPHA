"""Bounded reads of run artifacts into plain tuples the figure contract accepts.

Everything crossing out of this module is a ``tuple[float, ...]`` or a ``str``: the
renderer never sees a DataFrame, a ``datetime``, or a Polars expression. Sampling is
endpoint-preserving so a bounded series still starts and ends where the run did.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli.run_projection import MAX_CHART_BARS, MAX_CHART_POINTS, _candle_rows, _frame
from alpha_core import DataError


def frame(rdir: Path, name: str, *sort: str) -> pl.DataFrame | None:
    """Read one artifact, or ``None`` when the run never emitted it."""
    return _frame(rdir, name, *sort)


def require(rdir: Path, name: str, *sort: str) -> pl.DataFrame:
    result = _frame(rdir, name, *sort)
    if result is None or result.is_empty():
        raise DataError(f"{name} is missing or empty for this run")
    return result


def sample(size: int, limit: int = MAX_CHART_POINTS) -> list[int]:
    """Endpoint-preserving uniform indices, so a capped series keeps its start and end."""
    if size <= limit:
        return list(range(size))
    if limit == 1:
        return [0]
    return [round(index * (size - 1) / (limit - 1)) for index in range(limit)]


def epochs(column: pl.Series) -> tuple[float, ...]:
    out: list[float] = []
    for value in column.to_list():
        if isinstance(value, datetime):
            out.append(value.timestamp())
        elif isinstance(value, int | float) and not isinstance(value, bool):
            out.append(float(value))
        else:
            raise DataError(f"expected a timestamp, got {value!r}")
    return tuple(out)


def floats(column: pl.Series, *, name: str) -> tuple[float, ...]:
    out: list[float] = []
    for value in column.to_list():
        if value is None or isinstance(value, bool) or not isinstance(value, int | float):
            raise DataError(f"{name} contains a non-numeric value {value!r}")
        number = float(value)
        if not math.isfinite(number):
            raise DataError(f"{name} contains a non-finite value")
        out.append(number)
    return tuple(out)


def optional_floats(column: pl.Series) -> tuple[float | None, ...]:
    """Nullable series stay nullable: a missing value is never silently turned into zero."""
    out: list[float | None] = []
    for value in column.to_list():
        if value is None:
            out.append(None)
            continue
        number = float(value)
        out.append(number if math.isfinite(number) else None)
    return tuple(out)


def strings(column: pl.Series) -> tuple[str, ...]:
    return tuple("" if value is None else str(value) for value in column.to_list())


def drawdown(equity: tuple[float, ...]) -> tuple[float, ...]:
    peak = -math.inf
    out: list[float] = []
    for value in equity:
        peak = max(peak, value)
        out.append(value / peak - 1.0)
    return tuple(out)


def rebase(values: tuple[float, ...]) -> tuple[float, ...]:
    if not values or values[0] == 0:
        raise DataError("cannot rebase a series whose first value is zero or missing")
    return tuple(value / values[0] for value in values)


def bars(
    manifest: dict[str, Any], *, data_dir: Path, limit: int = MAX_CHART_BARS
) -> tuple[list[dict[str, float]], str | None]:
    """Point-in-time candles for the run's window, or a reason they are unavailable.

    Bars are the one figure input that is not itself an immutable artifact, so they are
    read back through the frozen snapshot rather than the live store.
    """
    symbol = manifest.get("symbol")
    snapshot = manifest.get("snapshot_id")
    if not isinstance(symbol, str) or not symbol:
        return [], "not_applicable"
    if not isinstance(snapshot, str) or not snapshot:
        return [], "snapshot_unavailable"
    rows = _candle_rows(
        symbol,
        snapshot,
        data_dir=data_dir,
        start=manifest.get("start") if isinstance(manifest.get("start"), str) else None,
        end=manifest.get("end") if isinstance(manifest.get("end"), str) else None,
    )
    if not rows:
        return [], "snapshot_unavailable"
    picked = sample(len(rows), limit)
    return [rows[index] for index in picked], None
