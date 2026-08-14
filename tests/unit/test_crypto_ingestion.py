from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1
from alpha_data.crypto.ingestion import ingest_provider_pages, ingest_provider_payload
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
    assert result.raw_manifest["receipt"] == result.receipt.to_dict()
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


def test_paged_ingestion_preserves_each_exact_response_and_binds_all_inputs(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    first = b"timestamp,value\n2026-08-14T00:00:00Z,1\n"
    second = b"timestamp,value\n2026-08-14T01:00:00Z,2\n"

    result = ingest_provider_pages(
        store,
        dataset=_dataset(),
        pages=(
            (first, (("page", "1"),), ("next=cursor-a",)),
            (second, (("cursor", "cursor-a"), ("page", "2")), ("terminal",)),
        ),
        fetched_at=NOW,
        provider_schema="fixture-v1",
        parser_version="fixture-parser-v1",
        logical_name="page.csv",
        parser=lambda payload: pl.read_csv(io.BytesIO(payload), try_parse_dates=True),
        observed_column="timestamp",
        key_columns=("timestamp",),
    )

    assert len(result.receipts) == 2
    assert len(result.raw_manifests) == 2
    assert result.normalized_manifest["input_manifest_ids"] == [
        manifest["manifest_id"] for manifest in result.raw_manifests
    ]
    assert result.quality.row_count == 2
    for manifest, payload in zip(result.raw_manifests, (first, second), strict=True):
        assert (store.bulk_root / str(manifest["artifact_key"])).read_bytes() == payload


def test_paged_ingestion_freezes_all_fetched_pages_before_parser_failure(tmp_path: Path) -> None:
    store = _store(tmp_path)
    pages = (
        (b"first-invalid-page", (("page", "1"),), ("next=cursor",)),
        (b"second-invalid-page", (("page", "2"),), ("terminal",)),
    )

    with pytest.raises(DataError, match="response is malformed"):
        ingest_provider_pages(
            store,
            dataset=_dataset(),
            pages=pages,
            fetched_at=NOW,
            provider_schema="fixture-v1",
            parser_version="fixture-parser-v1",
            logical_name="page.json",
            parser=parse_funding_history,
            observed_column="timestamp",
            key_columns=("timestamp",),
        )

    assert [item["artifact_kind"] for item in store.inventory()] == ["raw", "raw"]


def test_paged_ingestion_supports_exact_heterogeneous_resources_and_combiner(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    archive = b"2026-08-14T00:00:00Z,1\n"
    tail = b'{"timestamp":"2026-08-14T01:00:00Z","value":2}'
    checksum = hashlib.sha256(archive).hexdigest()

    def parse_archive(payload: bytes) -> pl.DataFrame:
        return pl.read_csv(
            io.BytesIO(payload),
            has_header=False,
            new_columns=["timestamp", "value"],
            try_parse_dates=True,
        )

    def parse_tail(payload: bytes) -> pl.DataFrame:
        record = json.loads(payload)
        return pl.DataFrame(
            {
                "timestamp": [datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))],
                "value": [record["value"]],
            }
        )

    result = ingest_provider_pages(
        store,
        dataset=_dataset(),
        pages=(
            (archive, (("resource", "archive"),), ("historical",)),
            (tail, (("resource", "tail"),), ("unfinished_tail",)),
        ),
        fetched_at=NOW,
        provider_schema="fixture-mixed-v1",
        parser_version="fixture-mixed-parser-v1",
        logical_name="resource.bin",
        parser=parse_archive,
        page_parsers=(parse_archive, parse_tail),
        upstream_checksums=(checksum, None),
        combine_frames=lambda frames: pl.concat(frames).sort("timestamp"),
        observed_column="timestamp",
        key_columns=("timestamp",),
    )

    assert result.quality.row_count == 2
    assert result.receipts[0].upstream_checksum == checksum
    assert result.receipts[1].upstream_checksum is None
