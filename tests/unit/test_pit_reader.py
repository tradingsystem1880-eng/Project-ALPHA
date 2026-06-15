from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import aapl_4for1_split, linear_bars


def _reader(tmp_path: Path) -> PointInTimeReader:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 25), 12))  # 25th..(25+11)
    return PointInTimeReader(store, actions={"AAPL": [aapl_4for1_split()]})


def test_firewall_excludes_future_bars(tmp_path: Path) -> None:
    r = _reader(tmp_path)
    when = datetime(2020, 8, 28, tzinfo=UTC)
    out = r.as_of("AAPL", when)
    ts_max = out["ts"].max()
    assert ts_max is not None
    assert isinstance(ts_max, datetime)
    assert ts_max <= when  # no future bars
    assert out.height == 4  # 25,26,27,28


def test_split_applied_when_known(tmp_path: Path) -> None:
    r = _reader(tmp_path)
    out = r.as_of("AAPL", datetime(2020, 9, 5, tzinfo=UTC))
    pre = out.filter(out["ts"] < datetime(2020, 8, 31, tzinfo=UTC))
    post = out.filter(out["ts"] >= datetime(2020, 8, 31, tzinfo=UTC))
    # pre-ex closes are quartered (100..105 → 25..26.25); post-ex unadjusted
    assert pre["close"].to_list()[0] == pytest.approx(100.0 / 4)
    assert post["close"].to_list()[0] == pytest.approx(106.0)
