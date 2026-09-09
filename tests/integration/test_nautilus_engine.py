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
    """Buy 1 on the first open, then sell 2 (net short) on the third; a netting flip snapshot."""

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
    assert result.fills == 2
    assert len(result.equity_curve) == 6
    assert all(math.isfinite(value) for _ts, value in result.equity_curve)
