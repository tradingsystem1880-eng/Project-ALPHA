"""Metamorphic relations for the backtest engine (t+1-open fills, fee crediting, marking).

Relations (each is a statement about the engine as a function, not a golden number):
1. Zero signal ⇒ zero fills and an equity curve identical to starting cash at every session.
2. Price-scale homogeneity: multiplying every OHLC by k and buying the same share count scales
   P&L (equity − cash, incl. proportional fees) by exactly k.
3. Long/short antisymmetry with zero fees: a BUY-then-SELL round trip and its mirror
   SELL-then-BUY over the same fills realise P&L of equal magnitude and opposite sign.
Dividend crediting at ``pay_date`` is pinned by ``tests/integration/test_dividend_credit.py``.
"""

from __future__ import annotations

import pytest
from nautilus_trader.model.enums import AccountType, OrderSide

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_core import Bar
from tests.fixtures.nautilus_fixtures import BuyAndHold, DoNothing, RoundTrip, ladder_bars

pytestmark = pytest.mark.oracle

_CASH = 1_000_000.0


def _scaled(bars: list[Bar], k: float) -> list[Bar]:
    return [
        b.model_copy(
            update={"open": b.open * k, "high": b.high * k, "low": b.low * k, "close": b.close * k}
        )
        for b in bars
    ]


def test_zero_signal_leaves_equity_at_starting_cash() -> None:
    inst = equity_instrument("AAPL")
    bars = ladder_bars("AAPL", n=6)
    bar_type = daily_bar_type("AAPL")
    strategy = DoNothing(bar_type)
    result = run_backtest(inst, to_execution_feed(bars, bar_type), strategy, fee_bps=25.0)
    assert strategy.bars_seen == len(bars)  # the strategy ran; it simply never traded
    assert result.fills == 0 and len(result.trades) == 0
    assert len(result.equity_curve) == len(bars)
    assert all(v == pytest.approx(_CASH) for _, v in result.equity_curve)
    assert result.final_equity == pytest.approx(_CASH)


@pytest.mark.parametrize("k", [0.5, 3.0])
@pytest.mark.parametrize("fee_bps", [0.0, 10.0])
def test_pnl_is_homogeneous_of_degree_one_in_price(k: float, fee_bps: float) -> None:
    inst = equity_instrument("AAPL")
    bars = ladder_bars("AAPL", n=6, first_open=200.0)
    base = run_backtest(
        inst, to_execution_feed(bars, daily_bar_type("AAPL")), BuyAndHold(inst.id), fee_bps=fee_bps
    )
    scaled = run_backtest(
        inst,
        to_execution_feed(_scaled(bars, k), daily_bar_type("AAPL")),
        BuyAndHold(inst.id),
        fee_bps=fee_bps,
    )
    assert base.fills == scaled.fills == 1
    for (ts_b, eq_b), (ts_s, eq_s) in zip(base.equity_curve, scaled.equity_curve, strict=True):
        assert ts_b == ts_s
        assert eq_s - _CASH == pytest.approx(k * (eq_b - _CASH), abs=1e-6)


def test_long_and_short_round_trips_are_antisymmetric_without_fees() -> None:
    inst = equity_instrument("AAPL")
    bars = ladder_bars("AAPL", n=6)
    runs = {
        side: run_backtest(
            inst,
            to_execution_feed(bars, daily_bar_type("AAPL")),
            RoundTrip(inst.id, exit_at=3, opening_side=side),
            account_type=AccountType.MARGIN,
            fee_bps=0.0,
        )
        for side in (OrderSide.BUY, OrderSide.SELL)
    }
    long_pnl = runs[OrderSide.BUY].trades[0].realized_pnl
    short_pnl = runs[OrderSide.SELL].trades[0].realized_pnl
    assert long_pnl != 0.0  # the ladder trends, so the relation is not vacuous
    assert short_pnl == pytest.approx(-long_pnl, abs=1e-6)
    assert runs[OrderSide.BUY].final_equity - _CASH == pytest.approx(
        -(runs[OrderSide.SELL].final_equity - _CASH), abs=1e-6
    )
