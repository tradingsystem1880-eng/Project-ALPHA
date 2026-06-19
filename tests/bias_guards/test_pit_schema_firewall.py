"""A malformed stored frame must fail loud at the PIT boundary, never reach positional reads."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alpha_core import DataError
from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard


def test_disordered_stored_frame_raises_at_as_of(tmp_path: Path) -> None:
    bars = linear_bars("X", date(2024, 1, 1), 6)
    scrambled = bars[[0, 1, 3, 2, 4, 5]]  # ts no longer strictly increasing
    store = ParquetStore(tmp_path)
    # write the parquet directly so the store's write-time sort cannot silently repair it
    (store.root / "bars").mkdir(parents=True, exist_ok=True)
    scrambled.write_parquet(store.root / "bars" / "X.parquet")

    with pytest.raises(DataError):
        PointInTimeReader(store, actions={}).as_of("X", datetime(2024, 1, 6, tzinfo=UTC))
