"""Calibration and metamorphic oracles for the bar-permutation Monte Carlo test.

Modules under test: ``alpha_validation.mcpt`` and ``alpha_validation.metrics.profit_factor``.

Primary sources: Masters, *Testing and Tuning Market Trading Systems* (Apress 2018), ch. 7 — the
MCPT p-value is the fraction of permutations whose statistic is at least the observed one, with
the observed series counted as one of the permutations; Davison & Hinkley, *Bootstrap Methods
and their Application* (1997) §4.2.5 — ``(1 + #{T* >= t}) / (1 + R)`` is the valid Monte Carlo
p-value, never exactly zero; under the null that the observed series is exchangeable with its
permutations the p-value is (sub-)uniform, so ``P(p <= alpha) <= alpha`` up to the discreteness of
``R + 1`` levels. The tolerance policy is the ``bernoulli_band`` used across the calibration
suite. Profit factor is gross profit over gross loss (the ratio upstream and the native tear
sheet both compute); it is undefined without a loss.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.bar_permutation import OHLC
from alpha_validation.mcpt import permutation_test, permutation_test_multi
from alpha_validation.metrics import profit_factor
from tests.oracles._reference.tolerances import FLOAT64_REL, bernoulli_band

pytestmark = pytest.mark.oracle


def _random_walk_bars(rng: np.random.Generator, n: int) -> OHLC:
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, size=n)))
    open_ = np.concatenate([[100.0], close[:-1] * np.exp(rng.normal(0.0, 0.004, size=n - 1))])
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0.0, 0.008, size=n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0.0, 0.008, size=n)))
    return OHLC(open=open_, high=high, low=low, close=close)


def _breakout_profit_factor(bars: OHLC, lookback: int = 12) -> float:
    """Upstream's Donchian demo: long above the prior rolling max, short below the min."""
    close = bars.close
    n = close.size
    signal = np.zeros(n)
    state = 0.0
    for i in range(lookback, n):
        window = close[i - lookback : i]
        if close[i] > window.max():
            state = 1.0
        elif close[i] < window.min():
            state = -1.0
        signal[i] = state
    rets = np.diff(np.log(close))
    pnl = signal[:-1] * rets
    value = profit_factor(pnl)
    return 1.0 if value is None else value  # no losing bar: score as break-even, never inf


# ---------------------------------------------------------------- metamorphic


def test_p_value_and_percentile_follow_davison_hinkley_on_the_null_draws() -> None:
    bars = _random_walk_bars(np.random.default_rng(1), 160)
    result = permutation_test(bars, _breakout_profit_factor, n_perms=49, seed=3)
    at_least = int(np.sum(result.null >= result.observed))
    assert result.p_value == pytest.approx((1 + at_least) / (1 + 49), rel=FLOAT64_REL)
    assert result.percentile == pytest.approx(float(np.mean(result.null < result.observed)))
    assert result.n_paths == 49 and result.null.shape == (49,)
    assert result.p_value > 0.0
    assert result.passed == (result.percentile >= result.threshold)


def test_a_permutation_invariant_score_gives_a_degenerate_null_and_p_value_one() -> None:
    bars = _random_walk_bars(np.random.default_rng(2), 80)
    # the end-to-end log return is preserved by construction (up to rounding)
    end_return = permutation_test(
        bars, lambda b: float(np.log(b.close[-1] / b.close[0])), n_perms=20, seed=0
    )
    np.testing.assert_allclose(end_return.null, end_return.observed, rtol=1e-9)
    # an exactly invariant statistic ties every permutation: p = (1 + N) / (1 + N) = 1
    constant = permutation_test(bars, lambda b: float(b.close.size), n_perms=20, seed=0)
    assert constant.p_value == pytest.approx(1.0)
    assert constant.percentile == 0.0 and not constant.passed


def test_seed_determinism_and_multi_market_agreement() -> None:
    bars = _random_walk_bars(np.random.default_rng(4), 120)
    other = _random_walk_bars(np.random.default_rng(5), 120)
    a = permutation_test(bars, _breakout_profit_factor, n_perms=15, start_index=10, seed=8)
    b = permutation_test(bars, _breakout_profit_factor, n_perms=15, start_index=10, seed=8)
    assert np.array_equal(a.null, b.null) and a.p_value == b.p_value
    joint = permutation_test_multi(
        [bars, other],
        lambda markets: _breakout_profit_factor(markets[0]),
        n_perms=15,
        start_index=10,
        seed=8,
    )
    np.testing.assert_allclose(joint.null, a.null, rtol=1e-9)


def test_profit_factor_is_gross_profit_over_gross_loss_and_undefined_without_a_loss() -> None:
    returns = np.array([0.02, -0.01, 0.03, -0.02, 0.0, 0.01])
    assert profit_factor(returns) == pytest.approx(0.06 / 0.03, rel=FLOAT64_REL)
    assert profit_factor(np.array([0.01, 0.0, 0.02])) is None
    assert profit_factor(np.array([-0.01, -0.02])) == 0.0
    assert profit_factor(returns * 3.0) == pytest.approx(profit_factor(returns) or 0.0)
    with pytest.raises(DataError):
        profit_factor(np.array([]))
    with pytest.raises(DataError):
        profit_factor(np.array([0.1, np.nan]))


# ---------------------------------------------------------------- calibration


@pytest.mark.slow_oracle
def test_p_value_is_calibrated_under_the_exchangeable_null() -> None:
    """Random-walk bars are exchangeable with their permutations, so P(p <= alpha) ~ alpha."""
    rng = np.random.default_rng(303)
    m, n_perms, alpha = 400, 39, 0.10
    hits = 0
    for _ in range(m):
        bars = _random_walk_bars(rng, 90)
        result = permutation_test(
            bars, _breakout_profit_factor, n_perms=n_perms, seed=int(rng.integers(2**31))
        )
        hits += result.p_value <= alpha
    rate = hits / m
    assert rate <= alpha + bernoulli_band(alpha, m), f"P(p<={alpha})={rate:.4f}"
    floor = alpha - bernoulli_band(alpha, m) - 1.0 / (n_perms + 1)  # discreteness slack
    assert rate >= floor, f"P(p<={alpha})={rate:.4f}"
