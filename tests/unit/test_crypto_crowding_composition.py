from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from alpha_cli.research_crypto_data import (
    compose_crypto_crowding_observations,
    load_crypto_crowding_observations,
)
from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_research import evaluate_crypto_crowding


def _frames() -> dict[str, pl.DataFrame]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    funding_times = [start + timedelta(hours=8 * index) for index in range(370)]
    hourly_times = [
        start - timedelta(hours=25) + timedelta(hours=index) for index in range(25 + 8 * 369 + 1)
    ]
    event_time = funding_times[368]
    exit_bar_time = funding_times[369] - timedelta(hours=1)

    def bars(family: str) -> pl.DataFrame:
        closes = [100.0 for _ in hourly_times]
        if family == "mark":
            closes[hourly_times.index(exit_bar_time)] = 99.8
        if family == "trade":
            closes = [100.0 + 0.01 * index for index in range(len(hourly_times))]
        if family == "premium":
            closes = [
                0.002 if value == event_time - timedelta(hours=1) else -0.001
                for value in hourly_times
            ]
        return pl.DataFrame(
            {
                "timestamp": hourly_times,
                "category": ["linear"] * len(hourly_times),
                "symbol": ["BTCUSDT"] * len(hourly_times),
                "family": [family] * len(hourly_times),
                "close": closes,
            }
        )

    return {
        "funding": pl.DataFrame(
            {
                "timestamp": funding_times,
                "category": ["linear"] * len(funding_times),
                "symbol": ["BTCUSDT"] * len(funding_times),
                "funding_rate": [
                    0.02 if index == 368 else 0.001 + index * 0.000001
                    for index in range(len(funding_times))
                ],
            }
        ),
        "open_interest": pl.DataFrame(
            {
                "timestamp": hourly_times,
                "category": ["linear"] * len(hourly_times),
                "symbol": ["BTCUSDT"] * len(hourly_times),
                "open_interest": [1_000.0 + index for index in range(len(hourly_times))],
            }
        ),
        "long_short_ratio": pl.DataFrame(
            {
                "timestamp": hourly_times,
                "category": ["linear"] * len(hourly_times),
                "symbol": ["BTCUSDT"] * len(hourly_times),
                "long_short_ratio": [1.25] * len(hourly_times),
            }
        ),
        "premium_bars": bars("premium"),
        "mark_bars": bars("mark"),
        "index_bars": bars("index"),
        "derivative_bars": bars("trade"),
        "instrument_catalog": pl.DataFrame(
            {
                "symbol": ["BTCUSDT"],
                "category": ["linear"],
                "status": ["Trading"],
                "base_coin": ["BTC"],
                "quote_coin": ["USDT"],
                "funding_interval_minutes": [480],
            }
        ),
    }


def _snapshot_fixture(
    tmp_path: Path,
) -> tuple[CryptoSnapshotV1, dict[str, CryptoQualityReportV1]]:
    semantics = {
        "funding": ("funding_interval", "dimensionless_rate", "provider_event_utc"),
        "open_interest": (
            "1h",
            "base_coin_if_linear_quote_coin_if_inverse",
            "provider_event_utc",
        ),
        "long_short_ratio": ("1h", "dimensionless_ratio", "provider_event_utc"),
        "premium_bars": ("1h", "quote_price", "interval_start_utc"),
        "mark_bars": ("1h", "quote_price", "interval_start_utc"),
        "index_bars": ("1h", "quote_price", "interval_start_utc"),
        "derivative_bars": ("1h", "quote_price", "interval_start_utc"),
        "instrument_catalog": (
            "catalog_snapshot",
            "provider_native",
            "fetch_knowledge_utc",
        ),
    }
    members: list[CryptoSnapshotMemberV1] = []
    reports: dict[str, CryptoQualityReportV1] = {}
    for family, frame in _frames().items():
        artifact_key = f"normalized/{family}.parquet"
        path = tmp_path / artifact_key
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        catalog = family == "instrument_catalog"
        frequency, units, timestamp_convention = semantics[family]
        members.append(
            CryptoSnapshotMemberV1(
                dataset=CryptoDatasetIdentityV1(
                    provider="bybit",
                    venue="bybit",
                    market_type="linear",
                    family=family,  # type: ignore[arg-type]
                    instrument="linear" if catalog else "BTCUSDT",
                    base_asset=None if catalog else "BTC",
                    quote_asset=None if catalog else "USDT",
                    frequency=frequency,
                    units=units,
                    timestamp_convention=timestamp_convention,
                ),
                artifact_key=artifact_key,
                artifact_sha256=digest,
            )
        )
        reports[digest] = CryptoQualityReportV1(
            dataset_sha256=digest,
            method_version="crypto-quality-v1",
            state="qualified",
            failures=(),
            warnings=(),
            observed_start=datetime(2025, 1, 1, tzinfo=UTC),
            observed_end=datetime(2025, 5, 4, tzinfo=UTC),
            row_count=frame.height,
            correction_lineage=(),
        )
    return (
        CryptoSnapshotV1.create(
            members=tuple(members),
            asset_master_version="reviewed-native-v1",
            qualification_versions=("crypto-quality-v1",),
        ),
        reports,
    )


def test_compose_crowding_observations_preserves_causal_clocks_and_last_event() -> None:
    observations = compose_crypto_crowding_observations(
        _frames(), correction_lineage=("reviewed-correction",)
    )

    assert len(observations) == 369
    event = observations[-1]
    assert event.entry_time == event.funding_time + timedelta(hours=1)
    assert event.exit_time == event.funding_time + timedelta(hours=8)
    assert event.entry_available_at == event.entry_time
    assert event.exit_available_at == event.exit_time
    assert event.long_short_ratio == pytest.approx(1.25)
    assert event.recent_trend > 0
    assert event.recent_volatility >= 0
    assert event.correction_lineage == ("reviewed-correction",)

    result = evaluate_crypto_crowding(observations, evidence_zone="D1")
    assert [item.observation_index for item in result.primary_events] == [368]


def test_compose_crowding_observations_fails_on_missing_hourly_input() -> None:
    frames = _frames()
    frames["mark_bars"] = frames["mark_bars"].filter(
        pl.col("timestamp") != frames["funding"]["timestamp"][-1] - timedelta(hours=1)
    )

    with pytest.raises(DataError, match="missing exact mark_bars close"):
        compose_crypto_crowding_observations(frames, correction_lineage=())


@pytest.mark.parametrize(
    "failure",
    [
        "shape",
        "identity",
        "duplicate",
        "provider_family",
        "short_history",
        "catalog",
        "missing_ratio",
        "lineage",
        "interval",
    ],
)
def test_compose_crowding_observations_rejects_invalid_provider_inputs(failure: str) -> None:
    frames = _frames()
    lineage: object = ()
    if failure == "shape":
        frames["funding"] = frames["funding"].drop("funding_rate")
    elif failure == "identity":
        frames["funding"] = frames["funding"].with_columns(pl.lit("inverse").alias("category"))
    elif failure == "duplicate":
        frames["funding"] = pl.concat([frames["funding"], frames["funding"].head(1)])
    elif failure == "provider_family":
        frames["premium_bars"] = frames["premium_bars"].with_columns(pl.lit("mark").alias("family"))
    elif failure == "short_history":
        frames["funding"] = frames["funding"].head(1)
    elif failure == "catalog":
        frames["instrument_catalog"] = frames["instrument_catalog"].drop("status")
    elif failure == "missing_ratio":
        first_funding = frames["funding"]["timestamp"][0]
        frames["long_short_ratio"] = frames["long_short_ratio"].filter(
            pl.col("timestamp") != first_funding
        )
    elif failure == "lineage":
        lineage = ("",)
    else:
        funding = frames["funding"]
        frames["funding"] = funding.with_columns(
            pl.when(pl.int_range(pl.len()) == 369)
            .then(pl.col("timestamp") + timedelta(hours=1))
            .otherwise(pl.col("timestamp"))
            .alias("timestamp")
        )

    with pytest.raises(DataError):
        compose_crypto_crowding_observations(
            frames,
            correction_lineage=lineage,  # type: ignore[arg-type]
        )


def test_load_crowding_observations_reads_exact_snapshot_members(tmp_path: Path) -> None:
    snapshot, reports = _snapshot_fixture(tmp_path)

    observations = load_crypto_crowding_observations(snapshot, reports, bulk_root=tmp_path)

    assert len(observations) == 369
    assert observations[-1].funding_time == datetime(2025, 5, 3, 16, tzinfo=UTC)


def test_load_crowding_observations_rejects_correction_without_row_clock(tmp_path: Path) -> None:
    snapshot, reports = _snapshot_fixture(tmp_path)
    artifact_sha256 = snapshot.members[0].artifact_sha256
    original = reports[artifact_sha256]
    reports[artifact_sha256] = CryptoQualityReportV1(
        dataset_sha256=original.dataset_sha256,
        method_version=original.method_version,
        state=original.state,
        failures=original.failures,
        warnings=original.warnings,
        observed_start=original.observed_start,
        observed_end=original.observed_end,
        row_count=original.row_count,
        correction_lineage=("provider-revision",),
    )

    with pytest.raises(DataError, match="lack row-level availability"):
        load_crypto_crowding_observations(snapshot, reports, bulk_root=tmp_path)
