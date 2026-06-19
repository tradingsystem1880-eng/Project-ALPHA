"""Probabilistic + Deflated Sharpe Ratio (Bailey & López de Prado).

Two overfitting-aware corrections to a bare Sharpe estimate (spec §8; the gauntlet's headline
"is this skill or luck?" statistic):

- **PSR** — the Probabilistic Sharpe Ratio: ``P(true SR > benchmark)`` given the *observed* Sharpe,
  the sample length, and the return distribution's skewness and kurtosis. Fat tails and negative
  skew (typical of trading returns) inflate the standard error of a Sharpe, so a naive Sharpe
  overstates significance; PSR corrects for both and for short samples.
- **DSR** — the Deflated Sharpe Ratio: PSR measured against the *expected maximum* Sharpe a
  zero-skill researcher would attain after trying ``N`` strategy configurations (multiple-testing /
  selection bias). The benchmark is the order-statistic of ``N`` draws from the cross-trial Sharpe
  distribution. With one trial there is nothing to deflate and DSR collapses to ``PSR(0)``.

Everything is computed in *per-observation* (non-annualized) Sharpe units so the numerator,
benchmark, and standard-error terms are consistent; pass ``trial_sharpes`` in the same units.
Pure ``numpy``/``scipy``; fails loud (``DataError``) on degenerate input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

from alpha_core import DataError
from alpha_validation.metrics import FloatArray, FloatSeq

# Euler–Mascheroni constant, for the expected-maximum order statistic of N Gaussian draws.
_EULER_MASCHERONI = 0.5772156649015329


@dataclass(frozen=True)
class DeflatedSharpeResult:
    """The PSR/DSR verdict for one return series against an ``n_trials``-wide search."""

    sharpe: float  # observed per-observation (non-annualized) Sharpe
    psr: float  # P(true SR > 0), skew/kurtosis/length adjusted
    dsr: float  # PSR measured against the expected-max Sharpe over n_trials (deflated)
    expected_max_sharpe: float  # the deflation benchmark SR0 (per-observation units)
    n_trials: int
    threshold: float
    passed: bool  # dsr >= threshold


def _as_returns(returns: FloatSeq) -> FloatArray:
    arr = np.asarray(returns, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise DataError(f"deflated/probabilistic Sharpe needs >= 2 returns, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError("probabilistic Sharpe requires finite returns")
    return arr


def _observed_sharpe(returns: FloatArray) -> float:
    std = float(np.std(returns, ddof=1))
    if std <= 0.0:
        raise DataError("probabilistic Sharpe undefined for a zero-variance return series")
    return float(np.mean(returns)) / std


def probabilistic_sharpe_ratio(returns: FloatSeq, *, benchmark_sr: float = 0.0) -> float:
    """``P(true Sharpe > benchmark_sr)`` from the observed Sharpe, skew, kurtosis, and sample size.

    ``benchmark_sr`` is in per-observation Sharpe units (``0`` tests "is there any edge?"). Uses the
    non-normality-adjusted standard error of the Sharpe estimator (Mertens / Bailey–López de Prado).
    Fails loud (``DataError``) on a degenerate denominator (an ill-conditioned moment combination).
    """
    if not math.isfinite(benchmark_sr):
        raise DataError(f"benchmark_sr must be finite, got {benchmark_sr!r}")
    r = _as_returns(returns)
    n = r.size
    sr = _observed_sharpe(r)
    skew = float(stats.skew(r, bias=True))
    kurt = float(stats.kurtosis(r, fisher=False, bias=True))  # non-excess (3 for a normal)
    variance = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    if variance <= 0.0:
        raise DataError(
            f"probabilistic Sharpe standard error is non-positive (variance={variance})"
        )
    z = (sr - benchmark_sr) * math.sqrt(n - 1) / math.sqrt(variance)
    return float(stats.norm.cdf(z))


def expected_max_sharpe(trial_variance: float, n_trials: int) -> float:
    """Expected maximum Sharpe of ``n_trials`` zero-skill trials (per-observation units).

    ``sqrt(trial_variance) · [(1-γ)·Φ⁻¹(1 - 1/N) + γ·Φ⁻¹(1 - 1/(N·e))]`` (Bailey–López de Prado);
    ``γ`` is Euler–Mascheroni. Returns ``0.0`` when there is nothing to deflate (``n_trials <= 1``
    or no cross-trial dispersion). Fails loud on a negative variance.
    """
    if trial_variance < 0.0:
        raise DataError(f"trial_variance must be >= 0, got {trial_variance}")
    if n_trials <= 1 or trial_variance == 0.0:
        return 0.0
    gamma = _EULER_MASCHERONI
    term = (1.0 - gamma) * float(stats.norm.ppf(1.0 - 1.0 / n_trials)) + gamma * float(
        stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    )
    return math.sqrt(trial_variance) * term


def deflated_sharpe(
    returns: FloatSeq,
    *,
    trial_sharpes: FloatSeq | None = None,
    threshold: float = 0.95,
) -> DeflatedSharpeResult:
    """Deflated Sharpe verdict for ``returns`` against the search that produced it.

    ``trial_sharpes`` are the per-observation Sharpes of *every* configuration tried (including this
    one); their count is the multiple-testing breadth ``N`` and their variance sets the deflation
    benchmark. Omit them (or pass a single value) for a standalone run — then ``N=1``, ``SR0=0``,
    and DSR equals ``PSR(0)``. Passes when ``dsr >= threshold``. Fails loud (``DataError``) on a bad
    threshold or non-finite trial Sharpes.
    """
    if not 0.0 < threshold < 1.0:
        raise DataError(f"threshold must be in (0, 1), got {threshold}")
    r = _as_returns(returns)
    sr = _observed_sharpe(r)
    psr = probabilistic_sharpe_ratio(r, benchmark_sr=0.0)

    if trial_sharpes is None:
        n_trials, sr0 = 1, 0.0
    else:
        trials = np.asarray(trial_sharpes, dtype=np.float64)
        if trials.ndim != 1 or trials.size < 1:
            raise DataError(
                f"trial_sharpes must be a non-empty 1-D array, got shape {trials.shape}"
            )
        if not bool(np.all(np.isfinite(trials))):
            raise DataError("trial_sharpes must all be finite")
        n_trials = int(trials.size)
        trial_variance = float(np.var(trials, ddof=1)) if n_trials >= 2 else 0.0
        sr0 = expected_max_sharpe(trial_variance, n_trials)

    dsr = probabilistic_sharpe_ratio(r, benchmark_sr=sr0)
    return DeflatedSharpeResult(
        sharpe=sr,
        psr=psr,
        dsr=dsr,
        expected_max_sharpe=sr0,
        n_trials=n_trials,
        threshold=threshold,
        passed=dsr >= threshold,
    )
