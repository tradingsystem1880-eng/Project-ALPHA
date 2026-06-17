"""Randomized-price null (spec §8 gate 3): a real edge must beat the same strategy on random charts.

The gate runs the *same* strategy on price paths whose exploitable structure has been destroyed
(an i.i.d. bootstrap of the price returns) and asks whether the observed performance sits in the
extreme tail of that null distribution. A toy causal momentum strategy stands in for the engine
here; the CLI injects the real backtest in Phase 5.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.montecarlo import NullResult, randomized_price_null
from tests.fixtures.validation_fixtures import ar1_returns, causal_momentum


def test_real_momentum_edge_beats_random_charts() -> None:
    # strongly autocorrelated prices -> momentum has a genuine edge -> top of the null distribution
    structured = ar1_returns(400, phi=0.6, seed=1)
    result = randomized_price_null(structured, causal_momentum, n_paths=400, threshold=0.95, seed=7)
    assert isinstance(result, NullResult)
    assert result.passed
    assert result.percentile > 0.95  # observed Sharpe in the extreme upper tail of the null
    assert result.p_value < 0.05


def test_percentile_and_pvalue_bounds_and_determinism() -> None:
    structured = ar1_returns(300, phi=0.4, seed=3)
    a = randomized_price_null(structured, causal_momentum, n_paths=300, seed=42)
    b = randomized_price_null(structured, causal_momentum, n_paths=300, seed=42)
    assert (a.observed, a.percentile, a.p_value) == (b.observed, b.percentile, b.p_value)  # seeded
    assert a.n_paths == 300 and a.null.shape == (300,)
    assert 0.0 <= a.percentile <= 1.0
    assert 0.0 < a.p_value <= 1.0  # (1 + #>=) / (1 + B): strictly positive, never exactly 0
    assert a.percentile > 0.5 and a.p_value < 0.5  # a genuine edge ranks high and is significant


def test_block_bootstrap_null_is_a_valid_alternative() -> None:
    # block > 1 retains short-range dependence (a more conservative null) and still yields a result
    structured = ar1_returns(300, phi=0.5, seed=8)
    result = randomized_price_null(structured, causal_momentum, n_paths=300, block=5.0, seed=2)
    assert result.null.shape == (300,)
    assert 0.0 <= result.percentile <= 1.0
    assert bool(np.all(np.isfinite(result.null)))


def test_non_finite_statistic_on_a_path_fails_loud() -> None:
    # a statistic that is non-finite on resampled paths must fail loud, not silently rank NaNs
    noise = np.random.default_rng(0).normal(0.0, 0.01, size=50)
    with pytest.raises(DataError):
        randomized_price_null(
            noise, causal_momentum, statistic=lambda r: float("nan"), n_paths=20, seed=1
        )


def test_fails_loud_on_bad_input() -> None:
    noise = np.random.default_rng(0).normal(0.0, 0.01, size=50)
    with pytest.raises(DataError):
        randomized_price_null(noise, causal_momentum, n_paths=0)  # need >= 1 path
    with pytest.raises(DataError):
        randomized_price_null(noise, causal_momentum, threshold=1.0)  # threshold in (0, 1)
    with pytest.raises(DataError):
        randomized_price_null(np.array([0.01]), causal_momentum)  # < 2 observations
