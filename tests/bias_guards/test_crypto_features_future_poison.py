"""Future-poison guards for the crypto feature derivations and the quality clock gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.features import (
    QualifiedCryptoFrame,
    feature_frame_bytes,
    funding_features,
    onchain_features,
    open_interest_features,
)
from alpha_data.crypto.quality import qualify_crypto_frame

NOW = datetime(2026, 8, 15, tzinfo=UTC)
SHA = "a" * 64


def _dataset(family: str, provider: str = "bybit") -> CryptoDatasetIdentityV1:
    return CryptoDatasetIdentityV1(
        provider=provider,
        venue=provider,
        market_type="linear",
        family=family,  # type: ignore[arg-type]
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="1h",
        units="provider_native",
        timestamp_convention="interval_end_utc",
    )


def _source(
    family: str,
    frame: pl.DataFrame,
    *,
    provider: str = "bybit",
    observed_end: datetime,
) -> QualifiedCryptoFrame:
    return QualifiedCryptoFrame(
        name=family,
        dataset=_dataset(family, provider),
        artifact_sha256=SHA,
        quality=CryptoQualityReportV1(
            dataset_sha256=SHA,
            method_version="crypto-quality-v1",
            state="qualified",
            failures=(),
            warnings=(),
            observed_start=observed_end - timedelta(hours=frame.height),
            observed_end=observed_end,
            row_count=frame.height,
            correction_lineage=(),
        ),
        frame=frame,
    )


def _hours(count: int) -> list[datetime]:
    return [NOW - timedelta(hours=count - index) for index in range(count)]


@pytest.mark.bias_guard
def test_funding_features_never_read_a_later_observation() -> None:
    """``cum_sum``/``diff`` are trailing: appending future rows may not rewrite earlier rows."""
    timestamps = _hours(6)
    clean = _source(
        "funding",
        pl.DataFrame({"timestamp": timestamps, "funding_rate": [0.001 * i for i in range(6)]}),
        observed_end=timestamps[-1],
    )
    clean_frame, _ = funding_features(clean, available_at=NOW)

    future = timestamps + [NOW + timedelta(hours=index) for index in range(1, 4)]
    poisoned = _source(
        "funding",
        pl.DataFrame(
            {
                "timestamp": future,
                "funding_rate": [0.001 * i for i in range(6)] + [9_999.0, -9_999.0, 9_999.0],
            }
        ),
        observed_end=timestamps[-1],
    )
    poisoned_frame, _ = funding_features(poisoned, available_at=NOW + timedelta(hours=4))

    assert feature_frame_bytes(poisoned_frame.head(6).drop("available_at")) == feature_frame_bytes(
        clean_frame.drop("available_at")
    )
    assert (
        poisoned_frame["cumulative_funding"].to_list()[6:]
        != clean_frame["cumulative_funding"].to_list()
    )


@pytest.mark.bias_guard
def test_open_interest_and_onchain_changes_never_read_a_later_observation() -> None:
    timestamps = _hours(6)
    clean_oi = _source(
        "open_interest",
        pl.DataFrame(
            {"timestamp": timestamps, "open_interest": [100.0 + 10 * i for i in range(6)]}
        ),
        observed_end=timestamps[-1],
    )
    clean_frame, _ = open_interest_features(clean_oi, available_at=NOW)
    poisoned_oi = _source(
        "open_interest",
        pl.DataFrame(
            {
                "timestamp": timestamps + [NOW + timedelta(hours=1)],
                "open_interest": [100.0 + 10 * i for i in range(6)] + [9_999_999.0],
            }
        ),
        observed_end=timestamps[-1],
    )
    poisoned_frame, _ = open_interest_features(poisoned_oi, available_at=NOW + timedelta(hours=2))

    assert feature_frame_bytes(poisoned_frame.head(6).drop("available_at")) == feature_frame_bytes(
        clean_frame.drop("available_at")
    )

    columns = {
        "asset": ["BTC"] * 4 + ["ETH"] * 4,
        "metric": ["AdrActCnt"] * 8,
        "family": ["addresses"] * 8,
    }
    clean_onchain = _source(
        "onchain_metrics",
        pl.DataFrame(
            columns
            | {
                "timestamp": _hours(4) * 2,
                "value": [10.0, 12.0, 14.0, 16.0, 20.0, 22.0, 24.0, 26.0],
            }
        ),
        provider="coinmetrics",
        observed_end=NOW - timedelta(hours=1),
    )
    onchain_clean, _ = onchain_features(clean_onchain, available_at=NOW)
    poisoned_onchain = _source(
        "onchain_metrics",
        pl.DataFrame(
            {
                "asset": columns["asset"] + ["BTC", "ETH"],
                "metric": columns["metric"] + ["AdrActCnt", "AdrActCnt"],
                "family": columns["family"] + ["addresses", "addresses"],
                "timestamp": _hours(4) * 2 + [NOW + timedelta(hours=1)] * 2,
                "value": [10.0, 12.0, 14.0, 16.0, 20.0, 22.0, 24.0, 26.0, 9e9, -9e9],
            }
        ),
        provider="coinmetrics",
        observed_end=NOW - timedelta(hours=1),
    )
    onchain_poisoned, _ = onchain_features(poisoned_onchain, available_at=NOW + timedelta(hours=2))

    per_asset = onchain_poisoned.filter(pl.col("timestamp") <= NOW).sort("asset", "timestamp")
    assert feature_frame_bytes(per_asset.drop("available_at")) == feature_frame_bytes(
        onchain_clean.sort("asset", "timestamp").drop("available_at")
    )


@pytest.mark.bias_guard
def test_feature_availability_may_never_precede_an_input_observation() -> None:
    timestamps = _hours(3)
    late = _source(
        "funding",
        pl.DataFrame({"timestamp": timestamps, "funding_rate": [0.001, 0.002, 0.003]}),
        observed_end=NOW + timedelta(hours=1),
    )
    with pytest.raises(DataError, match="availability precedes an input observation"):
        funding_features(late, available_at=NOW)


@pytest.mark.bias_guard
def test_quality_gates_quarantine_observations_the_cutoff_cannot_know() -> None:
    columns = {
        "open": [10.0, 11.0],
        "high": [12.0, 13.0],
        "low": [9.0, 10.0],
        "close": [11.0, 12.0],
        "volume": [5.0, 6.0],
        "available_at": [NOW - timedelta(hours=2), NOW - timedelta(hours=1)],
    }
    clean = pl.DataFrame({"timestamp": _hours(2)} | columns)
    report = qualify_crypto_frame(
        _dataset("market_bars"),
        clean,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
        availability_column="available_at",
    )
    assert report.state == "qualified"

    poisoned = clean.with_columns(
        pl.Series("timestamp", [NOW - timedelta(hours=1), NOW + timedelta(hours=1)])
    )
    future_observation = qualify_crypto_frame(
        _dataset("market_bars"),
        poisoned,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
        availability_column="available_at",
    )
    assert future_observation.state == "quarantined"
    assert "future_observation" in future_observation.failures

    future_availability = qualify_crypto_frame(
        _dataset("market_bars"),
        clean.with_columns(
            pl.Series("available_at", [NOW - timedelta(hours=2), NOW + timedelta(hours=1)])
        ),
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW,
        as_of=NOW,
        availability_column="available_at",
    )
    assert future_availability.state == "quarantined"
    assert "future_availability" in future_availability.failures

    future_knowledge = qualify_crypto_frame(
        _dataset("market_bars"),
        clean,
        artifact_sha256=SHA,
        observed_column="timestamp",
        key_columns=("timestamp",),
        knowledge_time=NOW + timedelta(hours=1),
        as_of=NOW,
        availability_column="available_at",
    )
    assert future_knowledge.state == "quarantined"
    assert "future_knowledge_time" in future_knowledge.failures
