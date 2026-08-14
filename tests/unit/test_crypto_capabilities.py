from __future__ import annotations

from datetime import UTC, datetime

from alpha_data.crypto.capabilities import project_provider_capabilities
from alpha_data.crypto.contracts import (
    FAMILY_AUTHORITIES,
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
)


def test_capabilities_separate_support_receipt_verification_and_qualification() -> None:
    observed_at = datetime(2026, 8, 14, tzinfo=UTC)
    dataset = CryptoDatasetIdentityV1(
        provider="bybit",
        venue="bybit",
        market_type="linear",
        family="open_interest",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="1h",
        units="base_coin_if_linear_quote_coin_if_inverse",
        timestamp_convention="provider_event_utc",
    )
    quality = CryptoQualityReportV1(
        dataset_sha256="a" * 64,
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=observed_at,
        observed_end=observed_at,
        row_count=1,
        correction_lineage=(),
    )
    capabilities = project_provider_capabilities(
        (
            {
                "artifact_kind": "normalized",
                "dataset": dataset.to_dict(),
                "quality": quality.to_dict(),
            },
        )
    )

    assert len(capabilities) == len(FAMILY_AUTHORITIES)
    by_family = {item.family: item for item in capabilities}
    assert by_family["open_interest"].verification_state == "receipt_verified"
    assert by_family["open_interest"].qualification_state == "qualified"
    assert by_family["open_interest"].earliest == observed_at
    assert by_family["open_interest"].frequencies == (
        "15m",
        "1d",
        "1h",
        "30m",
        "4h",
        "5m",
    )
    assert by_family["market_bars"].verification_state == "not_verified"
    assert by_family["market_bars"].qualification_state == "unverified"
    assert by_family["market_reference"].authentication == "demo_key"
    assert by_family["comparison_bars"].limits == ("diagnostic_only_no_automatic_substitution",)


def test_non_authoritative_artifact_cannot_claim_family_verification() -> None:
    dataset = CryptoDatasetIdentityV1(
        provider="bybit",
        venue="bybit",
        market_type="spot",
        family="market_bars",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="1h",
        units="provider_native",
        timestamp_convention="provider_event_utc",
    )
    quality = CryptoQualityReportV1(
        dataset_sha256="b" * 64,
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=None,
        observed_end=None,
        row_count=0,
        correction_lineage=(),
    )

    capabilities = project_provider_capabilities(
        (
            {
                "artifact_kind": "normalized",
                "dataset": dataset.to_dict(),
                "quality": quality.to_dict(),
            },
        )
    )

    market = next(item for item in capabilities if item.family == "market_bars")
    assert market.provider == "binance"
    assert market.verification_state == "not_verified"
    assert market.qualification_state == "unverified"
