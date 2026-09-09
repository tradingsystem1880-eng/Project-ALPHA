"""The nautilus run harness honors decide-on-close-t / fill-at-open-t+1 (spec §7, §13)."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType, OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import crypto_instrument, equity_instrument
from tests.fixtures.nautilus_fixtures import DecideCloseExecuteOpen, DoNothing, ladder_bars, ns


def test_engine_processes_bars_no_fills_for_do_nothing() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    strat = DoNothing(bar_type)
    result = run_backtest(inst, to_execution_feed(ladder_bars("AAPL", n=4), bar_type), strat)
    assert strat.bars_seen == 4
    assert result.orders == 0
    assert result.fills == 0


@pytest.mark.bias_guard
def test_market_order_decided_on_close_fills_at_next_open() -> None:
    # Decide on the first bar (session 2024-01-02, close 105); the order must fill at the OPEN of
    # the NEXT session (2024-01-03 open = 110), NOT the decision bar's close. This is the causality
    # / execution convention: a signal at t can only transact at t+1's open.
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    strat = DecideCloseExecuteOpen(bar_type, inst.id)
    result = run_backtest(inst, to_execution_feed(ladder_bars("AAPL", n=4), bar_type), strat)
    assert result.fills == 1
    assert strat.fill_price == 110.0  # open of t+1, not the decision bar's close (105)
    assert strat.fill_ts == ns(datetime(2024, 1, 3, tzinfo=UTC))


class _FlipLongToShort(Strategy):  # type: ignore[misc]
    """Buy 1, sell 2 (a netting flip to short), then buy 1 to flatten: two round trips."""

    def __init__(self, bar_type: BarType, instrument_id: InstrumentId) -> None:
        super().__init__()
        self._bar_type = bar_type
        self._iid = instrument_id
        self._quotes = 0

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)
        self.subscribe_quote_ticks(self._iid)

    def on_quote_tick(self, quote: object) -> None:
        self._quotes += 1
        if self._quotes == 2:
            side, qty = OrderSide.BUY, 1
        elif self._quotes == 4:
            side, qty = OrderSide.SELL, 2
        elif self._quotes == 6:
            side, qty = OrderSide.BUY, 1
        else:
            return
        self.submit_order(
            self.order_factory.market(
                instrument_id=self._iid, order_side=side, quantity=Quantity.from_int(qty)
            )
        )


def test_margin_account_settles_in_the_pair_quote_currency_across_a_flip() -> None:
    # A USDT-quoted pair on a MARGIN account: flipping long → short leaves a netting position
    # snapshot whose realized PnL is in USDT. With the account denominated in USD nautilus needs a
    # USDT→USD rate that no feed provides and the equity read crashes mid-run; the account must be
    # denominated in the pair's quote currency (the venue's own cash) so no conversion happens.
    inst = crypto_instrument("XRP/USDT")
    bar_type = daily_bar_type("XRP/USDT")
    strat = _FlipLongToShort(bar_type, inst.id)
    result = run_backtest(
        inst,
        to_execution_feed(ladder_bars("XRP/USDT", n=6), bar_type, price_precision=5),
        strat,
        starting_cash=1_000.0,
        account_type=AccountType.MARGIN,
    )
    assert result.fills == 3
    assert len(result.equity_curve) == 6
    assert all(math.isfinite(value) for _ts, value in result.equity_curve)
    # Both round trips reach the trade log: the flipped long leg (a netting snapshot) and the short.
    assert [(t.side, t.quantity, t.entry_price, t.exit_price) for t in result.trades] == [
        ("BUY", 1.0, 110.0, 130.0),
        ("SELL", 1.0, 130.0, 150.0),
    ]
    assert [t.realized_pnl for t in result.trades] == [20.0, -20.0]
    assert result.trades[0].exit_ts == result.trades[1].entry_ts


class _LongFlatLong(Strategy):  # type: ignore[misc]
    """Two separate long round trips (buy 1 / sell 1 / buy 2 / sell 2) with a flat bar between."""

    def __init__(self, bar_type: BarType, instrument_id: InstrumentId) -> None:
        super().__init__()
        self._bar_type = bar_type
        self._iid = instrument_id
        self._quotes = 0

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)
        self.subscribe_quote_ticks(self._iid)

    def on_quote_tick(self, quote: object) -> None:
        self._quotes += 1
        plan = {
            2: (OrderSide.BUY, 1),
            3: (OrderSide.SELL, 1),
            5: (OrderSide.BUY, 2),
            6: (OrderSide.SELL, 2),
        }
        if self._quotes not in plan:
            return
        side, qty = plan[self._quotes]
        self.submit_order(
            self.order_factory.market(
                instrument_id=self._iid, order_side=side, quantity=Quantity.from_int(qty)
            )
        )


def test_trade_log_keeps_every_round_trip_on_a_netting_venue() -> None:
    # Before the snapshot read only the LAST round trip survived (one position id per instrument
    # and strategy); the trade log must reconcile with the equity curve's realized PnL.
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    result = run_backtest(
        inst,
        to_execution_feed(ladder_bars("AAPL", n=6), bar_type),
        _LongFlatLong(bar_type, inst.id),
    )
    assert result.fills == 4
    rows = [
        (t.side, t.quantity, t.entry_price, t.exit_price, t.realized_pnl) for t in result.trades
    ]
    assert rows == [("BUY", 1.0, 110.0, 120.0, 10.0), ("BUY", 2.0, 140.0, 150.0, 20.0)]
    assert sum(t.realized_pnl for t in result.trades) == pytest.approx(
        result.equity_curve[-1][1] - result.equity_curve[0][1]
    )
