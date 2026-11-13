"""Read-only synthetic stock diagnostics. Never dispatch, deserialize or authorize resume."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from uuid import UUID

from alpha_cli._native_fixture_store import _events
from alpha_cli.control_store import ControlStore
from alpha_cli.native_stock_fixture import (
    ARTIFACT_LIMITS,
    STAGES,
    StockFixtureRequest,
    digest,
    validate_stock_snapshot,
)
from alpha_cli.native_stock_profile import (
    ProfileSelection,
    bind_profile_declaration,
    read_recorded_profile,
    verify_selected_profile,
)
from alpha_core import DataError


def _read(work: Path, name: str, limit: int) -> bytes | None:
    path = work / name
    if work.is_symlink() or path.is_symlink() or work != work.resolve():
        raise DataError("unsafe stock inspection path")
    try:
        directory = os.open(work, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    try:
        try:
            descriptor = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise DataError("stock inspection artifact exceeds bound or is not a file")
            raw = stream.read(limit + 1)
    finally:
        os.close(directory)
    if len(raw) > limit:
        raise DataError("stock inspection artifact exceeds bound")
    return raw


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in items:
        if key in value:
            raise DataError("duplicate stock inspection JSON key")
        value[key] = item
    return value


def inspect_progress(work: Path, binding: dict[str, object]) -> dict[str, object]:
    """Read advisory attempts; no completed-stage, accounting or checkpoint authority."""
    raw = _read(work, "stock-progress.json", 8192)
    if raw is None:
        return {"status": "unavailable", "reason": "no_progress_snapshot"}
    try:
        progress = json.loads(raw, object_pairs_hook=_pairs)
        fields = {
            "schema",
            "request",
            "request_sha256",
            "state",
            "attempted_stages",
            "fake_model_attempts",
            "simulated_model_counter",
            "fake_tool_attempts",
            "continuation_checkpoint_sha256",
            "actual_model_calls",
            "scientific_acceptance",
        }
        if not isinstance(progress, dict) or set(progress) != fields:
            raise ValueError
        request = dict(progress["request"])
        if request.pop("schema") != "StockRDLoopFixtureRequestV1":
            raise ValueError
        typed = StockFixtureRequest(**request)
        stages = progress["attempted_stages"]
        if (
            progress["schema"] != "StockRDLoopProgressV1"
            or progress["request_sha256"] != digest(typed.payload())
            or any(request.get(key) != value for key, value in binding.items())
            or not binding
            or not isinstance(stages, list)
            or stages != STAGES[: len(stages)]
            or len(stages) > 5
            or progress["state"]
            not in {
                "running",
                "checkpoint_ready",
                "completed",
                "cancelled",
                "failed",
                "checkpoint_rejected",
            }
            or type(progress["actual_model_calls"]) is not int
            or progress["actual_model_calls"] != 0
            or progress["scientific_acceptance"] != "not_admitted"
            or type(progress["fake_model_attempts"]) is not int
            or progress["fake_model_attempts"]
            != sum(s in stages for s in ("direct_exp_gen", "feedback"))
            or type(progress["simulated_model_counter"]) is not int
            or progress["simulated_model_counter"]
            not in (
                {progress["fake_model_attempts"], 2}
                if typed.mode == "exhaust" and len(stages) >= 2
                else {progress["fake_model_attempts"]}
            )
            or type(progress["fake_tool_attempts"]) is not int
            or progress["fake_tool_attempts"] != sum(s in stages for s in ("coding", "running"))
            or progress["state"] == "completed"
            and stages != STAGES
        ):
            raise ValueError
        checkpoint_hash = progress["continuation_checkpoint_sha256"]
        checkpoint = _read(work, "stock-checkpoint.bin", 1_048_576)
        if checkpoint_hash is not None and (
            type(checkpoint_hash) is not str
            or checkpoint is None
            or hashlib.sha256(checkpoint).hexdigest() != checkpoint_hash
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
        raise DataError("stock progress evidence is invalid or differently bound") from error
    return {
        "status": "advisory_only",
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "state": progress["state"],
        "attempted_stages": stages,
        "stage_completion": "not_established_by_attempt_snapshot",
        "fake_model_attempts": progress["fake_model_attempts"],
        "simulated_model_counter": progress["simulated_model_counter"],
        "worker_profile_binding": "unverified_self_digest_only",
        "declared_worker_manifest_sha256": typed.manifest_sha256,
        "declared_mode": typed.mode,
        "declared_cpu_milliseconds": typed.cpu_milliseconds,
        "fake_tool_attempts": progress["fake_tool_attempts"],
        "continuation_checkpoint": "hash_verified_bytes_only" if checkpoint_hash else "unavailable",
        "continuation_checkpoint_sha256": checkpoint_hash,
    }


def inspect_current_artifacts(work: Path, binding: dict[str, object]) -> dict[str, object]:
    """Validate current artifacts independently of advisory progress; no journal authority."""
    raw = _read(work, "stock-receipt.json", 100_000)
    if raw is None:
        return {"status": "unavailable", "reason": "no_success_receipt"}
    snapshot = {"stock-receipt.json": raw}
    for name, cap in ARTIFACT_LIMITS:
        if name == "stock-receipt.json":
            continue
        value = _read(work, name, cap)
        if value is None:
            raise DataError("stock success artifact snapshot is incomplete")
        snapshot[name] = value
    try:
        receipt = json.loads(raw, object_pairs_hook=_pairs)
        request = dict(receipt["request"])
        if request.pop("schema") != "StockRDLoopFixtureRequestV1":
            raise ValueError
        typed = StockFixtureRequest(**request)
        if not binding or any(request.get(key) != value for key, value in binding.items()):
            raise ValueError
        diagnostic = validate_stock_snapshot(snapshot, typed)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
        raise DataError("stock current artifacts are invalid or differently bound") from error
    return {
        "status": "current_bytes_validated_only",
        "receipt_sha256": diagnostic["receipt_sha256"],
        "validated_receipt": receipt,
        "validated_trace": diagnostic["trace"],
        "trace_sha256": hashlib.sha256(snapshot["stock-trace.json"]).hexdigest(),
        "checkpoint_sha256": hashlib.sha256(snapshot["stock-checkpoint.bin"]).hexdigest(),
        "worker_profile_binding": "unverified",
        "declared_worker_manifest_sha256": typed.manifest_sha256,
        "declared_mode": typed.mode,
        "declared_cpu_milliseconds": typed.cpu_milliseconds,
        "durable_owner_receipt_binding": "unavailable_stock_outcome_has_no_receipt_hash",
        "scientific_acceptance": "not_admitted",
    }


def recover_stock_result(
    artifacts: dict[str, object],
    profile: dict[str, object],
    outcome: dict[str, object] | None,
    *,
    uncertain: bool,
    cancelled_or_failed: bool = False,
) -> dict[str, object]:
    """Recover exact owner-observed bytes, never a checkpoint/owner or scientific authority."""
    result: dict[str, object] = {
        "status": "unavailable",
        "scope": "owner_observed_stock_artifact_bytes_only",
        "owner_receipt_match": "unavailable",
        "resume_allowed": False,
        "scientific_acceptance": "not_admitted",
    }
    observed = outcome.get("stock_result") if outcome is not None else None
    if (
        uncertain
        or outcome is None
        or outcome.get("reason") != "exit"
        or type(outcome.get("returncode")) is not int
        or outcome["returncode"] != 0
        or not isinstance(observed, dict)
        or set(observed) != {"schema", "receipt_sha256"}
        or observed.get("schema") != "StockRDLoopObservationV1"
        or artifacts.get("status") != "current_bytes_validated_only"
    ):
        return result | {"reason": "owner_observation_or_validated_artifacts_unavailable"}
    observed_digest = observed["receipt_sha256"]
    if (
        type(observed_digest) is not str
        or len(observed_digest) != 64
        or any(ch not in "0123456789abcdef" for ch in observed_digest)
    ):
        return result | {"reason": "owner_observation_digest_invalid"}
    if artifacts.get("receipt_sha256") != observed_digest:
        return result | {
            "status": "mismatch",
            "owner_receipt_match": "mismatch",
            "reason": "current_receipt_differs_from_owner_observed_bytes",
        }
    result["owner_receipt_match"] = "verified"
    if cancelled_or_failed:
        return result | {"reason": "job_cancelled_or_failed"}
    if profile.get("status") == "mismatch":
        return result | {"status": "mismatch", "reason": "selected_profile_mismatch"}
    declaration = artifacts.get("profile_declaration")
    if profile.get("status") != "verified" or not isinstance(declaration, dict):
        return result | {"reason": "selected_profile_not_verified"}
    if declaration.get("status") != "verified":
        return result | {"status": "mismatch", "reason": "request_declaration_not_verified"}
    return result | {
        "status": "verified",
        "reason": "owner_observed_artifacts_recovered",
        "receipt_sha256": observed["receipt_sha256"],
    }


def inspect_run(
    root: Path, job_id: str, *, profile_selection: ProfileSelection | None = None
) -> dict[str, object]:
    """Use existing rows only; SQLite may use WAL/SHM sidecars, never row writes."""
    try:
        if str(UUID(job_id)) != job_id:
            raise ValueError
    except ValueError as error:
        raise DataError("stock inspection requires a canonical job UUID") from error
    from alpha_cli.native_supervisor import _fixture_root

    # Do not allow _fixture_root's separate daily-study route.
    if (root / "daily-rule-workspace.json").exists():
        raise DataError("stock inspection is synthetic-only")
    root = _fixture_root(root)
    with ControlStore(root)._readonly_transaction() as connection:
        job = ControlStore._require_job(connection, job_id)
        bounds = connection.execute(
            "SELECT count(*), sum(length(payload_json)) FROM job_events WHERE job_id=?",
            (job_id,),
        ).fetchone()
        if bounds[0] > 8192 or (bounds[1] or 0) > 4_194_304:
            raise DataError("stock inspection journal exceeds bound")
        try:
            events = _events(connection, job_id)
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
            raise DataError("stock inspection journal evidence is invalid") from error
        claim = events.get("native_claim")
        if claim is None or "stock_profile_sha256" not in claim:
            raise DataError("stock inspection requires an existing stock claim")
        binding = {k: claim[k] for k in ("job_id", "reservation_id", "owner_id", "spec_sha256")}
        outcome = events.get("native_outcome")
        consumed = "native_invocation" in events
        cancelled_or_failed = job["status"] in {
            "cancelled",
            "failed",
        } or ControlStore._active_job_cancellation(connection, job_id)
        recorded = None
        recorded_status = "not_requested"
        if profile_selection is not None:
            try:
                recorded = read_recorded_profile(connection, job_id, events)
                recorded_status = "identity_rebuilt"
            except DataError:
                recorded_status = "invalid_or_unavailable"
    profile = verify_selected_profile(recorded, profile_selection)
    profile["recorded_identity"] = recorded_status
    work = root / f"payload-{job_id}"
    try:
        progress = inspect_progress(work, binding)
    except (DataError, OSError):
        progress = {"status": "invalid", "reason": "advisory_progress_validation_failed"}
    try:
        artifacts = inspect_current_artifacts(work, binding)
    except (DataError, OSError):
        artifacts = {"status": "invalid", "reason": "success_artifact_validation_failed"}
    progress = bind_profile_declaration(progress, profile)
    artifacts = bind_profile_declaration(artifacts, profile)
    recovered = recover_stock_result(
        artifacts,
        profile,
        outcome,
        uncertain="native_uncertain" in events,
        cancelled_or_failed=cancelled_or_failed,
    )
    owner_match = recovered["owner_receipt_match"]
    artifacts["durable_owner_receipt_binding"] = owner_match
    profile["durable_owner_receipt_binding"] = owner_match
    return {
        "schema": "StockRDLoopInspectionV1",
        "classification": "synthetic_only_unqualified",
        "dispatch": binding | {"profile_sha256": claim["stock_profile_sha256"]},
        "invocation_consumed": consumed,
        "observed_start": "native_started" in events,
        "owner_outcome": outcome["reason"] if outcome else "unresolved",
        "owner_returncode": outcome["returncode"] if outcome else None,
        "success_receipt": "owner_observed_bytes_verified"
        if owner_match == "verified"
        else "not_verified_by_inspection",
        "owner_uncertainty": "native_uncertain" in events,
        "job_cancellation_or_failure": cancelled_or_failed,
        "profile_verification": profile,
        "progress": progress,
        "artifact_validation": artifacts,
        "result_recovery": recovered,
        "resume_allowed": False,
        "resume_authority": "none",
        "recovery": "original_live_owner_required_no_relaunch_or_allowance_reset",
        "scientific_acceptance": "not_admitted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--profile-source", type=Path)
    parser.add_argument("--profile-runtime", type=Path)
    parser.add_argument("--profile-mode", choices=("resume", "cancel", "exhaust", "tamper"))
    args = parser.parse_args()
    provided = (args.profile_source, args.profile_runtime, args.profile_mode)
    if any(value is not None for value in provided) and any(value is None for value in provided):
        parser.error("profile comparison requires source, runtime and explicit mode together")
    selected = (
        ProfileSelection(args.profile_source, args.profile_runtime, args.profile_mode)
        if all(value is not None for value in provided)
        else None
    )
    try:
        result = inspect_run(args.data_dir, args.job_id, profile_selection=selected)
    except (DataError, OSError):
        # Never disclose raw artifact bytes, exception text, SQL or local paths.
        print(json.dumps({"schema": "StockRDLoopInspectionV1", "status": "invalid_or_unavailable"}))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
