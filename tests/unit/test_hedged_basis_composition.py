from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from alpha_cli.research_crypto_strategy import (
    compose_hedged_basis_observations,
    load_hedged_basis_observations,
)
from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_research import CryptoCrowdingObservationV1
from alpha_strategies.hedged_basis import evaluate_hedged_basis


def _crowding_rows() -> tuple[CryptoCrowdingObservationV1, ...]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows: list[CryptoCrowdingObservationV1] = []
    for index in range(420):
        funding_time = start + timedelta(hours=8 * index)
        event = index == 380
        rows.append(
            CryptoCrowdingObservationV1(
                funding_time=funding_time,
                funding_available_at=funding_time,
                funding_rate=0.02 if event else 0.001 + index * 0.000001,
                open_interest=1_000.0 + index + (100.0 if event else 0.0),
                open_interest_available_at=funding_time,
                premium=0.002 if event else -0.001,
                premium_available_at=funding_time,
                entry_time=funding_time + timedelta(hours=1),
                entry_available_at=funding_time + timedelta(hours=1),
                entry_mark=100.0,
                entry_index=100.0,
                exit_time=funding_time + timedelta(hours=8),
                exit_available_at=funding_time + timedelta(hours=8),
                exit_mark=99.0 if event else 100.0,
                exit_index=100.0,
                long_short_ratio=1.0,
                recent_trend=0.0,
                recent_volatility=0.01,
                regime="normal",
                diagnostics_available_at=funding_time,
            )
        )
    return tuple(rows)


def _spot(rows: tuple[CryptoCrowdingObservationV1, ...]) -> pl.DataFrame:
    event = rows[380]
    return pl.DataFrame(
        {
            "open_time": [event.funding_time, event.exit_time - timedelta(hours=1)],
            "close_time": [
                event.entry_time - timedelta(milliseconds=1),
                event.exit_time - timedelta(milliseconds=1),
            ],
            "close": [100.0, 100.0],
        }
    )


def _candidate_snapshot(
    tmp_path: Path, rows: tuple[CryptoCrowdingObservationV1, ...]
) -> tuple[CryptoSnapshotV1, dict[str, CryptoQualityReportV1]]:
    semantics = {
        "funding": ("funding_interval", "dimensionless_rate", "provider_event_utc"),
        "open_interest": (
            "1h",
            "base_coin_if_linear_quote_coin_if_inverse",
            "provider_event_utc",
        ),
        "premium_bars": ("1h", "quote_price", "interval_start_utc"),
        "mark_bars": ("1h", "quote_price", "interval_start_utc"),
        "index_bars": ("1h", "quote_price", "interval_start_utc"),
        "derivative_bars": ("1h", "quote_price", "interval_start_utc"),
        "instrument_catalog": (
            "catalog_snapshot",
            "provider_native",
            "fetch_knowledge_utc",
        ),
        "long_short_ratio": ("1h", "dimensionless_ratio", "provider_event_utc"),
    }
    members: list[CryptoSnapshotMemberV1] = []
    reports: dict[str, CryptoQualityReportV1] = {}
    for index, (family, (frequency, units, timestamp)) in enumerate(semantics.items(), start=1):
        digest = f"{index:064x}"
        catalog = family == "instrument_catalog"
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
                    timestamp_convention=timestamp,
                ),
                artifact_key=f"normalized/{family}.parquet",
                artifact_sha256=digest,
            )
        )
        reports[digest] = CryptoQualityReportV1(
            dataset_sha256=digest,
            method_version="crypto-quality-v1",
            state="qualified",
            failures=(),
            warnings=(),
            observed_start=rows[0].funding_time,
            observed_end=rows[-1].exit_time,
            row_count=420,
            correction_lineage=(),
        )
    spot_path = tmp_path / "normalized/market_bars.parquet"
    spot_path.parent.mkdir(parents=True)
    _spot(rows).write_parquet(spot_path)
    spot_digest = hashlib.sha256(spot_path.read_bytes()).hexdigest()
    members.append(
        CryptoSnapshotMemberV1(
            dataset=CryptoDatasetIdentityV1(
                provider="binance",
                venue="binance",
                market_type="spot",
                family="market_bars",
                instrument="BTCUSDT",
                base_asset="BTC",
                quote_asset="USDT",
                frequency="1h",
                units="provider_native_ohlcv",
                timestamp_convention="interval_start_utc",
            ),
            artifact_key="normalized/market_bars.parquet",
            artifact_sha256=spot_digest,
        )
    )
    reports[spot_digest] = CryptoQualityReportV1(
        dataset_sha256=spot_digest,
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=rows[380].funding_time,
        observed_end=rows[380].exit_time,
        row_count=2,
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


def test_compose_hedged_basis_uses_registered_events_and_exact_spot_closes() -> None:
    rows = _crowding_rows()
    observations = compose_hedged_basis_observations(
        rows,
        _spot(rows),
        bybit_snapshot_sha256="a" * 64,
        binance_spot_sha256="b" * 64,
    )

    assert len(observations) == 1
    assert observations[0].event_time == rows[380].funding_time
    assert observations[0].bybit_perp_entry == 100.0
    assert observations[0].bybit_perp_exit == 99.0
    assert observations[0].binance_spot_entry == 100.0
    assert observations[0].binance_spot_exit == 100.0
    assert evaluate_hedged_basis(observations).trades[0].net_return == pytest.approx(0.026)


def test_compose_hedged_basis_rejects_missing_future_or_duplicate_spot_bars() -> None:
    rows = _crowding_rows()
    spot = _spot(rows)

    with pytest.raises(DataError, match="exact Binance spot close"):
        compose_hedged_basis_observations(
            rows,
            spot.head(1),
            bybit_snapshot_sha256="a" * 64,
            binance_spot_sha256="b" * 64,
        )
    future = spot.with_columns(
        pl.when(pl.col("open_time") == rows[380].funding_time)
        .then(pl.col("close_time") + timedelta(hours=2))
        .otherwise(pl.col("close_time"))
        .alias("close_time")
    )
    with pytest.raises(DataError, match="not causally available"):
        compose_hedged_basis_observations(
            rows,
            future,
            bybit_snapshot_sha256="a" * 64,
            binance_spot_sha256="b" * 64,
        )
    with pytest.raises(DataError, match="duplicated"):
        compose_hedged_basis_observations(
            rows,
            pl.concat((spot, spot.head(1))),
            bybit_snapshot_sha256="a" * 64,
            binance_spot_sha256="b" * 64,
        )


def test_load_hedged_basis_requires_exact_qualified_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = _crowding_rows()
    snapshot, reports = _candidate_snapshot(tmp_path, rows)
    monkeypatch.setattr(
        "alpha_cli.research_crypto_data.load_crypto_crowding_observations",
        lambda *_args, **_kwargs: rows,
    )

    loaded = load_hedged_basis_observations(snapshot, reports, bulk_root=tmp_path)
    assert len(loaded) == 1
    assert loaded[0].input_sha256[0][0] == "binance_spot"
    assert loaded[0].input_sha256[1][0] == "bybit_linear"

    with pytest.raises(DataError, match="nine-family"):
        load_hedged_basis_observations(
            CryptoSnapshotV1.create(
                members=snapshot.members[:-1],
                asset_master_version=snapshot.asset_master_version,
                qualification_versions=snapshot.qualification_versions,
            ),
            reports,
            bulk_root=tmp_path,
        )
    spot_hash = snapshot.members[-1].artifact_sha256
    warned = {
        **reports,
        spot_hash: CryptoQualityReportV1(
            dataset_sha256=spot_hash,
            method_version="crypto-quality-v1",
            state="warning",
            failures=(),
            warnings=("cross_venue_divergence",),
            observed_start=rows[380].funding_time,
            observed_end=rows[380].exit_time,
            row_count=2,
            correction_lineage=(),
        ),
    }
    with pytest.raises(DataError, match="unqualified"):
        load_hedged_basis_observations(snapshot, warned, bulk_root=tmp_path)
