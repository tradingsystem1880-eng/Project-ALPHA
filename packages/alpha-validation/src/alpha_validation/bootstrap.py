"""Block-bootstrap BCa confidence intervals for return statistics (spec §8 gate 4).

A bare point estimate of Sharpe or CAGR is not reportable — the gate requires an interval. Daily
returns are serially dependent, so the i.i.d. bootstrap understates uncertainty; we resample with
the Politis-Romano *stationary bootstrap* (random geometric-length blocks with circular wrap),
which preserves short-range dependence, then correct the percentile interval for median bias and
skew with the BCa (bias-corrected and accelerated) adjustment of Efron.

The acceleration is estimated by the leave-one-out jackknife. On serially dependent data this is an
approximation (a block jackknife would be more faithful); it is a documented v1 choice.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy import stats

from alpha_core import DataError
from alpha_validation.metrics import FloatArray, FloatSeq

IndexArray = npt.NDArray[np.intp]
Statistic = Callable[[FloatArray], float]


@dataclass(frozen=True)
class ConfidenceInterval:
    """A two-sided confidence interval around a point estimate."""

    point: float
    lower: float
    upper: float
    confidence: float


def stationary_bootstrap_indices(
    n: int, *, mean_block: float, n_resamples: int, rng: np.random.Generator
) -> IndexArray:
    """``(n_resamples, n)`` matrix of resampling indices for the stationary bootstrap.

    Each step either continues the current block (advance one index, wrapping circularly) or, with
    probability ``1 / mean_block``, restarts at a fresh uniform index — giving geometric block
    lengths of mean ``mean_block``. Fails loud (``DataError``) on ``n < 2``,
    non-positive ``n_resamples``, or non-positive / non-finite ``mean_block``.
    """
    if n < 2:
        raise DataError(f"stationary_bootstrap_indices needs n >= 2, got {n}")
    if n_resamples < 1:
        raise DataError(f"n_resamples must be >= 1, got {n_resamples}")
    if not np.isfinite(mean_block) or mean_block <= 0.0:
        raise DataError(f"mean_block must be finite > 0, got {mean_block!r}")
    restart_prob = 1.0 / mean_block
    restart = rng.random((n_resamples, n)) < restart_prob
    fresh = rng.integers(0, n, size=(n_resamples, n))
    idx = np.empty((n_resamples, n), dtype=np.intp)
    idx[:, 0] = fresh[:, 0]  # every row begins with a fresh draw
    for t in range(1, n):
        continued = (idx[:, t - 1] + 1) % n
        idx[:, t] = np.where(restart[:, t], fresh[:, t], continued)
    return idx


def _resolve_mean_block(mean_block: float | None, n: int) -> float:
    # n**(1/3) is the textbook growth rate for block length; a data-driven (Politis-White) choice
    # is a later refinement.
    return float(max(1.0, round(n ** (1.0 / 3.0)))) if mean_block is None else mean_block


def _jackknife_acceleration(data: FloatArray, statistic: Statistic) -> float:
    n = data.size
    theta_loo = np.array([statistic(np.delete(data, i)) for i in range(n)], dtype=np.float64)
    centered = theta_loo.mean() - theta_loo
    denom = 6.0 * float(np.sum(centered**2)) ** 1.5
    if denom == 0.0:
        return 0.0  # no jackknife variation -> no skew correction
    return float(np.sum(centered**3) / denom)


def block_bootstrap_ci(
    data: FloatSeq,
    statistic: Statistic,
    *,
    confidence: float = 0.95,
    n_resamples: int = 2000,
    mean_block: float | None = None,
    seed: int | None = None,
) -> ConfidenceInterval:
    """BCa confidence interval for ``statistic`` of a serially-dependent return series.

    Resamples ``data`` with the stationary bootstrap, then maps the requested ``confidence`` onto
    bias-corrected, acceleration-adjusted percentiles of the bootstrap distribution. ``statistic``
    must be defined on every resample (e.g. ``sharpe_ratio`` requires non-zero variance). Fails loud
    (``DataError``) on ``confidence`` outside ``(0, 1)`` or fewer than 2 observations.
    """
    if not 0.0 < confidence < 1.0:
        raise DataError(f"confidence must be in (0, 1), got {confidence}")
    x = np.asarray(data, dtype=np.float64)
    if x.ndim != 1 or x.size < 2:
        raise DataError(f"block_bootstrap_ci needs >= 2 observations, got shape {x.shape}")
    if not bool(np.all(np.isfinite(x))):
        raise DataError("block_bootstrap_ci requires finite observations")

    point = statistic(x)
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(
        x.size, mean_block=_resolve_mean_block(mean_block, x.size), n_resamples=n_resamples, rng=rng
    )
    replicates = np.array([statistic(x[row]) for row in idx], dtype=np.float64)

    # bias correction z0: how far the bootstrap median sits from the point estimate, in z-units.
    below = float(np.mean(replicates < point))
    below = min(max(below, 1.0 / (2 * n_resamples)), 1.0 - 1.0 / (2 * n_resamples))  # avoid +/-inf
    z0 = float(stats.norm.ppf(below))
    accel = _jackknife_acceleration(x, statistic)

    alpha = 1.0 - confidence
    lower = _bca_percentile(replicates, z0, accel, alpha / 2.0)
    upper = _bca_percentile(replicates, z0, accel, 1.0 - alpha / 2.0)
    return ConfidenceInterval(point=point, lower=lower, upper=upper, confidence=confidence)


def _bca_percentile(replicates: FloatArray, z0: float, accel: float, prob: float) -> float:
    z = z0 + float(stats.norm.ppf(prob))
    denom = 1.0 - accel * z
    if denom <= 0.0:
        # extreme acceleration would push the adjusted percentile past +/-inf; fail loud rather
        # than silently collapse the interval to a raw min/max replicate.
        raise DataError(f"BCa adjustment unstable: 1 - a*z = {denom:.3g} <= 0 (a={accel:.3g})")
    adjusted = float(stats.norm.cdf(z0 + z / denom))
    return float(np.quantile(replicates, adjusted))
