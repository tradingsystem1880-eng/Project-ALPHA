"""Hash-bound private acquisition evidence and repeatable provider-quality checks."""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alpha_cli.comparison_acquisition import AcquisitionPlan, _hash, _read, _write
from alpha_cli.investigation_comparisons import ComparisonPlan, ComparisonSeries
from alpha_core import DataError
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt
from alpha_data.adapters.tiingo_adapter import TiingoAdapter, parse_tiingo_eod
from alpha_data.pipeline import stage_and_promote
from alpha_data.snapshot import create_snapshot, snapshot_manifest_hash
from alpha_data.store import ParquetStore


def _inventory(root: Path) -> dict[str, str]:
    files = {}
    total = 0
    for count, path in enumerate(root.rglob("*"), 1):
        if count > 1024:
            raise DataError("acquisition artifact count bound exceeded")
        if path.is_symlink():
            raise DataError("acquisition artifact cannot be symlinked")
        if not path.is_file() or path == root / "result.json":
            continue
        size = path.stat().st_size
        total += size
        if size > 32 * 1024 * 1024 or total > 256 * 1024 * 1024:
            raise DataError("acquisition artifact byte bound exceeded")
        files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _replay(root: Path, scope: dict[str, Any], attempts: list[dict[str, Any]]) -> None:
    plan = AcquisitionPlan.model_validate_json(json.dumps(scope["plan"]))
    if len(attempts) != len(plan.series):
        raise DataError("acquisition attempt count differs from reserved requests")
    for index, attempt in enumerate(attempts):
        if _read(root / f"attempt-{index}.json") != attempt:
            raise DataError("acquisition artifact attempt mismatch")
        if attempt.get("status") not in {"failed", "succeeded"}:
            raise DataError("acquisition attempt is not terminal")
        item = plan.series[index]
        documents = [
            _read(path)
            for path in (root / "data/store/receipts/tiingo").glob("*/receipt.json")
            if _read(path).get("dataset", {}).get("symbol") == item.symbol
        ]
        if not documents and attempt["status"] == "failed":
            continue  # Transport/parser failures may have no receipt-backed candidate.
        if len(documents) != 1:
            raise DataError("acquisition artifact requires one receipt per parsed request")
        document = documents[0]
        receipt = FetchReceipt.from_dict(document["receipt"])
        identity = DatasetIdentity.from_dict(document["dataset"])
        expected_identity = DatasetIdentity(
            symbol=item.symbol,
            provider="tiingo",
            provider_symbol=item.symbol,
            venue=item.venue,
            asset_class=item.asset_class,
            timeframe="1D",
            calendar=item.calendar,
            currency=item.currency,
            price_basis="raw",
        )
        if identity != expected_identity or (receipt.requested_start, receipt.requested_end) != (
            plan.start,
            plan.end,
        ):
            raise DataError("acquisition artifact provider identity/window mismatch")
        receipt_root = root / "data/store/receipts/tiingo" / receipt.receipt_id
        if _read(receipt_root / "receipt.json") != {
            "schema_version": 1,
            "dataset": identity.to_dict(),
            "receipt": receipt.to_dict(),
        }:
            raise DataError("acquisition artifact receipt metadata mismatch")
        raw = (receipt_root / "response.bin").read_bytes()
        if (
            len(raw) > scope["max_response_bytes"]
            or hashlib.sha256(raw).hexdigest() != receipt.response_sha256
        ):
            raise DataError("acquisition artifact raw response mismatch")
        parsed = parse_tiingo_eod(
            raw,
            symbol=item.symbol,
            provider_symbol=item.symbol,
            asset_class=item.asset_class,
            venue=item.venue,
            calendar=item.calendar,
            currency=item.currency,
            start=plan.start,
            end=plan.end,
            fetched_at=receipt.fetched_at,
        )
        if parsed.receipt != receipt:
            raise DataError("acquisition artifact does not reproduce provider receipt")
        with tempfile.TemporaryDirectory(prefix="alpha-acquisition-verify-") as temporary:
            replay = Path(temporary)
            try:
                stage_and_promote(ParquetStore(replay), parsed, authoritative_source="tiingo")
                kind = "candidates"
            except DataError:
                kind = "quarantine"
                if not (replay / kind / "tiingo" / receipt.receipt_id / "quality.json").is_file():
                    raise
            relative = f"{kind}/tiingo/{receipt.receipt_id}"
            candidate = ParquetStore(root / "data/store" / relative)
            replay_candidate = ParquetStore(replay / relative)
            if (
                not candidate.read_bars(item.symbol).equals(replay_candidate.read_bars(item.symbol))
                or candidate.read_actions(item.symbol) != replay_candidate.read_actions(item.symbol)
                or candidate.read_provenance(item.symbol)
                != replay_candidate.read_provenance(item.symbol)
                or _read(candidate.root / "quality.json")
                != _read(replay_candidate.root / "quality.json")
            ):
                raise DataError("acquisition artifact parsing/quality does not reproduce")
        if attempt["status"] == "failed":
            continue
        store = ParquetStore(root / "data/store")
        if kind != "candidates" or (
            not parsed.bars.equals(store.read_bars(item.symbol))
            or parsed.actions != store.read_actions(item.symbol)
            or candidate.read_provenance(item.symbol) != store.read_provenance(item.symbol)
        ):
            raise DataError("acquisition artifact does not reproduce provider parsing")
        dates = {ts.date().isoformat() for ts in parsed.bars["ts"].to_list()}
        if not set(scope["required_dates"]) <= dates:
            raise DataError("acquisition artifact missing drawdown endpoints")
        if any(ts.time().isoformat() != "00:00:00" for ts in parsed.bars["ts"].to_list()):
            raise DataError("acquisition artifact has non-daily labels")
        quality_path = f"data/store/candidates/tiingo/{receipt.receipt_id}/quality.json"
        if attempt != dict(
            status="succeeded",
            symbol=item.symbol,
            receipt_id=receipt.receipt_id,
            quality_path=quality_path,
        ):
            raise DataError("acquisition artifact success receipt mismatch")


def _result(root: Path, scope: dict[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    succeeded = all(item["status"] == "succeeded" for item in attempts)
    result: dict[str, Any] = dict(
        schema_version=1,
        status="succeeded" if succeeded else "failed",
        authority="none",
        admitted=False,
        request_sha256=_hash(scope),
        attempts=attempts,
        data_root=str(root / "data"),
        qualification="provider_required_session_ohlcv_checks_only"
        if succeeded
        else "not_established",
        required_session_coverage="passed" if succeeded else "not_established",
        historical_vintage="unverified",
        independent_source_agreement="not_tested",
        instrument_metadata="operator_declared",
    )
    if succeeded:
        plan = AcquisitionPlan.model_validate_json(json.dumps(scope["plan"]))
        snapshot_id = "acquisition_" + _hash(scope)[:24]
        snapshot = root / "data/snapshots" / snapshot_id
        digest = snapshot_manifest_hash(snapshot)
        source_store = ParquetStore(root / "data/store")
        snapshot_store = ParquetStore(snapshot)
        for item in plan.series:
            if (
                not source_store.read_bars(item.symbol).equals(
                    snapshot_store.read_bars(item.symbol)
                )
                or source_store.read_actions(item.symbol)
                != snapshot_store.read_actions(item.symbol)
                or source_store.read_provenance(item.symbol)
                != snapshot_store.read_provenance(item.symbol)
            ):
                raise DataError("acquisition artifact snapshot differs from replayed provider data")
        result["comparisons"] = ComparisonPlan(
            series=[
                ComparisonSeries(
                    snapshot_id=snapshot_id,
                    snapshot_sha256=digest,
                    symbol=item.symbol,
                    role=item.role,
                )
                for item in plan.series
            ]
        ).model_dump(mode="json")
        if _read(root / "comparisons.json") != result["comparisons"]:
            raise DataError("acquisition artifact comparison plan mismatch")
    return result


def finish_batch(
    root: Path, scope: dict[str, Any], attempts: list[dict[str, Any]]
) -> dict[str, Any]:
    _inventory(root)
    _replay(root, scope, attempts)
    if all(item["status"] == "succeeded" for item in attempts):
        plan = AcquisitionPlan.model_validate_json(json.dumps(scope["plan"]))
        snapshot_id = "acquisition_" + _hash(scope)[:24]
        create_snapshot(
            ParquetStore(root / "data/store"),
            root / "data/snapshots",
            snapshot_id,
            [item.symbol for item in plan.series],
            source="tiingo",
            adapter_version=TiingoAdapter.version,
            parser_version=TiingoAdapter.parser_version,
            created_at=datetime.now(UTC),
        )
        digest = snapshot_manifest_hash(root / "data/snapshots" / snapshot_id)
        _write(
            root / "comparisons.json",
            ComparisonPlan(
                series=[
                    ComparisonSeries(
                        snapshot_id=snapshot_id,
                        snapshot_sha256=digest,
                        symbol=item.symbol,
                        role=item.role,
                    )
                    for item in plan.series
                ]
            ).model_dump(mode="json"),
        )
    result = _result(root, scope, attempts)
    _write(root / "result.json", {"result": result, "artifacts": _inventory(root)})
    return result


def verify_batch(root: Path, scope: dict[str, Any]) -> dict[str, Any]:
    record = _read(root / "result.json")
    if record.get("artifacts") != _inventory(root):
        raise DataError("acquisition artifact inventory mismatch")
    attempts = [
        _read(root / f"attempt-{index}.json") for index in range(len(scope["plan"]["series"]))
    ]
    _replay(root, scope, attempts)
    result = _result(root, scope, attempts)
    if record.get("result") != result:
        raise DataError("acquisition artifact result mismatch")
    return result
