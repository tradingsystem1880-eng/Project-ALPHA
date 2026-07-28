"""Market-structure context: order blocks, fair-value gaps, trend state, and location.

Study 3 asks whether the two patterns behave differently *depending on where they occur*, so the
conditioning variables need their own definitions. Two of these also let the study reproduce the
user's existing order-block and FVG findings on the same data, which is the cheapest available
check that this pipeline and their prior one are measuring the same objects.

Trend state matters most. A descending trendline broken upward inside a structural downtrend is a
different event from the same break inside a range, and pooling them hides whichever effect is
smaller. Two independent definitions are provided (moving-average relationship and price versus a
long VWAP) precisely so a result that only survives under one of them can be spotted as fragile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import (
    OHLCV,
    FloatArray,
    atr,
    rolling_max,
    rolling_min,
    rolling_vwap,
)

Direction = Literal["bullish", "bearish"]
TrendState = Literal["uptrend", "downtrend", "range"]


@dataclass(frozen=True)
class OrderBlock:
    """Last opposite-direction candle before a displacement leg that broke structure."""

    index: int
    direction: Direction
    top: float
    bottom: float
    displacement_atr: float
    mitigated_index: int  # first later bar to trade back into the zone (-1 if unmitigated)

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    @property
    def is_unmitigated(self) -> bool:
        return self.mitigated_index < 0


@dataclass(frozen=True)
class FairValueGap:
    """Three-bar imbalance: bar i's range fails to overlap bar i-2's."""

    index: int
    direction: Direction
    top: float
    bottom: float
    filled_index: int  # -1 while unfilled

    @property
    def is_unfilled(self) -> bool:
        return self.filled_index < 0


def find_order_blocks(
    bars: OHLCV,
    *,
    displacement_atr: float = 1.5,
    structure_lookback: int = 20,
    atr_window: int = 14,
) -> list[OrderBlock]:
    """Order blocks formed by a displacement leg of at least ``displacement_atr``.

    Two conditions must both hold, which is what separates an order block from any large candle:
    the move must be large relative to prevailing volatility, **and** it must break structure by
    exceeding the prior ``structure_lookback`` bars' extreme. The origin candle is then the last one
    that closed against the direction of the move.
    """
    if displacement_atr <= 0.0:
        raise DataError(f"displacement_atr must be > 0, got {displacement_atr}")
    if structure_lookback < 1:
        raise DataError(f"structure_lookback must be >= 1, got {structure_lookback}")

    n = len(bars)
    atr_series = atr(bars, window=atr_window)
    prior_low = rolling_min(bars.low, structure_lookback)
    prior_high = rolling_max(bars.high, structure_lookback)
    bullish_candle = bars.close > bars.open

    out: list[OrderBlock] = []
    for i in range(1, n):
        move = bars.close[i] - bars.open[i]
        size = abs(move) / max(float(atr_series[i]), 1e-12)
        if size < displacement_atr:
            continue

        down = move < 0
        # Structure break measured against bars strictly before this one.
        if down:
            if i < 1 or bars.low[i] >= prior_low[i - 1]:
                continue
            origin = _last_candle_where(bullish_candle, i, want=True)
        else:
            if i < 1 or bars.high[i] <= prior_high[i - 1]:
                continue
            origin = _last_candle_where(bullish_candle, i, want=False)
        if origin < 0:
            continue

        top = float(max(bars.open[origin], bars.close[origin]))
        bottom = float(min(bars.open[origin], bars.close[origin]))
        direction: Direction = "bearish" if down else "bullish"

        # Mitigation: price trades back into the zone after the displacement leg completes.
        mitigated = -1
        if i + 1 < n:
            back = np.flatnonzero((bars.high[i + 1 :] >= bottom) & (bars.low[i + 1 :] <= top))
            if back.size:
                mitigated = int(i + 1 + back[0])

        out.append(
            OrderBlock(
                index=origin,
                direction=direction,
                top=top,
                bottom=bottom,
                displacement_atr=float(size),
                mitigated_index=mitigated,
            )
        )
    return out


def _last_candle_where(flags: np.ndarray, before: int, *, want: bool) -> int:
    for j in range(before - 1, max(-1, before - 30), -1):
        if bool(flags[j]) is want:
            return j
    return -1


def find_fair_value_gaps(bars: OHLCV) -> list[FairValueGap]:
    """Three-bar fair-value gaps, each tracked until the first bar that trades through it."""
    n = len(bars)
    out: list[FairValueGap] = []
    for i in range(2, n):
        if bars.low[i] > bars.high[i - 2]:
            top, bottom, direction = float(bars.low[i]), float(bars.high[i - 2]), "bullish"
        elif bars.high[i] < bars.low[i - 2]:
            top, bottom, direction = float(bars.low[i - 2]), float(bars.high[i]), "bearish"
        else:
            continue

        filled = -1
        if i + 1 < n:
            through = np.flatnonzero((bars.low[i + 1 :] <= bottom) & (bars.high[i + 1 :] >= top))
            if through.size:
                filled = int(i + 1 + through[0])

        out.append(
            FairValueGap(
                index=i,
                direction=direction,  # type: ignore[arg-type]
                top=top,
                bottom=bottom,
                filled_index=filled,
            )
        )
    return out


def trend_state_ma(
    bars: OHLCV, *, fast: int = 50, slow: int = 200, band: float = 0.01
) -> list[TrendState]:
    """Per-bar trend state from a fast/slow moving-average relationship.

    ``band`` creates a neutral zone: when the averages are within ``band`` of each other the
    state is "range" rather than being flipped by noise. Both averages are causal.
    """
    if fast >= slow:
        raise DataError(f"fast ({fast}) must be < slow ({slow})")
    ma_f = _trailing_mean(bars.close, fast)
    ma_s = _trailing_mean(bars.close, slow)
    rel = (ma_f - ma_s) / np.maximum(ma_s, 1e-12)
    return ["uptrend" if r > band else "downtrend" if r < -band else "range" for r in rel]


def trend_state_vwap(bars: OHLCV, *, window: int = 540, band: float = 0.02) -> list[TrendState]:
    """Per-bar trend state from price versus a long rolling VWAP (default 90 days of 4H bars)."""
    vwap = rolling_vwap(bars, window)
    rel = (bars.close - vwap) / np.maximum(vwap, 1e-12)
    return ["uptrend" if r > band else "downtrend" if r < -band else "range" for r in rel]


def distance_from_low(bars: OHLCV, *, window: int = 540) -> FloatArray:
    """Fractional distance of each close above its trailing low.

    The second matching variable for the control group. Without it a control drawn from anywhere in
    the series would sit far above support on average, making the pattern look good for the trivial
    reason that it is measured near a floor.
    """
    lows = rolling_min(bars.low, window)
    return (bars.close - lows) / np.maximum(lows, 1e-12)


def _trailing_mean(values: FloatArray, window: int) -> FloatArray:
    csum = np.concatenate(([0.0], np.cumsum(values)))
    idx = np.arange(values.size)
    lo = np.maximum(0, idx - window + 1)
    return (csum[idx + 1] - csum[lo]) / (idx - lo + 1).astype(np.float64)
