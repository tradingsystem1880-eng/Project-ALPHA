"""Shared fail-loud array coercion for the pure D1 analysis-family modules."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from alpha_core import DataError


def finite_array(values: Sequence[float], label: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise DataError(f"{label} must be one-dimensional")
    if not np.all(np.isfinite(array)):
        raise DataError(f"{label} must contain only finite values")
    return array


def average_ranks(array: np.ndarray) -> np.ndarray:
    """Average (tie-sharing) 1-based ranks, deterministic for equal values."""
    order = np.argsort(array, kind="stable")
    ranks = np.empty(array.size, dtype=float)
    sorted_values = array[order]
    start = 0
    while start < array.size:
        stop = start
        while stop + 1 < array.size and sorted_values[stop + 1] == sorted_values[start]:
            stop += 1
        ranks[order[start : stop + 1]] = (start + stop) / 2.0 + 1.0
        start = stop + 1
    return ranks


def pearson_or_none(x: np.ndarray, y: np.ndarray) -> float | None:
    """Pearson correlation clamped to [-1, 1]; None (never fabricated) when degenerate."""
    x_std = float(np.std(x))
    y_std = float(np.std(y))
    if x_std == 0.0 or y_std == 0.0:
        return None
    value = float(np.mean((x - np.mean(x)) * (y - np.mean(y))) / (x_std * y_std))
    return max(-1.0, min(1.0, value))
