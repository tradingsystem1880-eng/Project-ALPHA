"""A symbol that later stops trading must still be readable as-of a date it was alive."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard


def test_delisted_symbol_present_in_as_of_window(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # "DEAD" trades only Jan 2024 then delists. As-of mid-Jan it MUST be visible.
    store = ParquetStore(tmp_path)
    store.write_bars("DEAD", linear_bars("DEAD", date(2024, 1, 1), 10))
    out = PointInTimeReader(store, actions={}).as_of("DEAD", datetime(2024, 1, 7, tzinfo=UTC))
    assert out.height == 7
    assert out["close"].max() is not None
