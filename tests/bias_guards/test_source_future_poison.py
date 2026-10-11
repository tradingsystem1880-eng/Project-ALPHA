"""The typed DataSource path must exclude future bars and be immune to post-cutoff data."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.source import PointInTimeSource
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard


def test_typed_source_excludes_and_is_immune_to_future_data(tmp_path: Path) -> None:
    clean = linear_bars("X", date(2024, 1, 1), 10)
    store = ParquetStore(tmp_path)
    store.write_bars("X", clean)
    when = datetime(2024, 1, 5, tzinfo=UTC)

    baseline = PointInTimeSource(store, actions={}).as_of("X", when)
    assert len(baseline) == 5  # only 2024-01-01 .. 2024-01-05
    assert all(b.ts <= when for b in baseline)

    # poison every bar strictly after `when` with an absurd close, rewrite, re-query
    poisoned = clean.with_columns(
        pl.when(pl.col("ts") > when).then(pl.lit(9.9e9)).otherwise(pl.col("close")).alias("close")
    )
    store.write_bars("X", poisoned)
    after = PointInTimeSource(store, actions={}).as_of("X", when)

    assert after == baseline  # frozen Bars compare by value; future poison cannot leak in

    # Non-vacuity: an IN-window change MUST be reflected, proving the firewall reads in-window
    # data (so the future-invariance above isn't trivially true for an empty/ignored result).
    # Bump the bar at `when` by +0.3 (within its OHLC range, so the typed Bar still validates).
    edited = clean.with_columns(
        pl.when(pl.col("ts") == when)
        .then(pl.col("close") + 0.3)
        .otherwise(pl.col("close"))
        .alias("close")
    )
    store.write_bars("X", edited)
    changed = PointInTimeSource(store, actions={}).as_of("X", when)
    assert changed != baseline
    assert changed[-1].close == pytest.approx(baseline[-1].close + 0.3)  # in-window edit is visible


def test_invalid_future_bar_is_filtered_before_typed_validation(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    clean = linear_bars("X", date(2024, 1, 1), 10)
    when = datetime(2024, 1, 5, tzinfo=UTC)
    store.write_bars("X", clean)
    source = PointInTimeSource(store, actions={})
    baseline = source.as_of("X", when)
    poisoned = clean.with_columns(
        pl.when(pl.col("ts") > when).then(float("nan")).otherwise(pl.col("close")).alias("close")
    )
    store.write_bars("X", poisoned)
    assert source.as_of("X", when) == baseline

    # Deliberately leaky twin reads beyond the cutoff and must detect the invalid future bar.
    with pytest.raises(DataError, match="Bar.close must be finite"):
        source.as_of("X", datetime(2024, 1, 10, tzinfo=UTC))

    # In-window poison must fail; the guard cannot pass by ignoring all input rows.
    store.write_bars("X", clean.with_columns(pl.lit(float("nan")).alias("close")))
    with pytest.raises(DataError, match="Bar.close must be finite"):
        source.as_of("X", when)
