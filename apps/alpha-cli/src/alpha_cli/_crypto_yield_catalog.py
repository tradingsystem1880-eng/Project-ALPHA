"""Bounded pool discovery from an exact verified local DefiLlama catalog."""

from __future__ import annotations

import polars as pl

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoQualityReportV1
from alpha_data.crypto.storage import CryptoBulkStore

from ._crypto_analysis import normalized_member


def empty_yield_catalog() -> dict[str, object]:
    return {
        "state": "unavailable",
        "manifest_id": None,
        "captured_at": None,
        "total_matches": 0,
        "items": [],
        "next_action": "Acquire a DefiLlama yield-pool catalog first.",
    }


def yield_catalog(store: CryptoBulkStore, *, query: str, limit: int) -> dict[str, object]:
    if not 1 <= limit <= 100 or len(query) > 80:
        raise DataError("yield-pool search requires limit 1..100 and at most 80 query characters")
    store.verify_readable()
    candidates: list[tuple[str, str]] = []
    for manifest in store.metadata_inventory():
        dataset = manifest.get("dataset")
        if (
            not isinstance(dataset, dict)
            or dataset.get("provider") != "defillama"
            or dataset.get("family") != "yield_pools"
        ):
            continue
        quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
        if quality.state == "qualified" and quality.observed_end is not None:
            candidates.append((quality.observed_end.isoformat(), str(manifest["manifest_id"])))
    if not candidates:
        return empty_yield_catalog()
    captured_at, manifest_id = max(candidates)
    member, _ = normalized_member(store, manifest_id)
    if member.dataset.frequency != "catalog_snapshot" or member.dataset.instrument != "all":
        raise DataError("yield-pool catalog has the wrong dataset identity")
    try:
        frame = pl.read_parquet(store.bulk_root / member.artifact_key)
        term = query.strip().lower()
        if term:
            frame = frame.filter(
                pl.any_horizontal(
                    [
                        pl.col(column).str.to_lowercase().str.contains(term, literal=True)
                        for column in ("pool_id", "project", "chain", "symbol")
                    ]
                )
            )
        count = frame.height
        items = (
            frame.sort(["tvl_usd", "pool_id"], descending=[True, False])
            .head(limit)
            .select("pool_id", "project", "chain", "symbol", "tvl_usd", "apy")
            .to_dicts()
        )
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError("verified yield-pool catalog is unreadable") from exc
    return {
        "state": "available",
        "manifest_id": manifest_id,
        "captured_at": captured_at,
        "total_matches": count,
        "items": items,
        "next_action": "Select a pool to acquire its provider-reported history.",
    }
