"""run_backtest emits a typed trade log + equity curve (spec §11 result schema)."""

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
    """Buy 100 at the first open, sell 100 at the third open — one closed round-trip."""

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


def test_result_schema_round_trip() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    # opens: 100, 110, 120, 130, 140 -> buy @100 (quote 1), sell @120 (quote 3)
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
    result = run_backtest(inst, to_execution_feed(bars, bar_type), _RoundTrip(bar_type, inst.id))

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.instrument_id == "AAPL.SIM"
    assert trade.side == "BUY"
    assert trade.quantity == pytest.approx(100.0)
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_price == pytest.approx(120.0)
    assert trade.realized_pnl == pytest.approx(2000.0)  # (120 - 100) * 100
    assert trade.realized_return == pytest.approx(0.2)
    assert trade.entry_ts == datetime(2024, 1, 2, tzinfo=UTC)
    assert trade.exit_ts == datetime(2024, 1, 4, tzinfo=UTC)

    assert result.starting_equity == pytest.approx(1_000_000.0)
    assert result.final_equity == pytest.approx(1_002_000.0)  # realized +2000
    assert len(result.equity_curve) >= 2
