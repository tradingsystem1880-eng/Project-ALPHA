"""Metamorphic relations for the Probabilistic / Deflated Sharpe ratio (Bailey & López de Prado).

Primary sources: Bailey & López de Prado, "The Sharpe Ratio Efficient Frontier" (J. Risk 2012)
for PSR, and "The Deflated Sharpe Ratio" (J. Portfolio Mgmt 2014) for SR0 = E[max SR] over N
zero-skill trials. The relations below hold for the exact formulas; an off-by-one in N, a
swapped skew/kurtosis term, or a wrong Euler–Mascheroni weighting breaks at least one.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats

from alpha_validation.dsr import (
    deflated_sharpe,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from tests.oracles._reference.tolerances import MONOTONE_SLACK

pytestmark = pytest.mark.oracle

_EULER_MASCHERONI = 0.5772156649015329
_RNG = np.random.default_rng(7)
_POSITIVE_EDGE = _RNG.normal(0.02, 0.1, size=300)  # a series with a clearly positive Sharpe
_NEGATIVE_EDGE = -_POSITIVE_EDGE


def test_dsr_with_one_trial_equals_psr() -> None:
    """N=1 ⇒ SR0=0 ⇒ DSR == PSR(0): nothing to deflate."""
    solo = deflated_sharpe(_POSITIVE_EDGE)
    explicit = deflated_sharpe(_POSITIVE_EDGE, trial_sharpes=[solo.sharpe])
    assert solo.n_trials == 1 and solo.expected_max_sharpe == 0.0
    assert solo.dsr == pytest.approx(solo.psr)
    assert explicit.dsr == pytest.approx(solo.psr)
    assert solo.psr == pytest.approx(probabilistic_sharpe_ratio(_POSITIVE_EDGE))


def test_dsr_is_monotone_non_increasing_in_the_number_of_trials() -> None:
    """More trials at fixed dispersion ⇒ higher SR0 ⇒ lower DSR."""
    base = deflated_sharpe(_POSITIVE_EDGE).sharpe
    previous_dsr = 1.0
    previous_sr0 = -1.0
    for n_trials in (2, 4, 8, 32, 128, 1024):
        trials = np.linspace(base - 0.05, base + 0.05, n_trials)  # constant-ish variance
        result = deflated_sharpe(_POSITIVE_EDGE, trial_sharpes=trials)
        assert result.n_trials == n_trials
        assert result.expected_max_sharpe > previous_sr0
        assert result.dsr <= previous_dsr + MONOTONE_SLACK
        previous_dsr, previous_sr0 = result.dsr, result.expected_max_sharpe


def test_dsr_is_monotone_non_increasing_in_trial_dispersion() -> None:
    """Wider spread of trial Sharpes ⇒ larger SR0 ⇒ lower DSR (N fixed)."""
    base = deflated_sharpe(_POSITIVE_EDGE).sharpe
    previous_dsr = 1.0
    for spread in (0.001, 0.01, 0.05, 0.1, 0.3):
        trials = np.linspace(base - spread, base + spread, 16)
        result = deflated_sharpe(_POSITIVE_EDGE, trial_sharpes=trials)
        assert result.dsr <= previous_dsr + MONOTONE_SLACK
        previous_dsr = result.dsr


@given(
    st.floats(min_value=1e-6, max_value=4.0),
    st.integers(min_value=2, max_value=100_000),
)
@settings(max_examples=100, deadline=None)
def test_expected_max_sharpe_matches_the_closed_form(variance: float, n_trials: int) -> None:
    """SR0 = sqrt(V)·[(1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e))] transcribed independently."""
    expected = math.sqrt(variance) * (
        (1.0 - _EULER_MASCHERONI) * stats.norm.ppf(1.0 - 1.0 / n_trials)
        + _EULER_MASCHERONI * stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    )
    assert expected_max_sharpe(variance, n_trials) == pytest.approx(expected, rel=1e-12)


@given(st.floats(min_value=1e-6, max_value=4.0), st.floats(min_value=1.0, max_value=100.0))
@settings(max_examples=100, deadline=None)
def test_expected_max_sharpe_scales_with_the_trial_standard_deviation(
    variance: float, k: float
) -> None:
    """SR0(k²·V, N) == k · SR0(V, N)."""
    assert expected_max_sharpe(k * k * variance, 50) == pytest.approx(
        k * expected_max_sharpe(variance, 50), rel=1e-12
    )


def test_expected_max_sharpe_is_zero_when_there_is_nothing_to_deflate() -> None:
    assert expected_max_sharpe(0.5, 1) == 0.0
    assert expected_max_sharpe(0.0, 500) == 0.0
    assert expected_max_sharpe(0.5, 2) > 0.0


def test_psr_is_symmetric_under_return_negation() -> None:
    """PSR(−r; −b) == 1 − PSR(r; b): negating returns mirrors the estimator around the benchmark."""
    for benchmark in (0.0, 0.05, -0.05):
        assert probabilistic_sharpe_ratio(_NEGATIVE_EDGE, benchmark_sr=-benchmark) == pytest.approx(
            1.0 - probabilistic_sharpe_ratio(_POSITIVE_EDGE, benchmark_sr=benchmark), abs=1e-12
        )


def test_psr_is_monotone_decreasing_in_the_benchmark() -> None:
    values = [
        probabilistic_sharpe_ratio(_POSITIVE_EDGE, benchmark_sr=b)
        for b in np.linspace(-0.5, 0.5, 21)
    ]
    assert all(later <= earlier + 1e-15 for earlier, later in zip(values, values[1:], strict=False))


def test_psr_grows_with_sample_length_at_fixed_moments() -> None:
    """Tiling the series k times keeps SR/skew/kurtosis and multiplies n: PSR must rise (SR>0)."""
    values = [probabilistic_sharpe_ratio(np.tile(_POSITIVE_EDGE, k)) for k in (1, 2, 4, 8)]
    assert all(later > earlier for earlier, later in zip(values, values[1:], strict=False))


def test_psr_matches_the_mertens_standard_error_transcribed_independently() -> None:
    """PSR = Φ[(SR−b)·sqrt(n−1) / sqrt(1 − γ₃·SR + (γ₄−1)/4·SR²)] with biased sample moments."""
    r = _POSITIVE_EDGE
    n = r.size
    sr = float(np.mean(r) / np.std(r, ddof=1))
    skew = float(stats.skew(r, bias=True))
    kurt = float(stats.kurtosis(r, fisher=False, bias=True))
    for benchmark in (0.0, 0.1):
        z = (sr - benchmark) * math.sqrt(n - 1) / math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2)
        assert probabilistic_sharpe_ratio(r, benchmark_sr=benchmark) == pytest.approx(
            float(stats.norm.cdf(z)), rel=1e-12
        )
