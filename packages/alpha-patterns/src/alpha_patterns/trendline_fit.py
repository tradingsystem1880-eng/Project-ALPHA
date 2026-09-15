"""Window trendline fitting by slope optimisation, trendline breakouts, and meta-label features.

``fit_trendlines_single`` starts from the least-squares line through a window, pivots the line on
the bar farthest above (resistance) or below (support) it, then searches the slope by step-halving
until the line touches the pivot and never crosses price. ``trendline_breakout`` fits that pair on
the ``lookback`` bars *before* each bar, projects both lines one step forward and flags a close
beyond either. ``breakout_features`` records, for every resistance breakout trade, the five
per-trade descriptors used for meta-labelling and the trade outcome under a take-profit /
stop-loss / holding-period exit.

This complements ``alpha_patterns.trendline`` (swing-anchored lines with break rules); it is a
window-fitting alternative, not a replacement.

Provenance: github.com/neurotrader888/TrendLineAutomation/trendline_automation.py@63b1429 and
github.com/neurotrader888/TrendlineBreakoutMetaLabel/{trendline_breakout,trendline_break_dataset}.py
@874d938 (MIT); adapted: typed results, ``DataError`` instead of ``assert``/``Exception``, the
feature builder normalises by ALPHA's causal simple-mean ATR of log prices and
``directional_index`` ADX instead of ``pandas_ta`` (Wilder smoothing), and incomplete trades are
never returned. The fitting and breakout logic is unchanged (parity fixture
``tests/fixtures/neurotrader/trendline_fit.json``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_patterns.indicators import rolling_median
from alpha_patterns.oscillators import directional_index
from alpha_patterns.series import OHLCV, FloatArray, IntArray, log_atr

_LINE_TOLERANCE = 1e-5
_MIN_STEP = 0.0001


@dataclass(frozen=True)
class FittedLine:
    """``y = slope * x + intercept`` over a window's bar offsets ``0 .. n-1``."""

    slope: float
    intercept: float

    def value_at(self, x: float) -> float:
        return self.slope * x + self.intercept


@dataclass(frozen=True)
class TrendlinePair:
    support: FittedLine
    resistance: FittedLine


def _check_values(values: FloatArray, name: str) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 3:
        raise DataError(f"{name} needs a 1-D array of >= 3 values, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{name} contains non-finite values")
    return arr


def _line_error(support: bool, pivot: int, slope: float, y: FloatArray) -> float:
    """Squared error of the pivot-anchored line, or ``-1.0`` when it crosses price."""
    intercept = -slope * pivot + y[pivot]
    diffs = slope * np.arange(y.size) + intercept - y
    if support and diffs.max() > _LINE_TOLERANCE:
        return -1.0
    if not support and diffs.min() < -_LINE_TOLERANCE:
        return -1.0
    return float(np.sum(diffs**2))


def _optimize_slope(support: bool, pivot: int, init_slope: float, y: FloatArray) -> FittedLine:
    slope_unit = float(y.max() - y.min()) / y.size
    curr_step = 1.0
    best_slope = init_slope
    best_err = _line_error(support, pivot, init_slope, y)
    if best_err < 0.0:
        raise DataError("initial trendline crosses price; the pivot is not the extreme bar")
    get_derivative = True
    derivative = 0.0
    while curr_step > _MIN_STEP:
        if get_derivative:
            test_slope = best_slope + slope_unit * _MIN_STEP
            test_err = _line_error(support, pivot, test_slope, y)
            derivative = test_err - best_err
            if test_err < 0.0:
                test_slope = best_slope - slope_unit * _MIN_STEP
                test_err = _line_error(support, pivot, test_slope, y)
                derivative = best_err - test_err
            if test_err < 0.0:
                raise DataError("trendline slope derivative failed on both sides; check the data")
            get_derivative = False
        step = slope_unit * curr_step
        test_slope = best_slope - step if derivative > 0.0 else best_slope + step
        test_err = _line_error(support, pivot, test_slope, y)
        if test_err < 0.0 or test_err >= best_err:
            curr_step *= 0.5
        else:
            best_err, best_slope = test_err, test_slope
            get_derivative = True
    return FittedLine(best_slope, -best_slope * pivot + float(y[pivot]))


def fit_trendlines_single(values: FloatArray) -> TrendlinePair:
    """Support and resistance lines through one series (closes, usually log)."""
    data = _check_values(values, "trendline values")
    x = np.arange(data.size)
    slope, intercept = np.polyfit(x, data, 1)
    residual = data - (slope * x + intercept)
    upper_pivot, lower_pivot = int(residual.argmax()), int(residual.argmin())
    return TrendlinePair(
        support=_optimize_slope(True, lower_pivot, float(slope), data),
        resistance=_optimize_slope(False, upper_pivot, float(slope), data),
    )


def fit_trendlines_high_low(high: FloatArray, low: FloatArray, close: FloatArray) -> TrendlinePair:
    """Resistance on highs and support on lows, both initialised from the close's fit."""
    h, lo, c = (_check_values(a, n) for a, n in ((high, "high"), (low, "low"), (close, "close")))
    if not h.size == lo.size == c.size:
        raise DataError("high, low and close must have the same length")
    x = np.arange(c.size)
    slope, intercept = np.polyfit(x, c, 1)
    line = slope * x + intercept
    upper_pivot, lower_pivot = int((h - line).argmax()), int((lo - line).argmin())
    return TrendlinePair(
        support=_optimize_slope(True, lower_pivot, float(slope), lo),
        resistance=_optimize_slope(False, upper_pivot, float(slope), h),
    )


@dataclass(frozen=True)
class TrendlineBreakoutSeries:
    """Per-bar projected lines (NaN before ``lookback``) and the persisted ``{-1, 0, 1}`` signal."""

    support: FloatArray
    resistance: FloatArray
    signal: IntArray
    lookback: int


def trendline_breakout(close: FloatArray, *, lookback: int) -> TrendlineBreakoutSeries:
    """Fit on the ``lookback`` bars before ``i`` (never ``i`` itself), project to ``i``, compare.

    The signal persists: a bar between the two lines keeps the previous state, so this is a
    position series, not an event series.
    """
    data = _check_values(close, "close")
    if lookback < 3 or lookback >= data.size:
        raise DataError(f"lookback must be in [3, {data.size - 1}], got {lookback}")
    n = data.size
    support = np.full(n, np.nan)
    resistance = np.full(n, np.nan)
    signal = np.zeros(n, dtype=np.intp)
    for i in range(lookback, n):
        pair = fit_trendlines_single(data[i - lookback : i])
        s_val, r_val = pair.support.value_at(lookback), pair.resistance.value_at(lookback)
        support[i], resistance[i] = s_val, r_val
        if data[i] > r_val:
            signal[i] = 1
        elif data[i] < s_val:
            signal[i] = -1
        else:
            signal[i] = signal[i - 1]
    return TrendlineBreakoutSeries(support, resistance, signal, lookback)


@dataclass(frozen=True)
class BreakoutTrade:
    """One completed resistance-breakout trade in log-price units with its meta-label features."""

    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    atr: float
    resist_slope: float
    resist_intercept: float
    resist_slope_atr: float  # resistance slope / ATR
    tl_err_atr: float  # mean signed (line - price) over the window / ATR
    max_dist_atr: float  # max (line - price) over the window / ATR
    vol_ratio: float  # breakout-bar volume / trailing median volume
    adx: float

    @property
    def log_return(self) -> float:
        return self.exit_price - self.entry_price

    @property
    def label(self) -> bool:
        """The meta-label: did the raw breakout make money?"""
        return self.log_return > 0.0


def breakout_features(
    bars: OHLCV,
    *,
    lookback: int,
    hold_period: int = 12,
    tp_mult: float = 3.0,
    sl_mult: float = 3.0,
    atr_lookback: int = 168,
) -> list[BreakoutTrade]:
    """Every completed long resistance-breakout trade with its five meta-label features.

    Entry on the first bar whose log close exceeds the resistance line fitted on the previous
    ``lookback`` bars; exit on take-profit (``tp_mult`` ATR), stop-loss (``sl_mult`` ATR) or after
    ``hold_period`` bars, whichever comes first. A trade still open at the end of the series is
    not returned, so every returned label is settled.
    """
    if atr_lookback < lookback:
        raise DataError(f"atr_lookback {atr_lookback} must be >= lookback {lookback}")
    if lookback < 3:
        raise DataError(f"lookback must be >= 3, got {lookback}")
    if hold_period < 1 or tp_mult <= 0.0 or sl_mult <= 0.0:
        raise DataError("hold_period must be >= 1 and tp_mult/sl_mult > 0")
    n = len(bars)
    if n <= atr_lookback:
        return []
    close = np.log(bars.close)
    atr = log_atr(bars, atr_lookback)
    vol_ratio = bars.volume / rolling_median(bars.volume, atr_lookback)
    adx = directional_index(bars, window=lookback).adx
    trades: list[BreakoutTrade] = []
    pending: dict[str, float] | None = None
    for i in range(atr_lookback, n):
        if pending is None:
            window = close[i - lookback : i]
            resistance = fit_trendlines_single(window).resistance
            r_val = resistance.value_at(lookback)
            if close[i] > r_val:
                if atr[i] <= 0.0 or not np.isfinite(vol_ratio[i]) or not np.isfinite(adx[i]):
                    raise DataError(f"breakout at bar {i} has a degenerate ATR, volume or ADX")
                line_vals = resistance.intercept + np.arange(lookback) * resistance.slope
                diff = line_vals - window
                pending = {
                    "entry_index": float(i),
                    "entry_price": float(close[i]),
                    "atr": float(atr[i]),
                    "tp": float(close[i] + atr[i] * tp_mult),
                    "sl": float(close[i] - atr[i] * sl_mult),
                    "hp_i": float(i + hold_period),
                    "resist_slope": resistance.slope,
                    "resist_intercept": resistance.intercept,
                    "resist_slope_atr": resistance.slope / float(atr[i]),
                    "tl_err_atr": float(np.sum(diff) / lookback / atr[i]),
                    "max_dist_atr": float(diff.max() / atr[i]),
                    "vol_ratio": float(vol_ratio[i]),
                    "adx": float(adx[i]),
                }
        if pending is not None and (
            close[i] >= pending["tp"] or close[i] <= pending["sl"] or i >= pending["hp_i"]
        ):
            trades.append(
                BreakoutTrade(
                    entry_index=int(pending["entry_index"]),
                    exit_index=i,
                    entry_price=pending["entry_price"],
                    exit_price=float(close[i]),
                    atr=pending["atr"],
                    resist_slope=pending["resist_slope"],
                    resist_intercept=pending["resist_intercept"],
                    resist_slope_atr=pending["resist_slope_atr"],
                    tl_err_atr=pending["tl_err_atr"],
                    max_dist_atr=pending["max_dist_atr"],
                    vol_ratio=pending["vol_ratio"],
                    adx=pending["adx"],
                )
            )
            pending = None
    return trades
