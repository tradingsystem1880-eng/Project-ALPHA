"""The nautilus run harness honors decide-on-close-t / fill-at-open-t+1 (spec §7, §13)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_execution.instruments import equity_instrument
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
