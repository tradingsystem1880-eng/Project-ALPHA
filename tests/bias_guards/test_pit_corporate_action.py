"""A split must be invisible before its announce_date and applied only to pre-ex bars."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import aapl_4for1_split, linear_bars

pytestmark = pytest.mark.bias_guard


def _reader(tmp_path: Path) -> PointInTimeReader:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 25), 12, first_close=100.0))
    return PointInTimeReader(store, actions={"AAPL": [aapl_4for1_split()]})


def test_split_invisible_before_announce(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # announce is 2020-07-30; as_of on 2020-08-28 is AFTER announce, so it's known.
    # Build a query BEFORE announce by using an earlier `when` that still has bars:
    # all fixture bars are >= 2020-08-25 (after announce), so instead assert the gate
    # via a reader whose action announce is in the future relative to `when`.
    from alpha_core import ActionType, CorporateAction

    store = ParquetStore(tmp_path)
    store.write_bars("ZZ", linear_bars("ZZ", date(2020, 1, 2), 5, first_close=100.0))
    future_announce = CorporateAction(
        symbol="ZZ",
        action_type=ActionType.SPLIT,
        ex_date=date(2020, 6, 1),
        announce_date=date(2020, 5, 1),
        ratio=4.0,
    )
    r2 = PointInTimeReader(store, actions={"ZZ": [future_announce]})
    out = r2.as_of("ZZ", datetime(2020, 1, 6, tzinfo=UTC))  # before the 2020-05-01 announce
    assert out["close"].to_list() == [100.0, 101.0, 102.0, 103.0, 104.0]  # unadjusted


def test_split_applied_to_pre_ex_only_when_known(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _reader(tmp_path)
    out = r.as_of("AAPL", datetime(2020, 9, 5, tzinfo=UTC))
    by_ts = {row["ts"].date(): row["close"] for row in out.iter_rows(named=True)}
    assert by_ts[date(2020, 8, 30)] == pytest.approx(105.0 / 4)  # pre-ex quartered
    assert by_ts[date(2020, 8, 31)] == pytest.approx(106.0)  # ex day unadjusted
