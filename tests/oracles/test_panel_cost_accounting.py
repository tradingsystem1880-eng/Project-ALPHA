"""Independent trade-notional accounting for the Phase C replacement-cost proxy.

This is the registered $1-per-leg, equal-weight replacement convention, not a
portfolio backtest: no price drift, universe entry/exit, or impact is modeled.
"""

import numpy as np
import pytest

from alpha_research.panel import cost_adjusted_spread

pytestmark = pytest.mark.oracle


@pytest.mark.parametrize("cost_bps", [0.0, 5.0, 30.0])
@pytest.mark.parametrize("spread", [-0.01, 0.0, 0.03])
@pytest.mark.parametrize(
    ("after", "replacement_fraction"),
    [
        ([0.5, 0.5, -0.5, -0.5, 0.0, 0.0], 0.0),
        ([0.5, 0.0, -0.5, -0.5, 0.5, 0.0], 0.25),
        ([0.5, 0.0, -0.5, 0.0, 0.5, -0.5], 0.5),
        ([-0.5, -0.5, 0.5, 0.5, 0.0, 0.0], 1.0),
    ],
)
def test_replacement_cost_matches_explicit_long_short_trades(
    after: list[float], replacement_fraction: float, spread: float, cost_bps: float
) -> None:
    before = np.array([0.5, 0.5, -0.5, -0.5, 0.0, 0.0])
    trades = np.asarray(after) - before
    paid_cost = sum(abs(float(trade)) * cost_bps / 10_000 for trade in trades)
    # Absolute tolerance covers only float64 arithmetic on these bounded notionals.
    assert cost_adjusted_spread(spread, replacement_fraction, cost_bps=cost_bps) == pytest.approx(
        spread - paid_cost, rel=1e-12, abs=1e-14
    )
