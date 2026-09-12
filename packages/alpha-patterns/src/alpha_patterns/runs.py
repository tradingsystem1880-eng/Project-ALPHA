"""Wald–Wolfowitz runs test as a trailing indicator of streakiness.

A run is a maximal streak of equal signs. Under independence the number of runs in ``n`` signs
with ``n_pos`` positives and ``n_neg`` negatives has mean ``2 n_pos n_neg / n + 1`` and variance
``(mean - 1)(mean - 2) / (n - 1)``; the z-score of the observed count is negative when signs
cluster (trending) and positive when they alternate (mean-reverting). ``rolling_runs_z`` applies
it to the signs of close-to-close changes over a trailing window.

Provenance: github.com/neurotrader888/TradeDependenceRunsTest/{runs_test,runs_indicator}.py
@5f63804 (MIT); adapted: numpy arrays, a documented NaN for degenerate windows (all one sign, where
the variance is zero and upstream divides by zero), ``DataError`` validation. The statistic is
unchanged (parity fixture ``tests/fixtures/neurotrader/runs.json``). Wald & Wolfowitz (1940).
"""

from __future__ import annotations

import math

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import FloatArray


def runs_z(signs: FloatArray) -> float:
    """Z-score of the observed number of runs; NaN when all signs agree (variance is zero).

    Zeros are counted in ``n`` and break a run without being positive or negative, as upstream.
    """
    s = np.asarray(signs, dtype=np.float64)
    if s.ndim != 1 or s.size < 2:
        raise DataError(f"runs test needs a 1-D array of >= 2 signs, got shape {s.shape}")
    if not bool(np.all(np.isfinite(s))):
        raise DataError("runs test signs contain non-finite values")
    n = s.size
    n_pos = int(np.sum(s > 0))
    n_neg = int(np.sum(s < 0))
    mean = 2.0 * n_pos * n_neg / n + 1.0
    var = (mean - 1.0) * (mean - 2.0) / (n - 1)
    if var <= 0.0:
        return math.nan
    runs = 1 + int(np.sum(s[1:] != s[:-1]))
    return float((runs - mean) / math.sqrt(var))


def rolling_runs_z(close: FloatArray, *, lookback: int) -> FloatArray:
    """``runs_z`` of the signs of close changes over ``[i-lookback+1, i]``; NaN before that."""
    c = np.asarray(close, dtype=np.float64)
    if c.ndim != 1 or c.size < 2:
        raise DataError(f"rolling runs needs a 1-D array of >= 2 closes, got shape {c.shape}")
    if lookback < 2 or lookback >= c.size:
        raise DataError(f"lookback must be in [2, {c.size - 1}], got {lookback}")
    signs = np.concatenate(([np.nan], np.sign(np.diff(c))))
    out = np.full(c.size, np.nan)
    for i in range(lookback, c.size):
        out[i] = runs_z(signs[i - lookback + 1 : i + 1])
    return out
