from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from alpha_core import ActionType, CorporateAction
from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard


def test_knowledge_gate_uses_utc_date_for_non_utc_when(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("X", linear_bars("X", date(2024, 1, 1), 10))
    split = CorporateAction(symbol="X", action_type=ActionType.SPLIT,
                            ex_date=date(2024, 1, 8), announce_date=date(2024, 1, 5), ratio=2.0)
    reader = PointInTimeReader(store, actions={"X": [split]})
    # `when` just after midnight in UTC+14 is still 2024-01-04 in UTC → split NOT yet known
    tz_plus = timezone(timedelta(hours=14))
    out = reader.as_of("X", datetime(2024, 1, 5, 1, 0, tzinfo=tz_plus))  # = 2024-01-04 11:00 UTC
    pre = out.filter(out["ts"] < datetime(2024, 1, 8, tzinfo=UTC))
    assert pre["close"].to_list() == linear_bars("X", date(2024, 1, 1), 4)["close"].to_list()
