"""Bounded retained-bar diagnostics, never provider coverage or admission authority."""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any

import polars as pl

from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
)
from alpha_data.crypto.quality import (
    DAILY_BAR_AUDIT_COLUMNS,
    DAILY_BAR_AUDIT_NUMERIC_COLUMNS,
    audit_daily_bar_grid,
)
from alpha_data.crypto.storage import CryptoBulkStore
from alpha_data.crypto.verification import (
    DEFAULT_METADATA_READ_BYTES,
    ArtifactVerificationBudget,
    MetadataVerificationBudget,
)


def retained_daily_bar_audit(
    store: CryptoBulkStore,
    manifest_id: str,
    *,
    start: datetime,
    end: datetime,
    as_of: datetime,
    cadence_seconds: int,
    max_hash_bytes: int,
    max_input_bytes: int = 32 * 1024 * 1024,
    max_rows: int = 50000,
    max_missing_ranges: int = 1000,
    max_metadata_bytes: int = DEFAULT_METADATA_READ_BYTES,
) -> dict[str, Any]:
    """Verify selected immutable evidence, decode capped rows, inspect caller grid.

    Hash budget excludes the separately bounded final payload read (<= max_input+1).
    Row limits bound returned rows, not Parquet decoder/decompression peak memory.
    """
    if any(
        type(v) is not int or v < 1
        for v in (max_hash_bytes, max_input_bytes, max_rows, max_missing_ranges, max_metadata_bytes)
    ):
        raise DataError("retained bar audit limits must be positive")
    if max_input_bytes > 32 * 1024 * 1024 or max_rows > 50000 or max_missing_ranges > 1000:
        raise DataError("retained bar audit exceeds supported inspection resource limits")
    hashing = ArtifactVerificationBudget(max_hash_bytes)
    metadata = MetadataVerificationBudget(max_metadata_bytes)
    result: dict[str, Any] = {
        "audit_state": "unavailable",
        "reason": "RETAINED_BAR_AUDIT_UNAVAILABLE",
        "manifest_id": manifest_id if re.fullmatch("[0-9a-f]{64}", manifest_id) else None,
        "execution_authority": False,
        "provider_history_complete": False,
        "point_in_time_eligibility": False,
        "inspection_provider_calls": 0,
        "historical_quota_usage": None,
        "row_audit": None,
        "stored_quality": None,
        "limits": {
            "normalized_payload_bytes": max_input_bytes,
            "payload_read_bytes": max_input_bytes + 1,
            "returned_rows": max_rows,
            "missing_ranges": max_missing_ranges,
            "artifact_hash_bytes": max_hash_bytes,
            "metadata_bytes": max_metadata_bytes,
        },
        "limit_exclusions": [
            "decoder/decompression peak memory",
            "local identity/capacity queries",
            "wall time",
        ],
        "next_action": "review_retained_evidence_bounds_and_declared_grid",
    }
    try:
        store.require_active(manifest_id, metadata_budget=metadata)
        manifest, payload = store.read_verified_normalized(
            manifest_id, max_bytes=max_input_bytes, budget=hashing, metadata_budget=metadata
        )
        dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
        # Validate supported native identity/grid before decoding bytes.
        if not (
            dataset.provider == dataset.venue == "binance"
            and dataset.market_type == "spot"
            and dataset.family == "market_bars"
            and dataset.frequency == "1d"
            and dataset.units == "provider_native_ohlcv"
            and dataset.timestamp_convention == "interval_start_utc"
            and cadence_seconds == 86400
        ):
            raise DataError("retained bar audit native identity/cadence unsupported")
        quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
        if (
            quality.dataset_sha256 != manifest.get("artifact_sha256")
            or quality.row_count > max_rows
        ):
            raise DataError("retained bar audit quality row/hash binding exceeds bounds")
        parent_ids = manifest.get("input_manifest_ids")
        assert isinstance(parent_ids, list)
        later_capture = False
        for parent_id in parent_ids:
            store.require_active(parent_id, metadata_budget=metadata)
            raw = store.verify_manifest(parent_id, budget=hashing, metadata_budget=metadata)
            receipt = CryptoRawReceiptV1.from_dict(raw.get("receipt"))
            if (
                receipt.dataset != dataset
                or receipt.response_sha256 != raw.get("artifact_sha256")
                or receipt.response_bytes != raw.get("artifact_bytes")
            ):
                raise DataError("retained bar audit source receipt identity differs")
            later_capture = later_capture or receipt.fetched_at > as_of
        schema = pl.read_parquet_schema(io.BytesIO(payload))
        if not set(DAILY_BAR_AUDIT_COLUMNS) <= set(schema):
            raise DataError("retained bar audit Parquet columns unsupported")
        for name in ("open_time", "close_time"):
            dtype = schema[name]
            if not isinstance(dtype, pl.Datetime) or dtype.time_unit not in {"ms", "us"}:
                raise DataError("retained bar audit timestamp precision unsupported")
        numeric = {
            pl.Float32,
            pl.Float64,
            pl.Int8,
            pl.Int16,
            pl.Int32,
            pl.Int64,
            pl.UInt8,
            pl.UInt16,
            pl.UInt32,
            pl.UInt64,
            pl.Null,
        }
        if any(schema[column] not in numeric for column in DAILY_BAR_AUDIT_NUMERIC_COLUMNS):
            raise DataError("retained bar audit numeric Parquet schema unsupported")
        frame = pl.read_parquet(
            io.BytesIO(payload),
            columns=list(DAILY_BAR_AUDIT_COLUMNS),
            n_rows=max_rows + 1,
            parallel="row_groups",
            rechunk=False,
            low_memory=True,
        )
        if frame.height > max_rows or frame.height != quality.row_count:
            raise DataError("retained bar audit actual rows exceed or differ from declared bounds")
        result["row_audit"] = audit_daily_bar_grid(
            dataset,
            frame,
            artifact_sha256=str(manifest["artifact_sha256"]),
            start=start,
            end=end,
            as_of=as_of,
            cadence_seconds=cadence_seconds,
            max_rows=max_rows,
            max_missing_ranges=max_missing_ranges,
        )
        result.update(
            audit_state="inspected",
            reason="RETAINED_GRID_INSPECTED",
            dataset=dataset.to_dict(),
            artifact_sha256=manifest["artifact_sha256"],
            normalized_payload_bytes=len(payload),
            raw_lineage_verified="hash_size_identity_only",
            source_retrieved_after_as_of=later_capture,
            as_of_semantics="declared_grid_closure_cutoff_not_source_vintage",
            stored_quality={
                "state": quality.state,
                "row_count": quality.row_count,
                "method_version": quality.method_version,
                "unchanged": True,
            },
            next_action="review_stored_quality_and_declared_grid_findings_without_automatic_repair",
        )
    except (DataError, OSError, ValueError, TypeError, RecursionError, pl.exceptions.PolarsError):
        result.update(audit_state="unavailable", reason="RETAINED_BAR_AUDIT_UNAVAILABLE")
    result.update(
        hash_bytes_reserved=hashing.reserved_bytes,
        hash_bytes_read=hashing.bytes_read,
        metadata_bytes_reserved=metadata.reserved_bytes,
        metadata_bytes_read=metadata.bytes_read,
    )
    return result
