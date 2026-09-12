"""Market-profile support and resistance: the modes of a recency-weighted price density.

The trailing window's log closes are smoothed into a density whose bandwidth is a multiple of the
log-ATR (so "how wide is a level" scales with volatility) and whose weights rise linearly toward
the present; every sufficiently prominent mode of that density is a level. Levels at bar ``i`` use
bars ``i-lookback+1 .. i``, and, as upstream, the penetration signal at ``i`` compares the previous
and current close against the levels of bar ``i`` itself: causal, but the current close is part of
the density it is tested against.

Provenance: github.com/neurotrader888/TechnicalAnalysisAutomation/mp_support_resist.py
@da99c20bf3d977b639451258cd6cfca9baa1dcc3 (MIT); adapted: numpy KDE and peak finding
(``alpha_patterns._kde``) instead of SciPy, ``log_atr`` (causal simple mean) instead of
``pandas_ta`` Wilder ATR for the window bandwidth, typed results, fail-loud flat windows. The
weighting, grid, bandwidth and prominence rules are unchanged (parity fixture
``tests/fixtures/neurotrader/market_profile.json`` with the ATR supplied as an input).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_patterns._kde import prominent_peaks, weighted_gaussian_kde
from alpha_patterns.series import OHLCV, FloatArray, IntArray, log_atr

_GRID_STEPS = 200


@dataclass(frozen=True)
class MarketProfile:
    """The density over log price and the levels (in price units) read off its modes."""

    grid: FloatArray  # log prices
    density: FloatArray
    peaks: IntArray  # grid indices of the prominent modes
    levels: FloatArray  # exp(grid[peaks])


def market_profile(
    log_prices: FloatArray,
    *,
    atr: float,
    first_w: float = 0.1,
    atr_mult: float = 3.0,
    prom_thresh: float = 0.1,
) -> MarketProfile:
    """Levels of one window: bandwidth ``atr * atr_mult``, weights from ``first_w`` to 1."""
    x = np.asarray(log_prices, dtype=np.float64)
    if x.ndim != 1 or x.size < 2:
        raise DataError(f"market profile needs >= 2 prices, got shape {x.shape}")
    if not bool(np.all(np.isfinite(x))):
        raise DataError("market profile prices contain non-finite values")
    if not (np.isfinite(atr) and atr > 0.0):
        raise DataError(f"market profile atr must be finite and > 0, got {atr}")
    if not 0.0 < prom_thresh < 1.0:
        raise DataError(f"prom_thresh must be in (0, 1), got {prom_thresh}")
    w_step = (1.0 - first_w) / x.size
    weights = np.asarray(first_w + np.arange(x.size) * w_step, dtype=np.float64)
    weights[weights < 0.0] = 0.0
    lo, hi = float(x.min()), float(x.max())
    if hi <= lo:
        raise DataError("market profile window is flat; no density can be estimated")
    grid = np.arange(lo, hi, (hi - lo) / _GRID_STEPS)
    density = weighted_gaussian_kde(x, grid, bandwidth_factor=atr * atr_mult, weights=weights)
    peaks = prominent_peaks(density, min_prominence=float(density.max()) * prom_thresh)
    return MarketProfile(grid=grid, density=density, peaks=peaks, levels=np.exp(grid[peaks]))


def support_resistance_levels(
    bars: OHLCV,
    *,
    lookback: int,
    first_w: float = 0.01,
    atr_mult: float = 3.0,
    prom_thresh: float = 0.25,
) -> list[FloatArray | None]:
    """Per-bar level arrays (price units); ``None`` before the first full window."""
    if lookback < 2 or lookback >= len(bars):
        raise DataError(f"lookback must be in [2, {len(bars) - 1}], got {lookback}")
    log_close = np.log(bars.close)
    atr = log_atr(bars, lookback)
    out: list[FloatArray | None] = [None] * len(bars)
    for i in range(lookback, len(bars)):
        window = log_close[i - lookback + 1 : i + 1]
        out[i] = market_profile(
            window, atr=float(atr[i]), first_w=first_w, atr_mult=atr_mult, prom_thresh=prom_thresh
        ).levels
    return out


def sr_penetration_signal(close: FloatArray, levels: list[FloatArray | None]) -> IntArray:
    """``{-1, 0, 1}`` position: last level crossed upward -> long, downward -> short; persists."""
    c = np.asarray(close, dtype=np.float64)
    if len(levels) != c.size:
        raise DataError(f"levels length {len(levels)} does not match close length {c.size}")
    signal = np.zeros(c.size, dtype=np.intp)
    current = 0
    for i in range(1, c.size):
        lv = levels[i]
        if lv is None:
            continue
        last_c, curr_c = c[i - 1], c[i]
        for level in lv:
            if curr_c > level >= last_c:
                current = 1
            elif curr_c < level <= last_c:
                current = -1
        signal[i] = current
    return signal
