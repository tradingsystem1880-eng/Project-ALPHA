"""Protected completion of one cleaned-up synthetic rule trial in existing ledgers."""

from __future__ import annotations

import hashlib
import json

from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_cli._native_fixture_store import _append, _events, _reservation
from alpha_cli._native_loop_admission import NativeLaunch
from alpha_cli._native_rule_artifacts import publish_rule_run, validate_rule_artifacts
from alpha_cli._native_rule_economics import CostedRuleStudy
from alpha_cli._native_rule_environment import measure_rule_environment
from alpha_cli._native_rule_protocol import require_rule_confirmation, worker_request
from alpha_cli.control_store import ControlStore, _at, _canonical_json, _content_id
from alpha_core import DataError


def complete_rule_trial(
    store: ControlStore, job_id: str, launch: NativeLaunch
) -> dict[str, object]:
    """Reconcile immutable successful process evidence; never spawn, refund, or approve."""
    if type(launch) is not NativeLaunch or launch.study is None or launch.authority is None:
        raise DataError("rule completion requires its approved typed native launch")
    authority = launch.authority
    if authority.root != store._data_dir:
        raise DataError("rule completion belongs to another store")
    contract = authority.verify()
    daily = isinstance(launch.study, DailyRuleStudyV1)
    if isinstance(launch.study, DailyRuleStudyV1):
        from alpha_cli._native_daily_rule_protocol import reopen_daily_study

        reopen_daily_study(store._data_dir, launch.study)
    work = store._data_dir / f"payload-{job_id}"
    with store._transaction(write=True) as connection:
        events = _events(connection, job_id)
        claim = events.get("native_claim")
        outcome = events.get("native_outcome")
        if (
            claim is None
            or outcome is None
            or "native_uncertain" in events
            or outcome["reason"] != "exit"
            or outcome["returncode"] != 0
            or outcome["cleanup_scope"]
            != ("docker_container_and_posix_process_group" if daily else "posix_process_group")
            or store._active_job_cancellation(connection, job_id)
        ):
            raise DataError(
                "rule completion requires trusted clean native outcome without uncertainty"
            )
        if daily:
            created = events.get("native_container_created")
            started = events.get("native_started")
            if (
                not isinstance(created, dict)
                or not isinstance(started, dict)
                or created.get("container_id") != started.get("container_id")
                or not isinstance(created.get("container_id"), str)
                or any(
                    created.get(key) != claim.get(key)
                    for key in (
                        "container_name",
                        "image_id",
                        "resource_fingerprint",
                        "deadline_monotonic_ns",
                    )
                )
            ):
                raise DataError(
                    "daily completion container/deadline differs from trusted claim and start"
                )
        observed = outcome.get("rule_result")
        if not isinstance(observed, dict) or observed.get("schema") != (
            "DailyNativeRuleObservationV1" if daily else "SyntheticNativeRuleObservationV1"
        ):
            raise DataError("rule completion requires its trusted observed receipt binding")
        existing = connection.execute(
            """SELECT a.* FROM research_attempt_records a
            JOIN research_launch_attempt_links l ON l.attempt_id=a.attempt_id
            WHERE l.reservation_id=?""",
            (claim["reservation_id"],),
        ).fetchone()
        if existing is not None:
            attempt = store._research_attempt_view(
                existing, launch_reservation_id=str(claim["reservation_id"])
            )
            if (
                existing["status"] != "completed"
                or existing["contract_id"] != authority.contract_id
            ):
                raise DataError("rule reservation already has a different terminal outcome")
            store._verify_research_attempt_run(
                project_id=authority.project_id, attempt=attempt, contract_payload=contract
            )
            return attempt
        reservation = _reservation(connection, job_id)
        if (
            reservation["contract_id"] != authority.contract_id
            or reservation["project_id"] != authority.project_id
        ):
            raise DataError("rule completion changed its contract identity")
        job = store._require_job(connection, job_id)
        request = json.loads(job["request_json"])
        spec = request["native_invocation_spec"]
        if (
            spec["native_manifest_sha256"] != launch.fingerprint
            or spec["implementation_fingerprints"] != launch.implementation_fingerprints()
        ):
            raise DataError("rule completion implementation differs from reservation")
        review = store._latest_research_review(connection, authority.contract_id)
        assert review is not None
        receipt_id = require_rule_confirmation(
            connection, authority.project_id, authority.contract_id, str(review["actor"])
        )
        budget = json.loads(reservation["budget_reserved_json"])
        admission = {
            "schema": "DailyNativeAdmissionV1" if daily else "SyntheticNativeAdmissionV1",
            "job_id": job_id,
            "reservation_id": reservation["reservation_id"],
            "spec_sha256": reservation["config_fingerprint"],
            "manifest_sha256": launch.fingerprint,
            "owner_id": claim["owner_id"],
            "mode": launch.mode,
            "loop_steps": budget["rdagent_native_v1_loop_steps"],
            "rule_request": worker_request(isinstance(launch.study, CostedRuleStudy)),
            "rule_profile": measure_rule_environment(
                daily or isinstance(launch.study, CostedRuleStudy)
            ),
            "study_id": launch.study.content_sha256,
            "trial_id": reservation["reservation_id"],
            "owner_receipt_id": receipt_id,
        }
        if isinstance(launch.study, DailyRuleStudyV1):
            from alpha_cli._native_daily_rule_protocol import daily_worker_request

            admission.update(
                rule_request=daily_worker_request(launch.study),
                query_sha256=launch.study.query_sha256,
                cpu_milliseconds=budget["rdagent_native_v1_cpu_milliseconds"],
                container_name=claim["container_name"],
                image_id=claim["image_id"],
                resource_fingerprint=claim["resource_fingerprint"],
                deadline_monotonic_ns=claim["deadline_monotonic_ns"],
                container_id=events["native_container_created"]["container_id"],
            )
        receipt_bytes = launch.verify_result(work, admission)
        if hashlib.sha256(receipt_bytes).hexdigest() != observed["receipt_sha256"]:
            raise DataError("rule result changed from the trusted observed receipt")
        native_receipt = json.loads(receipt_bytes)
        manifest = publish_rule_run(
            store._data_dir,
            project_id=authority.project_id,
            contract_id=authority.contract_id,
            contract=contract,
            execution_fingerprint=str(reservation["config_fingerprint"]),
            native_receipt=native_receipt,
            native_receipt_bytes=receipt_bytes,
        )
        run_id = str(manifest["run_id"])
        rdir, verified = store._verified_run(run_id)
        validate_rule_artifacts(rdir, verified, contract)
        store._require_research_run(
            run_id,
            project_id=authority.project_id,
            contract_id=authority.contract_id,
            contract_payload=contract,
            phase="deep_research",
            config_fingerprint=str(reservation["config_fingerprint"]),
        )
        details = {
            "attempt_number": 1,
            "evidence_zone": "D1",
            "synthetic_rule_engineering_only": True,
            "study_id": launch.study.content_sha256,
            "trial_id": reservation["reservation_id"],
            "scientific_acceptance": "not_admitted",
            "variant_exposures": 2,
            "native_receipt_ref": {
                "artifact": "native_receipt.json",
                "content_sha256": observed["receipt_sha256"],
            },
            "rule_positions_ref": {
                "artifact": "rule_positions.json",
                "content_sha256": manifest["artifacts"]["rule_positions.json"]["sha256"],
            },
        }
        if isinstance(launch.study, DailyRuleStudyV1):
            details.update(
                synthetic_rule_engineering_only=launch.study.data_origin == "artificial_fixture",
                daily_rule_discovery_only=True,
                data_origin=launch.study.data_origin,
                query_sha256=launch.study.query_sha256,
                outcome=native_receipt["economics"]["outcome"],
            )
        identity = {
            "schema_version": 1,
            "project_id": authority.project_id,
            "contract_id": authority.contract_id,
            "phase": "deep_research",
            "kind": reservation["kind"],
            "status": "completed",
            "config_fingerprint": reservation["config_fingerprint"],
            "budget_used": {},
            "run_id": run_id,
            "error": None,
            "details": details,
            "launch_reservation_id": reservation["reservation_id"],
        }
        attempt_id = _content_id("ra", identity)
        timestamp = _at(None)
        connection.execute(
            """INSERT INTO research_attempt_records VALUES
            (?, ?, ?, 'deep_research', ?, 'completed', ?, '{}', ?, NULL, ?, ?)""",
            (
                attempt_id,
                authority.project_id,
                authority.contract_id,
                reservation["kind"],
                reservation["config_fingerprint"],
                run_id,
                _canonical_json(details, "rule completion details"),
                timestamp,
            ),
        )
        connection.execute(
            "INSERT INTO research_launch_attempt_links VALUES (?, ?, ?)",
            (reservation["reservation_id"], attempt_id, timestamp),
        )
        _append(connection, job_id, "status", {"from": "running", "to": "succeeded"})
        connection.execute("UPDATE jobs SET status='succeeded' WHERE job_id=?", (job_id,))
        connection.execute(
            """INSERT INTO research_execution_events VALUES
            (?, ?, ?, 'idle', ?, 'system', ?, ?, 'owner', NULL, ?, NULL, NULL)""",
            (
                authority.project_id,
                int(reservation["execution_sequence"]) + 1,
                authority.contract_id,
                timestamp,
                "Exploratory daily rule/control completed; no promotion authority."
                if daily
                else "Synthetic native position mechanics completed; no market evidence.",
                "Review immutable query, actual accounting and baseline/control report."
                if daily
                else "Review immutable synthetic artifacts; empirical acceptance remains blocked.",
                "native:daily-rule-discovery-complete"
                if daily
                else "native:rule-engineering-complete",
            ),
        )
        row = connection.execute(
            "SELECT * FROM research_attempt_records WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        assert row is not None
        return store._research_attempt_view(
            row, launch_reservation_id=str(reservation["reservation_id"])
        )
