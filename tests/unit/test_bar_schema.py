"""Frame-level schema firewall for stored bars — fail loud on malformed frames.

Turns the implicit "bars arrive ts-sorted, OHLC-consistent, finite/positive" invariant that
``pit.py`` positional reads depend on into a mechanically-enforced contract that raises
``DataError`` (never a bare/foreign exception).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.schema import validate_bars
from tests.fixtures.pit_fixtures import linear_bars


def test_clean_bars_pass_through_unchanged() -> None:
    df = linear_bars("X", date(2024, 1, 1), 10)
    assert validate_bars(df, symbol="X").equals(df)


def test_missing_column_fails_loud() -> None:
    df = linear_bars("X", date(2024, 1, 1), 5).drop("volume")
    with pytest.raises(DataError):
        validate_bars(df, symbol="X")


@pytest.mark.parametrize("col", ["open", "high", "low", "close"])
def test_non_positive_price_fails_loud(col: str) -> None:
    df = linear_bars("X", date(2024, 1, 1), 5).with_columns(
        pl.when(pl.int_range(pl.len()) == 2).then(0.0).otherwise(pl.col(col)).alias(col)
    )
    with pytest.raises(DataError):
        validate_bars(df, symbol="X")


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_price_fails_loud(bad: float) -> None:
    df = linear_bars("X", date(2024, 1, 1), 5).with_columns(
        pl.when(pl.int_range(pl.len()) == 1).then(bad).otherwise(pl.col("close")).alias("close")
    )
    with pytest.raises(DataError):
        validate_bars(df, symbol="X")


def test_high_below_low_fails_loud() -> None:
    df = linear_bars("X", date(2024, 1, 1), 5).with_columns(
        pl.when(pl.int_range(pl.len()) == 3).then(0.01).otherwise(pl.col("high")).alias("high")
    )
    with pytest.raises(DataError):
        validate_bars(df, symbol="X")


def test_negative_volume_fails_loud() -> None:
    df = linear_bars("X", date(2024, 1, 1), 5).with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(-1.0).otherwise(pl.col("volume")).alias("volume")
    )
    with pytest.raises(DataError):
        validate_bars(df, symbol="X")


def test_disordered_ts_fails_loud() -> None:
    df = linear_bars("X", date(2024, 1, 1), 5)
    shuffled = df[[0, 2, 1, 3, 4]]  # ts no longer strictly increasing
    with pytest.raises(DataError):
        validate_bars(shuffled, symbol="X")


def test_duplicate_ts_fails_loud() -> None:
    df = linear_bars("X", date(2024, 1, 1), 5)
    dup = pl.concat([df, df[4]])  # repeat the last timestamp
    with pytest.raises(DataError):
        validate_bars(dup, symbol="X")


def test_empty_frame_fails_loud() -> None:
    empty = linear_bars("X", date(2024, 1, 1), 1).filter(
        pl.col("ts") == datetime(1900, 1, 1, tzinfo=UTC)
    )
    with pytest.raises(DataError):
        validate_bars(empty, symbol="X")
