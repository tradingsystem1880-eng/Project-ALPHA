"""Local pool discovery must verify exact source bytes and lineage."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_cli._crypto_yield_catalog import yield_catalog
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.storage import Capacity, CryptoBulkStore


def _publish_yield_catalog(
    root: Path, frame: pl.DataFrame
) -> tuple[CryptoBulkStore, dict[str, object], dict[str, object]]:
    root.mkdir(parents=True, exist_ok=True)
    bulk = root / "bulk"
    bulk.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=root / "manifests",
        expected_volume_uuid="test",
        volume_uuid=lambda _: "test",
        capacity=lambda _: Capacity(total_bytes=1000000, free_bytes=900000),
        minimum_free_bytes=0,
    )
    handle = store.begin_staging(
        provider="defillama", receipt_id="catalog", logical_name="pools.json", expected_bytes=3
    )
    handle = store.append_staging(handle, b"raw")
    raw = store.publish_staging(handle, expected_sha256=hashlib.sha256(b"raw").hexdigest())
    buffer = io.BytesIO()
    frame.write_parquet(buffer)
    payload = buffer.getvalue()
    now = datetime(2026, 10, 2, tzinfo=UTC)
    dataset = CryptoDatasetIdentityV1(
        provider="defillama",
        venue="defillama",
        market_type="reference",
        family="yield_pools",
        instrument="all",
        base_asset=None,
        quote_asset="USD",
        frequency="catalog_snapshot",
        units="usd_tvl_and_percent_apy",
        timestamp_convention="provider_observation_utc",
    )
    quality = CryptoQualityReportV1(
        dataset_sha256=hashlib.sha256(payload).hexdigest(),
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=now,
        observed_end=now,
        row_count=frame.height,
        correction_lineage=(),
    )
    normalized = store.publish_normalized(
        payload, dataset=dataset, input_manifest_ids=(str(raw["manifest_id"]),), quality=quality
    )
    return store, raw, normalized


def test_yield_catalog_literal_search_bound_and_raw_lineage(tmp_path: Path) -> None:
    frame = pl.DataFrame(
        {
            "pool_id": ["a", "b"],
            "project": ["aave-v3", "uniswap"],
            "chain": ["Ethereum", "Ethereum"],
            "symbol": ["WEETH", "ETH[USDC]"],
            "tvl_usd": [200.0, 100.0],
            "apy": [1.2, 2.3],
        }
    )
    store, raw, _ = _publish_yield_catalog(tmp_path, frame)
    result = yield_catalog(store, query="ETH", limit=1)
    assert result["total_matches"] == 2
    assert isinstance(result["items"], list)
    assert result["items"][0]["pool_id"] == "a"
    assert yield_catalog(store, query="[", limit=10)["total_matches"] == 1
    for query, limit in (("x" * 81, 10), ("", 101), ("", 0)):
        with pytest.raises(DataError, match="search requires"):
            yield_catalog(store, query=query, limit=limit)
    (store.bulk_root / str(raw["artifact_key"])).write_bytes(b"BAD")
    with pytest.raises(DataError, match="integrity"):
        yield_catalog(store, query="", limit=10)


def test_yield_catalog_tie_order_is_stable_across_physical_row_order(tmp_path: Path) -> None:
    frame = pl.DataFrame(
        {
            "pool_id": ["z", "b", "a", "m"],
            "project": ["eth-z", "eth-b", "eth-a", "eth-m"],
            "chain": ["Ethereum"] * 4,
            "symbol": ["ETH"] * 4,
            "tvl_usd": [10.0, 10.0, 10.0, 8.0],
            "apy": [1.0, 2.0, 3.0, 4.0],
        }
    )
    forward_store, _, forward_manifest = _publish_yield_catalog(tmp_path / "forward", frame)
    reverse_store, _, reverse_manifest = _publish_yield_catalog(
        tmp_path / "reverse", frame.reverse()
    )

    forward = yield_catalog(forward_store, query=" ETH ", limit=100)
    reverse = yield_catalog(reverse_store, query=" ETH ", limit=100)
    assert isinstance(forward["items"], list)
    assert isinstance(reverse["items"], list)
    forward_items = forward["items"]
    reverse_items = reverse["items"]
    assert forward["total_matches"] == reverse["total_matches"] == 4
    assert [item["pool_id"] for item in forward_items] == ["a", "b", "z", "m"]
    assert forward_items == reverse_items
    assert len(forward_items) == 4
    assert forward["manifest_id"] == forward_manifest["manifest_id"]
    assert reverse["manifest_id"] == reverse_manifest["manifest_id"]
    assert forward["captured_at"] == reverse["captured_at"] == "2026-10-02T00:00:00+00:00"

    empty = yield_catalog(forward_store, query="no-such-pool", limit=100)
    assert empty["total_matches"] == 0
    assert empty["items"] == []
    assert empty["manifest_id"] == forward_manifest["manifest_id"]


def test_yield_catalog_fails_closed_on_normalized_artifact_tamper(tmp_path: Path) -> None:
    frame = pl.DataFrame(
        {
            "pool_id": ["a"],
            "project": ["aave-v3"],
            "chain": ["Ethereum"],
            "symbol": ["ETH"],
            "tvl_usd": [200.0],
            "apy": [1.2],
        }
    )
    store, _, normalized = _publish_yield_catalog(tmp_path, frame)
    artifact = store.bulk_root / str(normalized["artifact_key"])
    artifact.write_bytes(artifact.read_bytes() + b"tamper")

    with pytest.raises(DataError, match="integrity"):
        yield_catalog(store, query="ETH", limit=1)
