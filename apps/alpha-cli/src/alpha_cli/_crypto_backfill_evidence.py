"""Verify retained backfill outputs through the existing raw/normalized store.

This is an explicit resume preflight, not data qualification, coverage, quota or
research authority. Warning/quarantined captures keep their original quality state.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import cast

from alpha_cli._crypto_acquisition import bybit_plan
from alpha_cli._crypto_backfill import BackfillWindow, split_symbol
from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoFamily,
    CryptoMarketType,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
)
from alpha_data.crypto.storage import CryptoBulkStore
from alpha_data.crypto.verification import ArtifactVerificationBudget, MetadataVerificationBudget


def verify_completed_window(
    store: CryptoBulkStore,
    symbol: str,
    window: BackfillWindow,
    entry: Mapping[str, object],
    *,
    provider: str,
    family: CryptoFamily,
    category: str,
    frequency: str,
    quote: str,
    now: datetime,
    budget: ArtifactVerificationBudget | None = None,
    metadata_budget: MetadataVerificationBudget | None = None,
) -> None:
    """Reopen one v1 completion; never repair it or repeat a provider request."""
    manifest_id = entry.get("manifest_id")
    if not isinstance(manifest_id, str) or re.fullmatch(r"[0-9a-f]{64}", manifest_id) is None:
        raise DataError("completed backfill window has no verifiable manifest identity")
    base, quote_asset = split_symbol(symbol, quote=quote)
    if provider == "bybit":
        plan = bybit_plan(
            family,
            symbol,
            base=base,
            quote=quote_asset,
            category=category,
            frequency=frequency,
            start=window.start,
            end=window.end,
            fetched_at=now,
        )
        expected = plan.dataset
        request = {key: str(value) for key, value in plan.params.items() if key != "cursor"}
    elif provider == "binance" and family == "market_bars" and window.period is not None:
        expected = CryptoDatasetIdentityV1(
            provider="binance",
            venue="binance",
            market_type=cast(CryptoMarketType, category),
            family=family,
            instrument=symbol,
            base_asset=base,
            quote_asset=quote_asset,
            frequency=frequency,
            units="provider_native_ohlcv",
            timestamp_convention="interval_start_utc",
        )
        request = {
            "market": {"spot": "spot", "linear": "um", "inverse": "cm"}[category],
            "family": "klines",
            "symbol": symbol,
            "period": window.period,
            "interval": frequency,
        }
    else:
        raise DataError("completed backfill window has an unsupported request identity")
    store.verify_readable()  # root identity only; no write probe
    if metadata_budget is None:
        store.require_active(manifest_id)
        manifest = store.verify_manifest(manifest_id, budget=budget)
    else:
        store.require_active(manifest_id, metadata_budget=metadata_budget)
        manifest = store.verify_manifest(
            manifest_id, budget=budget, metadata_budget=metadata_budget
        )
    if (
        manifest.get("artifact_kind") != "normalized"
        or manifest.get("dataset") != expected.to_dict()
    ):
        raise DataError("completed backfill artifact kind or dataset identity differs")
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    if quality.dataset_sha256 != manifest.get("artifact_sha256") or quality.state != entry.get(
        "quality_state"
    ):
        raise DataError("completed backfill quality binding differs")
    input_ids = manifest.get("input_manifest_ids")
    assert isinstance(input_ids, list)  # verify_manifest validates nonempty unique lineage
    for input_id in input_ids:
        if metadata_budget is None:
            store.require_active(input_id)
            raw = store.verify_manifest(input_id, budget=budget)
        else:
            store.require_active(input_id, metadata_budget=metadata_budget)
            raw = store.verify_manifest(input_id, budget=budget, metadata_budget=metadata_budget)
        receipt = CryptoRawReceiptV1.from_dict(raw.get("receipt"))
        actual_request = dict(receipt.request)
        if (
            receipt.dataset != expected
            or receipt.response_sha256 != raw.get("artifact_sha256")
            or receipt.response_bytes != raw.get("artifact_bytes")
            or any(actual_request.get(key) != value for key, value in request.items())
        ):
            raise DataError("completed backfill raw receipt does not bind the requested window")
