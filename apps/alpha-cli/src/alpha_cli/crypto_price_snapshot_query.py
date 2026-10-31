"""Read-only bounded Binance daily spot price query; no research admission authority.

Completed-day clocks reconstruct an execution convention from captured data. They do
not establish historical provider publication, revision availability, or executable prices.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

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

_MAX_ROWS = 4_000
_MAX_BYTES = 32 * 1024 * 1024
_MAX_RAW_BYTES = 8 * 1024 * 1024
_DAY = timedelta(days=1)
_SCHEMA = {
    "open_time": pl.Datetime("us", "UTC"),
    "open": pl.Float64(),
    "high": pl.Float64(),
    "low": pl.Float64(),
    "close": pl.Float64(),
    "base_volume": pl.Float64(),
    "close_time": pl.Datetime("us", "UTC"),
    "quote_volume": pl.Float64(),
    "trade_count": pl.Int64(),
    "taker_buy_base_volume": pl.Float64(),
    "taker_buy_quote_volume": pl.Float64(),
}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _day(value: datetime, label: str) -> datetime:
    value = require_utc(value, label)
    if value != value.replace(hour=0, minute=0, second=0, microsecond=0):
        raise DataError(f"{label} must be a UTC day boundary")
    return value


@dataclass(frozen=True)
class BinanceDailyPriceRowV1:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    base_volume: float
    close_time: datetime
    quote_volume: float
    trade_count: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float

    @property
    def available_at(self) -> datetime:
        return self.open_time + _DAY

    def to_dict(self) -> dict[str, object]:
        return {
            name: value.isoformat() if isinstance(value, datetime) else value
            for name, value in (
                *((name, getattr(self, name)) for name in _SCHEMA),
                ("available_at", self.available_at),
            )
        }


@dataclass(frozen=True)
class BinanceDailyPriceSnapshotQueryV1:
    snapshot_id: str
    normalized_manifest_id: str
    dataset: CryptoDatasetIdentityV1
    artifact_sha256: str
    quality_method_version: str
    source_receipts: tuple[CryptoRawReceiptV1, ...]
    start: datetime
    end: datetime
    available_by: datetime
    rows: tuple[BinanceDailyPriceRowV1, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "BinanceDailyPriceSnapshotQueryV1",
            "snapshot_id": self.snapshot_id,
            "normalized_manifest_id": self.normalized_manifest_id,
            "dataset": self.dataset.to_dict(),
            "dataset_sha256": self.dataset.content_sha256,
            "artifact_sha256": self.artifact_sha256,
            "quality_method_version": self.quality_method_version,
            "source_receipts": [receipt.to_dict() for receipt in self.source_receipts],
            "start": self.start.isoformat(),
            "end_exclusive": self.end.isoformat(),
            "available_by": self.available_by.isoformat(),
            "requested_row_count": (self.end - self.start).days,
            "returned_row_count": len(self.rows),
            "coverage": "complete_requested_utc_days",
            "availability_basis": "completed_utc_day_reconstruction",
            "availability_semantics": (
                "available_at is next UTC day, not source-stamped historical publication; "
                "captured revisions may differ from values historically known"
            ),
            "raw_capture_after_available_by": any(
                receipt.fetched_at > self.available_by for receipt in self.source_receipts
            ),
            "point_in_time_claim": False,
            "claim_scope": "exploratory_reconstructed_history",
            "execution_authority": False,
            "rows": [row.to_dict() for row in self.rows],
        }

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.to_dict()).encode()).hexdigest()


def validate_binance_daily_price_identity(dataset: CryptoDatasetIdentityV1) -> None:
    """Shared closed identity check; identity validation grants no source authority."""
    if (
        dataset.provider != "binance"
        or dataset.venue != "binance"
        or dataset.market_type != "spot"
        or dataset.family != "market_bars"
        or dataset.frequency != "1d"
        or dataset.units != "provider_native_ohlcv"
        or dataset.timestamp_convention != "interval_start_utc"
        or dataset.base_asset != "BTC"
        or dataset.quote_asset != "USDT"
        or dataset.instrument != "BTCUSDT"
    ):
        raise DataError("price query requires exact Binance BTCUSDT spot daily native identity")


def _sources(
    store: CryptoBulkStore,
    manifest: dict[str, object],
    dataset: CryptoDatasetIdentityV1,
    metadata: tuple[dict[str, object], ...],
) -> tuple[CryptoRawReceiptV1, ...]:
    raw_ids = manifest.get("input_manifest_ids")
    if (
        not isinstance(raw_ids, list)
        or not 1 <= len(raw_ids) <= 100
        or any(not isinstance(item, str) for item in raw_ids)
        or len(set(raw_ids)) != len(raw_ids)
    ):
        raise DataError("price query requires one to 100 distinct raw source manifests")
    raws = []
    total = 0
    for raw_id in raw_ids:
        matches = [item for item in metadata if item.get("manifest_id") == raw_id]
        if len(matches) != 1 or matches[0].get("artifact_kind") != "raw":
            raise DataError("price query raw source manifest is missing or invalid")
        raw = matches[0]
        size = raw.get("artifact_bytes")
        if type(size) is not int or size < 1:
            raise DataError("price query raw source size is invalid")
        total += size
        if total > _MAX_RAW_BYTES:
            raise DataError("price query raw source exceeds 8 MiB input limit")
        receipt = CryptoRawReceiptV1.from_dict(raw.get("receipt"))
        request = dict(receipt.request)
        if (
            receipt.dataset != dataset
            or receipt.response_sha256 != raw.get("artifact_sha256")
            or receipt.response_bytes != size
            or raw.get("receipt_id") != receipt.receipt_id
            or receipt.provider_schema != "binance-public-rest-v1"
            or receipt.parser_version != "binance-archive-rest-v1"
            or request.get("symbol") != dataset.instrument
            or request.get("interval") != "1d"
        ):
            raise DataError("price query raw source receipt identity/schema differs")
        for key in ("startTime", "endTime", "limit"):
            value = request.get(key)
            if not isinstance(value, str) or re.fullmatch(r"[0-9]{1,16}", value) is None:
                raise DataError("price query raw source request bounds are invalid")
        if int(request["startTime"]) > int(request["endTime"]) or not (
            1 <= int(request["limit"]) <= 1_000
        ):
            raise DataError("price query raw source request bounds are invalid")
        raws.append((raw_id, raw, receipt))
    # Complete every size preflight before recursive hashing of any raw payload.
    for raw_id, raw, _ in raws:
        if store.verify_manifest(raw_id) != raw:
            raise DataError("price query raw source changed during verification")
    return tuple(receipt for _, _, receipt in raws)


def _frame(
    payload: bytes, manifest: dict[str, object]
) -> tuple[pl.DataFrame, CryptoQualityReportV1]:
    try:
        schema = pl.read_parquet_schema(io.BytesIO(payload))
        if list(schema) != list(_SCHEMA) or schema != _SCHEMA:
            raise DataError("price query native Parquet schema differs")
        frame = pl.read_parquet(io.BytesIO(payload), n_rows=_MAX_ROWS + 1, low_memory=True)
    except pl.exceptions.PolarsError as error:
        raise DataError("price query cannot decode bounded native Parquet") from error
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    if (
        not 1 <= frame.height <= _MAX_ROWS
        or quality.row_count != frame.height
        or quality.state != "qualified"
        or quality.failures
        or quality.warnings
        or quality.correction_lineage
        or quality.dataset_sha256 != manifest.get("artifact_sha256")
        or quality.observed_start != frame["open_time"][0]
        or quality.observed_end != frame["open_time"][-1]
    ):
        raise DataError("price query quality/coverage metadata differs or exceeds 4,000 rows")
    return frame, quality


def query_binance_daily_price_snapshot(
    snapshot: CryptoSnapshotV1,
    store: CryptoBulkStore,
    *,
    normalized_manifest_id: str,
    start: datetime,
    end: datetime,
    available_by: datetime,
) -> BinanceDailyPriceSnapshotQueryV1:
    """Return all requested closed UTC days, or fail; never return a partial study input.

    Bounds are inclusive start/exclusive end. The exact retained normalized manifest is
    mandatory because unchanged recaptures can share a snapshot ID but have new provenance.
    """
    if (
        not isinstance(normalized_manifest_id, str)
        or re.fullmatch(r"[0-9a-f]{64}", normalized_manifest_id) is None
    ):
        raise DataError("price query normalized manifest id must be lowercase SHA-256")
    start, end = _day(start, "start"), _day(end, "end")
    available_by = require_utc(available_by, "available_by")
    if not 1 <= (end - start).days <= _MAX_ROWS or end > available_by:
        raise DataError("price query requires a bounded complete closed-day range")
    if len(snapshot.members) != 1:
        raise DataError("price query requires exactly one frozen price member")
    member = snapshot.members[0]
    dataset = member.dataset
    validate_binance_daily_price_identity(dataset)
    store.verify_readable()
    metadata = store.metadata_inventory()
    matches = [item for item in metadata if item.get("manifest_id") == normalized_manifest_id]
    if (
        len(matches) != 1
        or matches[0].get("artifact_kind") != "normalized"
        or matches[0].get("dataset") != dataset.to_dict()
        or matches[0].get("artifact_key") != member.artifact_key
        or matches[0].get("artifact_sha256") != member.artifact_sha256
    ):
        raise DataError("price query exact normalized manifest/member binding differs")
    manifest = matches[0]
    receipts = _sources(store, manifest, dataset, metadata)
    verified, payload = store.read_verified_normalized(normalized_manifest_id, max_bytes=_MAX_BYTES)
    if verified != manifest:
        raise DataError("price query normalized manifest changed during verification")
    frame, quality = _frame(payload, manifest)
    if quality.method_version not in snapshot.qualification_versions:
        raise DataError("price query qualification version is not frozen")
    rows = []
    previous = None
    for row in frame.iter_rows(named=True):
        opened = _day(row["open_time"], "open_time")
        closed = require_utc(row["close_time"], "close_time")
        # Binance closes one millisecond before the following day boundary.
        if closed != opened + _DAY - timedelta(milliseconds=1) or (
            previous is not None and opened <= previous
        ):
            raise DataError("price query candle clocks are invalid or unordered")
        previous = opened
        if opened + _DAY > available_by or not start <= opened < end:
            continue
        numeric = [row[key] for key in _SCHEMA if key not in {"open_time", "close_time"}]
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in numeric):
            raise DataError("price query candle contains invalid numeric values")
        if (
            min(row[key] for key in ("open", "high", "low", "close")) <= 0
            or row["low"] > min(row["open"], row["close"])
            or row["high"] < max(row["open"], row["close"])
            or any(row[key] < 0 for key in _SCHEMA if "volume" in key)
            or row["trade_count"] < 0
        ):
            raise DataError("price query candle violates OHLCV invariants")
        if any(receipt.fetched_at < opened + _DAY for receipt in receipts):
            raise DataError("price query raw capture predates completed candle")
        opened_ms = int(opened.timestamp() * 1_000)
        if not any(
            int(dict(receipt.request)["startTime"])
            <= opened_ms
            <= int(dict(receipt.request)["endTime"])
            for receipt in receipts
        ):
            raise DataError("price query candle falls outside pinned raw request bounds")
        rows.append(BinanceDailyPriceRowV1(**row))
    if len(rows) != (end - start).days or any(
        row.open_time != start + index * _DAY for index, row in enumerate(rows)
    ):
        raise DataError("price query requested daily coverage is incomplete")
    return BinanceDailyPriceSnapshotQueryV1(
        snapshot.snapshot_id,
        normalized_manifest_id,
        dataset,
        member.artifact_sha256,
        quality.method_version,
        receipts,
        start,
        end,
        available_by,
        tuple(rows),
    )
