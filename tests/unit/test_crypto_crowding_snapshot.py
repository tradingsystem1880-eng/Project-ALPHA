from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alpha_cli import crypto_data_cmds
from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_data.crypto.research import assess_crypto_snapshot
from alpha_research import registered_crypto_crowding_plan

NOW = datetime(2026, 8, 15, tzinfo=UTC)

SEMANTICS = {
    "funding": ("funding_interval", "dimensionless_rate", "provider_event_utc"),
    "open_interest": (
        "1h",
        "base_coin_if_linear_quote_coin_if_inverse",
        "provider_event_utc",
    ),
    "premium_bars": ("1h", "quote_price", "provider_event_utc"),
    "mark_bars": ("1h", "quote_price", "provider_event_utc"),
    "index_bars": ("1h", "quote_price", "provider_event_utc"),
    "derivative_bars": ("1h", "quote_price", "provider_event_utc"),
    "instrument_catalog": ("catalog_snapshot", "provider_native", "fetch_knowledge_utc"),
}


def _snapshot(
    *, quote_asset: str = "USDT"
) -> tuple[CryptoSnapshotV1, dict[str, CryptoQualityReportV1]]:
    members: list[CryptoSnapshotMemberV1] = []
    reports: dict[str, CryptoQualityReportV1] = {}
    for index, (family, semantics) in enumerate(SEMANTICS.items(), start=1):
        catalog = family == "instrument_catalog"
        digest = f"{index:064x}"
        members.append(
            CryptoSnapshotMemberV1(
                dataset=CryptoDatasetIdentityV1(
                    provider="bybit",
                    venue="bybit",
                    market_type="linear",
                    family=family,  # type: ignore[arg-type]
                    instrument="linear" if catalog else "BTCUSDT",
                    base_asset=None if catalog else "BTC",
                    quote_asset=None if catalog else quote_asset,
                    frequency=semantics[0],
                    units=semantics[1],
                    timestamp_convention=semantics[2],
                ),
                artifact_key=f"normalized/{family}/{digest}.parquet",
                artifact_sha256=digest,
            )
        )
        reports[digest] = CryptoQualityReportV1(
            dataset_sha256=digest,
            method_version="crypto-quality-v1",
            state="qualified",
            failures=(),
            warnings=(),
            observed_start=NOW,
            observed_end=NOW,
            row_count=1,
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


def _install_verified_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: CryptoSnapshotV1,
    reports: dict[str, CryptoQualityReportV1],
) -> None:
    projection = assess_crypto_snapshot(
        snapshot,
        quality_reports=reports,
        required_families=(),
        purpose="research",
    )
    monkeypatch.setattr(
        crypto_data_cmds,
        "_verified_snapshot",
        lambda *_args, **_kwargs: (snapshot, reports, projection),
    )


def test_registered_crowding_plan_projects_exact_dataset_semantics() -> None:
    plan = registered_crypto_crowding_plan()
    requirements = crypto_data_cmds._crypto_crowding_requirements(plan)

    assert tuple(requirement.family for requirement in requirements) == plan.required_families
    assert all(requirement.provider == "bybit" for requirement in requirements)
    assert all(requirement.venue == "bybit" for requirement in requirements)
    assert all(requirement.market_type == "linear" for requirement in requirements)
    assert requirements[0].frequency == "funding_interval"
    assert requirements[-1].instrument == "linear"
    assert requirements[-1].base_asset is None
    assert requirements[-1].quote_asset is None


def test_crowding_compatibility_binds_snapshot_plan_and_asset_master(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, reports = _snapshot()
    _install_verified_snapshot(monkeypatch, snapshot, reports)

    result = crypto_data_cmds.crypto_crowding_snapshot_compatibility(snapshot.snapshot_id)

    assert result["eligible"] is True
    assert result["snapshot_id"] == snapshot.snapshot_id
    assert result["bundle_id"] == "bybit_btcusdt_crowding_reversal_v1"
    assert len(str(result["operator_fingerprint"])) == 64
    assert result["asset_master_version"] == "reviewed-native-v1"
    assert result["execution_authority"] is False


def test_crowding_compatibility_rejects_mixed_quote_before_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, reports = _snapshot(quote_asset="USDC")
    _install_verified_snapshot(monkeypatch, snapshot, reports)

    with pytest.raises(DataError, match="dataset_mismatch:.*:quote_asset"):
        crypto_data_cmds.crypto_crowding_snapshot_compatibility(snapshot.snapshot_id)
