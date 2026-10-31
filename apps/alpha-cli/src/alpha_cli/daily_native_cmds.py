"""Thin CLI dispatch into the existing registered native owner and ControlStore."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from alpha_cli._native_daily_rule_protocol import study_from_contract
from alpha_cli._native_loop_admission import NativeLaunch
from alpha_cli._native_rule_authority import RuleAuthority
from alpha_cli._native_rule_completion import complete_rule_trial
from alpha_cli.control_store import ControlStore, ResearchPhase
from alpha_cli.native_supervisor import start_daily_owner
from alpha_core import DataError


def draft_daily_request(
    project_id: str,
    *,
    data_dir: Path,
    source_pack_id: str,
    snapshot_id: str,
    normalized_manifest_id: str,
) -> dict[str, object]:
    """Freeze the approved bounded recipe over one already-acquired qualified snapshot."""
    from alpha_cli._native_daily_rule_container import daily_container_profile
    from alpha_cli._native_daily_rule_protocol import draft_daily_contract
    from alpha_cli._native_daily_rule_study import bind_daily_study, daily_rule_terms_proposal
    from alpha_cli._native_rule_environment import (
        measure_rule_environment,
        rule_implementation_fingerprints,
    )
    from alpha_cli.crypto_bulk_store import configured_crypto_bulk_store
    from alpha_cli.crypto_price_snapshot_query import query_binance_daily_price_snapshot
    from alpha_data.crypto.contracts import CryptoSnapshotV1

    if len(snapshot_id) != 64 or any(
        character not in "0123456789abcdef" for character in snapshot_id
    ):
        raise DataError("daily draft requires an exact crypto snapshot identity")
    root = data_dir.resolve()
    store = ControlStore(root)
    pack = store.get_research_source_pack(source_pack_id)
    if pack.get("project_id") != project_id:
        raise DataError("daily draft source pack belongs to another project")
    bulk = configured_crypto_bulk_store(root)
    bulk.verify_readable()
    path = root / "crypto" / "snapshots" / (snapshot_id + ".json")
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise DataError("daily draft snapshot path is unsafe")
    try:
        with path.open("rb") as handle:
            payload = handle.read(65537)
        if len(payload) > 65536:
            raise DataError("daily draft snapshot manifest exceeds its bound")
        snapshot = CryptoSnapshotV1.from_dict(json.loads(payload))
    except (ValueError, OSError) as error:
        raise DataError("daily draft crypto snapshot is unavailable") from error
    if snapshot.snapshot_id != snapshot_id:
        raise DataError("daily draft snapshot path differs from its identity")
    end = datetime(2023, 1, 1, tzinfo=UTC)
    query = query_binance_daily_price_snapshot(
        snapshot,
        bulk,
        normalized_manifest_id=normalized_manifest_id,
        start=datetime(2020, 1, 1, tzinfo=UTC),
        end=end,
        available_by=end,
    )
    economics, resources = daily_rule_terms_proposal()
    study = bind_daily_study(
        query,
        snapshot_sha256=snapshot_id,
        runtime_profile_sha256=measure_rule_environment(True),
        container_image_id=daily_container_profile()["image_id"],
        storage_config_sha256=hashlib.sha256(
            (root / "crypto" / "storage-config.json").read_bytes()
        ).hexdigest(),
        economics=economics,
        resources=resources,
        data_origin="captured_provider_history",
    )
    contract = draft_daily_contract(
        source_pack_id,
        rule_implementation_fingerprints(True, daily_study=study),
        {
            "variants": 5,
            "wall_seconds": 60,
            "source_requests": 0,
            "rdagent_native_v1_model_calls": 0,
            "rdagent_native_v1_input_tokens": 0,
            "rdagent_native_v1_output_tokens": 0,
            "rdagent_native_v1_tool_calls": 0,
            "rdagent_native_v1_loop_steps": 5,
            "rdagent_native_v1_cpu_milliseconds": 60000,
        },
        study,
    )
    record = store.create_research_contract(
        project_id, scope="exploration", payload=contract, created_by="codex", author_kind="agent"
    )
    phases: tuple[tuple[str, ResearchPhase], ...] = (
        ("captured", "triage"),
        ("triage", "exploration_review"),
    )
    for previous, next_phase in phases:
        if store.research_case_summary(project_id)["phase"] == previous:
            store.transition_research_phase(
                project_id,
                to_phase=next_phase,
                contract_id=str(record["contract_id"]),
                actor="codex",
                reason="Freeze the exact bounded daily study for owner review.",
                next_action="Owner confirms the exact immutable exploration contract.",
                responsibility="owner",
            )
    return record


def run_daily_deep(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Launch once, or reconcile existing work. Never replenish, refund, or respawn."""
    root = data_dir.resolve()
    store = ControlStore(root)
    case = store.research_case_summary(project_id)
    contract_id = str(case["active_contract_id"])
    authority = RuleAuthority(root, project_id, contract_id)
    contract = authority.verify()
    study = study_from_contract(contract)
    configured = os.environ.get("ALPHA_RDAGENT_SOURCE")
    if not configured:
        raise DataError("daily native execution requires explicit pinned ALPHA_RDAGENT_SOURCE")
    launch = NativeLaunch(
        Path(configured).resolve(), "INCONCLUSIVE", study=study, authority=authority
    )
    latest = case.get("latest_attempt_id")
    if isinstance(latest, str):
        completed = store.verified_research_attempt(project_id, latest)
        attempt = completed["attempt"]
        if (
            isinstance(attempt, dict)
            and attempt.get("phase") == "deep_research"
            and attempt.get("contract_id") == contract_id
        ):
            if attempt.get("status") == "completed":
                return {"attempt": attempt, "case": case, "reconnected": True}
            raise DataError("daily native trial is terminal; no replacement trial is authorized")
    active = case.get("active_job_id")
    if isinstance(active, str):
        state = store.native_fixture_status(active, reconnect=True)
        if state.get("state") == "pending_scientific_admission":
            attempt = complete_rule_trial(store, active, launch)
            return {
                "attempt": attempt,
                "case": store.research_case_summary(project_id),
                "reconnected": True,
            }
        return {"job_id": active, "native": state, "reconnected": True}
    checkpoint = case.get("checkpoint")
    if (
        case.get("execution_state") == "queued"
        and isinstance(checkpoint, str)
        and checkpoint.startswith("daily-native:queued:")
    ):
        original_job_id = checkpoint.removeprefix("daily-native:queued:")
        with store._transaction(write=False) as connection:
            job = connection.execute(
                "SELECT job_id,status FROM jobs WHERE job_id=? AND project_id=?",
                (original_job_id, project_id),
            ).fetchone()
            reservation = connection.execute(
                """SELECT r.reservation_id FROM research_launch_reservations r
                JOIN research_execution_events e ON e.project_id=r.project_id
                    AND e.sequence=r.execution_sequence
                WHERE e.active_job_id=? AND r.project_id=? AND r.contract_id=?
                    AND r.phase='deep_research'""",
                (original_job_id, project_id, contract_id),
            ).fetchone()
        return {
            "job_id": original_job_id,
            "reconnected": True,
            "state": "pre_dispatch_interrupted",
            "job_recorded": job is not None,
            "reservation_recorded": reservation is not None,
            "recovery_required": (
                "Inspect the original job before explicitly reconciling preparation; "
                "no replacement or dispatch was attempted."
            ),
        }
    if case.get("phase") != "deep_research" or case.get("execution_state") != "idle":
        raise DataError("daily native launch requires completed D0 and idle approved D1")
    job_id = str(uuid4())
    spec = store.build_d1_native_invocation_spec(
        project_id, contract_id, job_id, attempt_number=1, native_manifest_sha256=launch.fingerprint
    )
    try:
        store.transition_research_execution(
            project_id,
            to_state="queued",
            contract_id=contract_id,
            actor="codex",
            reason="Queue the exact owner-confirmed daily native study.",
            next_action="Reserve the unchanged allowance before dispatch.",
            responsibility="codex",
            checkpoint=f"daily-native:queued:{job_id}",
        )
        store.create_research_job(
            project_id,
            contract_id=contract_id,
            job_id=job_id,
            request={
                "stage": "rdagent_native",
                "contract_id": contract_id,
                "job_id": job_id,
                "attempt_number": 1,
                "native_invocation_spec": spec,
            },
        )
        store.set_job_status(job_id, "running")
        store.transition_research_execution(
            project_id,
            to_state="running",
            contract_id=contract_id,
            actor="system",
            reason="Bind the durable job to the registered native owner.",
            next_action="Inspect or cancel the bound job.",
            responsibility="codex",
            active_job_id=job_id,
            checkpoint="daily-native:running",
        )
        reservation = store.reserve_d1_native_research_launch(
            project_id, contract_id, job_id, native_manifest_sha256=launch.fingerprint
        )
    except Exception as error:
        raise DataError(
            f"daily native job {job_id} could not confirm its reservation or job preparation; "
            "inspect that existing job and its accounting, do not launch a replacement"
        ) from error
    budget = reservation.get("budget_reserved")
    if not isinstance(budget, dict):
        raise DataError(
            f"daily native reservation {job_id} has no bounded budget; inspect, do not retry"
        )
    wall = budget.get("wall_seconds")
    if isinstance(wall, bool) or not isinstance(wall, int | float) or wall <= 0:
        raise DataError(f"daily native reservation {job_id} has no remaining wall allowance")
    seconds = min(float(wall), float(study.resources.max_wall_seconds))
    # Startup failures retain the committed job/reservation. No generic job failure or refund
    # is fabricated while dispatch or cleanup may have an uncertain outcome.
    try:
        process = start_daily_owner(root, job_id, native=launch, seconds=seconds)
    except Exception as error:
        raise DataError(
            f"daily native job {job_id} has a committed reservation but dispatch is uncertain; "
            "inspect or reconnect that existing job, do not launch a replacement"
        ) from error
    try:
        process.wait(timeout=seconds + 20)
    except subprocess.TimeoutExpired:
        return {
            "job_id": job_id,
            "native": store.native_fixture_status(job_id, reconnect=True),
            "reconnected": False,
        }
    state = store.native_fixture_status(job_id, reconnect=True)
    if state.get("state") == "pending_scientific_admission":
        attempt = complete_rule_trial(store, job_id, launch)
        return {
            "job_id": job_id,
            "attempt": attempt,
            "case": store.research_case_summary(project_id),
        }
    return {"job_id": job_id, "native": state, "reconnected": False}
