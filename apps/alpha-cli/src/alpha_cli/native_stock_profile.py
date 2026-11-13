"""Diagnostic current-profile comparison; never owner, execution or resume authority."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from alpha_cli._native_stock_launch import StockFixtureLaunch
from alpha_cli.control_store import (
    ControlStore,
    _canonical_json,
    _content_id,
    _d1_native_budget,
    _d1_native_spec,
)
from alpha_cli.native_stock_fixture import stock_fixture_manifest
from alpha_core import DataError


@dataclass(frozen=True)
class ProfileSelection:
    source: Path
    runtime: Path
    mode: str


@dataclass(frozen=True)
class RecordedProfile:
    spec: dict[str, object]
    cpu_milliseconds: int


def _decode(raw: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise DataError("duplicate recorded profile JSON key")
            result[key] = value
        return result

    if len(raw.encode()) > 65_536:
        raise DataError("recorded stock profile metadata exceeds bound")
    result = json.loads(raw, object_pairs_hook=pairs)
    if not isinstance(result, dict):
        raise DataError("recorded stock profile metadata is not an object")
    return result


def read_recorded_profile(
    connection: sqlite3.Connection, job_id: str, events: dict[str, dict[str, object]]
) -> RecordedProfile:
    """Rebuild historical identity, without evaluating current approval or owner eligibility."""
    try:
        claim = events["native_claim"]
        consumed = events["native_invocation"]
        row = connection.execute(
            """SELECT r.*, c.payload_json AS contract_payload_json, c.scope AS contract_scope,
                c.parent_contract_id AS contract_parent, e.active_job_id
            FROM research_launch_reservations r
            JOIN research_contracts c ON c.contract_id=r.contract_id AND c.project_id=r.project_id
            JOIN research_execution_events e ON e.project_id=r.project_id
                AND e.sequence=r.execution_sequence WHERE r.reservation_id=?""",
            (claim["reservation_id"],),
        ).fetchone()
        if row is None:
            raise DataError("recorded stock reservation is unavailable")
        job = ControlStore._require_job(connection, job_id)
        request = _decode(str(job["request_json"]))
        payload = _decode(str(row["contract_payload_json"]))
        spec = request["native_invocation_spec"]
        if not isinstance(spec, dict):
            raise DataError("recorded stock invocation is not an object")
        expected = _d1_native_spec(
            project_id=str(row["project_id"]),
            contract_id=str(row["contract_id"]),
            job_id=job_id,
            attempt_number=cast(int, request["attempt_number"]),
            payload=payload,
            native_manifest_sha256=cast(str, spec["native_manifest_sha256"]),
        )
        if (
            row["phase"] != "deep_research"
            or row["active_job_id"] != job_id
            or job["kind"] != "research:event-study"
            or job["project_id"] != row["project_id"]
            or request.get("stage") != "rdagent_native"
            or request.get("job_id") != job_id
            or request.get("contract_id") != row["contract_id"]
            or _content_id(
                "rc",
                {
                    "schema_version": 1,
                    "project_id": row["project_id"],
                    "scope": row["contract_scope"],
                    "parent_contract_id": row["contract_parent"],
                    "payload": payload,
                },
            )
            != row["contract_id"]
            or _canonical_json(expected, "rebuilt stock spec")
            != _canonical_json(spec, "recorded stock spec")
            or expected["spec_sha256"] != row["config_fingerprint"]
            or expected["spec_sha256"] != claim["spec_sha256"]
            or expected["native_manifest_sha256"] != claim["stock_profile_sha256"]
            or consumed["profile_sha256"] != claim["stock_profile_sha256"]
        ):
            raise DataError("recorded stock profile bindings differ")
        budget = _d1_native_budget(_decode(str(row["budget_reserved_json"])))
        approved = cast(dict[str, object], expected["approved_budget"])
        for key, minimum in {
            "rdagent_native_v1_loop_steps": 5,
            "rdagent_native_v1_model_calls": 2,
            "rdagent_native_v1_tool_calls": 2,
            "rdagent_native_v1_cpu_milliseconds": 1,
        }.items():
            if not minimum <= budget[key] <= cast(int, approved[key]):
                raise DataError("recorded stock request envelope differs")
        return RecordedProfile(
            expected, min(60_000, cast(int, budget["rdagent_native_v1_cpu_milliseconds"]))
        )
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        raise DataError("recorded stock profile is unavailable or invalid") from error


def verify_selected_profile(
    recorded: RecordedProfile | None, selected: ProfileSelection | None
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "unavailable",
        "scope": "current_files_match_recorded_only",
        "historical_worker_execution": "unavailable",
        "durable_owner_receipt_binding": "unavailable",
        "resume_allowed": False,
        "scientific_acceptance": "not_admitted",
    }
    if selected is None or recorded is None:
        return result | {"reason": "explicit_selection_or_recorded_consumption_unavailable"}
    try:
        # Constructor and measurement are file reads only. Never request admission,
        # call command/verify_result, spawn, or consult environment/auth configuration.
        measured = StockFixtureLaunch(
            selected.source, selected.mode, stock_runtime=selected.runtime
        )
        implementation = measured.implementation_fingerprints()
        worker = stock_fixture_manifest()
        if measured.measure() != measured.fingerprint:
            return result | {"reason": "selected_measurement_unstable"}
        spec = recorded.spec
        if (
            measured.fingerprint != spec["native_manifest_sha256"]
            or implementation != spec["implementation_fingerprints"]
        ):
            return result | {
                "status": "mismatch",
                "reason": "selected_identity_differs_from_record",
                "recorded_profile_sha256": spec["native_manifest_sha256"],
                "measured_profile_sha256": measured.fingerprint,
            }
        return result | {
            "status": "verified",
            "reason": "selected_current_identity_matches_record",
            "recorded_profile_sha256": spec["native_manifest_sha256"],
            "measured_profile_sha256": measured.fingerprint,
            "worker_manifest_sha256": worker,
            "selected_mode": selected.mode,
            "cpu_milliseconds": recorded.cpu_milliseconds,
            "runtime_scope": "python_pyvenv_selector_and_declared_lock_only",
        }
    except (DataError, OSError, ValueError, TypeError, KeyError, RecursionError):
        return result | {"reason": "selected_profile_cannot_be_measured"}


def bind_profile_declaration(
    evidence: dict[str, object], profile: dict[str, object]
) -> dict[str, object]:
    comparison = {"status": "unavailable", "scope": "current_request_declaration_only"}
    if profile.get("status") == "verified" and evidence.get("status") in {
        "advisory_only",
        "current_bytes_validated_only",
    }:
        matches = all(
            evidence.get(key) is not None
            and type(evidence.get(key)) is type(profile.get(value))
            and evidence.get(key) == profile.get(value)
            for key, value in {
                "declared_worker_manifest_sha256": "worker_manifest_sha256",
                "declared_mode": "selected_mode",
                "declared_cpu_milliseconds": "cpu_milliseconds",
            }.items()
        )
        comparison["status"] = "verified" if matches else "mismatch"
    return evidence | {"profile_declaration": comparison}
