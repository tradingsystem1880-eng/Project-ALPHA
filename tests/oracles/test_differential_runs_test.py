"""Differential, metamorphic and calibration oracles for the trade-dependence runs test.

Module under test: ``alpha_validation.trade_dependence``.

Primary source: Wald & Wolfowitz, "On a Test Whether Two Samples are from the Same Population",
*Annals of Mathematical Statistics* 11(2), 1940 — for ``n_pos`` positive and ``n_neg`` negative
signs in exchangeable order the run count ``R`` has ``E[R] = 2 n_pos n_neg / n + 1`` and
``Var[R] = 2 n_pos n_neg (2 n_pos n_neg - n) / (n^2 (n - 1))``, and ``(R - E[R]) / sd`` is
asymptotically N(0, 1). The differential oracle recomputes both moments by exhaustive
enumeration of every arrangement (the exact permutation distribution, no formula involved); the
calibration oracle checks the two-sided p-value against the Bernoulli band under iid signs. A
wrong ``+1``, a population instead of ``n - 1`` denominator, or a run counter that ignores zeros
breaks the relations below. Parity with ``alpha_patterns.runs.runs_z`` is pinned because the
two layers cannot import each other.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest
from scipy.stats import norm

from alpha_core import DataError
from alpha_patterns.runs import runs_z
from alpha_validation.trade_dependence import runs_test, trade_runs_test
from tests.oracles._reference.tolerances import FLOAT64_REL, bernoulli_band

pytestmark = pytest.mark.oracle


def _exact_moments(n_pos: int, n_neg: int) -> tuple[float, float]:
    """Mean and variance of the run count over every arrangement of the signs."""
    n = n_pos + n_neg
    counts: list[int] = []
    for positive_slots in itertools.combinations(range(n), n_pos):
        signs = np.full(n, -1.0)
        signs[list(positive_slots)] = 1.0
        counts.append(1 + int(np.sum(signs[1:] != signs[:-1])))
    arr = np.asarray(counts, dtype=np.float64)
    return float(arr.mean()), float(arr.var())


@pytest.mark.parametrize(("n_pos", "n_neg"), [(3, 4), (5, 5), (2, 6), (7, 3), (4, 4)])
def test_expected_runs_and_variance_match_exhaustive_enumeration(n_pos: int, n_neg: int) -> None:
    n = n_pos + n_neg
    exact_mean, exact_var = _exact_moments(n_pos, n_neg)
    signs = np.concatenate([np.ones(n_pos), -np.ones(n_neg)])
    result = runs_test(signs)
    assert result.expected_runs == pytest.approx(exact_mean, rel=FLOAT64_REL)
    # the code's variance is implied by z: var = ((R - mean) / z)^2 ; R = 2 for this ordering
    implied_var = ((result.n_runs - result.expected_runs) / result.z) ** 2
    assert implied_var == pytest.approx(exact_var, rel=1e-9)
    assert result.n_runs == 2 and result.n_signs == n
    # closed form from the paper
    assert implied_var == pytest.approx(
        2.0 * n_pos * n_neg * (2.0 * n_pos * n_neg - n) / (n**2 * (n - 1)), rel=1e-9
    )


def test_p_value_is_the_two_sided_normal_tail_and_symmetric() -> None:
    rng = np.random.default_rng(11)
    signs = rng.choice([-1.0, 1.0], size=80)
    result = runs_test(signs)
    assert result.p_value == pytest.approx(2.0 * norm.sf(abs(result.z)), rel=FLOAT64_REL)
    assert 0.0 < result.p_value <= 1.0
    # reversing the order or flipping every sign leaves the run structure unchanged
    for twin in (signs[::-1], -signs):
        other = runs_test(twin)
        assert other.z == pytest.approx(result.z, rel=FLOAT64_REL)
        assert other.n_runs == result.n_runs
    # clustered outcomes score negative, alternating outcomes score positive
    assert runs_test(np.repeat([1.0, -1.0], 20)).z < 0.0
    assert runs_test(np.tile([1.0, -1.0], 20)).z > 0.0


def test_parity_with_alpha_patterns_runs_z_including_zero_signs() -> None:
    rng = np.random.default_rng(5)
    for _ in range(50):
        n = int(rng.integers(4, 60))
        signs = rng.choice([-1.0, 0.0, 1.0], size=n, p=[0.45, 0.1, 0.45])
        reference = runs_z(signs)
        if math.isnan(reference):
            with pytest.raises(DataError):
                runs_test(signs)
            assert trade_runs_test(signs) is None
            continue
        assert runs_test(signs).z == pytest.approx(reference, rel=FLOAT64_REL)
        scaled = trade_runs_test(signs * 3.5)
        assert scaled is not None
        assert scaled.z == pytest.approx(reference, rel=FLOAT64_REL)


@pytest.mark.slow_oracle
def test_two_sided_p_value_is_calibrated_under_independent_outcomes() -> None:
    """Under iid signs P(p <= alpha) ~ alpha, up to the discreteness of the run count."""
    rng = np.random.default_rng(404)
    m, n, alpha = 2000, 200, 0.05
    hits = 0
    for _ in range(m):
        pnl = rng.normal(0.0, 1.0, size=n)
        result = trade_runs_test(pnl)
        assert result is not None
        hits += result.p_value <= alpha
    rate = hits / m
    band = bernoulli_band(alpha, m)
    assert abs(rate - alpha) <= band, f"P(p<={alpha})={rate:.4f}, band={band:.4f}"
