"""The equity curve marks an OPEN position to market each session (not just realized cash)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from tests.fixtures.nautilus_fixtures import BuyAndHold, ladder_bars


def test_equity_curve_marks_open_position_to_market() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    # opens 100, 110, 120, 130, 140; buy 100 @ open 100 on session 0, then hold (never close)
    result = run_backtest(
        inst, to_execution_feed(ladder_bars("AAPL"), bar_type), BuyAndHold(inst.id)
    )

    assert not result.trades  # position never closed -> no realized trades
    assert len(result.equity_curve) == 5  # one snapshot per session
    curve = dict(result.equity_curve)
    # bought 100 sh @100 on session 0; equity = 1M + unrealized (+10/sh per session as opens climb)
    assert curve[datetime(2024, 1, 2, tzinfo=UTC)] == pytest.approx(1_000_000.0)  # entry, no gain
    assert curve[datetime(2024, 1, 3, tzinfo=UTC)] == pytest.approx(1_001_000.0)  # +10/sh
    assert curve[datetime(2024, 1, 6, tzinfo=UTC)] == pytest.approx(1_004_000.0)  # +40/sh
    assert result.final_equity == pytest.approx(1_004_000.0)  # MtM, not realized cash (~990k)
