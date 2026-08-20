"""Atomic raw-to-normalized crypto ingestion with exact quality bindings."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import polars as pl

from alpha_core import DataError

from .contracts import (
    CryptoAcquisitionScopeV1,
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
)
from .quality import qualify_crypto_frame
from .storage import CryptoBulkStore


@dataclass(frozen=True)
class CryptoIngestionResultV1:
    receipt: CryptoRawReceiptV1
    raw_manifest: dict[str, object]
    normalized_manifest: dict[str, object]
    quality: CryptoQualityReportV1
    schema_version: int = 1


@dataclass(frozen=True)
class CryptoPagedIngestionResultV1:
    receipts: tuple[CryptoRawReceiptV1, ...]
    raw_manifests: tuple[dict[str, object], ...]
    normalized_manifest: dict[str, object]
    quality: CryptoQualityReportV1
    schema_version: int = 1


def ingest_provider_payload(
    store: CryptoBulkStore,
    *,
    dataset: CryptoDatasetIdentityV1,
    payload: bytes,
    request: tuple[tuple[str, str], ...],
    fetched_at: datetime,
    provider_schema: str,
    parser_version: str,
    logical_name: str,
    parser: Callable[[bytes], pl.DataFrame],
    observed_column: str,
    key_columns: tuple[str, ...],
    pagination: tuple[str, ...] = (),
    upstream_checksum: str | None = None,
    expected_cadence: timedelta | None = None,
    period_start_timestamps: bool = False,
    availability_column: str | None = None,
    correction_lineage: tuple[str, ...] = (),
    unexplained_revision: bool = False,
    acquisition_scope: CryptoAcquisitionScopeV1 | None = None,
) -> CryptoIngestionResultV1:
    """Freeze exact provider bytes before parsing, then publish qualified Parquet separately."""
    receipt, raw_manifest = _stage_one_page(
        store,
        dataset=dataset,
        payload=payload,
        request=request,
        pagination=pagination,
        fetched_at=fetched_at,
        provider_schema=provider_schema,
        parser_version=parser_version,
        logical_name=logical_name,
        upstream_checksum=upstream_checksum,
        empty_payload_error="crypto provider payload must be non-empty bytes",
    )
    quality, normalized_manifest = _publish_qualified(
        store,
        parser(payload),
        dataset=dataset,
        input_manifest_ids=(str(raw_manifest["manifest_id"]),),
        fetched_at=fetched_at,
        observed_column=observed_column,
        key_columns=key_columns,
        expected_cadence=expected_cadence,
        period_start_timestamps=period_start_timestamps,
        availability_column=availability_column,
        correction_lineage=correction_lineage,
        unexplained_revision=unexplained_revision,
        acquisition_scope=acquisition_scope,
    )
    return CryptoIngestionResultV1(
        receipt=receipt,
        raw_manifest=raw_manifest,
        normalized_manifest=normalized_manifest,
        quality=quality,
    )


def ingest_provider_pages(
    store: CryptoBulkStore,
    *,
    dataset: CryptoDatasetIdentityV1,
    pages: tuple[tuple[bytes, tuple[tuple[str, str], ...], tuple[str, ...]], ...],
    fetched_at: datetime,
    provider_schema: str,
    parser_version: str,
    logical_name: str,
    parser: Callable[[bytes], pl.DataFrame],
    observed_column: str,
    key_columns: tuple[str, ...],
    page_parsers: tuple[Callable[[bytes], pl.DataFrame], ...] | None = None,
    upstream_checksums: tuple[str | None, ...] | None = None,
    combine_frames: Callable[[tuple[pl.DataFrame, ...]], pl.DataFrame] | None = None,
    expected_cadence: timedelta | None = None,
    period_start_timestamps: bool = False,
    availability_column: str | None = None,
    correction_lineage: tuple[str, ...] = (),
    unexplained_revision: bool = False,
    acquisition_scope: CryptoAcquisitionScopeV1 | None = None,
) -> CryptoPagedIngestionResultV1:
    """Freeze every exact provider page, then qualify one deterministically ordered dataset."""
    if not pages or len(pages) > 100:
        raise DataError("crypto paged ingestion requires between 1 and 100 pages")
    parsers = page_parsers or tuple(parser for _ in pages)
    checksums = upstream_checksums or tuple(None for _ in pages)
    if len(parsers) != len(pages) or len(checksums) != len(pages):
        raise DataError("crypto paged ingestion resource contracts do not match page count")
    receipts: list[CryptoRawReceiptV1] = []
    raw_manifests: list[dict[str, object]] = []
    for page_number, ((payload, request, pagination), checksum) in enumerate(
        zip(pages, checksums, strict=True), start=1
    ):
        receipt, raw_manifest = _stage_one_page(
            store,
            dataset=dataset,
            payload=payload,
            request=request,
            pagination=pagination,
            fetched_at=fetched_at,
            provider_schema=provider_schema,
            parser_version=parser_version,
            logical_name=f"page-{page_number:03d}-{logical_name}",
            upstream_checksum=checksum,
            empty_payload_error="crypto provider page must be non-empty bytes",
        )
        raw_manifests.append(raw_manifest)
        receipts.append(receipt)

    frames = tuple(
        page_parser(payload) for page_parser, (payload, _, _) in zip(parsers, pages, strict=True)
    )
    frame = (
        combine_frames(frames)
        if combine_frames is not None
        else pl.concat(frames, how="vertical_relaxed").sort(list(key_columns))
    )
    quality, normalized_manifest = _publish_qualified(
        store,
        frame,
        dataset=dataset,
        input_manifest_ids=tuple(str(item["manifest_id"]) for item in raw_manifests),
        fetched_at=fetched_at,
        observed_column=observed_column,
        key_columns=key_columns,
        expected_cadence=expected_cadence,
        period_start_timestamps=period_start_timestamps,
        availability_column=availability_column,
        correction_lineage=correction_lineage,
        unexplained_revision=unexplained_revision,
        acquisition_scope=acquisition_scope,
    )
    return CryptoPagedIngestionResultV1(
        receipts=tuple(receipts),
        raw_manifests=tuple(raw_manifests),
        normalized_manifest=normalized_manifest,
        quality=quality,
    )


def _stage_one_page(
    store: CryptoBulkStore,
    *,
    dataset: CryptoDatasetIdentityV1,
    payload: bytes,
    request: tuple[tuple[str, str], ...],
    pagination: tuple[str, ...],
    fetched_at: datetime,
    provider_schema: str,
    parser_version: str,
    logical_name: str,
    upstream_checksum: str | None,
    empty_payload_error: str,
) -> tuple[CryptoRawReceiptV1, dict[str, object]]:
    """Freeze one payload's exact bytes under its receipt before anything parses them."""
    if not isinstance(payload, bytes) or not payload:
        raise DataError(empty_payload_error)
    response_hash = hashlib.sha256(payload).hexdigest()
    receipt = CryptoRawReceiptV1.create(
        dataset=dataset,
        request=request,
        fetched_at=fetched_at,
        response_sha256=response_hash,
        response_bytes=len(payload),
        provider_schema=provider_schema,
        parser_version=parser_version,
        pagination=pagination,
        upstream_checksum=upstream_checksum,
    )
    handle = store.begin_staging(
        provider=dataset.provider,
        receipt_id=receipt.receipt_id,
        logical_name=logical_name,
        expected_bytes=len(payload),
    )
    handle = store.resume_payload(handle, payload)
    raw_manifest = store.publish_staging(handle, expected_sha256=response_hash, receipt=receipt)
    return receipt, raw_manifest


def _publish_qualified(
    store: CryptoBulkStore,
    frame: pl.DataFrame,
    *,
    dataset: CryptoDatasetIdentityV1,
    input_manifest_ids: tuple[str, ...],
    fetched_at: datetime,
    observed_column: str,
    key_columns: tuple[str, ...],
    expected_cadence: timedelta | None,
    period_start_timestamps: bool,
    availability_column: str | None,
    correction_lineage: tuple[str, ...],
    unexplained_revision: bool,
    acquisition_scope: CryptoAcquisitionScopeV1 | None,
) -> tuple[CryptoQualityReportV1, dict[str, object]]:
    """Qualify one normalized frame and publish it against its exact raw lineage."""
    output = io.BytesIO()
    frame.write_parquet(output, compression="zstd", statistics=True)
    normalized = output.getvalue()
    quality = qualify_crypto_frame(
        dataset,
        frame,
        artifact_sha256=hashlib.sha256(normalized).hexdigest(),
        observed_column=observed_column,
        key_columns=key_columns,
        knowledge_time=fetched_at,
        as_of=fetched_at,
        expected_cadence=expected_cadence,
        period_start_timestamps=period_start_timestamps,
        availability_column=availability_column,
        correction_lineage=correction_lineage,
        unexplained_revision=unexplained_revision,
    )
    normalized_manifest = store.publish_normalized(
        normalized,
        dataset=dataset,
        input_manifest_ids=input_manifest_ids,
        quality=quality,
        acquisition_scope=acquisition_scope,
    )
    return quality, normalized_manifest


__all__ = [
    "CryptoIngestionResultV1",
    "CryptoPagedIngestionResultV1",
    "ingest_provider_pages",
    "ingest_provider_payload",
]
