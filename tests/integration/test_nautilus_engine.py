"""The nautilus run harness honors decide-on-close-t / fill-at-open-t+1 (spec §7, §13)."""

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

_OPENS = [100.0, 110.0, 120.0, 130.0]


def _bars(symbol: str) -> list[Bar]:
    return [
        Bar(
            symbol=symbol,
            ts=datetime(2024, 1, 2 + i, tzinfo=UTC),
            open=op,
            high=op + 5.0,
            low=op - 5.0,
            close=op + 1.0,  # close distinct from the next session's open, so a wrong fill shows
            volume=1000.0,
        )
        for i, op in enumerate(_OPENS)
    ]


class _DoNothing(Strategy):  # type: ignore[misc]  # nautilus Strategy is untyped (Cython)
    def __init__(self, bar_type: object) -> None:
        super().__init__()
        self._bt = bar_type
        self.bars_seen = 0

    def on_start(self) -> None:
        self.subscribe_bars(self._bt)

    def on_bar(self, bar: object) -> None:
        self.bars_seen += 1


class _DecideCloseExecuteOpen(Strategy):  # type: ignore[misc]  # nautilus Strategy is untyped
    """Decide once on the first bar's close; submit the market order on the next open quote."""

    def __init__(self, bar_type: object, instrument_id: object) -> None:
        super().__init__()
        self._bt = bar_type
        self._iid = instrument_id
        self._decided = False
        self._want = False
        self.fill_price: float | None = None
        self.fill_ts: int | None = None

    def on_start(self) -> None:
        self.subscribe_bars(self._bt)
        self.subscribe_quote_ticks(self._iid)

    def on_bar(self, bar: object) -> None:
        if not self._decided:  # decide exactly once, on the close of t
            self._decided = True
            self._want = True

    def on_quote_tick(self, quote: object) -> None:
        if self._want:  # execute at the next session open (t+1)
            self._want = False
            self.submit_order(
                self.order_factory.market(
                    instrument_id=self._iid,
                    order_side=OrderSide.BUY,
                    quantity=Quantity.from_int(1),
                )
            )

    def on_order_filled(self, event: object) -> None:
        self.fill_price = float(event.last_px)  # type: ignore[attr-defined]  # nautilus OrderFilled
        self.fill_ts = int(event.ts_event)  # type: ignore[attr-defined]


def test_engine_processes_bars_no_fills_for_do_nothing() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    data = to_execution_feed(_bars("AAPL"), bar_type)
    strat = _DoNothing(bar_type)
    result = run_backtest(inst, data, strat)
    assert strat.bars_seen == len(_OPENS)
    assert result.orders == 0
    assert result.fills == 0


@pytest.mark.bias_guard
def test_market_order_decided_on_close_fills_at_next_open() -> None:
    # Decide on the first bar (session 2024-01-02, close 101); the order must fill at the OPEN of
    # the NEXT session (2024-01-03 open = 110), NOT bar 0's close (101). This is the causality /
    # execution convention: a signal at t can only transact at t+1's open.
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    data = to_execution_feed(_bars("AAPL"), bar_type)
    strat = _DecideCloseExecuteOpen(bar_type, inst.id)
    result = run_backtest(inst, data, strat)
    assert result.fills == 1
    assert strat.fill_price == 110.0  # open of t+1, not 101 (close of t)
    assert strat.fill_ts == int(datetime(2024, 1, 3, tzinfo=UTC).timestamp() * 1_000_000_000)
