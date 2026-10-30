"""Bounded, hash-verified query for one frozen DefiLlama chain-TVL member."""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, cast

import polars as pl

from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
    CryptoSnapshotV1,
    require_utc,
)
from alpha_data.crypto.storage import CryptoBulkStore

_MAX_DEFI_TVL_PARQUET_BYTES = 32 * 1024 * 1024
_MAX_DEFI_TVL_ROWS = 50_000
_MAX_QUERY_LIMIT = 1_000
_MAX_QUERY_OFFSET = 100_000
_EXPECTED_COLUMNS = {
    "chain": pl.String(),
    "observed_at": pl.Datetime("us", "UTC"),
    "tvl_usd": pl.Float64(),
    "available_at": pl.Datetime("us", "UTC"),
}


@dataclass(frozen=True)
class DefiTvlObservationV1:
    chain: str
    observed_at: datetime
    tvl_usd: float
    available_at: datetime

    def to_dict(self) -> dict[str, str | float]:
        return {
            "chain": self.chain,
            "observed_at": _utc_text(self.observed_at),
            "tvl_usd": self.tvl_usd,
            "available_at": _utc_text(self.available_at),
        }


@dataclass(frozen=True)
class DefiTvlSnapshotQueryV1:
    snapshot_id: str
    normalized_manifest_id: str
    dataset: CryptoDatasetIdentityV1
    dataset_sha256: str
    artifact_sha256: str
    quality_method_version: str
    source_receipt: CryptoRawReceiptV1
    available_by: datetime | None
    raw_capture_after_available_by: bool | None
    available_row_count: int
    limit: int
    offset: int
    rows: tuple[DefiTvlObservationV1, ...]
    schema_version: Literal[1] = 1
    availability_basis: Literal["defillama_next_utc_day_contract"] = (
        "defillama_next_utc_day_contract"
    )
    point_in_time_claim: Literal[False] = False

    @property
    def units(self) -> str:
        return self.dataset.units

    @property
    def source_fetched_at(self) -> datetime:
        return self.source_receipt.fetched_at

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.rows) < self.available_row_count

    @property
    def next_offset(self) -> int | None:
        return self.offset + len(self.rows) if self.has_more else None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "normalized_manifest_id": self.normalized_manifest_id,
            "dataset": self.dataset.to_dict(),
            "dataset_sha256": self.dataset_sha256,
            "units": self.dataset.units,
            "artifact_sha256": self.artifact_sha256,
            "quality_method_version": self.quality_method_version,
            "source_receipt": {
                "receipt_id": self.source_receipt.receipt_id,
                "fetched_at": _utc_text(self.source_receipt.fetched_at),
                "response_sha256": self.source_receipt.response_sha256,
                "provider_schema": self.source_receipt.provider_schema,
                "parser_version": self.source_receipt.parser_version,
            },
            "availability_basis": self.availability_basis,
            "availability_semantics": (
                "available_at is the parser's next-UTC-day convention, not a source-stamped "
                "historical publication time"
            ),
            "available_by": _utc_text(self.available_by) if self.available_by else None,
            "raw_capture_after_available_by": self.raw_capture_after_available_by,
            "point_in_time_claim": self.point_in_time_claim,
            "available_row_count": self.available_row_count,
            "limit": self.limit,
            "offset": self.offset,
            "returned_row_count": len(self.rows),
            "has_more": self.has_more,
            "next_offset": self.next_offset,
            "rows": [row.to_dict() for row in self.rows],
            "execution_authority": False,
        }


def _utc_text(value: datetime) -> str:
    return require_utc(value, "query timestamp").isoformat().replace("+00:00", "Z")


def parse_available_by(value: str | None) -> datetime | None:
    """Parse one bounded UTC instant used only as an available_at row filter."""
    if value is None:
        return None
    if len(value) > 64 or "T" not in value:
        raise DataError("--available-by must be an ISO-8601 UTC instant")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError("--available-by must be an ISO-8601 UTC instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise DataError("--available-by must include a UTC offset")
    return require_utc(parsed, "available_by")


def _validate_bounds(*, limit: int, offset: int) -> None:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_QUERY_LIMIT:
        raise DataError(f"snapshot query limit must be between 1 and {_MAX_QUERY_LIMIT}")
    if (
        not isinstance(offset, int)
        or isinstance(offset, bool)
        or not 0 <= offset <= _MAX_QUERY_OFFSET
    ):
        raise DataError(f"snapshot query offset must be between 0 and {_MAX_QUERY_OFFSET}")


def _validate_identity(dataset: CryptoDatasetIdentityV1) -> None:
    if (
        dataset.provider != "defillama"
        or dataset.venue != "defillama"
        or dataset.market_type != "network"
        or dataset.family != "defi_tvl"
        or dataset.quote_asset != "USD"
        or dataset.frequency != "1d"
        or dataset.units != "usd"
        or dataset.timestamp_convention != "utc_day_start_available_next_day"
        or re.fullmatch(r"[a-z0-9-]{1,64}", dataset.instrument) is None
    ):
        raise DataError("snapshot query supports only the DefiLlama daily USD defi_tvl identity")


def _selected_manifest(
    store: CryptoBulkStore,
    *,
    dataset: CryptoDatasetIdentityV1,
    artifact_key: str,
    artifact_sha256: str,
    normalized_manifest_id: str | None,
) -> tuple[dict[str, object], bytes, CryptoRawReceiptV1]:
    store.verify_readable()
    matches = [
        item
        for item in store.metadata_inventory()
        if item.get("artifact_kind") == "normalized"
        and item.get("artifact_key") == artifact_key
        and item.get("artifact_sha256") == artifact_sha256
        and item.get("dataset") == dataset.to_dict()
        and (normalized_manifest_id is None or item.get("manifest_id") == normalized_manifest_id)
    ]
    if len(matches) != 1:
        raise DataError(
            "snapshot member normalized manifest is missing or ambiguous; "
            "use --manifest-id with the exact retained normalized manifest"
        )
    manifest = matches[0]
    manifest_id = manifest.get("manifest_id")
    if not isinstance(manifest_id, str):
        raise DataError("snapshot member normalized manifest identity is invalid")
    receipt = _source_receipt(store, manifest, dataset)
    verified, payload = store.read_verified_normalized(
        manifest_id, max_bytes=_MAX_DEFI_TVL_PARQUET_BYTES
    )
    if verified != manifest:
        raise DataError("snapshot member manifest changed during query verification")
    return verified, payload, receipt


def _source_receipt(
    store: CryptoBulkStore, manifest: dict[str, object], dataset: CryptoDatasetIdentityV1
) -> CryptoRawReceiptV1:
    raw_ids = manifest.get("input_manifest_ids")
    if not isinstance(raw_ids, list) or len(raw_ids) != 1 or not isinstance(raw_ids[0], str):
        raise DataError("defi_tvl snapshot member must have exactly one raw source receipt")
    matches = [item for item in store.metadata_inventory() if item.get("manifest_id") == raw_ids[0]]
    if len(matches) != 1:
        raise DataError("defi_tvl raw source manifest is missing or ambiguous")
    raw_manifest = matches[0]
    raw_bytes = raw_manifest.get("artifact_bytes")
    if type(raw_bytes) is not int or not 0 <= raw_bytes <= 8 * 1024 * 1024:
        raise DataError("defi_tvl raw source exceeds the 8 MiB input limit")
    if raw_manifest.get("artifact_kind") != "raw":
        raise DataError("defi_tvl input lineage does not resolve to raw provider data")
    receipt = CryptoRawReceiptV1.from_dict(raw_manifest.get("receipt"))
    if (
        receipt.dataset.to_dict() != dataset.to_dict()
        or receipt.response_sha256 != raw_manifest.get("artifact_sha256")
        or receipt.response_bytes != raw_manifest.get("artifact_bytes")
        or raw_manifest.get("receipt_id") != receipt.receipt_id
        or receipt.response_bytes > 8 * 1024 * 1024
        or dict(receipt.request).get("chain") != dataset.instrument
    ):
        raise DataError("defi_tvl source receipt does not match its raw manifest")
    if (
        receipt.provider_schema != "defillama-v2-historical-chain-tvl"
        or receipt.parser_version != "defillama-chain-tvl-v1"
    ):
        raise DataError("defi_tvl source schema or parser version is unsupported")
    if store.verify_manifest(raw_ids[0]) != raw_manifest:
        raise DataError("defi_tvl raw manifest changed during query verification")
    return receipt


def _validated_frame(
    payload: bytes,
    *,
    dataset: CryptoDatasetIdentityV1,
    manifest: dict[str, object],
) -> tuple[pl.DataFrame, CryptoQualityReportV1]:
    try:
        parquet_schema = pl.read_parquet_schema(io.BytesIO(payload))
    except pl.exceptions.PolarsError as exc:
        raise DataError("defi_tvl normalized artifact is not readable Parquet") from exc
    if list(parquet_schema) != list(_EXPECTED_COLUMNS) or parquet_schema != _EXPECTED_COLUMNS:
        raise DataError("defi_tvl Parquet schema is unsupported")
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    if (
        quality.state != "qualified"
        or quality.dataset_sha256 != manifest.get("artifact_sha256")
        or quality.row_count > _MAX_DEFI_TVL_ROWS
        or not quality.method_version
    ):
        raise DataError("defi_tvl quality metadata does not match the normalized artifact")
    try:
        frame = pl.read_parquet(
            io.BytesIO(payload),
            columns=["observed_at", "tvl_usd", "available_at"],
            n_rows=_MAX_DEFI_TVL_ROWS + 1,
            parallel="row_groups",
            rechunk=False,
            low_memory=True,
        )
    except pl.exceptions.PolarsError as exc:
        raise DataError("defi_tvl normalized artifact could not be read within row bounds") from exc
    if frame.height > _MAX_DEFI_TVL_ROWS:
        raise DataError(f"defi_tvl snapshot exceeds the {_MAX_DEFI_TVL_ROWS:,}-row input limit")
    expected_data_schema = {
        "observed_at": _EXPECTED_COLUMNS["observed_at"],
        "tvl_usd": _EXPECTED_COLUMNS["tvl_usd"],
        "available_at": _EXPECTED_COLUMNS["available_at"],
    }
    if dict(frame.schema) != expected_data_schema:
        raise DataError("defi_tvl Parquet data schema is unsupported")
    if quality.row_count != frame.height:
        raise DataError("defi_tvl quality row count does not match the normalized artifact")
    if frame.is_empty():
        raise DataError("defi_tvl Parquet contains no observations")
    rows = frame.iter_rows(named=True)
    previous: datetime | None = None
    for row in rows:
        observed_at = row["observed_at"]
        value = row["tvl_usd"]
        available_at = row["available_at"]
        if (
            not isinstance(observed_at, datetime)
            or not isinstance(available_at, datetime)
            or not isinstance(value, float)
            or not math.isfinite(value)
            or value < 0
        ):
            raise DataError("defi_tvl observation values do not match the dataset identity")
        observed_at = require_utc(observed_at, "defi_tvl observed_at")
        available_at = require_utc(available_at, "defi_tvl available_at")
        if (
            observed_at != observed_at.replace(hour=0, minute=0, second=0, microsecond=0)
            or available_at != observed_at + timedelta(days=1)
            or (previous is not None and observed_at <= previous)
        ):
            raise DataError("defi_tvl observation clocks are invalid or unordered")
        previous = observed_at
    return frame, quality


def query_defi_tvl_snapshot(
    snapshot: CryptoSnapshotV1,
    store: CryptoBulkStore,
    *,
    limit: int = 100,
    offset: int = 0,
    available_by: datetime | None = None,
    normalized_manifest_id: str | None = None,
) -> DefiTvlSnapshotQueryV1:
    """Read one exact DefiLlama daily TVL member without creating or mutating artifacts."""
    _validate_bounds(limit=limit, offset=offset)
    if normalized_manifest_id is not None and (
        not isinstance(normalized_manifest_id, str)
        or re.fullmatch(r"[0-9a-f]{64}", normalized_manifest_id) is None
    ):
        raise DataError("normalized manifest id must be a lowercase SHA-256 digest")
    if available_by is not None:
        available_by = require_utc(available_by, "available_by")
    members = [member for member in snapshot.members if member.dataset.family == "defi_tvl"]
    if len(members) != 1 or len(snapshot.members) != 1:
        raise DataError("snapshot query requires exactly one defi_tvl member")
    member = members[0]
    dataset = member.dataset
    _validate_identity(dataset)
    manifest, payload, receipt = _selected_manifest(
        store,
        dataset=dataset,
        artifact_key=member.artifact_key,
        artifact_sha256=member.artifact_sha256,
        normalized_manifest_id=normalized_manifest_id,
    )
    manifest_id = cast(str, manifest["manifest_id"])
    frame, quality = _validated_frame(payload, dataset=dataset, manifest=manifest)
    if quality.method_version not in snapshot.qualification_versions:
        raise DataError("snapshot does not bind the defi_tvl qualification version")
    if available_by is not None:
        frame = frame.filter(pl.col("available_at") <= available_by)
    available_row_count = frame.height
    selected = frame.slice(offset, limit)
    observations = tuple(
        DefiTvlObservationV1(
            chain=dataset.instrument,
            observed_at=cast(datetime, row["observed_at"]),
            tvl_usd=cast(float, row["tvl_usd"]),
            available_at=cast(datetime, row["available_at"]),
        )
        for row in selected.iter_rows(named=True)
    )
    capture_relation = None if available_by is None else receipt.fetched_at > available_by
    return DefiTvlSnapshotQueryV1(
        snapshot_id=snapshot.snapshot_id,
        normalized_manifest_id=manifest_id,
        dataset=dataset,
        dataset_sha256=dataset.content_sha256,
        artifact_sha256=member.artifact_sha256,
        quality_method_version=quality.method_version,
        source_receipt=receipt,
        available_by=available_by,
        raw_capture_after_available_by=capture_relation,
        available_row_count=available_row_count,
        limit=limit,
        offset=offset,
        rows=observations,
    )
