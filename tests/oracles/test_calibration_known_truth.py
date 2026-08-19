"""Known-truth calibration oracles (``slow_oracle``): fixed-seed simulations with analytic answers.

Tolerance policy: every rate below is a Bernoulli proportion over ``M`` independent trials at a
known target ``p``; the accepted band is the two-sided normal approximation ``p ± z·sqrt(p(1−p)/M)``
with ``z = 3.89`` (α = 1e-4), so a false alarm on a correct implementation is a 1-in-10,000 event
per assertion at fixed seed (deterministic in practice), while a real miscalibration of a few
percentage points is caught. Bands are computed in-line so the arithmetic is auditable.

Sources: PSR/DSR — Bailey & LdP (2012, 2014); bootstrap CI coverage — Efron & Tibshirani,
*An Introduction to the Bootstrap* (1993) ch. 14; PBO under H0 — Bailey et al. (2016) §5
(uniform OOS rank of the IS-best when all configs are exchangeable); RC/SPA size — White (2000),
Hansen (2005): a level-α test rejects a true null with probability ≤ α.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from alpha_validation.bootstrap import block_bootstrap_ci
from alpha_validation.dsr import deflated_sharpe, probabilistic_sharpe_ratio
from alpha_validation.overfitting import probability_of_backtest_overfitting
from alpha_validation.reality_check import DataSnoopingResult, reality_check, spa_test
from tests.oracles._reference.sampling import noise_matrix
from tests.oracles._reference.tolerances import bernoulli_band as _band

pytestmark = pytest.mark.slow_oracle


def test_psr_is_uniform_under_the_null_of_zero_sharpe() -> None:
    """If true SR = 0 and returns are Gaussian, PSR(0) is a p-value complement ⇒ ~Uniform(0,1).

    Check: P(PSR > 0.95) ≈ 0.05 and P(PSR > 0.5) ≈ 0.5, each within the α=1e-4 band.
    """
    rng = np.random.default_rng(101)
    m, n = 4000, 252
    values = np.array([probabilistic_sharpe_ratio(rng.normal(0.0, 0.01, n)) for _ in range(m)])
    for level, p in ((0.95, 0.05), (0.5, 0.5)):
        rate = float(np.mean(values > level))
        assert abs(rate - p) < _band(p, m), f"P(PSR>{level})={rate:.4f} vs {p} ± {_band(p, m):.4f}"


def test_dsr_controls_the_false_positive_rate_at_the_selection_maximum() -> None:
    """N zero-skill trials; report the best. Deflating by SR0 keeps P(DSR ≥ 0.95) ≤ ~0.05 while
    the undeflated PSR of the same winner is grossly anti-conservative.

    DSR at the max is not exactly uniform (SR0 is an expected-max approximation, not the exact
    max distribution), so we assert (a) DSR FPR ≤ 0.05 + band and (b) PSR FPR ≫ 0.05.
    """
    rng = np.random.default_rng(202)
    m, n, n_trials = 1500, 252, 40
    dsr_hits = psr_hits = 0
    for _ in range(m):
        trials = noise_matrix(rng, n_trials, n)
        srs = trials.mean(axis=1) / trials.std(axis=1, ddof=1)
        best = trials[int(np.argmax(srs))]
        result = deflated_sharpe(best, trial_sharpes=srs)
        dsr_hits += result.dsr >= 0.95
        psr_hits += result.psr >= 0.95
    dsr_fpr, psr_fpr = dsr_hits / m, psr_hits / m
    assert dsr_fpr <= 0.05 + _band(0.05, m), f"DSR false-positive rate {dsr_fpr:.4f}"
    assert psr_fpr > 0.5, f"undeflated PSR should be badly anti-conservative, got {psr_fpr:.3f}"


def test_bca_bootstrap_ci_covers_the_true_mean_at_the_nominal_rate() -> None:
    """IID Gaussian, statistic = mean, 90% BCa interval ⇒ coverage ≈ 0.90.

    Bootstrap intervals are slightly under-covering at n=100 (Efron & Tibshirani §14.3), so the
    band is one-sided-tolerant: coverage within [0.90 − band − 0.02, 0.90 + band].
    """
    rng = np.random.default_rng(303)
    m, n, mu = 800, 100, 0.001
    covered = 0
    for i in range(m):
        x = rng.normal(mu, 0.01, n)
        ci = block_bootstrap_ci(x, np.mean, confidence=0.9, n_resamples=400, mean_block=1.0, seed=i)
        covered += ci.lower <= mu <= ci.upper
    coverage = covered / m
    assert 0.90 - _band(0.9, m) - 0.02 <= coverage <= 0.90 + _band(0.9, m), coverage


def test_pbo_on_exchangeable_noise_is_one_half() -> None:
    """All configs zero-skill ⇒ the IS-best's OOS relative rank is uniform ⇒ E[PBO] = 0.5.

    Averaged over M independent matrices (splits within one matrix are dependent, so the M
    matrix-level PBOs are the independent unit; each is a mean of C(8,4)=70 dependent
    indicators, so its variance is ≤ the Bernoulli 0.25 — the Bernoulli band is conservative).
    """
    rng = np.random.default_rng(404)
    m = 300
    pbos = [
        probability_of_backtest_overfitting(noise_matrix(rng, 160, 10), n_blocks=8).pbo
        for _ in range(m)
    ]
    mean_pbo = float(np.mean(pbos))
    assert abs(mean_pbo - 0.5) < _band(0.5, m), mean_pbo


@pytest.mark.parametrize("test_fn", [reality_check, spa_test])
def test_reality_check_and_spa_hold_their_size_under_the_null(
    test_fn: Callable[..., DataSnoopingResult],
) -> None:
    """S zero-mean strategies, α=0.05 ⇒ rejection rate ≤ 0.05 (RC is conservative by design;
    SPA is closer to nominal). Both must stay at or below α + band."""
    rng = np.random.default_rng(505)
    m, t, s = 400, 200, 8
    rejections = 0
    for i in range(m):
        perf = noise_matrix(rng, t, s)
        result = test_fn(perf, n_resamples=300, mean_block=1.0, alpha=0.05, seed=i)
        rejections += result.passed
    rate = rejections / m
    assert rate <= 0.05 + _band(0.05, m), f"{test_fn.__name__} size {rate:.4f}"
