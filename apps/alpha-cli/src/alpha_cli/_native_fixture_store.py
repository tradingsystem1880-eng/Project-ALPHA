"""Transactional synthetic lifecycle operations over existing ControlStore records.

Only the trusted supervisor issues observations. These records establish process facts in
the local trusted-writer model; they never admit scientific evidence or release budget.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
from collections.abc import Mapping
from typing import cast

from alpha_cli._native_rule_economics import CostedRuleStudy
from alpha_cli.control_store import (
    ControlStore,
    _at,
    _canonical_json,
    _content_id,
    _d1_native_spec,
    _required_text,
    _research_review_state,
)
from alpha_cli.native_supervisor import (
    _fixture_root,
    _lock_path,
    _open_lock,
    _Owner,
    _request_live_stop,
    _verify_observation,
    host_identity,
)
from alpha_core import DataError

if sys.platform != "win32":
    import fcntl

_EVENTS = ("native_claim", "native_started", "native_outcome", "native_uncertain")


def _events(connection: sqlite3.Connection, job_id: str) -> dict[str, dict[str, object]]:
    rows = connection.execute(
        "SELECT * FROM job_events WHERE job_id = ? ORDER BY sequence", (job_id,)
    ).fetchall()
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        kind = str(row["event_type"])
        if kind not in _EVENTS:
            continue
        if kind in result and kind != "native_uncertain":
            raise DataError("native lifecycle has duplicate protected events")
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, dict) or payload.get("schema") != "SyntheticNativeLifecycleV1":
            raise DataError("native lifecycle event has an invalid schema")
        common = {"schema", "job_id", "reservation_id", "spec_sha256", "owner_id"}
        extra = {
            "native_claim": {
                "owner_pid",
                "owner_birth",
                "host",
                "lock_device",
                "lock_inode",
                "runtime_sha256",
                "fixture",
                "seconds",
                "cleanup_scope",
            },
            "native_started": {"leader_pid"},
            "native_outcome": {
                "reason",
                "returncode",
                "elapsed_seconds",
                "cleanup_scope",
                "scientific_acceptance",
            },
            "native_uncertain": {"reason"},
        }
        has_rule_result = kind == "native_outcome" and "rule_result" in payload
        rule_fields = {"rule_result"} if has_rule_result else set()
        if set(payload) != common | extra[kind] | rule_fields:
            raise DataError("native lifecycle event fields do not match its closed contract")
        claim = result.get("native_claim")
        if kind == "native_claim":
            if result or payload.get("job_id") != job_id:
                raise DataError("native lifecycle claim identity/order is invalid")
            binding = connection.execute(
                """SELECT r.config_fingerprint, e.active_job_id FROM research_launch_reservations r
                JOIN research_execution_events e ON e.project_id=r.project_id
                    AND e.sequence=r.execution_sequence WHERE r.reservation_id=?""",
                (payload["reservation_id"],),
            ).fetchone()
            if (
                binding is None
                or binding["active_job_id"] != job_id
                or binding["config_fingerprint"] != payload["spec_sha256"]
            ):
                raise DataError("native claim has no matching reserved invocation")
        elif claim is None or any(
            payload.get(key) != claim.get(key)
            for key in ("job_id", "reservation_id", "spec_sha256", "owner_id")
        ):
            raise DataError("native lifecycle event changed its claim binding")
        if (
            kind == "native_outcome"
            and "native_started" not in result
            and payload.get("cleanup_scope") != "no_payload_spawn_attempted"
        ):
            raise DataError("native lifecycle outcome has no observed start")
        if kind == "native_outcome":
            elapsed = payload["elapsed_seconds"]
            if (
                isinstance(elapsed, bool)
                or not isinstance(elapsed, int | float)
                or not math.isfinite(elapsed)
                or elapsed < 0
                or payload["scientific_acceptance"] != "not_admitted"
                or payload["cleanup_scope"]
                not in {"posix_process_group", "no_payload_spawn_attempted"}
                or payload["reason"] not in {"exit", "timeout", "cancelled", "owner_error"}
                or (payload["returncode"] is not None and type(payload["returncode"]) is not int)
                or (
                    payload["returncode"] is None
                    and payload["cleanup_scope"] != "no_payload_spawn_attempted"
                )
            ):
                raise DataError("native lifecycle outcome contains invalid process evidence")
        if has_rule_result:
            from alpha_cli._native_rule_protocol import is_rule_contract

            observed = payload["rule_result"]
            digest = observed.get("receipt_sha256") if isinstance(observed, dict) else None
            reserved_contract = connection.execute(
                """SELECT c.payload_json FROM research_launch_reservations r
                JOIN research_contracts c ON c.contract_id=r.contract_id
                WHERE r.reservation_id=?""",
                (payload["reservation_id"],),
            ).fetchone()
            if (
                not isinstance(observed, dict)
                or set(observed) != {"schema", "receipt_sha256"}
                or observed.get("schema") != "SyntheticNativeRuleObservationV1"
                or type(digest) is not str
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
                or payload["reason"] != "exit"
                or payload["returncode"] != 0
                or payload["cleanup_scope"] != "posix_process_group"
                or claim is None
                or claim["fixture"] != "native_loop"
                or reserved_contract is None
                or not is_rule_contract(json.loads(reserved_contract["payload_json"]))
            ):
                raise DataError("native rule result observation binding is invalid")
        result[kind] = cast(dict[str, object], payload)
    return result


def _append(
    connection: sqlite3.Connection, job_id: str, kind: str, payload: dict[str, object]
) -> None:
    job = ControlStore._require_job(connection, job_id)
    timestamp = _at(None)
    ControlStore._require_monotonic(job["updated_at"], timestamp, "native fixture event")
    sequence = int(job["last_sequence"]) + 1
    connection.execute(
        "INSERT INTO job_events VALUES (?, ?, ?, ?, ?)",
        (job_id, sequence, kind, timestamp, _canonical_json(payload, "native fixture event")),
    )
    connection.execute(
        "UPDATE jobs SET updated_at = ?, heartbeat_at = ?, last_sequence = ? WHERE job_id = ?",
        (timestamp, timestamp, sequence, job_id),
    )


def _reservation(connection: sqlite3.Connection, job_id: str) -> sqlite3.Row:
    rows = connection.execute(
        """SELECT r.* FROM research_launch_reservations r
        JOIN research_execution_events e ON e.project_id=r.project_id
            AND e.sequence=r.execution_sequence
        WHERE e.active_job_id=? AND r.phase='deep_research'""",
        (job_id,),
    ).fetchall()
    if len(rows) != 1:
        raise DataError("native fixture requires exactly one admitted reservation")
    reservation = cast(sqlite3.Row, rows[0])
    job = ControlStore._require_job(connection, job_id)
    latest = ControlStore._latest_research_execution(connection, str(reservation["project_id"]))
    if (
        job["status"] != "running"
        or job["project_id"] != reservation["project_id"]
        or latest is None
        or latest["state"] != "running"
        or latest["sequence"] != reservation["execution_sequence"]
        or latest["active_job_id"] != job_id
    ):
        raise DataError("native fixture lost its running reservation/execution binding")
    if (
        connection.execute(
            "SELECT 1 FROM research_launch_attempt_links WHERE reservation_id=?",
            (reservation["reservation_id"],),
        ).fetchone()
        is not None
    ):
        raise DataError("native fixture reservation already has a terminal attempt")
    contract_id = str(reservation["contract_id"])
    project_id = str(reservation["project_id"])
    contract = ControlStore._require_research_contract(connection, project_id, contract_id)
    phase = ControlStore._latest_research_phase(connection, project_id)
    if (
        phase is None
        or phase["phase"] != "deep_research"
        or phase["contract_id"] != contract_id
        or _research_review_state(ControlStore._latest_research_review(connection, contract_id))
        != "approved"
    ):
        raise DataError("native fixture lost its active approved D1 contract")
    request = json.loads(str(job["request_json"]))
    if not isinstance(request, dict):
        raise DataError("native fixture job request must be an object")
    spec = request.get("native_invocation_spec", {})
    if (
        job["kind"] != "research:event-study"
        or request.get("stage") != "rdagent_native"
        or request.get("job_id") != job_id
        or request.get("contract_id") != contract_id
        or not isinstance(spec, dict)
        or not isinstance(spec.get("native_manifest_sha256"), str)
    ):
        raise DataError("native fixture job request changed its invocation binding")
    expected = _d1_native_spec(
        project_id=project_id,
        contract_id=contract_id,
        job_id=job_id,
        attempt_number=cast(int, request.get("attempt_number")),
        payload=ControlStore._validate_research_contract_for_approval(connection, contract),
        native_manifest_sha256=cast(str, spec["native_manifest_sha256"]),
    )
    if expected != spec or expected["spec_sha256"] != reservation["config_fingerprint"]:
        raise DataError("native fixture reserved invocation changed")
    return reservation


def claim(store: ControlStore, job_id: str, owner: object) -> dict[str, object]:
    if type(owner) is not _Owner or owner.job_id != job_id:
        raise DataError("native claim requires the live trusted fixture owner")
    _fixture_root(store._data_dir)
    if owner.root != store._data_dir:
        raise DataError("native owner belongs to another synthetic store")
    fields = owner.claim_fields()
    with store._transaction(write=True) as connection:
        if _events(connection, job_id):
            raise DataError("native fixture already has a launch claim; reconnect only")
        reservation = _reservation(connection, job_id)
        if store._active_job_cancellation(connection, job_id):
            raise DataError("native fixture cancellation prohibits launch claim")
        budget = json.loads(str(reservation["budget_reserved_json"]))
        if owner.seconds > budget.get("wall_seconds", 0):
            raise DataError("native fixture deadline exceeds its reserved wall budget")
        admission = None
        if owner.native is not None:
            if budget.get("rdagent_native_v1_cpu_milliseconds", 0) <= 0:
                raise DataError("native Python child requires positive reserved CPU before effects")
            if budget.get("variants", 0) < 1:
                raise DataError(
                    "fixed native experiment requires one reserved variant before effects"
                )
            request = json.loads(str(ControlStore._require_job(connection, job_id)["request_json"]))
            if (
                request["native_invocation_spec"]["native_manifest_sha256"]
                != owner.native.fingerprint
            ):
                raise DataError("native worker manifest differs from the reserved invocation")
            if (
                request["native_invocation_spec"]["implementation_fingerprints"]
                != owner.native.implementation_fingerprints()
            ):
                raise DataError("native worker differs from approved implementation fingerprints")
            rule_extra: dict[str, object] = {}
            if owner.native.study is not None:
                from alpha_cli._native_rule_environment import measure_rule_environment
                from alpha_cli._native_rule_protocol import (
                    require_rule_confirmation,
                    worker_request,
                )

                authority = owner.native.authority
                if (
                    authority is None
                    or authority.root != store._data_dir
                    or authority.project_id != reservation["project_id"]
                    or authority.contract_id != reservation["contract_id"]
                ):
                    raise DataError("rule authority differs from the reserved store/contract")
                contract = ControlStore._require_research_contract(
                    connection, authority.project_id, authority.contract_id
                )
                approved = ControlStore._validate_research_contract_for_approval(
                    connection, contract
                )
                if (
                    cast(dict[str, object], approved["analysis_plan"])["study"]
                    != owner.native.study.to_dict()
                ):
                    raise DataError("rule study differs from approved request")
                review = ControlStore._latest_research_review(connection, authority.contract_id)
                assert review is not None
                receipt_id = require_rule_confirmation(
                    connection, authority.project_id, authority.contract_id, str(review["actor"])
                )
                if (
                    budget.get("variants", 0) < 2
                    or budget.get("rdagent_native_v1_loop_steps", 0) < 5
                ):
                    raise DataError("rule baseline/control require two exposures and five stages")
                rule_extra = {
                    "rule_request": worker_request(isinstance(owner.native.study, CostedRuleStudy)),
                    "rule_profile": measure_rule_environment(
                        isinstance(owner.native.study, CostedRuleStudy)
                    ),
                    "study_id": owner.native.study.content_sha256,
                    "trial_id": reservation["reservation_id"],
                    "owner_receipt_id": receipt_id,
                }
            admission = {
                **rule_extra,
                "schema": "SyntheticNativeAdmissionV1",
                "job_id": job_id,
                "reservation_id": reservation["reservation_id"],
                "spec_sha256": reservation["config_fingerprint"],
                "manifest_sha256": owner.native.fingerprint,
                "owner_id": owner.owner_id,
                "mode": owner.native.mode,
                "loop_steps": budget["rdagent_native_v1_loop_steps"],
            }
        payload: dict[str, object] = {
            "schema": "SyntheticNativeLifecycleV1",
            "job_id": job_id,
            "reservation_id": reservation["reservation_id"],
            "spec_sha256": reservation["config_fingerprint"],
            **fields,
        }
        _append(connection, job_id, "native_claim", payload)
    # A rollback must never leave a usable child allowance in the live owner.
    owner.native_admission = admission
    return payload


def _failure_close(
    connection: sqlite3.Connection, job_id: str, outcome: dict[str, object], *, cancelled: bool
) -> None:
    reservation = _reservation(connection, job_id)
    timestamp = _at(None)
    error = "Synthetic native process only: " + (
        "cancelled" if cancelled else str(outcome["reason"])
    )
    identity: dict[str, object] = {
        "schema_version": 1,
        "project_id": reservation["project_id"],
        "contract_id": reservation["contract_id"],
        "phase": "deep_research",
        "kind": reservation["kind"],
        "status": "failed",
        "config_fingerprint": reservation["config_fingerprint"],
        "budget_used": {},
        "run_id": None,
        "error": error,
        "details": {
            "attempt_number": reservation["launch_number"],
            "evidence_zone": "D1",
            "native_process_only": True,
        },
        "launch_reservation_id": reservation["reservation_id"],
    }
    attempt_id = _content_id("ra", identity)
    connection.execute(
        """INSERT INTO research_attempt_records VALUES
        (?, ?, ?, 'deep_research', ?, 'failed', ?, '{}', NULL, ?, ?, ?)""",
        (
            attempt_id,
            reservation["project_id"],
            reservation["contract_id"],
            reservation["kind"],
            reservation["config_fingerprint"],
            error,
            _canonical_json(identity["details"], "native failure details"),
            timestamp,
        ),
    )
    connection.execute(
        "INSERT INTO research_launch_attempt_links VALUES (?, ?, ?)",
        (reservation["reservation_id"], attempt_id, timestamp),
    )
    terminal_status = "cancelled" if cancelled else "failed"
    _append(connection, job_id, "status", {"from": "running", "to": terminal_status})
    connection.execute(
        "UPDATE jobs SET status=?, terminal_error=? WHERE job_id=?",
        (terminal_status, None if cancelled else error, job_id),
    )
    # Validate the original sequence above, before appending the closure event.
    connection.execute(
        """INSERT INTO research_execution_events VALUES
        (?, ?, ?, 'failed', ?, 'system', ?, ?, 'owner', NULL, ?, ?, ?)""",
        (
            reservation["project_id"],
            int(reservation["execution_sequence"]) + 1,
            reservation["contract_id"],
            timestamp,
            error,
            "Inspect the synthetic-only process outcome; no scientific evidence was admitted.",
            "native:process-only",
            error,
            "Native dispatch and scientific acceptance remain disabled.",
        ),
    )


def record(store: ControlStore, job_id: str, value: object) -> dict[str, object]:
    observation = _verify_observation(value)
    owner = observation.owner
    if owner.job_id != job_id or owner.root != store._data_dir:
        raise DataError("native observation belongs to another job/store")
    with store._transaction(write=True) as connection:
        events = _events(connection, job_id)
        prior = events.get("native_claim")
        if prior is None or prior.get("owner_id") != owner.owner_id:
            raise DataError("native observation has no matching owner claim")
        payload = {
            key: prior[key]
            for key in ("schema", "job_id", "reservation_id", "spec_sha256", "owner_id")
        }
        payload.update(observation.fields)
        if "rule_result" in payload:
            binding = payload["rule_result"]
            if not isinstance(binding, Mapping):
                raise DataError("native rule observation has no immutable binding mapping")
            # Journal JSON and the returned dictionary own a separate plain copy;
            # mutating either cannot alter the owner's issued observation.
            payload["rule_result"] = dict(binding)
        previous = events.get(observation.kind)
        if previous is not None:
            if previous != payload:
                raise DataError("native observation replay changed its immutable outcome")
            return previous
        _reservation(connection, job_id)
        if "native_outcome" in events or "native_uncertain" in events:
            raise DataError("native owner cannot overwrite a completed or uncertain observation")
        if (
            observation.kind == "native_outcome"
            and "native_started" not in events
            and payload.get("cleanup_scope") != "no_payload_spawn_attempted"
        ):
            raise DataError("native outcome requires its observed start")
        if owner.cancel_received and not store._active_job_cancellation(connection, job_id):
            _append(
                connection,
                job_id,
                "cancel_requested",
                {"actor": "synthetic_fixture", "reason": "live owner received a stop request"},
            )
        _append(connection, job_id, observation.kind, payload)
        if observation.kind == "native_outcome":
            cancelled = store._active_job_cancellation(connection, job_id)
            if cancelled or payload["reason"] != "exit" or payload["returncode"] != 0:
                _failure_close(connection, job_id, payload, cancelled=cancelled)
    return payload


def heartbeat(store: ControlStore, job_id: str, owner: object) -> None:
    if type(owner) is not _Owner:
        raise DataError("native heartbeat requires the live trusted fixture owner")
    owner.verify()
    if owner.job_id != job_id or owner.root != store._data_dir:
        raise DataError("native heartbeat belongs to another job/store")
    with store._transaction(write=True) as connection:
        events = _events(connection, job_id)
        if events.get("native_claim", {}).get("owner_id") != owner.owner_id:
            raise DataError("native heartbeat has no matching claim")
        _reservation(connection, job_id)
        _append(connection, job_id, "heartbeat", {"owner_id": owner.owner_id})


def status(store: ControlStore, job_id: str, *, reconnect: bool = False) -> dict[str, object]:
    _fixture_root(store._data_dir)
    host = host_identity()
    with store._transaction(write=reconnect) as connection:
        store._require_job(connection, job_id)
        events = _events(connection, job_id)
        prior = events.get("native_claim")
        if prior is None:
            return {"claim": None, "state": "unclaimed"}
        if prior.get("host") != host:
            raise DataError("native fixture belongs to a foreign/unknown host epoch")
        path = _lock_path(store._data_dir, job_id)
        inode = os.stat(path, follow_symlinks=False)
        if (inode.st_dev, inode.st_ino) != (prior["lock_device"], prior["lock_inode"]):
            raise DataError("native fixture lock identity changed")
        outcome = events.get("native_outcome")
        if outcome is not None:
            job = store._require_job(connection, job_id)
            state = "pending_scientific_admission" if job["status"] == "running" else "closed"
        else:
            state = "quarantined" if "native_uncertain" in events else "owner_active"
            with _open_lock(store._data_dir, job_id) as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    state = "quarantined"
                    if reconnect and "native_uncertain" not in events:
                        uncertain = {
                            key: prior[key]
                            for key in (
                                "schema",
                                "job_id",
                                "reservation_id",
                                "spec_sha256",
                                "owner_id",
                            )
                        }
                        uncertain["reason"] = (
                            "owner lock released without a verified process outcome"
                        )
                        _append(connection, job_id, "native_uncertain", uncertain)
        return {"claim": prior, "state": state, "outcome": outcome}


def cancel(
    store: ControlStore, job_id: str, reason: str, *, notify: bool = True
) -> dict[str, object]:
    # Timestamp inside the write transaction: an intervening heartbeat must not make
    # cancellation stale before it acquires the writer lock.
    clean_reason = _required_text(reason, "native fixture cancellation reason")
    if notify:
        # Stop transport precedes every potentially blocked database operation. It
        # does not acknowledge cleanup, durable intent, or permission to release funds.
        _request_live_stop(store._data_dir, job_id)
    status(store, job_id)
    with store._transaction(write=True) as connection:
        job = store._require_job(connection, job_id)
        if job["status"] in {"queued", "running"}:
            if not store._active_job_cancellation(connection, job_id):
                _append(
                    connection,
                    job_id,
                    "cancel_requested",
                    {"actor": "synthetic_fixture", "reason": clean_reason},
                )
            outcome = _events(connection, job_id).get("native_outcome")
            if outcome is not None and job["status"] == "running":
                _failure_close(connection, job_id, outcome, cancelled=True)
    return status(store, job_id)
