"""Data-snooping tests: White's Reality Check + Hansen's SPA.

When many strategies are compared and the *best* is reported, its apparent edge is contaminated by
selection — with enough candidates one will look good by chance. These tests give a snooping-robust
p-value for the null "the best strategy has no positive expected performance against the benchmark":

- **White's Reality Check (RC, 2000):** the max mean performance across strategies, with a
  stationary-bootstrap null recentred by each strategy's own mean. Conservative — every candidate,
  however bad, widens the null.
- **Hansen's SPA (2005):** studentizes by each strategy's volatility and uses the *consistent*
  recentring that drops hopeless candidates from the null, so genuinely poor strategies no longer
  mask a good one. More powerful than RC; the recommended test.

Both consume a ``(T observations × S strategies)`` performance matrix — each column a strategy's
per-observation performance relative to the benchmark (use raw returns to test "beats zero"). They
reuse the project's stationary bootstrap, so the null shares its block-dependence handling and
seeding. A low p-value means the best strategy survives the snooping correction (gate passes).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_validation.bootstrap import stationary_bootstrap_indices
from alpha_validation.metrics import FloatArray


@dataclass(frozen=True)
class DataSnoopingResult:
    """A snooping-robust verdict (shared by Reality Check and SPA)."""

    statistic: float  # the observed max (studentized for SPA) performance
    p_value: float  # P(null max >= observed) — low ⇒ the best strategy is real
    n_strategies: int
    n_resamples: int
    alpha: float  # significance level for the pass/fail call
    passed: bool  # p_value <= alpha


def _bootstrap_means(
    m: FloatArray, *, n_resamples: int, mean_block: float, seed: int | None
) -> FloatArray:
    """``(n_resamples × S)`` matrix of stationary-bootstrap column means of ``m`` (``T × S``)."""
    n = m.shape[0]
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(n, mean_block=mean_block, n_resamples=n_resamples, rng=rng)
    means = np.empty((n_resamples, m.shape[1]), dtype=np.float64)
    for b in range(n_resamples):
        means[b] = m[idx[b]].mean(axis=0)
    return means


def _validate(m: FloatArray, n_resamples: int, mean_block: float, alpha: float) -> None:
    if m.ndim != 2 or m.shape[1] < 1:
        raise DataError(f"perf_matrix must be 2-D (T × S) with S >= 1, got {m.shape}")
    if m.shape[0] < 2:
        raise DataError(f"perf_matrix needs >= 2 observations, got {m.shape[0]}")
    if not bool(np.all(np.isfinite(m))):
        raise DataError("perf_matrix must be finite")
    if n_resamples < 1:
        raise DataError(f"n_resamples must be >= 1, got {n_resamples}")
    if not math.isfinite(mean_block) or mean_block <= 0.0:
        raise DataError(f"mean_block must be finite > 0, got {mean_block!r}")
    if not 0.0 < alpha < 1.0:
        raise DataError(f"alpha must be in (0, 1), got {alpha}")


def reality_check(
    perf_matrix: FloatArray,
    *,
    n_resamples: int = 2000,
    mean_block: float = 5.0,
    alpha: float = 0.05,
    seed: int | None = None,
) -> DataSnoopingResult:
    """White's Reality Check p-value for the best of ``S`` strategies (spec §8)."""
    m = np.asarray(perf_matrix, dtype=np.float64)
    _validate(m, n_resamples, mean_block, alpha)
    n = m.shape[0]
    sqrt_n = math.sqrt(n)
    f_bar = m.mean(axis=0)
    observed = float(np.max(sqrt_n * f_bar))

    boot = _bootstrap_means(m, n_resamples=n_resamples, mean_block=mean_block, seed=seed)
    null_max = np.max(sqrt_n * (boot - f_bar), axis=1)  # recentre each column by its own mean
    p_value = (1 + int(np.sum(null_max >= observed))) / (1 + n_resamples)
    return DataSnoopingResult(
        statistic=observed,
        p_value=p_value,
        n_strategies=int(m.shape[1]),
        n_resamples=n_resamples,
        alpha=alpha,
        passed=p_value <= alpha,
    )


def spa_test(
    perf_matrix: FloatArray,
    *,
    n_resamples: int = 2000,
    mean_block: float = 5.0,
    alpha: float = 0.05,
    seed: int | None = None,
) -> DataSnoopingResult:
    """Hansen's SPA (consistent) p-value for the best of ``S`` strategies (spec §8)."""
    m = np.asarray(perf_matrix, dtype=np.float64)
    _validate(m, n_resamples, mean_block, alpha)
    n = m.shape[0]
    sqrt_n = math.sqrt(n)
    f_bar = m.mean(axis=0)
    omega = np.std(m, axis=0, ddof=1)
    safe = omega > 0.0  # zero-variance columns carry no studentized signal

    t_stats = np.zeros_like(f_bar)
    t_stats[safe] = sqrt_n * f_bar[safe] / omega[safe]
    observed = max(0.0, float(np.max(t_stats)))

    # consistent recentring: keep a strategy's mean only if it is not hopelessly below zero
    log_log = 2.0 * math.log(math.log(n)) if math.log(n) > 1.0 else 0.0
    keep_threshold = np.where(safe, omega / sqrt_n * math.sqrt(max(log_log, 0.0)), np.inf)
    g = np.where(f_bar >= -keep_threshold, f_bar, 0.0)

    boot = _bootstrap_means(m, n_resamples=n_resamples, mean_block=mean_block, seed=seed)
    z = np.zeros_like(boot)
    z[:, safe] = sqrt_n * (boot[:, safe] - g[safe]) / omega[safe]
    null_max = np.maximum(0.0, np.max(z, axis=1))
    p_value = (1 + int(np.sum(null_max >= observed))) / (1 + n_resamples)
    return DataSnoopingResult(
        statistic=observed,
        p_value=p_value,
        n_strategies=int(m.shape[1]),
        n_resamples=n_resamples,
        alpha=alpha,
        passed=p_value <= alpha,
    )
