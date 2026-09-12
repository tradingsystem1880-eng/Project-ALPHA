"""Perceptually important points (PIPs): the few bars that best describe a window's shape.

Starting from the two endpoints, each step adds the interior bar farthest from the polyline through
the points chosen so far, so ``n_pips`` points summarise a window the way a chartist's eye would.
``pip_windows`` applies this to trailing windows and z-scores each result, which is the input the
research-layer pattern miner clusters. A window ending at ``end_index`` reads bars
``[end_index - lookback + 1, end_index]`` and nothing after it.

Provenance: github.com/neurotrader888/TechnicalAnalysisAutomation/perceptually_important.py
@da99c20bf3d977b639451258cd6cfca9baa1dcc3 (MIT) and the window extraction of
``pip_pattern_miner.py``; adapted: typed arrays and a named ``distance`` instead of an integer code,
fail-loud validation, and a documented deviation: when every interior bar lies exactly on the
current polyline the earliest interior bar is taken (upstream inserts index ``-1``). The three
distance measures are unchanged (parity fixture ``tests/fixtures/neurotrader/pips.json``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import FloatArray, IntArray

PipDistance = Literal["euclidean", "perpendicular", "vertical"]

# Chung, Fu, Luk & Ng (2001), "Flexible time series pattern matching based on perceptually
# important points" — the three point-to-segment distances used to rank candidates.


def _check_values(values: FloatArray, name: str) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise DataError(f"{name} needs a 1-D array of >= 2 values, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{name} contains non-finite values")
    return arr


def find_pips(
    values: FloatArray, n_pips: int, *, distance: PipDistance = "perpendicular"
) -> tuple[IntArray, FloatArray]:
    """``(indices, prices)`` of the ``n_pips`` most important points, in index order."""
    data = _check_values(values, "pip values")
    if n_pips < 2:
        raise DataError(f"n_pips must be >= 2, got {n_pips}")
    if n_pips > data.size:
        raise DataError(f"n_pips {n_pips} exceeds the {data.size} available bars")
    if distance not in ("euclidean", "perpendicular", "vertical"):
        raise DataError(f"unknown pip distance {distance!r}")

    pips_x: list[int] = [0, data.size - 1]
    pips_y: list[float] = [float(data[0]), float(data[-1])]
    for curr_point in range(2, n_pips):
        md = -1.0  # deviation from upstream (0.0): a collinear interior bar still gets chosen
        md_i = -1
        insert_index = -1
        for k in range(curr_point - 1):
            left, right = k, k + 1
            x0, x1 = pips_x[left], pips_x[right]
            y0, y1 = pips_y[left], pips_y[right]
            slope = (y1 - y0) / (x1 - x0)
            intercept = y0 - x0 * slope
            for i in range(x0 + 1, x1):
                if distance == "euclidean":
                    d = ((x0 - i) ** 2 + (y0 - data[i]) ** 2) ** 0.5
                    d += ((x1 - i) ** 2 + (y1 - data[i]) ** 2) ** 0.5
                elif distance == "perpendicular":
                    d = abs((slope * i + intercept) - data[i]) / (slope**2 + 1) ** 0.5
                else:
                    d = abs((slope * i + intercept) - data[i])
                if d > md:
                    md, md_i, insert_index = float(d), i, right
        pips_x.insert(insert_index, md_i)
        pips_y.insert(insert_index, float(data[md_i]))
    return np.asarray(pips_x, dtype=np.intp), np.asarray(pips_y, dtype=np.float64)


@dataclass(frozen=True)
class PipWindows:
    """Z-scored PIP prices of every trailing window, one row per window end."""

    matrix: FloatArray  # shape (n_windows, n_pips)
    end_index: IntArray  # the last bar each row read; row i is knowable at end_index[i]
    lookback: int
    n_pips: int


def pip_windows(
    values: FloatArray,
    *,
    lookback: int,
    n_pips: int,
    stride: int = 1,
    distance: PipDistance = "perpendicular",
) -> PipWindows:
    """PIPs of each closed trailing window of ``lookback`` bars, z-scored within the window.

    A flat window (zero price dispersion at the chosen points) cannot be normalised and is a
    ``DataError`` rather than a row of zeros.
    """
    data = _check_values(values, "pip window values")
    if lookback < 2 or lookback > data.size:
        raise DataError(f"lookback must be in [2, {data.size}], got {lookback}")
    if stride < 1:
        raise DataError(f"stride must be >= 1, got {stride}")
    ends = np.arange(lookback - 1, data.size, stride, dtype=np.intp)
    rows = np.empty((ends.size, n_pips), dtype=np.float64)
    for r, end in enumerate(ends):
        _, prices = find_pips(data[end - lookback + 1 : end + 1], n_pips, distance=distance)
        spread = float(np.std(prices))
        if spread == 0.0:
            raise DataError(f"pip window ending at bar {int(end)} is flat and cannot be z-scored")
        rows[r] = (prices - float(np.mean(prices))) / spread
    return PipWindows(matrix=rows, end_index=ends, lookback=lookback, n_pips=n_pips)
