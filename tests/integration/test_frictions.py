"""Frictions: side-aware slippage on the t+1 open + per-notional fees (spec §7)."""

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


class _RoundTrip(Strategy):  # type: ignore[misc]  # nautilus Strategy is untyped (Cython)
    """Buy 100 at the first open, sell 100 at the third open."""

    def __init__(self, bar_type: object, instrument_id: object) -> None:
        super().__init__()
        self._bt = bar_type
        self._iid = instrument_id
        self._n = 0

    def on_start(self) -> None:
        self.subscribe_bars(self._bt)
        self.subscribe_quote_ticks(self._iid)

    def on_quote_tick(self, quote: object) -> None:
        self._n += 1
        if self._n == 1:
            self._market(OrderSide.BUY)
        elif self._n == 3:
            self._market(OrderSide.SELL)

    def _market(self, side: object) -> None:
        self.submit_order(
            self.order_factory.market(
                instrument_id=self._iid, order_side=side, quantity=Quantity.from_int(100)
            )
        )


def _bars() -> list[Bar]:
    # opens 100, 110, 120, 130, 140 -> buy @ open 100, sell @ open 120
    return [
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


def test_slippage_fills_buy_above_and_sell_below_open() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    data = to_execution_feed(_bars(), bar_type, slippage_bps=50.0)  # 0.5% half-spread
    result = run_backtest(inst, data, _RoundTrip(bar_type, inst.id))
    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(100.0 * 1.005)  # buy fills at the ask
    assert trade.exit_price == pytest.approx(120.0 * 0.995)  # sell fills at the bid
    # gross PnL shrinks vs the frictionless 2000
    assert trade.realized_pnl == pytest.approx((120.0 * 0.995 - 100.0 * 1.005) * 100)


def test_fee_reduces_final_equity() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    data = to_execution_feed(_bars(), bar_type)  # no slippage
    result = run_backtest(inst, data, _RoundTrip(bar_type, inst.id), fee_bps=10.0)
    # commissions: buy 100*100*0.001=10 + sell 100*120*0.001=12 = 22; gross PnL 2000.
    assert result.final_equity == pytest.approx(1_002_000.0 - 22.0)
