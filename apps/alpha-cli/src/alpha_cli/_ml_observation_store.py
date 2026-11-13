"""Bounded diagnostic journal in existing records, never Qlib admission/accounting.

Shelved (2026-11-14, triage card A): not wired in, kept because it is the groundwork for
running Qlib models through RD-Agent research cases (W09), after the daily rule study.

Checkpoint writers are trusted local engineering callers. Hashes and declared
scopes detect drift/replay; they do not authenticate execution or fitted state.
No operation here creates an attempt, settles a reservation or dispatches a worker.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from alpha_cli.control_store import (
    ControlStore,
    _at,
    _canonical_json,
    _canonical_uuid,
    _d1_native_spec,
)
from alpha_cli.ml_contract import MLContractError, canonical_json_bytes
from alpha_cli.ml_native_plan import (
    W09ManifestV1,
    W09ProtocolV1,
    _completed_bindings,
    _hash,
    _require_hash,
    bind_worker_observations,
    build_manifest,
    fingerprint_worker,
    validate_manifest,
)
from alpha_core import DataError

_TYPE = "w09_observation"
_MAX_BYTES = 2 * 1024 * 1024
_MAX_EVENTS = 1026  # 64 folds * 8 calls * (entry + terminal), binding + outcome.
_EVENT_FIELDS = {
    "sequence",
    "component",
    "operation",
    "status",
    "error_type",
    "input_hashes",
    "input_row_counts",
    "input_row_ids_sha256",
    "output_hashes",
    "state_sha256",
}


def _calls(manifest: W09ManifestV1, fold: int) -> list[tuple[str, str]]:
    return [
        (node.name, operation)
        for node in manifest.components
        if node.fold == fold
        for operation in (node.operation, "predict")
        if operation != "predict" or node.name in {"lightgbm", "ridge"}
    ]


def validate_prefix(manifest: W09ManifestV1, snapshot: dict[str, Any], lock: str) -> None:
    """Validate a finite reported prefix; incomplete calls are never completions."""
    validate_manifest(manifest)
    protocol = manifest.protocol
    context = {
        "request_schema_version": protocol.request_schema_version,
        "recipe": protocol.recipe,
        "request_sha256": protocol.request_sha256,
        "panel_sha256": protocol.panel_sha256,
        "snapshot_sha256": protocol.snapshot_sha256,
        "worker_lock_sha256": lock,
    }
    try:
        if (
            set(snapshot) != {"authority", "status", "error_type", "context", "folds"}
            or snapshot["authority"] != "invocation_local_observation_only"
            or type(snapshot["context"]["request_schema_version"]) is not int
            or snapshot["context"] != context
            or snapshot["status"] not in {"entered", "failed", "completed"}
            or type(snapshot["folds"]) is not dict
        ):
            raise MLContractError("W09 checkpoint context or state differs")
        failed = snapshot["status"] == "failed"
        error = snapshot["error_type"]
        if (failed and (type(error) is not str or not 1 <= len(error) <= 200)) or (
            not failed and error is not None
        ):
            raise MLContractError("W09 checkpoint error differs")
        folds = snapshot["folds"]
        if set(folds) != {str(i) for i in range(len(folds))} or len(folds) > len(protocol.folds):
            raise MLContractError("W09 checkpoint folds are not a finite prefix")
        incomplete = False
        for fold in range(len(folds)):
            sealed = folds[str(fold)]
            events = sealed["events"]
            expected = _calls(manifest, fold)
            if (
                set(sealed) != {"events", "trace_sha256"}
                or type(events) is not list
                or not 1 <= len(events) <= len(expected)
                or sealed["trace_sha256"] != _hash(events)
                or incomplete
            ):
                raise MLContractError("W09 checkpoint trace differs")
            for index, event in enumerate(events):
                if (
                    type(event) is not dict
                    or set(event) != _EVENT_FIELDS
                    or type(event["sequence"]) is not int
                    or event["sequence"] != index
                    or (event["component"], event["operation"]) != expected[index]
                    or event["status"] not in {"entered", "failed", "completed"}
                    or incomplete
                ):
                    raise MLContractError("W09 checkpoint call order or shape differs")
                for key in (
                    "input_hashes",
                    "input_row_counts",
                    "input_row_ids_sha256",
                    "output_hashes",
                ):
                    values = event[key]
                    if (
                        type(values) is not dict
                        or len(values) > 32
                        or any(type(name) is not str or not 1 <= len(name) <= 64 for name in values)
                    ):
                        raise MLContractError("W09 checkpoint call mappings are invalid")
                for digest in [
                    *event["input_hashes"].values(),
                    *event["output_hashes"].values(),
                    *event["input_row_ids_sha256"].values(),
                ]:
                    _require_hash(digest)
                rows, counts = event["input_row_ids_sha256"], event["input_row_counts"]
                if (
                    set(rows) != set(counts)
                    or not set(rows) <= set(event["input_hashes"])
                    or any(type(count) is not int or count <= 0 for count in counts.values())
                ):
                    raise MLContractError("W09 checkpoint row metadata differs")
                name, operation = expected[index]
                if name in {"lightgbm", "ridge", "rank_ensemble"} and event["input_hashes"].get(
                    "context"
                ) != _hash({"request_sha256": protocol.request_sha256, "fold": fold}):
                    raise MLContractError("W09 checkpoint call belongs to another request/fold")
                outputs = event["output_hashes"]
                if event["status"] == "completed":
                    fields = (
                        {"state", "train_features", "other_0_features", "other_1_features"}
                        if name == "normalizer"
                        else {"state", "normalized_labels"}
                        if name.startswith("label.")
                        else {"state"}
                        if operation == "fit"
                        else {"scores"}
                        if operation == "predict"
                        else {"predictions", "diagnostics"}
                    )
                    if (
                        set(outputs) != fields
                        or event["state_sha256"] != outputs.get("state", _hash(outputs))
                        or event["error_type"] is not None
                    ):
                        raise MLContractError("W09 checkpoint completed outputs differ")
                else:
                    incomplete = True
                    error = event["error_type"]
                    if (
                        outputs
                        or event["state_sha256"] is not None
                        or (event["status"] == "entered" and error is not None)
                        or (
                            event["status"] == "failed"
                            and (type(error) is not str or not 1 <= len(error) <= 200)
                        )
                    ):
                        raise MLContractError("W09 checkpoint incomplete call claims outputs")
            incomplete = incomplete or len(events) != len(expected)
        if snapshot["status"] == "completed" and (incomplete or len(folds) != len(protocol.folds)):
            raise MLContractError("W09 checkpoint completion lacks all calls")
    except (KeyError, TypeError, ValueError) as exc:
        raise MLContractError(f"Unsupported W09 checkpoint: {exc}") from exc


def _scope(
    connection: sqlite3.Connection, job_id: str, reservation_id: str, manifest: W09ManifestV1
) -> dict[str, object]:
    """Verify record associations only; never reinterpret the approved reservation."""
    from alpha_cli._native_rule_protocol import is_rule_contract

    protocol = manifest.protocol
    job = ControlStore._require_job(connection, job_id)
    ControlStore._require_project_experiment(
        connection, protocol.project_id, protocol.experiment_id
    )
    contract = ControlStore._require_research_contract(
        connection, protocol.project_id, protocol.contract_id
    )
    payload = json.loads(contract["payload_json"])
    if type(payload) is not dict:
        raise DataError("W09 diagnostic contract payload must be an object")
    if is_rule_contract(payload) or ControlStore._has_native_claim(connection, job_id):
        raise DataError("W09 diagnostics cannot attach to rule/native-owner records")
    reservation = connection.execute(
        """SELECT r.*, e.active_job_id FROM research_launch_reservations r
        JOIN research_execution_events e ON e.project_id=r.project_id
        AND e.sequence=r.execution_sequence
        AND e.contract_id=r.contract_id WHERE r.reservation_id=?""",
        (reservation_id,),
    ).fetchone()
    request = json.loads(job["request_json"])
    if type(request) is not dict:
        raise DataError("W09 diagnostic job request must be an object")
    expected_mapping = {
        "manifest_id": manifest.manifest_id,
        "experiment_id": protocol.experiment_id,
        "request_sha256": protocol.request_sha256,
    }
    if (
        reservation is None
        or reservation["active_job_id"] != job_id
        or reservation["project_id"] != protocol.project_id
        or reservation["contract_id"] != protocol.contract_id
        or reservation["phase"] != "deep_research"
        or reservation["kind"] != "d1-deep-research"
        or job["kind"] != "research:event-study"
        or job["project_id"] != protocol.project_id
        or job["experiment_id"] is not None
        or request.get("stage") != "rdagent_native"
        or request.get("contract_id") != protocol.contract_id
        or request.get("job_id") != job_id
        or request.get("w09_diagnostic") != expected_mapping
        or type(request.get("attempt_number")) is not int
        or request.get("attempt_number") != reservation["launch_number"]
    ):
        raise DataError("W09 diagnostic reservation/job scope differs")
    spec = _d1_native_spec(
        project_id=protocol.project_id,
        contract_id=protocol.contract_id,
        job_id=job_id,
        attempt_number=reservation["launch_number"],
        payload=payload,
        native_manifest_sha256=manifest.manifest_id,
    )
    if (
        canonical_json_bytes(request.get("native_invocation_spec")) != canonical_json_bytes(spec)
        or reservation["config_fingerprint"] != spec["spec_sha256"]
    ):
        raise DataError("W09 diagnostic reserved manifest differs")
    attempt = connection.execute(
        """SELECT a.* FROM research_launch_attempt_links l JOIN research_attempt_records a
        ON a.attempt_id=l.attempt_id WHERE l.reservation_id=?""",
        (reservation_id,),
    ).fetchone()
    if attempt is not None and any(
        attempt[key] != reservation[key]
        for key in ("project_id", "contract_id", "phase", "kind", "config_fingerprint")
    ):
        raise DataError("W09 diagnostic terminal attempt scope differs")
    return {
        "job_id": job_id,
        "reservation_id": reservation_id,
        "manifest_id": manifest.manifest_id,
        "attempt_id": None if attempt is None else attempt["attempt_id"],
        "run_id": None if attempt is None else attempt["run_id"],
    }


def _delta(
    prior: dict[str, Any] | None, current: dict[str, Any], manifest: W09ManifestV1
) -> dict[str, Any]:
    if prior is None:
        if current["status"] != "entered" or current["folds"]:
            raise DataError("W09 durable association requires the pre-call checkpoint first")
        return {
            "kind": "bound",
            "snapshot": current,
            "protocol": json.loads(canonical_json_bytes(asdict(manifest.protocol))),
        }
    if prior["status"] != "entered" or prior["context"] != current["context"]:
        raise DataError("W09 checkpoint cannot replace a terminal invocation or context")
    changed: list[tuple[str, int, dict[str, Any]]] = []
    for fold in set(prior["folds"]) | set(current["folds"]):
        before = prior["folds"].get(fold, {"events": []})["events"]
        after = current["folds"].get(fold, {"events": []})["events"]
        if len(after) < len(before):
            raise DataError("W09 checkpoint cannot erase calls")
        for index, event in enumerate(after):
            previous = before[index] if index < len(before) else None
            if previous == event:
                continue
            if previous is None:
                if event["status"] != "entered":
                    raise DataError("W09 call completion requires its durable entry")
            elif (
                previous["status"] != "entered"
                or event["status"] == "entered"
                or any(
                    previous[key] != event[key]
                    for key in _EVENT_FIELDS
                    - {"status", "error_type", "output_hashes", "state_sha256"}
                )
            ):
                raise DataError("W09 checkpoint changed an immutable call")
            changed.append((fold, index, event))
    if changed:
        if len(changed) != 1 or current["status"] != "entered":
            raise DataError("W09 checkpoint must acknowledge one call transition at a time")
        fold, index, event = changed[0]
        return {"kind": "call", "fold": fold, "index": index, "event": event}
    if current["status"] not in {"completed", "failed"}:
        raise DataError("W09 checkpoint is not a transition")
    return {"kind": "terminal", "status": current["status"], "error_type": current["error_type"]}


def _apply(prior: dict[str, Any] | None, delta: dict[str, Any]) -> dict[str, Any]:
    if type(delta) is not dict:
        raise DataError("W09 journal transition must be an object")
    if (
        delta.get("kind") == "bound"
        and set(delta) == {"kind", "snapshot", "protocol"}
        and prior is None
    ):
        return copy.deepcopy(delta["snapshot"])
    if prior is None:
        raise DataError("W09 journal lacks initial binding")
    current = copy.deepcopy(prior)
    if delta.get("kind") == "call" and set(delta) == {"kind", "fold", "index", "event"}:
        sealed = current["folds"].setdefault(delta["fold"], {"events": []})
        index, events = delta["index"], sealed["events"]
        if type(index) is not int or not 0 <= index <= len(events):
            raise DataError("W09 journal call index differs")
        if index == len(events):
            events.append(delta["event"])
        else:
            events[index] = delta["event"]
        sealed["trace_sha256"] = _hash(events)
    elif delta.get("kind") == "terminal" and set(delta) == {"kind", "status", "error_type"}:
        current.update(status=delta["status"], error_type=delta["error_type"])
    else:
        raise DataError("W09 journal transition differs")
    return current


def _history(
    connection: sqlite3.Connection, scope: dict[str, str], manifest: W09ManifestV1, lock: str
) -> tuple[dict[str, Any] | None, set[str]]:
    rows = connection.execute(
        """SELECT CASE WHEN length(CAST(payload_json AS BLOB)) <= 16384
        THEN payload_json ELSE NULL END AS payload_json FROM job_events
        WHERE job_id=? AND event_type=? ORDER BY sequence LIMIT ?""",
        (scope["job_id"], _TYPE, _MAX_EVENTS + 1),
    ).fetchall()
    if len(rows) > _MAX_EVENTS:
        raise DataError("W09 journal exceeds its finite operation bound")
    prior = None
    hashes: set[str] = set()
    for row in rows:
        encoded = row["payload_json"]
        if encoded is None:
            raise DataError("W09 journal entry exceeds its byte bound")
        body = json.loads(encoded)
        if (
            set(body) != {"schema", "scope", "previous", "snapshot_sha256", "delta"}
            or body["schema"] != "W09DiagnosticJournalV1"
            or body["scope"] != scope
            or body["previous"] != (None if prior is None else _hash(prior))
        ):
            raise DataError("W09 journal identity or chain differs")
        current = _apply(prior, body["delta"])
        validate_prefix(manifest, current, lock)
        if current["status"] == "completed":
            _completed_bindings(manifest, current, lock)
        if (
            canonical_json_bytes(_delta(prior, current, manifest))
            != canonical_json_bytes(body["delta"])
            or _hash(current) != body["snapshot_sha256"]
            or body["snapshot_sha256"] in hashes
        ):
            raise DataError("W09 journal replay or content differs")
        hashes.add(body["snapshot_sha256"])
        prior = current
    return prior, hashes


def _report(
    binding: dict[str, object], snapshot: dict[str, Any] | None, manifest: W09ManifestV1
) -> dict[str, object]:
    components = []
    for node in manifest.components:
        events = (
            [] if snapshot is None else snapshot["folds"].get(str(node.fold), {}).get("events", [])
        )
        observed = next(
            (
                event
                for event in events
                if (event["component"], event["operation"]) == (node.name, node.operation)
            ),
            None,
        )
        components.append(
            {
                "component_id": node.component_id,
                "fold": node.fold,
                "observed": observed is not None,
                "status": "unknown"
                if observed is None or observed["status"] == "entered"
                else observed["status"],
                "state_sha256": None if observed is None else observed["state_sha256"],
            }
        )
    return {
        **binding,
        "authority": "durable_diagnostic_association_only",
        "status": "unknown"
        if snapshot is None or snapshot["status"] == "entered"
        else snapshot["status"],
        "snapshot": snapshot,
        "components": components,
        "fitted_state_verified": False,
        "durable_accounting_verified": False,
        "execution_allowed": False,
        "reuse_allowed": False,
        "approved_resource_units": None,
        "run_link_verified": False,
    }


def record(
    store: ControlStore,
    job_id: str,
    reservation_id: str,
    manifest: W09ManifestV1,
    checkpoint: bytes,
    *,
    worker_project: Path,
) -> dict[str, object]:
    """Append one reported transition atomically; repeated delivery never executes work."""
    if type(checkpoint) is not bytes or len(checkpoint) > _MAX_BYTES:
        raise DataError("W09 checkpoint exceeds its byte bound")
    try:
        value = json.loads(checkpoint)
        if canonical_json_bytes(value) != checkpoint or set(value) != {"scope", "snapshot"}:
            raise DataError("W09 checkpoint requires exact canonical transport bytes")
        scope = value["scope"]
        if set(scope) != {"job_id", "reservation_id", "manifest_id", "invocation_id"} or scope != {
            "job_id": job_id,
            "reservation_id": reservation_id,
            "manifest_id": manifest.manifest_id,
            "invocation_id": _canonical_uuid(scope["invocation_id"], "invocation_id"),
        }:
            raise DataError("W09 checkpoint transport scope differs")
        fingerprint = fingerprint_worker(worker_project)
        if fingerprint.sha256 != manifest.protocol.dependency_sha256:
            raise DataError("W09 checkpoint dependencies changed")
        lock = dict(fingerprint.files)["uv.lock"]
        snapshot = value["snapshot"]
        validate_prefix(manifest, snapshot, lock)
        if snapshot["status"] == "completed":
            bind_worker_observations(manifest, snapshot, worker_project=worker_project)
        with store._transaction(write=True) as connection:
            binding = _scope(connection, job_id, reservation_id, manifest)
            other = connection.execute(
                """SELECT 1 FROM job_events WHERE event_type=? AND job_id<>?
                AND json_extract(payload_json, '$.scope.invocation_id')=? LIMIT 1""",
                (_TYPE, job_id, scope["invocation_id"]),
            ).fetchone()
            if other is not None:
                raise DataError("W09 invocation is already associated with another job")
            prior, hashes = _history(connection, scope, manifest, lock)
            digest = _hash(snapshot)
            if digest not in hashes:
                if len(hashes) >= _MAX_EVENTS:
                    raise DataError("W09 journal exceeds its finite operation bound")
                delta = _delta(prior, snapshot, manifest)
                body = {
                    "schema": "W09DiagnosticJournalV1",
                    "scope": scope,
                    "previous": None if prior is None else _hash(prior),
                    "snapshot_sha256": digest,
                    "delta": delta,
                }
                encoded = _canonical_json(body, "W09 diagnostic journal", max_bytes=16384)
                job = store._require_job(connection, job_id)
                timestamp, sequence = _at(None), int(job["last_sequence"]) + 1
                store._require_monotonic(job["updated_at"], timestamp, "W09 checkpoint")
                connection.execute(
                    "INSERT INTO job_events VALUES (?, ?, ?, ?, ?)",
                    (job_id, sequence, _TYPE, timestamp, encoded),
                )
                connection.execute(
                    "UPDATE jobs SET updated_at=?, last_sequence=? WHERE job_id=?",
                    (timestamp, sequence, job_id),
                )
                prior = snapshot
            return _report(binding, prior, manifest)
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise DataError(f"Invalid W09 diagnostic checkpoint: {exc}") from exc


def read(
    store: ControlStore,
    job_id: str,
    reservation_id: str,
    manifest: W09ManifestV1 | None,
    invocation_id: str,
) -> dict[str, object]:
    """Reopen saved diagnostics without worker files or an in-memory manifest."""
    if manifest is not None:
        validate_manifest(manifest)
    invocation_id = _canonical_uuid(invocation_id, "invocation_id")
    try:
        with store._transaction(write=False) as connection:
            first = connection.execute(
                """SELECT CASE WHEN length(CAST(payload_json AS BLOB)) <= 16384
                THEN payload_json ELSE NULL END AS payload_json FROM job_events
                WHERE job_id=? AND event_type=? ORDER BY sequence LIMIT 1""",
                (job_id, _TYPE),
            ).fetchone()
            if first is None:
                if manifest is None:
                    raise DataError("W09 journal has no durable binding")
                binding = _scope(connection, job_id, reservation_id, manifest)
                return _report(binding, None, manifest)
            encoded = first["payload_json"]
            if encoded is None:
                raise DataError("W09 journal entry exceeds its byte bound")
            body = json.loads(encoded)
            metadata = body["delta"]["protocol"]
            if type(metadata) is not dict or type(metadata.get("folds")) is not list:
                raise DataError("W09 journal lacks its declared protocol metadata")
            recovered = build_manifest(
                W09ProtocolV1(**{**metadata, "folds": tuple(metadata["folds"])})
            )
            if manifest is not None and recovered != manifest:
                raise DataError("W09 journal manifest differs from supplied metadata")
            manifest = recovered
            scope = {
                "job_id": job_id,
                "reservation_id": reservation_id,
                "manifest_id": manifest.manifest_id,
                "invocation_id": invocation_id,
            }
            binding = _scope(connection, job_id, reservation_id, manifest)
            lock = body["delta"]["snapshot"]["context"]["worker_lock_sha256"]
            _require_hash(lock)
            snapshot, _ = _history(connection, scope, manifest, lock)
            return _report(binding, snapshot, manifest)
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise DataError(f"Invalid W09 diagnostic journal: {exc}") from exc
