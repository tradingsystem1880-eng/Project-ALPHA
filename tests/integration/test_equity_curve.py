"""The equity curve marks an OPEN position to market each session (not just realized cash)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_core import Bar


class _BuyAndHold(Strategy):  # type: ignore[misc]  # nautilus Strategy is untyped (Cython)
    """Buy 100 at the first open and hold (never close)."""

    def __init__(self, instrument_id: object) -> None:
        super().__init__()
        self._iid = instrument_id
        self._bought = False

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self._iid)

    def on_quote_tick(self, quote: object) -> None:
        if not self._bought:
            self._bought = True
            self.submit_order(
                self.order_factory.market(
                    instrument_id=self._iid,
                    order_side=OrderSide.BUY,
                    quantity=Quantity.from_int(100),
                )
            )


def test_equity_curve_marks_open_position_to_market() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    # opens 100, 110, 120, 130, 140; buy 100 @ open 100 on session 0, then hold
    bars = [
        Bar(
            symbol="AAPL",
            ts=datetime(2024, 1, 2 + i, tzinfo=UTC),
            open=100.0 + 10 * i,
            high=140.0 + 10 * i,
            low=90.0 + 10 * i,
            close=105.0 + 10 * i,
            volume=1000.0,
        )
        for i in range(5)
    ]
    result = run_backtest(inst, to_execution_feed(bars, bar_type), _BuyAndHold(inst.id))

    assert not result.trades  # position never closed -> no realized trades
    curve = dict(result.equity_curve)
    assert len(result.equity_curve) == 5  # one snapshot per session
    # held 100 shares bought @100; equity marks to each session's open (unrealized only)
    assert curve[datetime(2024, 1, 3, tzinfo=UTC)] == pytest.approx(1_001_000.0)  # +10/sh
    assert curve[datetime(2024, 1, 6, tzinfo=UTC)] == pytest.approx(1_004_000.0)  # +40/sh
    assert result.final_equity == pytest.approx(1_004_000.0)  # MtM, not realized cash (~990k)
