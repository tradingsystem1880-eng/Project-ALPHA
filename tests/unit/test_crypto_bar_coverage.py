from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import polars as pl
import pytest

from alpha_data.crypto.contracts import CryptoDatasetIdentityV1
from alpha_data.crypto.quality import audit_daily_bar_grid

START = datetime(2024, 1, 1, tzinfo=UTC)
DATASET = CryptoDatasetIdentityV1(
    provider="binance",
    venue="binance",
    market_type="spot",
    family="market_bars",
    instrument="BTCUSDT",
    base_asset="BTC",
    quote_asset="USDT",
    frequency="1d",
    units="provider_native_ohlcv",
    timestamp_convention="interval_start_utc",
)


def frame(days: list[int]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "open_time": [START + timedelta(days=d) for d in days],
            "open": [100.0] * len(days),
            "high": [105.0] * len(days),
            "low": [95.0] * len(days),
            "close": [101.0] * len(days),
            "base_volume": [20.0] * len(days),
            "close_time": [START + timedelta(days=d + 1, milliseconds=-1) for d in days],
            "quote_volume": [2020.0] * len(days),
            "trade_count": [10] * len(days),
            "taker_buy_base_volume": [10.0] * len(days),
            "taker_buy_quote_volume": [1010.0] * len(days),
        }
    )


def audit(data: pl.DataFrame) -> dict[str, Any]:
    return audit_daily_bar_grid(
        DATASET,
        data,
        artifact_sha256="a" * 64,
        start=START,
        end=START + timedelta(days=4),
        as_of=START + timedelta(days=10),
        cadence_seconds=86400,
        max_rows=100,
        max_missing_ranges=10,
    )


def test_leading_and_trailing_gaps_not_hidden_by_contiguous_observed_span() -> None:
    result = audit(frame([1, 2]))
    assert result["missing_slots"] == 2 and result["covered_slots"] == 2
    assert result["missing_ranges"] == [
        {"start": START.isoformat(), "end": (START + timedelta(days=1)).isoformat(), "slots": 1},
        {
            "start": (START + timedelta(days=3)).isoformat(),
            "end": (START + timedelta(days=4)).isoformat(),
            "slots": 1,
        },
    ]
    assert result["declared_grid_satisfied"] is False
    assert result["execution_authority"] is False


def test_duplicates_are_not_sorted_or_deduplicated_before_integrity_checks() -> None:
    data = frame([2, 1, 1, 1])
    data = data.with_columns(pl.Series("close", [101.0, 101.0, 102.0, 101.0]))
    result = audit(data)
    assert result["duplicate_timestamp_groups"] == 1
    assert result["duplicate_extra_rows"] == 2 and result["conflicting_duplicate_groups"] == 1
    assert "non_monotonic_time" in result["failures"]
    assert "duplicate_observation" in result["failures"]


def test_identical_duplicates_remain_a_failure_without_invented_conflict() -> None:
    result = audit(frame([0, 1, 1, 2, 3]))
    assert result["identical_duplicate_groups"] == 1
    assert result["conflicting_duplicate_groups"] == 0
    assert result["missing_slots"] == 0
    assert result["declared_grid_satisfied"] is False


def test_invalid_unplaceable_and_close_timestamps_block_grid_success() -> None:
    data = frame([0, 1, 2, 3]).with_columns(
        pl.Series("open_time", [START, None, START + timedelta(days=2), START + timedelta(days=3)]),
        pl.Series("close_time", [START - timedelta(seconds=1), START, START, START]),
    )
    result = audit(data)
    assert result["invalid_timestamp_rows"] == 1
    assert result["invalid_close_timestamp_rows"] == 3
    assert result["missing_slots"] == 1
    assert result["declared_grid_satisfied"] is False


def test_null_volume_and_invalid_ohlc_are_explicit_findings() -> None:
    data = frame([0, 1, 2, 3]).with_columns(
        pl.Series("base_volume", [None, 20.0, 20.0, 20.0]),
        pl.Series("high", [105.0, 90.0, 105.0, 105.0]),
    )
    result = audit(data)
    assert result["invalid_numeric_rows"] == 1
    assert "invalid_required_ohlcv_numeric" in result["failures"]
    assert result["declared_grid_satisfied"] is False


def test_missing_range_output_is_capped_without_capping_exact_missing_count() -> None:
    result = audit_daily_bar_grid(
        DATASET,
        frame([1, 3]),
        artifact_sha256="a" * 64,
        start=START,
        end=START + timedelta(days=6),
        as_of=START + timedelta(days=6),
        cadence_seconds=86400,
        max_rows=100,
        max_missing_ranges=1,
    )
    assert result["missing_slots"] == 4
    assert result["missing_range_count"] == 3
    ranges = result["missing_ranges"]
    assert isinstance(ranges, list) and len(ranges) == 1
    assert result["missing_ranges_truncated"] is True


def test_large_empty_expected_grid_uses_compact_range_not_slot_expansion() -> None:
    result = audit_daily_bar_grid(
        DATASET,
        frame([0]),
        artifact_sha256="a" * 64,
        start=START,
        end=datetime(9999, 1, 1, tzinfo=UTC),
        as_of=datetime(9999, 1, 1, tzinfo=UTC),
        cadence_seconds=86400,
        max_rows=100,
        max_missing_ranges=1,
    )
    missing = result["missing_slots"]
    assert isinstance(missing, int) and missing > 2_000_000
    assert result["missing_range_count"] == 1


@pytest.mark.bias_guard
def test_future_poison_cannot_change_requested_grid_findings_with_leaky_control() -> None:
    original = audit(frame([0, 1, 2, 3]))
    poison = frame([9]).with_columns(pl.lit(float("nan")).alias("base_volume"))
    result = audit(pl.concat([frame([0, 1, 2, 3]), poison]))
    for key in (
        "missing_slots",
        "covered_slots",
        "failures",
        "duplicate_extra_rows",
        "invalid_numeric_rows",
        "declared_grid_satisfied",
    ):
        assert result[key] == original[key]
    assert result["outside_window_rows"] == 1
    # Leaky control intentionally audits the future row as if it were in the grid.
    leaky = audit_daily_bar_grid(
        DATASET,
        pl.concat([frame([0, 1, 2, 3]), poison]),
        artifact_sha256="a" * 64,
        start=START,
        end=START + timedelta(days=10),
        as_of=START + timedelta(days=10),
        cadence_seconds=86400,
        max_rows=100,
        max_missing_ranges=10,
    )
    assert leaky["invalid_numeric_rows"] != original["invalid_numeric_rows"]


def test_duplicate_native_integer_counts_do_not_lose_precision() -> None:
    data = frame([0, 1, 1, 2, 3]).with_columns(
        pl.Series("trade_count", [10, 2**53, 2**53 + 1, 10, 10])
    )
    result = audit(data)
    assert result["conflicting_duplicate_groups"] == 1
    assert result["identical_duplicate_groups"] == 0


@pytest.mark.parametrize("count", [-1.0, 0.5])
def test_native_trade_count_is_nonnegative_and_integral(count: float) -> None:
    result = audit(frame([0, 1, 2, 3]).with_columns(pl.lit(count).alias("trade_count")))
    assert "invalid_native_trade_count" in result["failures"]
    assert result["declared_grid_satisfied"] is False


def test_nanosecond_timestamp_cannot_round_onto_daily_grid() -> None:
    from alpha_core import DataError

    data = frame([0, 1, 2, 3]).with_columns(
        (pl.col("open_time").dt.cast_time_unit("ns") + pl.duration(nanoseconds=1)).alias(
            "open_time"
        )
    )
    with pytest.raises(DataError, match="precision"):
        audit(data)
