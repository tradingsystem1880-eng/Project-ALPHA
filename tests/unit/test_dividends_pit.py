"""Dividends flow through the PIT firewall as decoupled cash events (spec §6.1.4)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alpha_core import ActionType
from alpha_data.corporate import cash_dividends
from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import aapl_4for1_split, aapl_dividend, linear_bars


def test_cash_dividends_filters_to_dividend_only() -> None:
    out = cash_dividends([aapl_4for1_split(), aapl_dividend()])
    assert [a.action_type for a in out] == [ActionType.DIVIDEND]
    assert out[0].amount == 0.82


def test_dividends_as_of_knowledge_gate_boundary(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 3), 12))
    r = PointInTimeReader(store, actions={"AAPL": [aapl_dividend()]})
    # announce_date = 2020-07-30: invisible the day before, visible on the announce day itself.
    assert r.dividends_as_of("AAPL", datetime(2020, 7, 29, tzinfo=UTC)) == []
    assert len(r.dividends_as_of("AAPL", datetime(2020, 7, 30, tzinfo=UTC))) == 1


def test_dividends_as_of_excludes_splits(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 25), 12))
    r = PointInTimeReader(store, actions={"AAPL": [aapl_4for1_split(), aapl_dividend()]})
    divs = r.dividends_as_of("AAPL", datetime(2020, 9, 5, tzinfo=UTC))
    assert [d.action_type for d in divs] == [ActionType.DIVIDEND]


def test_split_and_dividend_coexist(tmp_path: Path) -> None:
    # Both announced 2020-07-30. As of 2020-09-05 both are known: the split still
    # back-adjusts the pre-ex (8/31) price; the dividend rides the separate cash channel.
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 25), 12, first_close=100.0))
    r = PointInTimeReader(store, actions={"AAPL": [aapl_4for1_split(), aapl_dividend()]})
    when = datetime(2020, 9, 5, tzinfo=UTC)
    by_ts = {row["ts"].date(): row["close"] for row in r.as_of("AAPL", when).iter_rows(named=True)}
    assert by_ts[date(2020, 8, 30)] == pytest.approx(105.0 / 4)  # pre-ex still quartered
    assert by_ts[date(2020, 8, 31)] == pytest.approx(106.0)  # ex day unadjusted
    divs = r.dividends_as_of("AAPL", when)
    assert len(divs) == 1
    assert divs[0].pay_date == date(2020, 8, 13)
