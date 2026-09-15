"""Retracement-ratio density: where consecutive swing heights cluster in ratio space.

Provenance: github.com/neurotrader888/TechnicalAnalysisAutomation/retracement_ratios.py @ da99c20
(MIT). Adapted: takes the extreme prices as an array (``alpha_patterns.directional_change``
supplies them upstream of this layer), returns the density and its prominent peaks instead of
drawing them, and fails loud on zero-height segments, degenerate samples, and a grid that misses
the sample entirely. The density is a Gaussian kernel estimate (Silverman 1986 §2.4) of the *log*
ratios with SciPy's scalar-bandwidth convention (kernel width = ``bandwidth`` × sample standard
deviation, ddof=1; Scott 1992), on upstream's grid ``arange(-3, 3, 0.001)`` by default.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.signal import find_peaks
from scipy.stats import gaussian_kde

from alpha_core import DataError

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class RetracementDensity:
    log_ratio_grid: FloatArray
    ratio_grid: FloatArray  # exp(log_ratio_grid)
    density: FloatArray  # of the log ratio, on log_ratio_grid
    peak_ratios: FloatArray  # ratio at each prominent mode, highest density first


def retracement_ratios(extreme_prices: npt.ArrayLike) -> FloatArray:
    """Height of each swing segment divided by the previous segment's height.

    ``extreme_prices`` alternate highs and lows; segment ``i`` runs from extreme ``i`` to
    ``i + 1``. A zero-height segment makes the next ratio undefined and is a ``DataError``.
    """
    prices = np.asarray(extreme_prices, dtype=np.float64)
    if prices.ndim != 1 or not np.all(np.isfinite(prices)):
        raise DataError("extreme prices must be a finite one-dimensional array")
    if prices.size < 3:
        raise DataError("retracement ratios need at least three extremes")
    heights = np.abs(np.diff(prices))
    zero = np.flatnonzero(heights == 0.0)
    if zero.size:
        raise DataError(f"segment {int(zero[0])} has zero height; ratios are undefined")
    return np.asarray(heights[1:] / heights[:-1], dtype=np.float64)


def retracement_density(
    ratios: npt.ArrayLike,
    *,
    bandwidth: float = 0.01,
    log_grid: tuple[float, float, float] = (-3.0, 3.0, 0.001),
    min_prominence: float = 0.05,
) -> RetracementDensity:
    """Gaussian KDE of log retracement ratios and its modes.

    ``bandwidth`` is SciPy's scalar ``bw_method`` (kernel width as a multiple of the sample
    standard deviation of the log ratios). ``log_grid`` is ``(start, stop, step)`` in log-ratio
    space. Peaks are local maxima whose prominence is at least ``min_prominence`` times the
    maximum density, returned as ratios ordered by descending density.
    """
    values = np.asarray(ratios, dtype=np.float64)
    if values.ndim != 1 or values.size < 2:
        raise DataError("retracement density needs at least two ratios")
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        raise DataError("retracement ratios must be finite and positive")
    if not np.isfinite(bandwidth) or bandwidth <= 0.0:
        raise DataError(f"bandwidth must be positive, got {bandwidth}")
    start, stop, step = log_grid
    if not np.all(np.isfinite(log_grid)) or not (start < stop) or step <= 0.0:
        raise DataError("log_grid must satisfy start < stop with a positive step")
    if not (0.0 < min_prominence <= 1.0):
        raise DataError(f"min_prominence must be in (0, 1], got {min_prominence}")
    log_ratios = np.log(values)
    if float(np.std(log_ratios)) == 0.0:
        raise DataError("retracement ratios are all identical; no density")
    grid = np.arange(start, stop, step, dtype=np.float64)
    density = np.asarray(gaussian_kde(log_ratios, bw_method=bandwidth)(grid), dtype=np.float64)
    if float(density.max()) <= 0.0:
        raise DataError("log_grid does not cover the retracement ratios; the density is zero")
    peaks, _ = find_peaks(density, prominence=min_prominence * float(density.max()))
    order = np.argsort(-density[peaks], kind="stable")
    return RetracementDensity(
        log_ratio_grid=grid,
        ratio_grid=np.exp(grid),
        density=density,
        peak_ratios=np.exp(grid[peaks[order]]),
    )


__all__ = ["RetracementDensity", "retracement_density", "retracement_ratios"]
