"""Receipt-backed candidate validation and fail-closed canonical promotion."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import polars as pl

from alpha_core import CorporateAction, DataError
from alpha_data._atomic import publish
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt, FetchResult
from alpha_data.store import ParquetStore

_BAR_COLUMNS = ("ts", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class IngestOutcome:
    status: Literal["promoted"]
    provider: str
    receipt_id: str
    symbol: str
    quality_path: Path


def _safe_segment(value: str, *, label: str) -> str:
    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or any(not (char.isalnum() or char in "._:-") for char in value)
    ):
        raise DataError(f"invalid {label} {value!r}")
    return value


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _publish_directory(staging: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(staging, destination)
    except FileExistsError as exc:
        raise DataError(f"immutable ingest artifact already exists at {destination}") from exc


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    publish(destination, lambda temporary: shutil.copyfile(source, temporary))


def _receipt_document(identity: DatasetIdentity, receipt: FetchReceipt) -> dict[str, object]:
    return {
        "schema_version": 1,
        "dataset": identity.to_dict(),
        "receipt": receipt.to_dict(),
    }


def _store_receipt(
    store: ParquetStore,
    identity: DatasetIdentity,
    receipt: FetchReceipt,
    raw: bytes,
) -> Path:
    if (
        len(raw) != receipt.response_bytes
        or hashlib.sha256(raw).hexdigest() != receipt.response_sha256
    ):
        raise DataError("fetch receipt response hash/length does not match raw response bytes")
    provider = _safe_segment(identity.provider, label="provider")
    receipt_id = _safe_segment(receipt.receipt_id, label="receipt id")
    destination = store.root / "receipts" / provider / receipt_id
    document = _receipt_document(identity, receipt)
    if destination.exists():
        try:
            existing = json.loads((destination / "receipt.json").read_text(encoding="utf-8"))
            response = (destination / "response.bin").read_bytes()
        except (OSError, json.JSONDecodeError) as exc:
            raise DataError(f"corrupt immutable receipt at {destination}") from exc
        if existing != document or response != raw:
            raise DataError(f"immutable receipt conflict at {destination}")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{receipt_id}.", suffix=".tmp", dir=destination.parent)
    )
    try:
        (staging / "response.bin").write_bytes(raw)
        _write_json(staging / "receipt.json", document)
        _publish_directory(staging, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destination


def _verify_stored_receipt(
    store: ParquetStore,
    identity: DatasetIdentity,
    receipt: FetchReceipt,
) -> None:
    root = (
        store.root
        / "receipts"
        / _safe_segment(identity.provider, label="provider")
        / _safe_segment(receipt.receipt_id, label="receipt id")
    )
    try:
        document = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
        response = (root / "response.bin").read_bytes()
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"corrupt immutable receipt at {root}") from exc
    if document != _receipt_document(identity, receipt):
        raise DataError(f"stored receipt metadata does not match candidate at {root}")
    if (
        len(response) != receipt.response_bytes
        or hashlib.sha256(response).hexdigest() != receipt.response_sha256
    ):
        raise DataError(f"stored receipt response hash/length does not match at {root}")


def _quality_path_for_receipt(
    store: ParquetStore,
    *,
    provider: str,
    receipt_id: str,
) -> Path:
    paths = [
        store.root / root / provider / receipt_id / "quality.json"
        for root in ("candidates", "quarantine")
    ]
    existing = [path for path in paths if path.is_file()]
    if len(existing) != 1:
        raise DataError("canonical receipt must have exactly one immutable quality report")
    return existing[0]


def _rows_by_ts(frame: pl.DataFrame) -> dict[datetime, dict[str, object]]:
    return {row["ts"]: row for row in frame.select(_BAR_COLUMNS).iter_rows(named=True)}


def _bar_row_hash(row: dict[str, object]) -> str:
    payload: dict[str, object] = {}
    for name in _BAR_COLUMNS:
        value = row[name]
        payload[name] = value.isoformat() if isinstance(value, datetime) else value
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _merge_bars(current: pl.DataFrame | None, incoming: pl.DataFrame) -> pl.DataFrame:
    rows = _rows_by_ts(current) if current is not None else {}
    rows.update(_rows_by_ts(incoming))
    return pl.DataFrame(
        [rows[key] for key in sorted(rows)], schema=incoming.select(_BAR_COLUMNS).schema
    )


def _action_key(action: CorporateAction) -> tuple[str, date]:
    return action.action_type.value, action.ex_date


def _merge_actions(
    current: list[CorporateAction], incoming: list[CorporateAction]
) -> tuple[list[CorporateAction], list[str]]:
    merged = {_action_key(action): action for action in current}
    errors: list[str] = []
    for action in incoming:
        key = _action_key(action)
        previous = merged.get(key)
        if previous is not None and previous != action:
            errors.append(f"corporate_action_conflict:{key[0]}:{key[1].isoformat()}")
            continue
        merged[key] = action
    return (
        sorted(merged.values(), key=lambda action: (action.ex_date, action.action_type.value)),
        errors,
    )


def _quality_report(
    *,
    store: ParquetStore,
    result: FetchResult,
    authoritative_source: str,
    max_cross_source_price_difference: float,
) -> tuple[pl.DataFrame, list[CorporateAction], dict[str, object]]:
    assert result.identity is not None
    assert result.receipt is not None
    identity = result.identity
    receipt = result.receipt
    critical: list[str] = []
    warnings: list[str] = []
    if result.bars["ts"].n_unique() != result.bars.height:
        critical.append("duplicate_timestamps")
    for index, row in enumerate(result.bars.iter_rows(named=True)):
        values = [row[name] for name in _BAR_COLUMNS[1:]]
        if any(not isinstance(value, (int, float)) for value in values):
            critical.append(f"non_numeric_bar:{index}")
            continue
        open_, high, low, close, volume = (float(value) for value in values)
        prices = (open_, high, low, close)
        if (
            any(not math.isfinite(value) or value <= 0.0 for value in prices)
            or not math.isfinite(volume)
            or low > min(open_, close)
            or high < max(open_, close)
            or low > high
            or volume < 0.0
        ):
            critical.append(f"invalid_ohlcv:{index}")
    if identity.provider != authoritative_source:
        critical.append(
            f"source not authoritative:{identity.provider}:expected:{authoritative_source}"
        )
    current_bars: pl.DataFrame | None = None
    current_actions: list[CorporateAction] = []
    current_source: str | None = None
    if store._bars_path(result.symbol).exists():  # noqa: SLF001 -- pipeline/store peer contract
        current_bars = store.read_bars(result.symbol)
        current_actions = store.read_actions(result.symbol)
        provenance = store.read_provenance(result.symbol)
        source_value = provenance.get("source") if provenance is not None else None
        if isinstance(source_value, str):
            current_source = source_value

    incoming_rows = _rows_by_ts(result.bars)
    if identity.asset_class in {"stock", "etf"}:
        try:
            import exchange_calendars as xcals  # type: ignore[import-untyped]  # noqa: PLC0415
            from exchange_calendars.errors import (  # type: ignore[import-untyped]  # noqa: PLC0415
                CalendarError,
            )

            calendar = xcals.get_calendar(identity.calendar)
            expected_sessions = {
                timestamp.date()
                for timestamp in calendar.sessions_in_range(
                    receipt.requested_start.isoformat(), receipt.requested_end.isoformat()
                )
            }
        except (ValueError, KeyError, CalendarError) as exc:
            critical.append(f"invalid_exchange_calendar:{identity.calendar}:{type(exc).__name__}")
        else:
            incoming_dates = {timestamp.date() for timestamp in incoming_rows}
            for missing in sorted(expected_sessions - incoming_dates):
                critical.append(f"calendar_gap:{missing.isoformat()}")
    current_rows = _rows_by_ts(current_bars) if current_bars is not None else {}
    requested_current = {
        timestamp: row
        for timestamp, row in current_rows.items()
        if receipt.requested_start <= timestamp.date() <= receipt.requested_end
    }
    for timestamp in sorted(set(requested_current) - set(incoming_rows)):
        critical.append(f"missing_existing_session:{timestamp.date().isoformat()}")

    action_dates = {action.ex_date for action in [*current_actions, *result.actions]}
    changed: list[str] = []
    corrections: list[dict[str, str]] = []
    compared = 0
    for timestamp in sorted(set(current_rows).intersection(incoming_rows)):
        old = current_rows[timestamp]
        new = incoming_rows[timestamp]
        if any(old[column] != new[column] for column in _BAR_COLUMNS[1:]):
            changed.append(timestamp.isoformat())
            corrections.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "old_sha256": _bar_row_hash(old),
                    "new_sha256": _bar_row_hash(new),
                }
            )
        if current_source is not None and current_source != identity.provider:
            compared += 1
            old_value = old["close"]
            new_value = new["close"]
            if not isinstance(old_value, (int, float)) or not isinstance(new_value, (int, float)):
                raise DataError("canonical comparison encountered a non-numeric close")
            old_close = float(old_value)
            new_close = float(new_value)
            if not math.isfinite(old_close) or old_close <= 0.0:
                raise DataError("canonical comparison requires a finite positive close")
            if not math.isfinite(new_close) or new_close <= 0.0:
                continue
            difference = abs(new_close - old_close) / abs(old_close)
            if (
                timestamp.date() not in action_dates
                and difference > max_cross_source_price_difference
            ):
                critical.append(f"price_difference:{timestamp.date().isoformat()}:{difference:.8f}")

    merged_actions, action_errors = _merge_actions(current_actions, result.actions)
    critical.extend(action_errors)
    if current_source is None and current_bars is not None:
        warnings.append("canonical_source_unknown")
    merged_bars = _merge_bars(current_bars, result.bars)
    report: dict[str, object] = {
        "schema_version": 1,
        "status": "quarantined" if critical else "passed",
        "provider": identity.provider,
        "receipt_id": receipt.receipt_id,
        "symbol": result.symbol,
        "fetched_at": receipt.fetched_at.isoformat(),
        "critical_errors": sorted(set(critical)),
        "warnings": sorted(set(warnings)),
        "changed_timestamps": changed,
        "corrections": corrections,
        "compared_rows": compared,
        "incoming_rows": result.bars.height,
        "canonical_rows_after_merge": merged_bars.height,
    }
    return merged_bars, merged_actions, report


def _stage_candidate(
    store: ParquetStore,
    result: FetchResult,
    *,
    merged_bars: pl.DataFrame,
    merged_actions: list[CorporateAction],
    report: dict[str, object],
) -> Path:
    assert result.identity is not None
    assert result.receipt is not None
    identity = result.identity
    receipt = result.receipt
    provider = _safe_segment(identity.provider, label="provider")
    receipt_id = _safe_segment(receipt.receipt_id, label="receipt id")
    root_name = "quarantine" if report["status"] == "quarantined" else "candidates"
    destination = store.root / root_name / provider / receipt_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{receipt_id}.", suffix=".tmp", dir=destination.parent)
    )
    try:
        candidate = ParquetStore(staging)
        candidate.write_bars(result.symbol, merged_bars)
        candidate.write_actions(result.symbol, merged_actions)
        candidate.write_provenance(
            result.symbol,
            source=identity.provider,
            adapter_version=receipt.adapter_version,
            parser_version=receipt.parser_version,
            identity=identity,
            receipt=receipt,
        )
        _write_json(staging / "quality.json", report)
        _publish_directory(staging, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destination


def _promote_candidate(
    store: ParquetStore, candidate_root: Path, *, approved_repair: bool
) -> IngestOutcome:
    try:
        report = json.loads((candidate_root / "quality.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"corrupt candidate quality report at {candidate_root}") from exc
    if not isinstance(report, dict):
        raise DataError(f"invalid candidate quality report at {candidate_root}")
    symbol = report.get("symbol")
    provider = report.get("provider")
    receipt_id = report.get("receipt_id")
    if not isinstance(symbol, str) or not symbol:
        raise DataError(f"invalid candidate symbol at {candidate_root}")
    if not isinstance(provider, str) or not provider:
        raise DataError(f"invalid candidate provider at {candidate_root}")
    if not isinstance(receipt_id, str) or not receipt_id:
        raise DataError(f"invalid candidate identity at {candidate_root}")
    candidate = ParquetStore(candidate_root)
    provenance = candidate.read_provenance(symbol)
    if provenance is None or provenance.get("schema_version") != 2:
        raise DataError(f"candidate lacks versioned provenance at {candidate_root}")
    identity = DatasetIdentity.from_dict(provenance["dataset"])
    receipt = FetchReceipt.from_dict(provenance["receipt"])
    if (
        identity.symbol != symbol
        or identity.provider != provider
        or receipt.receipt_id != receipt_id
    ):
        raise DataError(f"candidate identity does not match quality report at {candidate_root}")
    _verify_stored_receipt(store, identity, receipt)
    bars = candidate.read_bars(symbol)
    actions = candidate.read_actions(symbol)
    backup_root = _create_promotion_backup(
        store,
        symbol=symbol,
        provider=provider,
        receipt_id=receipt_id,
    )
    store.begin_promotion(
        symbol,
        {
            "schema_version": 1,
            "provider": provider,
            "receipt_id": receipt_id,
            "approved_repair": approved_repair,
            "backup": str(backup_root.relative_to(store.root)),
        },
    )
    try:
        store.write_bars(symbol, bars)
        store.write_actions(symbol, actions)
        store.write_provenance(
            symbol,
            source=identity.provider,
            adapter_version=receipt.adapter_version,
            parser_version=receipt.parser_version,
            identity=identity,
            receipt=receipt,
        )
    except BaseException:
        _restore_promotion_backup(store, symbol=symbol, backup_root=backup_root)
        store.finish_promotion(symbol)
        raise
    else:
        store.finish_promotion(symbol)
    return IngestOutcome(
        status="promoted",
        provider=provider,
        receipt_id=receipt_id,
        symbol=symbol,
        quality_path=candidate_root / "quality.json",
    )


def _create_promotion_backup(
    store: ParquetStore,
    *,
    symbol: str,
    provider: str,
    receipt_id: str,
) -> Path:
    destination = (
        store.root
        / "promotion-backups"
        / _safe_segment(provider, label="provider")
        / _safe_segment(receipt_id, label="receipt id")
    )
    if destination.exists():
        raise DataError(f"immutable promotion backup already exists at {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{receipt_id}.", suffix=".tmp", dir=destination.parent)
    )
    paths = {
        "bars": (store._bars_path(symbol), "bars.parquet"),  # noqa: SLF001
        "actions": (store._actions_path(symbol), "actions.json"),  # noqa: SLF001
        "provenance": (store._provenance_path(symbol), "provenance.json"),  # noqa: SLF001
    }
    files: dict[str, dict[str, object]] = {}
    try:
        for name, (source, filename) in paths.items():
            present = source.is_file()
            entry: dict[str, object] = {"present": present}
            if present:
                target = staging / filename
                shutil.copyfile(source, target)
                entry.update(filename=filename, sha256=_file_hash(target))
            files[name] = entry
        _write_json(
            staging / "manifest.json",
            {
                "schema_version": 1,
                "symbol": symbol,
                "provider": provider,
                "receipt_id": receipt_id,
                "files": files,
            },
        )
        _publish_directory(staging, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destination


def _restore_promotion_backup(
    store: ParquetStore,
    *,
    symbol: str,
    backup_root: Path,
) -> None:
    try:
        manifest = json.loads((backup_root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"corrupt promotion backup at {backup_root}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise DataError(f"invalid promotion backup at {backup_root}")
    if manifest.get("symbol") != symbol or not isinstance(manifest.get("files"), dict):
        raise DataError(f"promotion backup does not match {symbol!r}")
    files = manifest["files"]
    destinations = {
        "bars": store._bars_path(symbol),  # noqa: SLF001 -- pipeline/store peer contract
        "actions": store._actions_path(symbol),  # noqa: SLF001 -- pipeline/store peer contract
        "provenance": store._provenance_path(symbol),  # noqa: SLF001 -- peer contract
    }
    for name, destination in destinations.items():
        entry = files.get(name)
        if not isinstance(entry, dict) or not isinstance(entry.get("present"), bool):
            raise DataError(f"invalid {name} entry in promotion backup at {backup_root}")
        if not entry["present"]:
            destination.unlink(missing_ok=True)
            continue
        filename = entry.get("filename")
        expected_hash = entry.get("sha256")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise DataError(f"invalid {name} filename in promotion backup at {backup_root}")
        source = backup_root / filename
        if not source.is_file() or not isinstance(expected_hash, str):
            raise DataError(f"missing {name} bytes in promotion backup at {backup_root}")
        if _file_hash(source) != expected_hash:
            raise DataError(f"hash mismatch for {name} in promotion backup at {backup_root}")
        _copy_atomic(source, destination)


def rollback_interrupted_promotion(
    store: ParquetStore,
    *,
    symbol: str,
    acknowledge: bool,
) -> None:
    """Restore exact pre-promotion bytes after an interrupted process, then clear the marker."""
    if not acknowledge:
        raise DataError("promotion rollback requires acknowledge=true")
    marker_path = store._promotion_path(symbol)  # noqa: SLF001 -- explicit repair seam
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataError(f"no interrupted canonical promotion for {symbol!r}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"corrupt promotion marker for {symbol!r}") from exc
    backup = marker.get("backup") if isinstance(marker, dict) else None
    if not isinstance(backup, str) or Path(backup).is_absolute() or ".." in Path(backup).parts:
        raise DataError(f"invalid promotion backup reference for {symbol!r}")
    backup_root = store.root / backup
    _restore_promotion_backup(store, symbol=symbol, backup_root=backup_root)
    store.finish_promotion(symbol)


def stage_and_promote(
    store: ParquetStore,
    result: FetchResult,
    *,
    authoritative_source: str,
    max_cross_source_price_difference: float = 0.01,
) -> IngestOutcome:
    """Persist a receipt, validate a merged candidate, and promote only on a clean gate."""
    if result.identity is None or result.receipt is None or result.raw_response is None:
        raise DataError("receipt-backed ingestion requires identity, receipt, and raw response")
    if (
        isinstance(max_cross_source_price_difference, bool)
        or not isinstance(max_cross_source_price_difference, (int, float))
        or not math.isfinite(max_cross_source_price_difference)
        or max_cross_source_price_difference < 0.0
    ):
        raise DataError("cross-source price-difference threshold must be finite and non-negative")
    if result.identity.symbol != result.symbol:
        raise DataError("fetch result symbol does not match dataset identity")
    if result.receipt.row_count != result.bars.height or result.receipt.action_count != len(
        result.actions
    ):
        raise DataError("fetch receipt counts do not match parsed result")
    _store_receipt(store, result.identity, result.receipt, result.raw_response)
    current = store.read_provenance(result.symbol)
    current_receipt = current.get("receipt") if current is not None else None
    if isinstance(current_receipt, dict) and (
        current_receipt.get("receipt_id") == result.receipt.receipt_id
    ):
        quality_path = _quality_path_for_receipt(
            store,
            provider=result.identity.provider,
            receipt_id=result.receipt.receipt_id,
        )
        return IngestOutcome(
            status="promoted",
            provider=result.identity.provider,
            receipt_id=result.receipt.receipt_id,
            symbol=result.symbol,
            quality_path=quality_path,
        )
    merged_bars, merged_actions, report = _quality_report(
        store=store,
        result=result,
        authoritative_source=authoritative_source,
        max_cross_source_price_difference=max_cross_source_price_difference,
    )
    candidate = _stage_candidate(
        store,
        result,
        merged_bars=merged_bars,
        merged_actions=merged_actions,
        report=report,
    )
    critical = report["critical_errors"]
    if isinstance(critical, list) and critical:
        details = ", ".join(str(item) for item in critical)
        raise DataError(
            f"candidate {result.receipt.receipt_id} quarantined for {result.symbol}: {details}"
        )
    return _promote_candidate(store, candidate, approved_repair=False)


def promote_quarantined(
    store: ParquetStore,
    *,
    provider: str,
    receipt_id: str,
    approve_differences: bool,
) -> IngestOutcome:
    """Explicitly promote one exact quarantined receipt after an owner-reviewed override."""
    if not approve_differences:
        raise DataError("quarantine repair requires approve_differences=true")
    root = (
        store.root
        / "quarantine"
        / _safe_segment(provider, label="provider")
        / _safe_segment(receipt_id, label="receipt id")
    )
    if not root.is_dir():
        raise DataError(f"no quarantined candidate at {root}")
    return _promote_candidate(store, root, approved_repair=True)
