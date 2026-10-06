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


def test_yield_catalog_literal_search_bound_and_raw_lineage(tmp_path: Path) -> None:
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "manifests",
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
        row_count=2,
        correction_lineage=(),
    )
    store.publish_normalized(
        payload, dataset=dataset, input_manifest_ids=(str(raw["manifest_id"]),), quality=quality
    )
    result = yield_catalog(store, query="ETH", limit=1)
    assert result["total_matches"] == 2
    assert isinstance(result["items"], list)
    assert result["items"][0]["pool_id"] == "a"
    assert yield_catalog(store, query="[", limit=10)["total_matches"] == 1
    for query, limit in (("x" * 81, 10), ("", 101), ("", 0)):
        with pytest.raises(DataError, match="search requires"):
            yield_catalog(store, query=query, limit=limit)
    (bulk / str(raw["artifact_key"])).write_bytes(b"BAD")
    with pytest.raises(DataError, match="integrity"):
        yield_catalog(store, query="", limit=10)
