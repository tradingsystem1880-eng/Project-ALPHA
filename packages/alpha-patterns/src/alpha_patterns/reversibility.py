"""Time-series irreversibility: does the window look the same played backwards?

Two measures. ``perm_ts_reversibility`` compares the distribution of ordinal patterns of the
window with that of the reversed window by Kullback–Leibler divergence (Zanin et al., 2018);
``relative_async_index`` builds the horizontal visibility graph of the window and of its reverse,
compares their out-degree sequences by the asynchronous index, and reports the log ratio of the
two directions (Yang & Shang, 2018). Both are 0 for a reversible process and grow with
directional asymmetry, the signature of a deterministic or trending regime.

Provenance: github.com/neurotrader888/TimeSeriesReversibility/reversibility.py@3d76b9e (MIT);
adapted: the horizontal visibility graph comes from ``alpha_patterns.visibility`` (the author's
own ``ts_to_vg`` rule) instead of ``ts2vg``, the KL divergence is computed in numpy instead of
``scipy.special.rel_entr``, the embedding dimension is a parameter (upstream fixes 3), NaN for an
undefined value, and rolling variants with the visibility-graph window cap. The measures are
unchanged, including the default-``argsort`` tie order inside the asynchronous index (parity
fixture ``tests/fixtures/neurotrader/reversibility.json``).
"""

from __future__ import annotations

import math

import numpy as np

from alpha_core import DataError
from alpha_patterns.entropy import ordinal_patterns
from alpha_patterns.series import FloatArray
from alpha_patterns.visibility import MAX_VG_LOOKBACK, visibility_graph


def _check(values: FloatArray, minimum: int) -> FloatArray:
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or x.size < minimum:
        raise DataError(f"need a 1-D array of >= {minimum} values, got shape {x.shape}")
    if not bool(np.all(np.isfinite(x))):
        raise DataError("reversibility input contains non-finite values")
    return x


def perm_ts_reversibility(values: FloatArray, *, d: int = 3) -> float:
    """KL divergence of forward vs reversed ordinal-pattern distributions; NaN if any pattern is
    absent in either direction (the divergence is then undefined, as upstream)."""
    x = _check(values, 10)
    fac = math.factorial(d)
    n = x.size - (d - 1)
    forward = ordinal_patterns(x, d)[d - 1 :].astype(np.intp)
    reverse = ordinal_patterns(np.flip(x), d)[d - 1 :].astype(np.intp)
    p_f = np.bincount(forward, minlength=fac) / n
    p_r = np.bincount(reverse, minlength=fac) / n
    if float(min(p_f.min(), p_r.min())) <= 0.0:
        return math.nan
    return float(np.sum(p_f * np.log(p_f / p_r)))


def async_index(first: FloatArray, second: FloatArray) -> float:
    """Share of pairs ordered by ``first`` that ``second`` inverts (not symmetric)."""
    a = np.asarray(first, dtype=np.float64)
    b = np.asarray(second, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 1 or a.size < 2:
        raise DataError("async index needs two 1-D arrays of equal length >= 2")
    order = np.argsort(
        a
    )  # default sort as upstream: tie order among equal degrees is part of the measure
    ranked = b[order]
    inversions = 0
    for i in range(ranked.size):
        inversions += int(np.sum(ranked[i] - ranked[i + 1 :] > 0.0))
    return inversions / (ranked.size * (ranked.size - 1) / 2.0)


def relative_async_index(values: FloatArray) -> float:
    """``-log(min / max)`` of the two asynchronous indices between forward and reversed
    horizontal-visibility out-degrees; NaN when either index is zero."""
    x = _check(values, 3)
    if x.size > MAX_VG_LOOKBACK:
        raise DataError(f"relative async index is quadratic; cap the window at {MAX_VG_LOOKBACK}")
    n = x.size
    hvg_f = visibility_graph(x, horizontal=True)
    hvg_r = visibility_graph(np.flip(x), horizontal=True)
    out_f = np.array([int(hvg_f[i, i:].sum()) for i in range(n)], dtype=np.float64)
    out_r = np.array([int(hvg_r[i, i:].sum()) for i in range(n)], dtype=np.float64)
    f_r = async_index(out_f, out_r)
    r_f = async_index(out_r, out_f)
    lo, hi = min(f_r, r_f), max(f_r, r_f)
    if hi <= 0.0 or lo <= 0.0:
        return math.nan
    return float(-math.log(lo / hi))


def rolling_perm_reversibility(values: FloatArray, *, window: int, d: int = 3) -> FloatArray:
    """``perm_ts_reversibility`` over ``[i-window+1, i]``; NaN before a full window."""
    x = _check(values, 10)
    if window < 10 or window > x.size:
        raise DataError(f"window must be in [10, {x.size}], got {window}")
    out = np.full(x.size, np.nan)
    for i in range(window - 1, x.size):
        out[i] = perm_ts_reversibility(x[i - window + 1 : i + 1], d=d)
    return out


def rolling_relative_async_index(values: FloatArray, *, window: int) -> FloatArray:
    """``relative_async_index`` over ``[i-window+1, i]``; NaN before a full window."""
    x = _check(values, 3)
    if window < 3 or window > min(MAX_VG_LOOKBACK, x.size):
        raise DataError(f"window must be in [3, {min(MAX_VG_LOOKBACK, x.size)}], got {window}")
    out = np.full(x.size, np.nan)
    for i in range(window - 1, x.size):
        out[i] = relative_async_index(x[i - window + 1 : i + 1])
    return out
