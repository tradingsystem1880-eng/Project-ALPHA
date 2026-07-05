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


class _LastOpenBuyer:  # assembled below; nautilus Strategy defined lazily to keep imports tidy
    pass


def test_final_equity_includes_last_session_fill_fee() -> None:
    # A fill on the FINAL open quote pays a fee AFTER the recorder samples that session, so
    # without a terminal re-sample the fee would never appear anywhere in the curve and
    # final_equity would be overstated by exactly the commission.
    from nautilus_trader.model.enums import OrderSide
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.model.objects import Quantity
    from nautilus_trader.trading.strategy import Strategy

    class LastOpenBuyer(Strategy):  # type: ignore[misc]
        def __init__(self, instrument_id: InstrumentId, n_sessions: int) -> None:
            super().__init__()
            self._iid = instrument_id
            self._n = n_sessions
            self._seen = 0

        def on_start(self) -> None:
            self.subscribe_quote_ticks(self._iid)

        def on_quote_tick(self, quote: object) -> None:
            self._seen += 1
            if self._seen == self._n:  # the last session's open
                self.submit_order(
                    self.order_factory.market(
                        instrument_id=self._iid,
                        order_side=OrderSide.BUY,
                        quantity=Quantity.from_int(100),
                    )
                )

    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    bars = ladder_bars("AAPL")
    fee_free = run_backtest(
        inst, to_execution_feed(bars, bar_type), LastOpenBuyer(inst.id, len(bars))
    )
    fee_paid = run_backtest(
        inst,
        to_execution_feed(bars, bar_type),
        LastOpenBuyer(inst.id, len(bars)),
        fee_bps=100.0,  # 1% of the 100 sh x 140 open = 140.00 commission
    )
    assert fee_free.fills == 1 and fee_paid.fills == 1
    assert fee_paid.final_equity == pytest.approx(fee_free.final_equity - 140.0)
