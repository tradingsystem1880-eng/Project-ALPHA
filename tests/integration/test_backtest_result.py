"""run_backtest emits a typed trade log + equity curve (spec §11 result schema)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from nautilus_trader.model.enums import AccountType, OrderSide

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from tests.fixtures.nautilus_fixtures import RoundTrip, ladder_bars


def test_result_schema_round_trip() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    # opens 100, 110, 120, 130, 140 -> buy @100 (quote 1), sell @120 (quote 3)
    result = run_backtest(
        inst, to_execution_feed(ladder_bars("AAPL"), bar_type), RoundTrip(inst.id)
    )

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
    assert len(result.equity_curve) == 5  # one snapshot per session


def test_short_round_trip_realized_pnl_and_sign() -> None:
    # Short on a MARGIN account: sell @100 (quote 1), cover @120 (quote 3). A short loses as the
    # price rises, so realized PnL and return must be negative and the trade tagged a SELL entry.
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    strat = RoundTrip(inst.id, opening_side=OrderSide.SELL)
    result = run_backtest(
        inst,
        to_execution_feed(ladder_bars("AAPL"), bar_type),
        strat,
        account_type=AccountType.MARGIN,
    )
    trade = result.trades[0]
    assert trade.side == "SELL"
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_price == pytest.approx(120.0)
    assert trade.realized_pnl == pytest.approx(-2000.0)  # (100 - 120) * 100
    assert trade.realized_return == pytest.approx(-0.2)
    assert result.final_equity == pytest.approx(998_000.0)
