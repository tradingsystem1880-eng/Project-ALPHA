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
from alpha_validation.metrics import FloatArray
from alpha_validation.montecarlo import NullResult, randomized_price_null


def _momentum(price_returns: FloatArray) -> FloatArray:
    # causal: take yesterday's sign as today's position; profits iff returns are autocorrelated
    position = np.sign(price_returns[:-1])
    return position * price_returns[1:]


def _ar1(n: int, phi: float, *, seed: int) -> FloatArray:
    rng = np.random.default_rng(seed)
    eps = rng.normal(0.0, 0.01, size=n)
    out = np.empty(n, dtype=np.float64)
    out[0] = eps[0]
    for t in range(1, n):
        out[t] = phi * out[t - 1] + eps[t]
    return out


def test_real_momentum_edge_beats_random_charts() -> None:
    # strongly autocorrelated prices -> momentum has a genuine edge -> top of the null distribution
    structured = _ar1(400, phi=0.6, seed=1)
    result = randomized_price_null(structured, _momentum, n_paths=400, threshold=0.95, seed=7)
    assert isinstance(result, NullResult)
    assert result.passed
    assert result.percentile > 0.95  # observed Sharpe in the extreme upper tail of the null
    assert result.p_value < 0.05


def test_no_structure_does_not_pass_the_null() -> None:
    # i.i.d. prices have no momentum to find -> observed is an unremarkable draw from the null
    noise = np.random.default_rng(2).normal(0.0, 0.01, size=400)
    result = randomized_price_null(noise, _momentum, n_paths=400, threshold=0.95, seed=7)
    assert not result.passed
    assert result.percentile < 0.95


def test_percentile_and_pvalue_are_consistent_and_deterministic() -> None:
    structured = _ar1(300, phi=0.4, seed=3)
    a = randomized_price_null(structured, _momentum, n_paths=300, seed=42)
    b = randomized_price_null(structured, _momentum, n_paths=300, seed=42)
    assert (a.observed, a.percentile, a.p_value) == (b.observed, b.percentile, b.p_value)
    assert a.n_paths == 300
    assert a.null.shape == (300,)
    assert a.percentile + a.p_value == pytest.approx(1.0)  # below + at-or-above partition the null


def test_fails_loud_on_bad_input() -> None:
    noise = np.random.default_rng(0).normal(0.0, 0.01, size=50)
    with pytest.raises(DataError):
        randomized_price_null(noise, _momentum, n_paths=0)  # need >= 1 path
    with pytest.raises(DataError):
        randomized_price_null(noise, _momentum, threshold=1.0)  # threshold in (0, 1)
    with pytest.raises(DataError):
        randomized_price_null(np.array([0.01]), _momentum)  # < 2 observations
