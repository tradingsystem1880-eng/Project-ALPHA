"""Dividend cash events credited at pay_date (spec 6.1.4) — the engine side of the two clocks.

The PIT layer already carries dividends on a decoupled cash channel (`dividends_as_of`); these
tests pin the engine hook that finally consumes it: entitlement = the net position held BEFORE
the ex-date session's open, cash lands in equity from the first session at/after pay_date, and a
short position is debited, not credited.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_core import ActionType, CorporateAction, DataError
from tests.fixtures.nautilus_fixtures import BuyAndHold, ladder_bars


def _dividend(ex: date, pay: date | None, amount: float) -> CorporateAction:
    return CorporateAction(
        symbol="AAPL", action_type=ActionType.DIVIDEND, ex_date=ex, pay_date=pay, amount=amount
    )


def _run(dividends: list[CorporateAction]) -> dict[datetime, float]:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    # ladder_bars: 5 sessions 2024-01-02..06; BuyAndHold buys 100 sh at the FIRST open
    result = run_backtest(
        inst,
        to_execution_feed(ladder_bars("AAPL"), bar_type),
        BuyAndHold(inst.id),
        dividends=dividends,
    )
    return dict(result.equity_curve)


def test_dividend_credited_at_pay_date_not_ex_date() -> None:
    # ex 01-04, pay 01-06, 0.50/sh on 100 held shares -> +50.00 from 01-06 only
    base = _run([])
    paid = _run([_dividend(date(2024, 1, 4), date(2024, 1, 6), 0.5)])
    for day in (2, 3, 4, 5):  # before pay_date the curve is untouched
        ts = datetime(2024, 1, day, tzinfo=UTC)
        assert paid[ts] == pytest.approx(base[ts])
    ts_pay = datetime(2024, 1, 6, tzinfo=UTC)
    assert paid[ts_pay] == pytest.approx(base[ts_pay] + 50.0)


def test_dividend_defaults_to_ex_date_when_pay_date_missing() -> None:
    base = _run([])
    paid = _run([_dividend(date(2024, 1, 4), None, 0.5)])
    ts_ex = datetime(2024, 1, 4, tzinfo=UTC)
    assert paid[ts_ex] == pytest.approx(base[ts_ex] + 50.0)


def test_position_opened_on_ex_date_open_is_not_entitled() -> None:
    # BuyAndHold fills at the FIRST session's open (01-02). A dividend whose ex date IS the first
    # session belongs to holders BEFORE that open -> position of 0 -> no credit, ever.
    base = _run([])
    paid = _run([_dividend(date(2024, 1, 2), date(2024, 1, 3), 1.0)])
    for ts, v in base.items():
        assert paid[ts] == pytest.approx(v)


def test_pay_date_beyond_backtest_end_is_never_credited() -> None:
    base = _run([])
    paid = _run([_dividend(date(2024, 1, 4), date(2024, 2, 1), 0.5)])
    for ts, v in base.items():
        assert paid[ts] == pytest.approx(v)


def test_short_position_is_debited() -> None:
    from nautilus_trader.model.enums import AccountType, OrderSide
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.model.objects import Quantity
    from nautilus_trader.trading.strategy import Strategy

    class SellAndHold(Strategy):  # type: ignore[misc]
        def __init__(self, instrument_id: InstrumentId) -> None:
            super().__init__()
            self._iid = instrument_id
            self._sold = False

        def on_start(self) -> None:
            self.subscribe_quote_ticks(self._iid)

        def on_quote_tick(self, quote: object) -> None:
            if not self._sold:
                self._sold = True
                self.submit_order(
                    self.order_factory.market(
                        instrument_id=self._iid,
                        order_side=OrderSide.SELL,
                        quantity=Quantity.from_int(100),
                    )
                )

    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    div = [_dividend(date(2024, 1, 4), date(2024, 1, 5), 0.5)]
    kw = dict(starting_cash=1_000_000.0, account_type=AccountType.MARGIN, leverage=2.0)
    base = dict(
        run_backtest(
            inst, to_execution_feed(ladder_bars("AAPL"), bar_type), SellAndHold(inst.id), **kw
        ).equity_curve
    )
    paid = dict(
        run_backtest(
            inst,
            to_execution_feed(ladder_bars("AAPL"), bar_type),
            SellAndHold(inst.id),
            dividends=div,
            **kw,
        ).equity_curve
    )
    ts_pay = datetime(2024, 1, 5, tzinfo=UTC)
    assert paid[ts_pay] == pytest.approx(base[ts_pay] - 50.0)  # shorts OWE the dividend


def test_non_dividend_action_fails_loud() -> None:
    split = CorporateAction(
        symbol="AAPL", action_type=ActionType.SPLIT, ex_date=date(2024, 1, 4), ratio=4.0
    )
    with pytest.raises(DataError, match="DIVIDEND"):
        _run([split])


def test_insolvent_fill_fails_loud_not_truncated() -> None:
    # A full-balance CASH fill whose commission tips the account negative makes nautilus STOP the
    # run without raising; with logging bypassed that silently yielded a truncated curve and
    # nonsense downstream statistics. run_backtest must fail loud with an actionable message.
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    from tests.fixtures.nautilus_fixtures import BuyAndHold as _BH

    with pytest.raises(DataError, match="stopped after"):
        run_backtest(
            inst,
            to_execution_feed(ladder_bars("AAPL"), bar_type),
            _BH(inst.id, qty=100),  # 100 sh @ open 100 = the entire 10k balance
            starting_cash=10_000.0,
            fee_bps=100.0,  # 1% commission tips the account negative on the fill
        )
