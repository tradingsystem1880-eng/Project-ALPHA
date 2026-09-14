"""CMMA (close minus moving average) and the intermarket-difference signal.

``cmma`` is the distance of the close from its trailing mean in ATR units, divided by
``sqrt(lookback)`` so readings are comparable across lookbacks (Masters, 2020, *Statistically
Sound Indicators for Financial Market Prediction*). ``intermarket_difference`` subtracts one
market's CMMA from another's to read relative strength, and ``threshold_revert_signal`` enters when
that difference exceeds a threshold and exits when it crosses back through zero.

Provenance: re-implemented from the published formula only. The neurotrader888
``IntramarketDifference`` repository carries no licence, so no code, fixture or data from it is
used; the CMMA definition is Masters' and the entry/exit rule is stated here.
"""

from __future__ import annotations

import math

import numpy as np

from alpha_core import DataError
from alpha_patterns.indicators import rolling_mean
from alpha_patterns.series import OHLCV, FloatArray, IntArray, atr


def cmma(bars: OHLCV, *, lookback: int, atr_lookback: int = 168) -> FloatArray:
    """``(close - SMA(close, lookback)) / (ATR(atr_lookback) * sqrt(lookback))``.

    NaN until both windows are full, so a partial average is never read as a signal.
    """
    if lookback < 2:
        raise DataError(f"lookback must be >= 2, got {lookback}")
    if atr_lookback < 1:
        raise DataError(f"atr_lookback must be >= 1, got {atr_lookback}")
    warm = max(lookback, atr_lookback) - 1
    if warm >= len(bars):
        raise DataError(f"need more than {warm} bars, got {len(bars)}")
    out = (bars.close - rolling_mean(bars.close, lookback)) / (
        atr(bars, atr_lookback) * math.sqrt(lookback)
    )
    out = np.asarray(out, dtype=np.float64).copy()
    out[:warm] = np.nan
    return out


def intermarket_difference(a: FloatArray, b: FloatArray) -> FloatArray:
    """``a - b`` for two aligned indicator series (e.g. two markets' CMMA)."""
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    if x.shape != y.shape or x.ndim != 1:
        raise DataError(f"series must be 1-D and aligned, got {x.shape} vs {y.shape}")
    return np.asarray(x - y, dtype=np.float64)


def threshold_revert_signal(indicator: FloatArray, *, threshold: float) -> IntArray:
    """``{-1, 0, 1}``: long above ``threshold``, short below ``-threshold``, flat once the
    indicator crosses zero against the position. NaN readings leave the position unchanged."""
    if not threshold > 0.0:
        raise DataError(f"threshold must be > 0, got {threshold}")
    x = np.asarray(indicator, dtype=np.float64)
    if x.ndim != 1:
        raise DataError(f"indicator must be 1-D, got shape {x.shape}")
    signal = np.zeros(x.size, dtype=np.intp)
    position = 0
    for i, v in enumerate(x):
        if math.isnan(v):
            signal[i] = position
            continue
        if (position == 1 and v < 0.0) or (position == -1 and v > 0.0):
            position = 0
        if v > threshold:
            position = 1
        elif v < -threshold:
            position = -1
        signal[i] = position
    return signal
