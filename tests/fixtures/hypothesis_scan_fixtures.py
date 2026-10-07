"""Small deterministic frozen stores for screening integration tests."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from alpha_data.crypto.contracts import CryptoQualityReportV1
from alpha_data.crypto.quality import QUALITY_METHOD_VERSION
from alpha_data.crypto.storage import CryptoBulkStore
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore
from tests.fixtures.cli_fixtures import seed_store


def frozen_equities(root: Path) -> None:
    for index, symbol in enumerate(("A", "B", "C", "D", "E")):
        seed_store(root, symbol=symbol, n=100, seed=index)
    create_snapshot(
        ParquetStore(root / "store"),
        root / "snapshots",
        "frozen",
        list("ABCDE"),
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2020, 4, 10, tzinfo=UTC),
    )


def crypto_store(root: Path) -> CryptoBulkStore:
    return CryptoBulkStore(
        bulk_root=root / "bulk",
        manifest_root=root / "crypto" / "manifests",
        expected_volume_uuid="fixture",
    )


def crypto_manifest(
    store: CryptoBulkStore,
    dataset: dict[str, Any],
    frame: pl.DataFrame,
    *,
    fetched_at: str = "2020-03-01T00:00:00Z",
) -> dict[str, object]:
    buffer = io.BytesIO()
    frame.write_parquet(buffer)
    raw = buffer.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    key = f"fixtures/{digest}.parquet"
    path = store.bulk_root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    parent = store._publish_manifest(
        {
            "artifact_kind": "raw",
            "artifact_key": key,
            "artifact_sha256": digest,
            "artifact_bytes": len(raw),
            "receipt": {"fetched_at": fetched_at},
        }
    )
    return store._publish_manifest(
        {
            "artifact_kind": "normalized",
            "artifact_key": key,
            "artifact_sha256": digest,
            "artifact_bytes": len(raw),
            "dataset": dataset,
            "input_manifest_ids": [parent["manifest_id"]],
            "quality": CryptoQualityReportV1(
                dataset_sha256=digest,
                method_version=QUALITY_METHOD_VERSION,
                state="qualified",
                failures=(),
                warnings=(),
                observed_start=None,
                observed_end=None,
                row_count=frame.height,
                correction_lineage=(),
            ).to_dict(),
        }
    )


def frozen_crypto(root: Path) -> CryptoBulkStore:
    from alpha_cli._crypto_panel import FAMILIES

    store = crypto_store(root)
    for column, symbol in enumerate(("AAAUSDT", "BBBUSDT", "CCCUSDT")):
        for family, (frequency, units, convention, value_name) in FAMILIES.items():
            dataset = {
                "schema_version": 1,
                "provider": "bybit",
                "venue": "bybit",
                "market_type": "linear",
                "family": family,
                "instrument": symbol,
                "base_asset": symbol[:-4],
                "quote_asset": "USDT",
                "frequency": frequency,
                "units": units,
                "timestamp_convention": convention,
            }
            rows = [
                {
                    "timestamp": datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i),
                    "symbol": symbol,
                    "category": "linear",
                    value_name: 100.0 + i * (column + 1) + (i % (column + 2)),
                }
                for i in range(55)
            ]
            crypto_manifest(store, dataset, pl.DataFrame(rows))
    return store
