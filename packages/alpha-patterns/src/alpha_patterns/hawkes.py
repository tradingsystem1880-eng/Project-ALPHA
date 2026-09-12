"""Hawkes-process volatility: a self-exciting, exponentially decaying sum of a range series.

Each bar's (normalised) range adds to an intensity that decays at rate ``kappa``, so clustered
volatility builds a high reading while quiet periods let it fade. The signal rule waits for the
intensity to drop below its trailing 5th percentile, then, on the first crossing above the trailing
95th percentile, goes with the direction price moved since that quiet bar; it flattens on the next
quiet reading. Everything is trailing: the quantiles use the last ``lookback`` readings and the
"since the dip" reference is a past bar.

Provenance: github.com/neurotrader888/VolatilityHawkes/hawkes.py@51c8557 (MIT); adapted: numpy
arrays, ``DataError`` validation, quantile windows that contain a NaN are NaN (pandas rolling
semantics, kept), and the upstream comparison of bar 0 with the series' last bar (a negative-index
artefact) is replaced by skipping bar 0. The recursion and the signal rule are unchanged (parity
fixture ``tests/fixtures/neurotrader/hawkes.json``).
"""

from __future__ import annotations

import math

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import FloatArray, IntArray


def hawkes_process(values: FloatArray, *, kappa: float) -> FloatArray:
    """``out[i] = out[i-1] * exp(-kappa) + values[i]``, scaled by ``kappa``; ``out[0]`` is NaN.

    A NaN in ``values`` restarts the recursion on the next finite bar, as upstream.
    """
    if not kappa > 0.0:
        raise DataError(f"hawkes kappa must be > 0, got {kappa}")
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or x.size < 2:
        raise DataError(f"hawkes needs a 1-D array of >= 2 values, got shape {x.shape}")
    alpha = math.exp(-kappa)
    out = np.full(x.size, np.nan)
    for i in range(1, x.size):
        out[i] = x[i] if math.isnan(out[i - 1]) else out[i - 1] * alpha + x[i]
    return np.asarray(out * kappa, dtype=np.float64)


def _rolling_quantile(values: FloatArray, window: int, q: float) -> FloatArray:
    out = np.full(values.size, np.nan)
    for i in range(window - 1, values.size):
        chunk = values[i - window + 1 : i + 1]
        if bool(np.all(np.isfinite(chunk))):
            out[i] = np.quantile(chunk, q)
    return out


def hawkes_vol_signal(close: FloatArray, hawkes: FloatArray, *, lookback: int) -> IntArray:
    """The upstream ``{-1, 0, 1}`` regime signal over a Hawkes volatility series."""
    c = np.asarray(close, dtype=np.float64)
    h = np.asarray(hawkes, dtype=np.float64)
    if c.shape != h.shape or c.ndim != 1:
        raise DataError(f"close and hawkes must be 1-D and equal length, got {c.shape}, {h.shape}")
    if lookback < 2 or lookback > c.size:
        raise DataError(f"lookback must be in [2, {c.size}], got {lookback}")
    q05 = _rolling_quantile(h, lookback, 0.05)
    q95 = _rolling_quantile(h, lookback, 0.95)
    signal = np.zeros(c.size, dtype=np.intp)
    last_below = -1
    current = 0
    for i in range(1, c.size):
        if h[i] < q05[i]:
            last_below = i
            current = 0
        if h[i] > q95[i] and h[i - 1] <= q95[i - 1] and last_below > 0:
            current = 1 if c[i] - c[last_below] > 0.0 else -1
        signal[i] = current
    return signal
