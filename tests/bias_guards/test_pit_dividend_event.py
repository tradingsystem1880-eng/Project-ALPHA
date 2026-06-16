"""A cash dividend must be invisible before its announce_date, never touch the price
series, and surface as a knowledge-gated cash event for pay-date crediting (spec §6.1.4)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import aapl_dividend, linear_bars

pytestmark = pytest.mark.bias_guard


def test_dividend_invisible_before_announce(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 7, 20), 12, first_close=100.0))
    r = PointInTimeReader(store, actions={"AAPL": [aapl_dividend()]})
    # announce is 2020-07-30; a query before it must not see the dividend.
    assert r.dividends_as_of("AAPL", datetime(2020, 7, 24, tzinfo=UTC)) == []


def test_dividend_never_adjusts_prices(tmp_path: Path) -> None:
    # The decouple property: the close series must be byte-identical with and without
    # the dividend in the action set — dividends are cash, never a price adjustment.
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 3), 12, first_close=100.0))
    when = datetime(2020, 8, 20, tzinfo=UTC)  # after both announce and ex-date
    with_div = PointInTimeReader(store, actions={"AAPL": [aapl_dividend()]})
    without = PointInTimeReader(store, actions={"AAPL": []})
    assert (
        with_div.as_of("AAPL", when)["close"].to_list()
        == without.as_of("AAPL", when)["close"].to_list()
    )


def test_dividend_exposed_as_cash_event_after_announce(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 3), 12, first_close=100.0))
    r = PointInTimeReader(store, actions={"AAPL": [aapl_dividend()]})
    divs = r.dividends_as_of("AAPL", datetime(2020, 8, 20, tzinfo=UTC))  # known by now
    assert len(divs) == 1
    d = divs[0]
    assert d.amount == 0.82
    assert d.ex_date == date(2020, 8, 7)
    assert d.pay_date == date(2020, 8, 13)  # the engine credits cash here
