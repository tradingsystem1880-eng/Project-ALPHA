"""Opening execution prices constrain affordability without leaking into close-time decisions."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.bias_guard


def test_next_open_price_changes_execution_rejection_but_not_close_decision() -> None:
    from alpha_backtest.engine import run_backtest
    from alpha_backtest.feed import daily_bar_type, to_execution_feed
    from alpha_backtest.instruments import equity_instrument
    from tests.fixtures.nautilus_fixtures import ladder_bars
    from tests.integration.test_order_rejection import _FixedNextOpenBuy

    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    clean = ladder_bars("AAPL")
    cheaper_open = list(clean)
    cheaper_open[1] = cheaper_open[1].model_copy(update={"open": 108.0})

    rejected = run_backtest(
        inst,
        to_execution_feed(clean, bar_type),
        _FixedNextOpenBuy(inst.id, bar_type, 100),
        # The $110 opening principal fits, but the $110 fee does not. The
        # cheaper $108 open remains affordable after its $108 fee.
        starting_cash=11_050,
        fee_bps=100,
    )
    affordable = run_backtest(
        inst,
        to_execution_feed(cheaper_open, bar_type),
        _FixedNextOpenBuy(inst.id, bar_type, 100),
        starting_cash=11_050,
        fee_bps=100,
    )

    assert rejected.decision_trace[0] == affordable.decision_trace[0]
    assert rejected.rejected == 1 and rejected.fills == 0
    assert len(rejected.execution_rejections) == 1
    rejection = rejected.execution_rejections[0]
    assert rejection.reason == "cash_plus_commission_exceeds_free_balance"
    assert rejection.reference_price == pytest.approx(110.0)
    assert rejection.available_cash == pytest.approx(11_050.0)
    assert rejection.required_cash == pytest.approx(11_110.0)
    assert affordable.rejected == 0 and affordable.fills == 1
