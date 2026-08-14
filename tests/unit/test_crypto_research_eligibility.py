from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoFamily,
    CryptoMarketType,
    CryptoQualityReportV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_data.crypto.research import assess_crypto_snapshot, require_crypto_snapshot

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _member(
    family: CryptoFamily, digest: str, *, provider: str | None = None
) -> CryptoSnapshotMemberV1:
    authorities = {
        "market_bars": "binance",
        "market_reference": "coingecko",
        "asset_metadata": "coingecko",
        "funding": "bybit",
    }
    resolved_provider = provider or authorities[family]
    market_type: CryptoMarketType = (
        "reference" if family in {"market_reference", "asset_metadata"} else "linear"
    )
    return CryptoSnapshotMemberV1(
        dataset=CryptoDatasetIdentityV1(
            provider=resolved_provider,
            venue=resolved_provider,
            market_type=market_type,
            family=family,
            instrument="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT" if market_type == "linear" else None,
            frequency="1d",
            units="native",
            timestamp_convention="interval_end_utc",
        ),
        artifact_key=f"normalized/{family}/{digest}.parquet",
        artifact_sha256=digest,
    )


def _report(
    digest: str, *, state: str = "qualified", method: str = "crypto-quality-v1"
) -> CryptoQualityReportV1:
    return CryptoQualityReportV1(
        dataset_sha256=digest,
        method_version=method,
        state=state,  # type: ignore[arg-type]
        failures=() if state == "qualified" else ("future_observation",),
        warnings=(),
        observed_start=NOW,
        observed_end=NOW,
        row_count=1,
        correction_lineage=(),
    )


def _snapshot(*members: CryptoSnapshotMemberV1) -> CryptoSnapshotV1:
    return CryptoSnapshotV1.create(
        members=members,
        asset_master_version="asset-master-v1",
        qualification_versions=("crypto-quality-v1",),
    )


def test_validation_snapshot_accepts_exact_market_data_and_marks_reference_supplemental() -> None:
    market = _member("market_bars", "a" * 64)
    reference = _member("market_reference", "b" * 64)
    funding = _member("funding", "c" * 64)
    snapshot = _snapshot(market, reference, funding)

    projection = assess_crypto_snapshot(
        snapshot,
        quality_reports={
            market.artifact_sha256: _report(market.artifact_sha256),
            reference.artifact_sha256: _report(reference.artifact_sha256),
            funding.artifact_sha256: _report(funding.artifact_sha256),
        },
        required_families=("market_bars", "funding"),
        purpose="validation",
    )

    assert projection.eligible is True
    assert projection.blockers == ()
    assert projection.qualified_families == ("funding", "market_bars", "market_reference")
    assert projection.supplemental_families == ("market_reference",)
    assert (
        require_crypto_snapshot(
            snapshot,
            quality_reports={
                market.artifact_sha256: _report(market.artifact_sha256),
                reference.artifact_sha256: _report(reference.artifact_sha256),
                funding.artifact_sha256: _report(funding.artifact_sha256),
            },
            required_families=("market_bars", "funding"),
            purpose="validation",
        )
        == projection
    )


def test_reference_only_snapshot_cannot_satisfy_validation_or_execution_price() -> None:
    reference = _member("market_reference", "a" * 64)
    metadata = _member("asset_metadata", "b" * 64)
    snapshot = _snapshot(reference, metadata)
    reports = {
        reference.artifact_sha256: _report(reference.artifact_sha256),
        metadata.artifact_sha256: _report(metadata.artifact_sha256),
    }

    for purpose in ("validation", "execution_price"):
        projection = assess_crypto_snapshot(
            snapshot,
            quality_reports=reports,
            required_families=(),
            purpose=purpose,
        )
        assert projection.eligible is False
        assert "provider_native_price_required" in projection.blockers
        with pytest.raises(DataError, match="provider_native_price_required"):
            require_crypto_snapshot(
                snapshot,
                quality_reports=reports,
                required_families=(),
                purpose=purpose,
            )


def test_snapshot_fails_closed_for_missing_bad_or_uncommitted_qualification() -> None:
    market = _member("market_bars", "a" * 64)
    funding = _member("funding", "b" * 64)
    snapshot = _snapshot(market, funding)

    missing = assess_crypto_snapshot(
        snapshot,
        quality_reports={market.artifact_sha256: _report(market.artifact_sha256)},
        required_families=("market_bars", "funding"),
        purpose="research",
    )
    assert f"missing_qualification:{funding.artifact_sha256}" in missing.blockers

    quarantined = assess_crypto_snapshot(
        snapshot,
        quality_reports={
            market.artifact_sha256: _report(market.artifact_sha256),
            funding.artifact_sha256: _report(funding.artifact_sha256, state="quarantined"),
        },
        required_families=("market_bars", "funding"),
        purpose="research",
    )
    assert f"not_qualified:{funding.artifact_sha256}:quarantined" in quarantined.blockers

    uncommitted = assess_crypto_snapshot(
        snapshot,
        quality_reports={
            market.artifact_sha256: _report(market.artifact_sha256),
            funding.artifact_sha256: _report(funding.artifact_sha256, method="future-method"),
        },
        required_families=("market_bars", "funding"),
        purpose="research",
    )
    assert f"qualification_version_not_frozen:{funding.artifact_sha256}" in uncommitted.blockers


def test_snapshot_rejects_family_authority_mismatch_and_invalid_requirements() -> None:
    wrong = _member("funding", "a" * 64, provider="binance")
    snapshot = _snapshot(wrong)
    projection = assess_crypto_snapshot(
        snapshot,
        quality_reports={wrong.artifact_sha256: _report(wrong.artifact_sha256)},
        required_families=("funding",),
        purpose="research",
    )
    assert "authority_mismatch:funding:binance" in projection.blockers

    with pytest.raises(DataError, match="required families"):
        assess_crypto_snapshot(
            snapshot,
            quality_reports={wrong.artifact_sha256: _report(wrong.artifact_sha256)},
            required_families=("funding", "funding"),
            purpose="research",
        )

    with pytest.raises(DataError, match="purpose"):
        assess_crypto_snapshot(
            snapshot,
            quality_reports={wrong.artifact_sha256: _report(wrong.artifact_sha256)},
            required_families=(),
            purpose="unsupported",  # type: ignore[arg-type]
        )


def test_snapshot_detects_duplicate_artifacts_and_report_hash_mismatch() -> None:
    market = _member("market_bars", "a" * 64)
    duplicate = _member("market_bars", "a" * 64)
    snapshot = _snapshot(market, duplicate)
    wrong_report = _report("b" * 64)

    projection = assess_crypto_snapshot(
        snapshot,
        quality_reports={market.artifact_sha256: wrong_report},
        required_families=("market_bars",),
        purpose="research",
    )

    assert "duplicate_snapshot_artifact" in projection.blockers
    assert f"qualification_hash_mismatch:{market.artifact_sha256}" in projection.blockers
