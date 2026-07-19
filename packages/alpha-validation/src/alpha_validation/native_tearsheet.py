"""Deterministic, Python-authoritative series for the native Workstation tear sheet.

The browser renders these values; it does not reproduce financial-statistic definitions. This
module deliberately emits plain frozen values so the CLI can serialize them without importing a
frontend or a report renderer.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import NormalDist

import numpy as np

from alpha_core import DataError
from alpha_validation.metrics import to_returns


@dataclass(frozen=True, slots=True)
class MonthlyReturn:
    year: int
    month: int
    return_value: float


@dataclass(frozen=True, slots=True)
class YearlyReturn:
    year: int
    return_value: float


@dataclass(frozen=True, slots=True)
class HistogramBin:
    left: float
    right: float
    count: int


@dataclass(frozen=True, slots=True)
class QQPoint:
    probability: float
    theoretical: float
    sample: float


@dataclass(frozen=True, slots=True)
class RollingMetric:
    ts: datetime
    return_value: float
    volatility: float
    sharpe: float | None


@dataclass(frozen=True, slots=True)
class NativeTearSheet:
    monthly: tuple[MonthlyReturn, ...]
    yearly: tuple[YearlyReturn, ...]
    histogram: tuple[HistogramBin, ...]
    qq: tuple[QQPoint, ...]
    rolling: tuple[RollingMetric, ...]


def _validate_timestamps(timestamps: Sequence[datetime], n_equity: int) -> None:
    if len(timestamps) != n_equity:
        raise DataError(
            f"native tear-sheet timestamps and equity must have the same length, got "
            f"{len(timestamps)} and {n_equity}"
        )
    if any(ts.tzinfo is None or ts.utcoffset() is None for ts in timestamps):
        raise DataError("native tear-sheet timestamps must be timezone-aware")
    pairs = zip(timestamps, timestamps[1:], strict=False)
    if any(current <= previous for previous, current in pairs):
        raise DataError("native tear-sheet timestamps must be strictly increasing")


def _compound(values: Sequence[float]) -> float:
    return float(math.prod(1.0 + value for value in values) - 1.0)


def _calendar_returns(
    timestamps: Sequence[datetime], returns: Sequence[float]
) -> tuple[tuple[MonthlyReturn, ...], tuple[YearlyReturn, ...]]:
    monthly_groups: dict[tuple[int, int], list[float]] = {}
    yearly_groups: dict[int, list[float]] = {}
    for ts, value in zip(timestamps[1:], returns, strict=True):
        monthly_groups.setdefault((ts.year, ts.month), []).append(value)
        yearly_groups.setdefault(ts.year, []).append(value)
    monthly = tuple(
        MonthlyReturn(year=year, month=month, return_value=_compound(values))
        for (year, month), values in sorted(monthly_groups.items())
    )
    yearly = tuple(
        YearlyReturn(year=year, return_value=_compound(values))
        for year, values in sorted(yearly_groups.items())
    )
    return monthly, yearly


def _distribution(
    returns: np.ndarray, histogram_bins: int
) -> tuple[tuple[HistogramBin, ...], tuple[QQPoint, ...]]:
    counts, edges = np.histogram(returns, bins=histogram_bins)
    histogram = tuple(
        HistogramBin(left=float(edges[index]), right=float(edges[index + 1]), count=int(count))
        for index, count in enumerate(counts)
    )
    ordered = np.sort(returns)
    normal = NormalDist()
    qq = tuple(
        QQPoint(
            probability=(index + 0.5) / len(ordered),
            theoretical=normal.inv_cdf((index + 0.5) / len(ordered)),
            sample=float(sample),
        )
        for index, sample in enumerate(ordered)
    )
    return histogram, qq


def _rolling(
    timestamps: Sequence[datetime],
    returns: np.ndarray,
    *,
    periods_per_year: int,
    rolling_window: int,
) -> tuple[RollingMetric, ...]:
    rows: list[RollingMetric] = []
    for end in range(rolling_window - 1, len(returns)):
        window = returns[end - rolling_window + 1 : end + 1]
        volatility = float(np.std(window, ddof=1)) * math.sqrt(periods_per_year)
        sharpe = None
        if volatility > 0.0:
            per_period_std = float(np.std(window, ddof=1))
            sharpe = float(np.mean(window)) / per_period_std * math.sqrt(periods_per_year)
        rows.append(
            RollingMetric(
                ts=timestamps[end + 1],
                return_value=_compound(window.tolist()),
                volatility=volatility,
                sharpe=sharpe,
            )
        )
    return tuple(rows)


def build_native_tearsheet(
    timestamps: Sequence[datetime],
    equity: Sequence[float],
    *,
    periods_per_year: int = 252,
    rolling_window: int = 126,
    histogram_bins: int = 20,
) -> NativeTearSheet:
    """Build calendar, distribution, Q-Q, and rolling series from canonical equity points."""

    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    if rolling_window < 2:
        raise DataError(f"rolling_window must be >= 2, got {rolling_window}")
    if not 2 <= histogram_bins <= 200:
        raise DataError(f"histogram_bins must be in [2, 200], got {histogram_bins}")
    _validate_timestamps(timestamps, len(equity))
    returns = to_returns(equity)
    monthly, yearly = _calendar_returns(timestamps, returns.tolist())
    histogram, qq = _distribution(returns, histogram_bins)
    return NativeTearSheet(
        monthly=monthly,
        yearly=yearly,
        histogram=histogram,
        qq=qq,
        rolling=_rolling(
            timestamps,
            returns,
            periods_per_year=periods_per_year,
            rolling_window=rolling_window,
        ),
    )


__all__ = [
    "HistogramBin",
    "MonthlyReturn",
    "NativeTearSheet",
    "QQPoint",
    "RollingMetric",
    "YearlyReturn",
    "build_native_tearsheet",
]
