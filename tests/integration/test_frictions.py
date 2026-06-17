"""Frictions: side-aware slippage on the t+1 open + per-notional fees (spec §7)."""

from __future__ import annotations

import pytest

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from tests.fixtures.nautilus_fixtures import RoundTrip, ladder_bars


def test_slippage_fills_buy_above_and_sell_below_open() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    data = to_execution_feed(ladder_bars("AAPL"), bar_type, slippage_bps=50.0)  # 0.5% half-spread
    trade = run_backtest(inst, data, RoundTrip(inst.id)).trades[0]
    assert trade.entry_price == pytest.approx(100.0 * 1.005)  # buy fills at the ask
    assert trade.exit_price == pytest.approx(120.0 * 0.995)  # sell fills at the bid
    assert trade.realized_pnl == pytest.approx((120.0 * 0.995 - 100.0 * 1.005) * 100)


def test_fee_reduces_final_equity() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    result = run_backtest(
        inst, to_execution_feed(ladder_bars("AAPL"), bar_type), RoundTrip(inst.id), fee_bps=10.0
    )
    # commissions: buy 100*100*0.001=10 + sell 100*120*0.001=12 = 22; gross PnL 2000.
    assert result.final_equity == pytest.approx(1_002_000.0 - 22.0)


def test_fee_and_slippage_combine() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    data = to_execution_feed(ladder_bars("AAPL"), bar_type, slippage_bps=50.0)
    result = run_backtest(inst, data, RoundTrip(inst.id), fee_bps=10.0)
    entry, exit_ = 100.0 * 1.005, 120.0 * 0.995  # slipped fills
    gross = (exit_ - entry) * 100
    fees = (entry + exit_) * 100 * 0.001  # 10 bps on each leg's notional
    assert result.trades[0].realized_pnl == pytest.approx(gross - fees)  # realized nets commissions
    assert result.final_equity == pytest.approx(1_000_000.0 + gross - fees)
