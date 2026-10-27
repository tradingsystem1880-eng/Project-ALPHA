from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from alpha_core import ActionType, CorporateAction, DataError
from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard


def test_naive_cutoff_is_rejected_before_data_read(tmp_path: Path) -> None:
    reader = PointInTimeReader(ParquetStore(tmp_path), actions={})
    with pytest.raises(DataError, match="cutoff must be timezone-aware"):
        reader.as_of("X", datetime(2024, 3, 11))


@pytest.mark.parametrize(
    "day", [date(2024, 3, 8), date(2024, 3, 11), date(2024, 11, 1), date(2024, 11, 4)]
)
@pytest.mark.parametrize("offset_us", [-1, 0, 1])
def test_named_zone_cutoff_matches_utc_across_dst(
    tmp_path: Path, day: date, offset_us: int
) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("X", linear_bars("X", day, 3))
    reader = PointInTimeReader(store, actions={})
    boundary = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    cutoff = boundary + timedelta(microseconds=offset_us)
    expected = reader.as_of("X", cutoff)
    actual = reader.as_of("X", cutoff.astimezone(ZoneInfo("America/New_York")))
    assert actual.equals(expected)
    assert actual.height == (0 if offset_us < 0 else 1)


def test_knowledge_gate_uses_utc_date_for_non_utc_when(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("X", linear_bars("X", date(2024, 1, 1), 10))
    split = CorporateAction(
        symbol="X",
        action_type=ActionType.SPLIT,
        ex_date=date(2024, 1, 8),
        announce_date=date(2024, 1, 5),
        ratio=2.0,
    )
    reader = PointInTimeReader(store, actions={"X": [split]})
    # `when` just after midnight in UTC+14 is still 2024-01-04 in UTC → split NOT yet known
    tz_plus = timezone(timedelta(hours=14))
    out = reader.as_of("X", datetime(2024, 1, 5, 1, 0, tzinfo=tz_plus))  # = 2024-01-04 11:00 UTC
    pre = out.filter(out["ts"] < datetime(2024, 1, 8, tzinfo=UTC))
    assert pre["close"].to_list() == linear_bars("X", date(2024, 1, 1), 4)["close"].to_list()
