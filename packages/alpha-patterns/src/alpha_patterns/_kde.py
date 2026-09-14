"""Weighted Gaussian kernel density and prominence-based peak finding, in numpy.

``alpha_patterns`` is numpy-only by contract, so the two SciPy calls the market-profile study
leans on are re-implemented here with SciPy's exact conventions (``gaussian_kde`` with a scalar
``bw_method`` and ``aweights``-style covariance; ``find_peaks`` plateau midpoints and prominence
bases). The unit tests are differential against SciPy.
"""

from __future__ import annotations

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import FloatArray, IntArray


def weighted_gaussian_kde(
    samples: FloatArray, grid: FloatArray, *, bandwidth_factor: float, weights: FloatArray
) -> FloatArray:
    """Density of ``samples`` on ``grid`` with SciPy's scalar-``bw_method`` semantics.

    The kernel width is ``bandwidth_factor * sqrt(weighted variance)`` where the variance uses the
    ``numpy.cov(aweights=...)`` unbiased correction ``1 / (1 - sum(w^2))`` on normalised weights.
    """
    x = np.asarray(samples, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    g = np.asarray(grid, dtype=np.float64)
    if x.ndim != 1 or x.size < 2:
        raise DataError(f"kde needs >= 2 samples, got shape {x.shape}")
    if w.shape != x.shape:
        raise DataError(f"kde weights must match samples, got {w.shape} vs {x.shape}")
    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(w)) and np.all(np.isfinite(g))):
        raise DataError("kde inputs contain non-finite values")
    if bool(np.any(w < 0.0)) or float(w.sum()) <= 0.0:
        raise DataError("kde weights must be non-negative with a positive sum")
    if not bandwidth_factor > 0.0:
        raise DataError(f"kde bandwidth_factor must be > 0, got {bandwidth_factor}")
    w = w / w.sum()
    mean = float(np.sum(w * x))
    denom = 1.0 - float(np.sum(w * w))
    if denom <= 0.0:
        raise DataError("kde weights are concentrated on one sample; variance is undefined")
    var = float(np.sum(w * (x - mean) ** 2)) / denom
    if var <= 0.0:
        raise DataError("kde samples have zero weighted variance")
    h2 = var * bandwidth_factor**2
    z = (g[:, None] - x[None, :]) ** 2 / h2
    density = (w[None, :] * np.exp(-0.5 * z)).sum(axis=1) / np.sqrt(2.0 * np.pi * h2)
    return np.asarray(density, dtype=np.float64)


def _local_maxima(y: FloatArray) -> IntArray:
    """Strict local maxima; a flat top reports its midpoint (SciPy ``_local_maxima_1d``)."""
    peaks: list[int] = []
    n = y.size
    i = 1
    while i < n - 1:
        if y[i - 1] < y[i]:
            ahead = i + 1
            while ahead < n - 1 and y[ahead] == y[i]:
                ahead += 1
            if y[ahead] < y[i]:
                peaks.append((i + ahead - 1) // 2)
                i = ahead
        i += 1
    return np.asarray(peaks, dtype=np.intp)


def _prominence(y: FloatArray, peak: int) -> float:
    left_min = right_min = float(y[peak])
    i = peak
    while i >= 0 and y[i] <= y[peak]:  # SciPy walks through the edge sample too
        left_min = min(left_min, float(y[i]))
        i -= 1
    i = peak
    while i < y.size and y[i] <= y[peak]:
        right_min = min(right_min, float(y[i]))
        i += 1
    return float(y[peak]) - max(left_min, right_min)


def prominent_peaks(y: FloatArray, *, min_prominence: float) -> IntArray:
    """Indices of local maxima whose prominence is at least ``min_prominence``."""
    arr = np.asarray(y, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 3:
        raise DataError(f"peak finding needs a 1-D array of >= 3 values, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError("peak finding input contains non-finite values")
    peaks = _local_maxima(arr)
    keep = [int(p) for p in peaks if _prominence(arr, int(p)) >= min_prominence]
    return np.asarray(keep, dtype=np.intp)
