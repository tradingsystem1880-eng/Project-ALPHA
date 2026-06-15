"""Poisoning bars AFTER `when` must not change the as_of(when) result."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard


def test_future_poison_does_not_change_as_of(tmp_path: Path) -> None:
    clean = linear_bars("X", date(2024, 1, 1), 10)
    store = ParquetStore(tmp_path)
    store.write_bars("X", clean)
    when = datetime(2024, 1, 5, tzinfo=UTC)
    baseline = PointInTimeReader(store, actions={}).as_of("X", when)

    # poison every bar strictly after `when` with absurd values, rewrite, re-read
    poisoned = clean.with_columns(
        pl.when(pl.col("ts") > when).then(pl.lit(9.9e9)).otherwise(pl.col("close")).alias("close")
    )
    store.write_bars("X", poisoned)
    after = PointInTimeReader(store, actions={}).as_of("X", when)

    assert baseline.equals(after)
