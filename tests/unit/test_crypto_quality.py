from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1
from alpha_data.crypto.quality import QUALITY_METHOD_VERSION, qualify_crypto_frame

SHA = "a" * 64
NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _dataset(family: str, market_type: str = "linear") -> CryptoDatasetIdentityV1:
    return CryptoDatasetIdentityV1(
        provider="bybit"
        if family not in {"dex_pools", "onchain_metrics"}
        else ("geckoterminal" if family == "dex_pools" else "coinmetrics"),
        venue="bybit",
        market_type=market_type,  # type: ignore[arg-type]
        family=family,  # type: ignore[arg-type]
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="1h",
        units="provider_native",
        timestamp_convention="UTC interval start",
    )


def test_common_quality_qualifies_complete_monotonic_finite_history() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [NOW - timedelta(hours=3), NOW - timedelta(hours=2)],
            "open": [10.0, 11.0],
            "high": [12.0, 13.0],
            "low": [9.0, 10.0],
            "close": [11.0, 12.0],
            "volume": [5.0, 6.0],
        }
    )
    report = qualify_crypto_frame(
        _dataset("market_bars"),
        frame,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
        expected_cadence=timedelta(hours=1),
        period_start_timestamps=True,
    )

    assert report.state == "qualified"
    assert report.method_version == QUALITY_METHOD_VERSION
    assert report.row_count == 2


def test_future_duplicate_nonfinite_and_partial_rows_quarantine() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [NOW + timedelta(hours=1), NOW + timedelta(hours=1)],
            "open": [1.0, 1.0],
            "high": [2.0, 2.0],
            "low": [0.5, 0.5],
            "close": [float("inf"), 1.0],
            "volume": [1.0, 1.0],
        }
    )
    report = qualify_crypto_frame(
        _dataset("market_bars"),
        frame,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
        expected_cadence=timedelta(hours=1),
        period_start_timestamps=True,
    )
    assert report.state == "quarantined"
    assert {"duplicate_observation", "future_observation", "nonfinite_value"}.issubset(
        report.failures
    )


def test_cadence_gap_and_corrections_are_explicit_not_repaired() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [NOW - timedelta(hours=4), NOW - timedelta(hours=2)],
            "funding_rate": [0.001, 0.002],
        }
    )
    report = qualify_crypto_frame(
        _dataset("funding"),
        frame,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
        expected_cadence=timedelta(hours=1),
        correction_lineage=("receipt_previous",),
    )
    assert report.state == "warning"
    assert report.warnings == ("cadence_gap",)
    assert report.correction_lineage == ("receipt_previous",)
    assert frame["timestamp"].to_list()[1] - frame["timestamp"].to_list()[0] == timedelta(hours=2)


def test_unexplained_provider_revision_is_quarantined_without_rewriting_values() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [NOW - timedelta(hours=2)],
            "funding_rate": [0.001],
        }
    )
    report = qualify_crypto_frame(
        _dataset("funding"),
        frame,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
        correction_lineage=("prior_response_sha256",),
        unexplained_revision=True,
    )

    assert report.state == "quarantined"
    assert report.failures == ("unexplained_provider_revision",)
    assert report.correction_lineage == ("prior_response_sha256",)
    assert frame["funding_rate"].to_list() == [0.001]


def test_family_rules_reject_impossible_derivatives_values() -> None:
    funding = pl.DataFrame({"timestamp": [NOW - timedelta(hours=1)], "funding_rate": [1.1]})
    oi = pl.DataFrame({"timestamp": [NOW - timedelta(hours=1)], "open_interest": [-1.0]})
    funding_report = qualify_crypto_frame(
        _dataset("funding"),
        funding,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
    )
    oi_report = qualify_crypto_frame(
        _dataset("open_interest"),
        oi,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
    )
    assert "funding_rate_out_of_bounds" in funding_report.failures
    assert "negative_open_interest" in oi_report.failures


def test_option_and_dex_diagnostics_block_silent_research_admission() -> None:
    options = pl.DataFrame(
        {
            "available_at": [NOW - timedelta(minutes=1)],
            "symbol": ["BTC-30AUG26-100000-C"],
            "mark_iv": [0.5],
            "open_interest": [10.0],
            "crossed_market": [True],
            "stale_snapshot": [False],
        }
    )
    option_report = qualify_crypto_frame(
        _dataset("option_quotes", "option"),
        options,
        artifact_sha256=SHA,
        observed_column="available_at",
        key_columns=("available_at", "symbol"),
        knowledge_time=NOW,
        as_of=NOW,
        availability_column="available_at",
    )
    pools = pl.DataFrame(
        {
            "pool_created_at": [NOW - timedelta(days=10)],
            "pool_address": ["0x1"],
            "reserve_usd": [100.0],
            "h24_volume_usd": [20_000.0],
        }
    )
    pool_report = qualify_crypto_frame(
        _dataset("dex_pools", "dex"),
        pools,
        artifact_sha256=SHA,
        observed_column="pool_created_at",
        key_columns=("pool_address",),
        knowledge_time=NOW,
        as_of=NOW,
    )
    assert option_report.state == "warning" and "crossed_option_market" in option_report.warnings
    assert pool_report.state == "warning"
    assert {"thin_dex_liquidity", "dex_volume_reserve_extreme"}.issubset(pool_report.warnings)


def test_point_in_time_cross_section_allows_one_shared_observation_time() -> None:
    options = pl.DataFrame(
        {
            "available_at": [NOW - timedelta(minutes=1)] * 2,
            "symbol": ["BTC-30AUG26-100000-C-USDT", "BTC-30AUG26-100000-P-USDT"],
            "mark_iv": [0.5, 0.6],
            "open_interest": [10.0, 20.0],
            "crossed_market": [False, False],
            "stale_snapshot": [False, False],
        }
    )

    report = qualify_crypto_frame(
        _dataset("option_quotes", "option"),
        options,
        artifact_sha256=SHA,
        observed_column="available_at",
        key_columns=("available_at", "symbol"),
        knowledge_time=NOW,
        as_of=NOW,
        availability_column="available_at",
    )

    assert report.state == "qualified"


def test_null_onchain_observation_and_future_availability_never_qualify() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [NOW - timedelta(days=1)],
            "available_at": [NOW + timedelta(seconds=1)],
            "metric": ["AdrActCnt"],
            "value": [None],
        },
        schema_overrides={"value": pl.Float64},
    )
    report = qualify_crypto_frame(
        _dataset("onchain_metrics", "network"),
        frame,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp", "metric"),
        knowledge_time=NOW,
        as_of=NOW,
        availability_column="available_at",
    )
    assert report.state == "quarantined"
    assert "future_availability" in report.failures
    assert "missing_onchain_value" in report.warnings


def test_common_quality_boundary_is_fail_closed_and_empty_is_honest() -> None:
    empty = qualify_crypto_frame(
        _dataset("funding"),
        pl.DataFrame(),
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
    )
    assert empty.state == "unavailable" and empty.failures == ("empty_dataset",)

    missing = qualify_crypto_frame(
        _dataset("funding"),
        pl.DataFrame({"funding_rate": [0.1]}),
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW + timedelta(seconds=1),
        as_of=NOW,
        availability_column="available_at",
    )
    assert {
        "missing_required_column:timestamp",
        "missing_required_column:available_at",
        "future_knowledge_time",
    }.issubset(missing.failures)

    naive = pl.DataFrame({"timestamp": [datetime(2026, 8, 14)], "funding_rate": [0.1]})
    with pytest.raises(DataError, match="aware datetimes"):
        qualify_crypto_frame(
            _dataset("funding"),
            naive,
            artifact_sha256=SHA,
            observed_column="timestamp",
            key_columns=("timestamp",),
            knowledge_time=NOW,
            as_of=NOW,
        )
    with pytest.raises(DataError, match="timezone-aware"):
        qualify_crypto_frame(
            _dataset("funding"),
            pl.DataFrame({"timestamp": [NOW], "funding_rate": [0.1]}),
            artifact_sha256=SHA,
            observed_column="timestamp",
            key_columns=("timestamp",),
            knowledge_time=NOW.replace(tzinfo=None),
            as_of=NOW,
        )
    with pytest.raises(DataError, match="cadence must be positive"):
        qualify_crypto_frame(
            _dataset("funding"),
            pl.DataFrame({"timestamp": [NOW - timedelta(hours=1)], "funding_rate": [0.1]}),
            artifact_sha256=SHA,
            observed_column="timestamp",
            key_columns=("timestamp",),
            knowledge_time=NOW,
            as_of=NOW,
            expected_cadence=timedelta(0),
        )


@pytest.mark.parametrize(
    ("family", "market_type", "columns", "expected"),
    (
        ("market_bars", "linear", {"open": [1.0]}, "missing_required_column:high"),
        (
            "market_bars",
            "linear",
            {"open": ["bad"], "high": [2.0], "low": [0.5], "close": [1.0]},
            "invalid_ohlc",
        ),
        (
            "market_bars",
            "linear",
            {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.0], "volume": [-1.0]},
            "negative_volume",
        ),
        ("premium_bars", "linear", {"value": [0.1]}, "missing_required_column:close"),
        ("long_short_ratio", "linear", {"long_short_ratio": [0.0]}, "invalid_long_short_ratio"),
        (
            "option_quotes",
            "option",
            {
                "mark_iv": [-0.1],
                "open_interest": [-1.0],
                "crossed_market": [False],
                "stale_snapshot": [True],
            },
            "negative_implied_volatility",
        ),
        ("option_instruments", "option", {"strike_price": [0.0]}, "invalid_option_strike"),
        ("historical_volatility", "option", {"volatility": [-0.1]}, "negative_volatility"),
        (
            "dex_pools",
            "dex",
            {"reserve_usd": [None], "h24_volume_usd": [-1.0]},
            "invalid_dex_liquidity",
        ),
        ("onchain_metrics", "network", {"value": [-1.0]}, "negative_onchain_value"),
        ("market_reference", "reference", {"current_price": [None]}, "missing_reference_price"),
    ),
)
def test_family_quality_rules_surface_invalid_native_values(
    family: str, market_type: str, columns: dict[str, list[object]], expected: str
) -> None:
    frame = pl.DataFrame(
        {"timestamp": [NOW - timedelta(hours=1)]} | columns,
        schema_overrides={name: pl.Float64 for name, values in columns.items() if values == [None]},
    )
    report = qualify_crypto_frame(
        _dataset(family, market_type),
        frame,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
    )
    assert expected in report.failures or expected in report.warnings


def test_negative_base_volume_quarantines_market_bars() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [NOW - timedelta(hours=2), NOW - timedelta(hours=1)],
            "open": [10.0, 11.0],
            "high": [12.0, 13.0],
            "low": [9.0, 10.0],
            "close": [11.0, 12.0],
            "base_volume": [5.0, 6.0],
            "quote_volume": [50.0, -1.0],
        }
    )
    report = qualify_crypto_frame(
        _dataset("market_bars"),
        frame,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
        expected_cadence=timedelta(hours=1),
        period_start_timestamps=True,
    )

    assert report.state == "quarantined"
    assert "negative_volume" in report.failures


def test_market_bars_without_any_volume_column_fail_loud() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [NOW - timedelta(hours=2), NOW - timedelta(hours=1)],
            "open": [10.0, 11.0],
            "high": [12.0, 13.0],
            "low": [9.0, 10.0],
            "close": [11.0, 12.0],
        }
    )
    report = qualify_crypto_frame(
        _dataset("market_bars"),
        frame,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
        expected_cadence=timedelta(hours=1),
        period_start_timestamps=True,
    )

    assert "missing_required_column:volume" in report.failures
