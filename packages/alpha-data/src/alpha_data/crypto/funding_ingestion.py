"""Offline composition of real raw retention and the funding-page collector.

Shelved (2026-11-14, triage card B): not wired in, kept for funding-event research; real
downloads wait on the durable acquisition journal.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, cast

from alpha_core import DataError

from .contracts import CryptoDatasetIdentityV1
from .ingestion import retain_provider_payload
from .providers.bybit_funding import FundingPageCollection, PageSupplier, collect_funding_pages
from .storage import CryptoBulkStore


def collect_retained_funding_pages(
    store: CryptoBulkStore,
    supply_page: PageSupplier,
    *,
    dataset: CryptoDatasetIdentityV1,
    fetched_at: datetime,
    start_ms: int,
    end_ms: int,
    max_calls: int = 10,
    max_total_bytes: int = 8 * 1024 * 1024,
) -> tuple[FundingPageCollection, tuple[dict[str, object], ...]]:
    """Raw-publish and verify each bounded body before any funding decoder sees it.

    No supplier is installed or registered here. On decode/collection failure, raw
    manifests remain discoverable through the existing store inventory; no partial
    collection, normalized data, quality admission or snapshot is published.
    """
    if (
        dataset.provider != "bybit"
        or dataset.venue != "bybit"
        or dataset.family != "funding"
        or dataset.market_type not in {"linear", "inverse"}
        or dataset.frequency != "funding_interval"
        or dataset.units != "dimensionless_rate"
        or dataset.timestamp_convention != "provider_event_utc"
    ):
        raise DataError("raw funding retention requires an exact native Bybit funding identity")
    manifests: list[dict[str, object]] = []

    def retained(params: dict[str, str | int], allowance: int) -> bytes:
        # Freeze request identity before the untrusted callback can mutate its argument.
        request = (
            ("endpoint", "funding"),
            *((key, str(value)) for key, value in sorted(params.items())),
        )
        pagination = (f"endTime={params['endTime']}",)
        store.verify_ready(required_bytes=allowance)
        payload = supply_page(params, allowance)
        _, manifest = retain_provider_payload(
            store,
            dataset=dataset,
            payload=payload,
            request=request,
            fetched_at=fetched_at,
            provider_schema="bybit-v5",
            parser_version="bybit-public-v1",
            logical_name="funding.json",
            max_payload_bytes=allowance,
            pagination=pagination,
        )
        manifests.append(manifest)
        return payload

    result = collect_funding_pages(
        retained,
        symbol=dataset.instrument,
        category=cast(Literal["linear", "inverse"], dataset.market_type),
        fetched_at=fetched_at,
        start_ms=start_ms,
        end_ms=end_ms,
        max_calls=max_calls,
        max_total_bytes=max_total_bytes,
    )
    return result, tuple(manifests)
