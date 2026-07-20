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
    gross_exposure: float | None = None
    net_exposure: float | None = None
    turnover: float | None = None


@dataclass(frozen=True, slots=True)
class ExposureTurnoverPoint:
    start_ts: datetime
    end_ts: datetime
    gross_exposure: float | None
    net_exposure: float | None
    turnover: float | None


@dataclass(frozen=True, slots=True)
class BenchmarkComparison:
    ts: datetime
    strategy_equity: float
    benchmark_equity: float | None
    strategy_return: float | None
    benchmark_return: float | None
    excess_return: float | None


@dataclass(frozen=True, slots=True)
class TradeObservation:
    """Closed-trade fields needed for Python-authoritative summary statistics."""

    side: str
    realized_pnl: float
    realized_return: float
    entry_ts: datetime
    exit_ts: datetime


@dataclass(frozen=True, slots=True)
class TradeStatistic:
    metric: str
    value: float | None
    unit: str
    available: bool
    unavailable_reason: str | None


@dataclass(frozen=True, slots=True)
class NativeTearSheet:
    monthly: tuple[MonthlyReturn, ...]
    yearly: tuple[YearlyReturn, ...]
    histogram: tuple[HistogramBin, ...]
    qq: tuple[QQPoint, ...]
    rolling: tuple[RollingMetric, ...]
    exposure_turnover: tuple[ExposureTurnoverPoint, ...] = ()
    benchmark: tuple[BenchmarkComparison, ...] = ()
    trade_statistics: tuple[TradeStatistic, ...] = ()
    exposure_available: bool = False
    turnover_available: bool = False
    benchmark_available: bool = False
    trade_statistics_available: bool = False


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
    gross_exposure: np.ndarray | None,
    net_exposure: np.ndarray | None,
    turnover: np.ndarray | None,
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
                gross_exposure=(
                    float(np.mean(gross_exposure[end - rolling_window + 1 : end + 1]))
                    if gross_exposure is not None
                    else None
                ),
                net_exposure=(
                    float(np.mean(net_exposure[end - rolling_window + 1 : end + 1]))
                    if net_exposure is not None
                    else None
                ),
                turnover=(
                    float(np.sum(turnover[end - rolling_window + 1 : end + 1]))
                    if turnover is not None
                    else None
                ),
            )
        )
    return tuple(rows)


def _optional_series(
    values: Sequence[float] | None,
    *,
    name: str,
    expected: int,
    non_negative: bool,
) -> np.ndarray | None:
    if values is None:
        return None
    if len(values) != expected:
        raise DataError(f"{name} must have {expected} values, got {len(values)}")
    array = np.asarray(values, dtype=np.float64)
    if not bool(np.all(np.isfinite(array))):
        raise DataError(f"{name} requires finite values")
    if non_negative and bool(np.any(array < 0.0)):
        raise DataError(f"{name} requires non-negative values")
    return array


def _benchmark_comparison(
    timestamps: Sequence[datetime],
    equity: Sequence[float],
    benchmark_equity: np.ndarray | None,
) -> tuple[BenchmarkComparison, ...]:
    strategy = np.asarray(equity, dtype=np.float64) / float(equity[0])
    benchmark = None
    if benchmark_equity is not None:
        if bool(np.any(benchmark_equity <= 0.0)):
            raise DataError("benchmark_equity requires strictly-positive values")
        benchmark = benchmark_equity / float(benchmark_equity[0])
    rows: list[BenchmarkComparison] = []
    for index, ts in enumerate(timestamps):
        strategy_return = None
        benchmark_return = None
        excess_return = None
        if index > 0:
            strategy_return = float(strategy[index] / strategy[index - 1] - 1.0)
            if benchmark is not None:
                benchmark_return = float(benchmark[index] / benchmark[index - 1] - 1.0)
                excess_return = strategy_return - benchmark_return
        rows.append(
            BenchmarkComparison(
                ts=ts,
                strategy_equity=float(strategy[index]),
                benchmark_equity=float(benchmark[index]) if benchmark is not None else None,
                strategy_return=strategy_return,
                benchmark_return=benchmark_return,
                excess_return=excess_return,
            )
        )
    return tuple(rows)


def _exposure_turnover_points(
    timestamps: Sequence[datetime],
    gross_exposure: np.ndarray | None,
    net_exposure: np.ndarray | None,
    turnover: np.ndarray | None,
) -> tuple[ExposureTurnoverPoint, ...]:
    return tuple(
        ExposureTurnoverPoint(
            start_ts=start,
            end_ts=end,
            gross_exposure=(float(gross_exposure[index]) if gross_exposure is not None else None),
            net_exposure=(float(net_exposure[index]) if net_exposure is not None else None),
            turnover=float(turnover[index]) if turnover is not None else None,
        )
        for index, (start, end) in enumerate(zip(timestamps[:-1], timestamps[1:], strict=True))
    )


_TRADE_STAT_UNITS: tuple[tuple[str, str], ...] = (
    ("trade_count", "count"),
    ("winning_trade_count", "count"),
    ("losing_trade_count", "count"),
    ("breakeven_trade_count", "count"),
    ("long_trade_count", "count"),
    ("short_trade_count", "count"),
    ("win_rate", "ratio"),
    ("total_realized_pnl", "account_currency"),
    ("average_realized_pnl", "account_currency"),
    ("median_realized_pnl", "account_currency"),
    ("average_realized_return", "ratio"),
    ("median_realized_return", "ratio"),
    ("profit_factor", "ratio"),
    ("average_holding_seconds", "seconds"),
    ("median_holding_seconds", "seconds"),
    ("largest_win_pnl", "account_currency"),
    ("largest_loss_pnl", "account_currency"),
)


def _stat(
    metric: str,
    value: float | None,
    unit: str,
    *,
    reason: str | None = None,
) -> TradeStatistic:
    return TradeStatistic(
        metric=metric,
        value=value,
        unit=unit,
        available=value is not None,
        unavailable_reason=reason if value is None else None,
    )


def _trade_statistics(
    trades: Sequence[TradeObservation] | None,
) -> tuple[TradeStatistic, ...]:
    if trades is None:
        return tuple(
            _stat(metric, None, unit, reason="trade_input_unavailable")
            for metric, unit in _TRADE_STAT_UNITS
        )
    for trade in trades:
        if trade.side not in {"BUY", "SELL"}:
            raise DataError(f"trade side must be BUY or SELL, got {trade.side!r}")
        if not math.isfinite(trade.realized_pnl) or not math.isfinite(trade.realized_return):
            raise DataError("trade statistics require finite realized PnL and returns")
        if (
            trade.entry_ts.tzinfo is None
            or trade.exit_ts.tzinfo is None
            or trade.entry_ts.utcoffset() is None
            or trade.exit_ts.utcoffset() is None
        ):
            raise DataError("trade statistics require timezone-aware timestamps")
        if trade.exit_ts <= trade.entry_ts:
            raise DataError("trade exit_ts must be strictly after entry_ts")
    n = len(trades)
    if n == 0:
        available_zero = {
            "trade_count",
            "winning_trade_count",
            "losing_trade_count",
            "breakeven_trade_count",
            "long_trade_count",
            "short_trade_count",
            "total_realized_pnl",
        }
        return tuple(
            _stat(
                metric,
                0.0 if metric in available_zero else None,
                unit,
                reason="no_closed_trades",
            )
            for metric, unit in _TRADE_STAT_UNITS
        )
    pnls = np.asarray([trade.realized_pnl for trade in trades], dtype=np.float64)
    realized_returns = np.asarray([trade.realized_return for trade in trades], dtype=np.float64)
    holding = np.asarray(
        [(trade.exit_ts - trade.entry_ts).total_seconds() for trade in trades], dtype=np.float64
    )
    winners = pnls[pnls > 0.0]
    losers = pnls[pnls < 0.0]
    gross_loss = abs(float(np.sum(losers)))
    values: dict[str, float | None] = {
        "trade_count": float(n),
        "winning_trade_count": float(winners.size),
        "losing_trade_count": float(losers.size),
        "breakeven_trade_count": float(np.count_nonzero(pnls == 0.0)),
        "long_trade_count": float(sum(trade.side == "BUY" for trade in trades)),
        "short_trade_count": float(sum(trade.side == "SELL" for trade in trades)),
        "win_rate": float(winners.size / n),
        "total_realized_pnl": float(np.sum(pnls)),
        "average_realized_pnl": float(np.mean(pnls)),
        "median_realized_pnl": float(np.median(pnls)),
        "average_realized_return": float(np.mean(realized_returns)),
        "median_realized_return": float(np.median(realized_returns)),
        "profit_factor": float(np.sum(winners)) / gross_loss if gross_loss > 0.0 else None,
        "average_holding_seconds": float(np.mean(holding)),
        "median_holding_seconds": float(np.median(holding)),
        "largest_win_pnl": float(np.max(winners)) if winners.size else None,
        "largest_loss_pnl": float(np.min(losers)) if losers.size else None,
    }
    return tuple(
        _stat(
            metric,
            values[metric],
            unit,
            reason="no_losing_trades" if metric == "profit_factor" else "no_matching_trades",
        )
        for metric, unit in _TRADE_STAT_UNITS
    )


def build_native_tearsheet(
    timestamps: Sequence[datetime],
    equity: Sequence[float],
    *,
    periods_per_year: int = 252,
    rolling_window: int = 126,
    histogram_bins: int = 20,
    gross_exposure: Sequence[float] | None = None,
    net_exposure: Sequence[float] | None = None,
    turnover: Sequence[float] | None = None,
    benchmark_equity: Sequence[float] | None = None,
    trades: Sequence[TradeObservation] | None = None,
) -> NativeTearSheet:
    """Build native analytics from canonical equity and optional execution evidence.

    Exposure and turnover are interval values aligned with ``equity[:-1]``. Benchmark equity is
    point-aligned with the strategy equity. Missing optional evidence stays explicitly unavailable;
    it is never inferred from returns or filled with zeroes.
    """

    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    if rolling_window < 2:
        raise DataError(f"rolling_window must be >= 2, got {rolling_window}")
    if not 2 <= histogram_bins <= 200:
        raise DataError(f"histogram_bins must be in [2, 200], got {histogram_bins}")
    _validate_timestamps(timestamps, len(equity))
    returns = to_returns(equity)
    gross = _optional_series(
        gross_exposure,
        name="gross_exposure",
        expected=len(returns),
        non_negative=True,
    )
    net = _optional_series(
        net_exposure,
        name="net_exposure",
        expected=len(returns),
        non_negative=False,
    )
    if (gross is None) != (net is None):
        raise DataError("gross_exposure and net_exposure must be supplied together")
    if gross is not None and net is not None and bool(np.any(np.abs(net) > gross + 1e-12)):
        raise DataError("net exposure magnitude cannot exceed gross exposure")
    turnover_values = _optional_series(
        turnover,
        name="turnover",
        expected=len(returns),
        non_negative=True,
    )
    benchmark_values = _optional_series(
        benchmark_equity,
        name="benchmark_equity",
        expected=len(equity),
        non_negative=False,
    )
    monthly, yearly = _calendar_returns(timestamps, returns.tolist())
    histogram, qq = _distribution(returns, histogram_bins)
    trade_statistics = _trade_statistics(trades)
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
            gross_exposure=gross,
            net_exposure=net,
            turnover=turnover_values,
        ),
        exposure_turnover=_exposure_turnover_points(
            timestamps,
            gross,
            net,
            turnover_values,
        ),
        benchmark=_benchmark_comparison(timestamps, equity, benchmark_values),
        trade_statistics=trade_statistics,
        exposure_available=gross is not None,
        turnover_available=turnover_values is not None,
        benchmark_available=benchmark_values is not None,
        trade_statistics_available=trades is not None,
    )


__all__ = [
    "BenchmarkComparison",
    "ExposureTurnoverPoint",
    "HistogramBin",
    "MonthlyReturn",
    "NativeTearSheet",
    "QQPoint",
    "RollingMetric",
    "TradeObservation",
    "TradeStatistic",
    "YearlyReturn",
    "build_native_tearsheet",
]
