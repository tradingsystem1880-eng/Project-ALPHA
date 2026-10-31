"""Restore only missing immutable daily evidence, keeping current authority and reservations.

This is not a database rollback facility. An older control catalog is never imported.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from alpha_cli import _artifacts
from alpha_cli._native_daily_rule_artifacts import (
    read_json_artifact,
    validate_daily_rule_artifacts,
)
from alpha_cli._native_daily_rule_protocol import reopen_daily_study, study_from_contract
from alpha_cli._native_fixture_store import _events
from alpha_cli._native_rule_authority import RuleAuthority
from alpha_cli._native_rule_environment import measure_rule_environment
from alpha_cli.control_store import ControlStore
from alpha_core import DataError


def _restore_missing_file(target: Path, payload: bytes) -> None:
    """Repair an already hash-admitted missing file; never add evidence or overwrite bytes."""
    descriptor, temporary = tempfile.mkstemp(prefix=".daily-restore-", dir=target.parent)
    staging = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(staging, target)
        except FileExistsError:
            if target.is_symlink() or not target.is_file() or target.read_bytes() != payload:
                raise DataError(
                    "daily evidence restore refuses conflicting concurrent bytes"
                ) from None
    finally:
        staging.unlink()


def _safe_file(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise DataError("daily evidence restore path is unsafe")
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise DataError("daily evidence restore symlink is unsupported")
    return path


def restore_daily_rule_evidence(root: Path, reference_root: Path, job_id: str) -> dict[str, object]:
    """Restore missing hash-bound files from an independent reference, without ledger writes."""
    if (
        root == reference_root
        or root != root.resolve()
        or reference_root != reference_root.resolve()
    ):
        raise DataError("daily evidence restore requires distinct canonical roots")
    store = ControlStore(root)
    with store._transaction(write=False) as connection:
        events = _events(connection, job_id)
        outcome = events.get("native_outcome")
        if (
            outcome is None
            or "native_uncertain" in events
            or outcome.get("reason") != "exit"
            or outcome.get("returncode") != 0
            or store._active_job_cancellation(connection, job_id)
        ):
            raise DataError("daily evidence restore requires a trusted clean completed outcome")
        row = connection.execute(
            """SELECT a.*, r.project_id AS reserved_project_id,
                r.contract_id AS reserved_contract_id
            FROM research_launch_reservations r
            JOIN research_launch_attempt_links l ON l.reservation_id=r.reservation_id
            JOIN research_attempt_records a ON a.attempt_id=l.attempt_id
            JOIN research_execution_events e ON e.project_id=r.project_id
                AND e.sequence=r.execution_sequence
            WHERE e.active_job_id=?""",
            (job_id,),
        ).fetchone()
        if row is None or row["status"] != "completed" or row["run_id"] is None:
            raise DataError("daily evidence restore requires its authoritative completed attempt")
        project_id, contract_id, run_id = (
            str(row[key]) for key in ("reserved_project_id", "reserved_contract_id", "run_id")
        )
        details = json.loads(row["details_json"])
        observation = outcome.get("rule_result")
        if (
            not isinstance(observation, dict)
            or observation.get("schema") != "DailyNativeRuleObservationV1"
        ):
            raise DataError("daily evidence restore requires its trusted receipt observation")
        observed_sha = observation.get("receipt_sha256")
        ref = details.get("native_receipt_ref")
        if not isinstance(ref, dict) or ref.get("content_sha256") != observed_sha:
            raise DataError("daily evidence restore attempt/observation receipt differs")
    contract = RuleAuthority(root, project_id, contract_id).verify()
    study = study_from_contract(contract)
    reopen_daily_study(root, study)
    if measure_rule_environment(True) != study.runtime_profile_sha256:
        raise DataError("daily evidence restore runtime profile differs from approval")
    reference_run = _safe_file(reference_root, "runs/" + run_id)
    native_path = _safe_file(reference_root, "runs/" + run_id + "/native_receipt.json")
    if native_path.stat().st_size > study.resources.max_artifact_bytes:
        raise DataError("daily reference receipt exceeds frozen artifact bound")
    native_bytes = native_path.read_bytes()
    if hashlib.sha256(native_bytes).hexdigest() != observed_sha:
        raise DataError("daily reference receipt differs from authoritative observed bytes")
    manifest = _artifacts.read_manifest(reference_run)
    validate_daily_rule_artifacts(reference_run, manifest, contract, source_data_dir=root)
    selectors = read_json_artifact(
        reference_run / "projections.json", maximum_bytes=study.resources.max_artifact_bytes
    )
    if not isinstance(selectors, dict):
        raise DataError("daily reference projection selectors are invalid")
    roles = selectors["roles"]
    assert isinstance(roles, dict)
    run_ids = [run_id, *(str(roles[role]["run_id"]) for role in ("baseline", "control"))]
    files: list[tuple[str, bytes]] = []

    def include(relative: str) -> None:
        remaining = study.resources.max_artifact_bytes - sum(len(raw) for _, raw in files)
        path = _safe_file(reference_root, relative)
        if len(files) >= 64 or path.stat().st_size > remaining:
            raise DataError("daily evidence restore exceeds frozen aggregate artifact bound")
        with path.open("rb") as stream:
            payload = stream.read(remaining + 1)
        if len(payload) > remaining:
            raise DataError("daily evidence restore exceeds frozen aggregate artifact bound")
        files.append((relative, payload))

    for selected_id in run_ids:
        selected_dir = _safe_file(reference_root, "runs/" + selected_id)
        selected_manifest = _artifacts.read_manifest(selected_dir)
        artifacts = selected_manifest["artifacts"]
        assert isinstance(artifacts, dict)
        for name in [*artifacts, "manifest.json"]:
            relative = "runs/" + selected_id + "/" + name
            include(relative)
    snapshot_id = str(selectors["chart_snapshot_id"])
    snapshot_manifest_path = _safe_file(
        reference_root, "snapshots/" + snapshot_id + "/manifest.json"
    )
    snapshot_manifest = json.loads(snapshot_manifest_path.read_text())
    snapshot_files = ["manifest.json"]
    for symbol in snapshot_manifest["symbols"].values():
        for kind in ("bars", "actions", "provenance"):
            filename = symbol.get(kind + "_file")
            if filename is not None:
                snapshot_files.append(filename)
    for name in snapshot_files:
        relative = "snapshots/" + snapshot_id + "/" + name
        include(relative)
    if sum(len(payload) for _, payload in files) > study.resources.max_artifact_bytes:
        raise DataError("daily evidence restore exceeds frozen aggregate artifact bound")
    # Validate the entire reference and all conflicts before publishing any missing file.
    for relative, payload in files:
        target = _safe_file(root, relative)
        if target.exists() and (not target.is_file() or target.read_bytes() != payload):
            raise DataError("daily evidence restore refuses conflicting existing bytes")
    restored: list[str] = []
    for relative, payload in files:
        target = _safe_file(root, relative)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)

            _restore_missing_file(target, payload)
            restored.append(relative)
    validated = _artifacts.read_manifest(root / "runs" / run_id)
    validate_daily_rule_artifacts(root / "runs" / run_id, validated, contract)
    return {
        "schema": "DailyRuleEvidenceRestoreV1",
        "job_id": job_id,
        "run_id": run_id,
        "receipt_sha256": observed_sha,
        "restored_files": restored,
        "control_database_replaced": False,
        "budget_or_exposure_reset": False,
        "data_origin": study.data_origin,
        "scientific_acceptance": "not_admitted",
    }
