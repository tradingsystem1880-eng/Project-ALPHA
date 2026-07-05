"""The Tier-1 cheap TS-momentum surrogate (``alpha_cli._surrogate``).

A vectorized, engine-free analogue of ``TimeSeriesMomentum`` that runs directly on a returns path
— the bulk of the randomized-price null distribution is built from it. These tests pin the
behavioural contract: it captures trend, manufactures no edge on noise, is deterministic, costs only
ever subtract, and ``allow_short=False`` sits out a downtrend.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_cli._surrogate import make_ts_momentum_surrogate
from alpha_core import DataError
from alpha_validation import StrategyFn, sharpe_ratio


def _surrogate(
    *, cost_bps: float = 0.0, allow_short: bool = True, rebalance_every: int = 5
) -> StrategyFn:
    """Build the surrogate with small, fast test params; only the varying knobs are arguments."""
    return make_ts_momentum_surrogate(
        lookback=20,
        skip=2,
        vol_window=10,
        target_vol=0.15,
        rebalance_every=rebalance_every,
        cost_bps=cost_bps,
        allow_short=allow_short,
    )


def test_rides_an_uptrend_long() -> None:
    rng = np.random.default_rng(0)
    pr = 0.002 + rng.normal(0.0, 0.005, 400)  # positive drift + noise
    out = _surrogate()(pr)
    assert out.shape == (400,)
    assert out.sum() > 0.0  # long the uptrend earns


def test_captures_trend_not_noise() -> None:
    f = _surrogate()
    trend = 0.002 + np.random.default_rng(1).normal(0.0, 0.005, 400)
    noise = np.random.default_rng(2).normal(0.0, 0.005, 400)  # zero drift
    assert sharpe_ratio(f(trend)) > sharpe_ratio(f(noise))


def test_is_deterministic() -> None:
    f = _surrogate()
    pr = np.random.default_rng(3).normal(0.001, 0.005, 300)
    assert np.array_equal(f(pr), f(pr))  # no RNG: identical every call
    assert np.array_equal(f(pr), _surrogate()(pr))  # same params -> same surrogate


def test_costs_only_ever_subtract() -> None:
    pr = 0.002 + np.random.default_rng(4).normal(0.0, 0.005, 400)
    free = _surrogate(cost_bps=0.0)(pr)
    costed = _surrogate(cost_bps=10.0)(pr)
    assert np.all(costed <= free + 1e-12)  # never improves a period
    assert costed.sum() < free.sum()  # there is turnover, so it strictly bites


def test_long_flat_sits_out_a_downtrend_but_short_profits() -> None:
    # strong negative drift so the lookback signal is reliably -1 across the path
    down = -0.005 + np.random.default_rng(5).normal(0.0, 0.002, 300)
    long_flat = _surrogate(allow_short=False)(down)
    short = _surrogate(allow_short=True)(down)
    assert np.allclose(long_flat, 0.0)  # long-flat strategy holds no position
    assert short.sum() > 0.0  # shorting a falling market earns


def test_bad_rebalance_fails_loud() -> None:
    with pytest.raises(DataError):
        _surrogate(rebalance_every=0)


def test_weights_and_costs_reproduce_the_surrogate_exactly() -> None:
    # The exposed series must be the SAME arithmetic the callable uses: w*pr - costs, bit-for-bit.
    import numpy as np

    f = _surrogate(cost_bps=10.0)
    pr = np.random.default_rng(6).normal(0.001, 0.005, 300)
    weights, costs = f.weights_and_costs(pr)  # type: ignore[attr-defined]
    assert np.array_equal(weights * pr - costs, f(pr))
    assert weights.shape == pr.shape and costs.shape == pr.shape
