from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import (
    FAMILY_AUTHORITIES,
    CryptoAssetIdentityV1,
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
    ProviderDatasetCapabilityV1,
)


def _dataset(*, quote: str = "USDT") -> CryptoDatasetIdentityV1:
    return CryptoDatasetIdentityV1(
        provider="binance",
        venue="BINANCE",
        market_type="spot",
        family="market_bars",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset=quote,
        frequency="1d",
        units="quote_per_base",
        timestamp_convention="open_time_utc",
    )


def test_dataset_identity_round_trips_without_merging_quotes() -> None:
    usdt = _dataset()
    usd = _dataset(quote="USD")

    assert CryptoDatasetIdentityV1.from_dict(usdt.to_dict()) == usdt
    assert usdt.content_sha256 != usd.content_sha256
    assert json.dumps(usdt.to_dict(), sort_keys=True) != json.dumps(usd.to_dict(), sort_keys=True)


def test_asset_identity_requires_contract_for_non_native_network_asset() -> None:
    with pytest.raises(DataError, match="contract address"):
        CryptoAssetIdentityV1(
            coingecko_id="usd-coin",
            network="ethereum",
            contract_address=None,
            native_asset=False,
            provider_symbols=(("binance", "USDC"),),
            valid_from=datetime(2018, 9, 26, tzinfo=UTC),
            valid_to=None,
            migration_lineage=(),
        )


def test_raw_receipt_rejects_secret_bearing_request_metadata() -> None:
    with pytest.raises(DataError, match="secret"):
        CryptoRawReceiptV1.create(
            dataset=_dataset(),
            request=(("symbol", "BTCUSDT"), ("api_key", "must-not-appear")),
            fetched_at=datetime(2026, 8, 14, tzinfo=UTC),
            response_sha256="a" * 64,
            response_bytes=10,
            provider_schema="binance-klines-v1",
            parser_version="1",
            pagination=(),
            upstream_checksum=None,
        )


def test_snapshot_identity_commits_to_ordered_membership() -> None:
    first = CryptoSnapshotMemberV1(
        dataset=_dataset(),
        artifact_key="normalized/market_bars/binance/btc.parquet",
        artifact_sha256="a" * 64,
    )
    second = CryptoSnapshotMemberV1(
        dataset=_dataset(quote="USD"),
        artifact_key="normalized/market_bars/binance/btc-usd.parquet",
        artifact_sha256="b" * 64,
    )
    left = CryptoSnapshotV1.create(
        members=(first, second), asset_master_version="am_1", qualification_versions=("quality-v1",)
    )
    right = CryptoSnapshotV1.create(
        members=(second, first), asset_master_version="am_1", qualification_versions=("quality-v1",)
    )

    assert left.snapshot_id != right.snapshot_id
    assert CryptoSnapshotV1.from_dict(left.to_dict()) == left


def test_every_primary_family_has_exactly_one_authority() -> None:
    assert FAMILY_AUTHORITIES == {
        "market_bars": "binance",
        "trades": "binance",
        "aggregate_trades": "binance",
        "book_snapshots": "binance",
        "funding": "bybit",
        "open_interest": "bybit",
        "long_short_ratio": "bybit",
        "mark_bars": "bybit",
        "index_bars": "bybit",
        "premium_bars": "bybit",
        "option_instruments": "bybit",
        "option_quotes": "bybit",
        "historical_volatility": "bybit",
        "asset_metadata": "coingecko",
        "market_reference": "coingecko",
        "onchain_metrics": "coinmetrics",
        "dex_pools": "geckoterminal",
        "dex_ohlcv": "geckoterminal",
        "dex_transactions": "geckoterminal",
        "comparison_bars": "ccxt:coinbase",
    }


def test_asset_identity_normalizes_and_checks_lifecycle() -> None:
    asset = CryptoAssetIdentityV1(
        coingecko_id=" usd-coin ",
        network="Ethereum",
        contract_address="0xABC",
        native_asset=False,
        provider_symbols=(("binance", "USDC"),),
        valid_from=datetime(2018, 9, 26, tzinfo=UTC),
        valid_to=datetime(2026, 1, 1, tzinfo=UTC),
        migration_lineage=("legacy-usdc",),
    )
    assert asset.contract_address == "0xabc"
    assert asset.to_dict()["valid_to"] == "2026-01-01T00:00:00Z"

    with pytest.raises(DataError, match="valid_to"):
        CryptoAssetIdentityV1(**{**asset.__dict__, "valid_to": datetime(2010, 1, 1, tzinfo=UTC)})
    with pytest.raises(DataError, match="native_asset"):
        CryptoAssetIdentityV1(**{**asset.__dict__, "native_asset": "false"})
    with pytest.raises(DataError, match="migration lineage"):
        CryptoAssetIdentityV1(**{**asset.__dict__, "migration_lineage": ("",)})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"family": "unknown"}, "family"),
        ({"market_type": "future"}, "market type"),
        ({"provider": ""}, "provider"),
    ],
)
def test_dataset_identity_rejects_unknown_or_empty_fields(
    change: dict[str, object], message: str
) -> None:
    with pytest.raises(DataError, match=message):
        CryptoDatasetIdentityV1(**(_dataset().__dict__ | change))

    with pytest.raises(DataError, match="invalid CryptoDatasetIdentityV1"):
        CryptoDatasetIdentityV1.from_dict({"schema_version": 1})
    with pytest.raises(DataError, match="invalid CryptoDatasetIdentityV1"):
        CryptoDatasetIdentityV1.from_dict({"schema_version": 2})


def test_receipt_quality_and_capability_contracts_are_honest() -> None:
    receipt = CryptoRawReceiptV1.create(
        dataset=_dataset(),
        request=(("symbol", "BTCUSDT"),),
        fetched_at=datetime(2026, 8, 14, tzinfo=UTC),
        response_sha256="a" * 64,
        response_bytes=10,
        provider_schema="binance-klines-v1",
        parser_version="1",
        pagination=("page-1",),
        upstream_checksum="b" * 64,
    )
    assert receipt.to_dict()["upstream_checksum"] == "b" * 64

    report = CryptoQualityReportV1(
        dataset_sha256=_dataset().content_sha256,
        method_version="quality-v1",
        state="warning",
        failures=("cadence_gap",),
        warnings=("partial_tail",),
        observed_start=datetime(2020, 1, 1, tzinfo=UTC),
        observed_end=datetime(2026, 1, 1, tzinfo=UTC),
        row_count=100,
        correction_lineage=("receipt-old",),
    )
    assert report.to_dict()["row_count"] == 100
    assert CryptoQualityReportV1.from_dict(report.to_dict()) == report
    with pytest.raises(DataError, match="cannot contain failures"):
        CryptoQualityReportV1(**{**report.__dict__, "state": "qualified"})
    with pytest.raises(DataError, match="row_count"):
        CryptoQualityReportV1(**{**report.__dict__, "row_count": -1})

    capability = ProviderDatasetCapabilityV1(
        provider="bybit",
        family="funding",
        authentication="none",
        earliest=datetime(2020, 1, 1, tzinfo=UTC),
        latest=datetime(2026, 1, 1, tzinfo=UTC),
        frequencies=("funding_interval",),
        limits=("200_per_page",),
        verification_state="verified",
        qualification_state="qualified",
    )
    assert capability.to_dict()["family"] == "funding"
    with pytest.raises(DataError, match="latest precedes"):
        ProviderDatasetCapabilityV1(
            **{
                **capability.__dict__,
                "latest": datetime(2019, 1, 1, tzinfo=UTC),
            }
        )


def test_receipt_and_snapshot_reject_malformed_values() -> None:
    receipt_values = {
        "dataset": _dataset(),
        "request": (("symbol", "BTCUSDT"),),
        "fetched_at": datetime(2026, 8, 14, tzinfo=UTC),
        "response_sha256": "a" * 64,
        "response_bytes": 10,
        "provider_schema": "schema",
        "parser_version": "1",
        "pagination": (),
        "upstream_checksum": None,
    }
    with pytest.raises(DataError, match="timezone-aware"):
        CryptoRawReceiptV1.create(
            **{**receipt_values, "fetched_at": datetime(2026, 8, 14)}  # type: ignore[arg-type]
        )
    with pytest.raises(DataError, match="response_bytes"):
        CryptoRawReceiptV1.create(
            **{**receipt_values, "response_bytes": -1}  # type: ignore[arg-type]
        )
    with pytest.raises(DataError, match="pagination"):
        CryptoRawReceiptV1.create(**{**receipt_values, "pagination": ["bad"]})  # type: ignore[arg-type]

    member = CryptoSnapshotMemberV1(
        dataset=_dataset(), artifact_key="raw/binance/a", artifact_sha256="a" * 64
    )
    with pytest.raises(DataError, match="safe logical path"):
        CryptoSnapshotMemberV1(
            dataset=_dataset(), artifact_key="../private", artifact_sha256="a" * 64
        )
    with pytest.raises(DataError, match="invalid CryptoSnapshotMemberV1"):
        CryptoSnapshotMemberV1.from_dict({})
    with pytest.raises(DataError, match="ordered membership"):
        CryptoSnapshotV1.create(
            members=(), asset_master_version="am_1", qualification_versions=("q1",)
        )
    snapshot = CryptoSnapshotV1.create(
        members=(member,), asset_master_version="am_1", qualification_versions=("q1",)
    )
    with pytest.raises(DataError, match="identity"):
        CryptoSnapshotV1(**{**snapshot.__dict__, "snapshot_id": "b" * 64})
    with pytest.raises(DataError, match="invalid CryptoSnapshotV1"):
        CryptoSnapshotV1.from_dict({"schema_version": 2})
    with pytest.raises(DataError, match="members"):
        CryptoSnapshotV1.from_dict({**snapshot.to_dict(), "members": "bad"})
