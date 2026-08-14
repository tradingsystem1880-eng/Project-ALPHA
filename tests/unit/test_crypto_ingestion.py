from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.providers.bybit import parse_funding_history
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

UUID = "758CBD77-1003-3BA3-AD28-1D647F5E2A08"
NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _store(tmp_path: Path) -> CryptoBulkStore:
    bulk = tmp_path / "bulk"
    bulk.mkdir(parents=True)
    return CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid=UUID,
        volume_uuid=lambda _: UUID,
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=1_000_000),
        minimum_free_bytes=100,
    )


def _payload(rate: str = "0.0001") -> bytes:
    return json.dumps(
        {
            "retCode": 0,
            "time": 1_786_752_000_000,
            "result": {
                "category": "linear",
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "fundingRate": rate,
                        "fundingRateTimestamp": "1786752000000",
                    }
                ],
            },
        }
    ).encode()


def _dataset() -> CryptoDatasetIdentityV1:
    return CryptoDatasetIdentityV1(
        provider="bybit",
        venue="bybit",
        market_type="linear",
        family="funding",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="funding_interval",
        units="dimensionless_rate",
        timestamp_convention="provider_event_utc",
    )


def test_provider_payload_freezes_raw_normalized_quality_and_offline_replay(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = ingest_provider_payload(
        store,
        dataset=_dataset(),
        payload=_payload(),
        request=(("endpoint", "funding"), ("symbol", "BTCUSDT")),
        fetched_at=NOW,
        provider_schema="bybit-v5",
        parser_version="bybit-public-v1",
        logical_name="funding.json",
        parser=parse_funding_history,
        observed_column="timestamp",
        key_columns=("timestamp", "symbol"),
    )

    assert result.quality.state == "qualified"
    assert result.raw_manifest["artifact_kind"] == "raw"
    assert result.normalized_manifest["artifact_kind"] == "normalized"
    assert result.normalized_manifest["input_manifest_ids"] == [result.raw_manifest["manifest_id"]]
    assert result.receipt.response_sha256 == result.raw_manifest["artifact_sha256"]
    assert store.verify_manifest(result.raw_manifest["manifest_id"]) == result.raw_manifest
    assert (
        store.verify_manifest(result.normalized_manifest["manifest_id"])
        == result.normalized_manifest
    )

    raw_path = store.bulk_root / str(result.raw_manifest["artifact_key"])
    assert parse_funding_history(raw_path.read_bytes()).equals(parse_funding_history(_payload()))


def test_provider_payload_preserves_raw_receipt_when_parsing_fails(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(DataError, match="fundingRate"):
        ingest_provider_payload(
            store,
            dataset=_dataset(),
            payload=_payload("not-a-number"),
            request=(("endpoint", "funding"),),
            fetched_at=NOW,
            provider_schema="bybit-v5",
            parser_version="bybit-public-v1",
            logical_name="funding.json",
            parser=parse_funding_history,
            observed_column="timestamp",
            key_columns=("timestamp", "symbol"),
        )

    inventory = store.inventory()
    assert len(inventory) == 1
    assert inventory[0]["artifact_kind"] == "raw"
