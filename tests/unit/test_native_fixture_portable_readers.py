"""Portable SQL consistency/atomicity tests; fixture journals are never issued authority."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from alpha_cli import _native_fixture_store as lifecycle
from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from tests.unit.test_research_control_store import (
    PROJECT_ID,
    START,
    _approved_native_d1,
    _native_d1_job,
    _project,
)

JOB = "4c657d82-fc1a-44d8-b49b-bfdcfe93c52c"


@dataclass
class InertCase:
    store: ControlStore
    contract: str
    reservation: dict[str, object]
    budget: object


@pytest.fixture
def inert(tmp_path: Path) -> InertCase:
    store = ControlStore(tmp_path)
    _project(store)
    contract, payload = _approved_native_d1(store)
    _, reservation = _native_d1_job(store, contract, job_id=JOB)
    budget = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    assert budget == payload["budget"]
    reserved = cast(dict[str, object], reservation["budget_reserved"])
    assert reserved["variants"] == 127
    assert reserved["rdagent_native_v1_loop_steps"] == 3
    return InertCase(store, contract, reservation, budget)


def _snapshot(case: InertCase) -> tuple[tuple[str, ...], object]:
    with case.store._transaction(write=False) as connection:
        rows = tuple(connection.iterdump())
    return rows, case.store.research_case_summary(PROJECT_ID)["elapsed_budget"]


def _reservation_read(case: InertCase) -> dict[str, object]:
    with case.store._transaction(write=False) as connection:
        return dict(lifecycle._reservation(connection, JOB))


def _journal_rows(case: InertCase) -> list[tuple[str, dict[str, object]]]:
    # Structural reader fixtures only: these deliberately do not identify a live owner.
    common: dict[str, object] = {
        "schema": "SyntheticNativeLifecycleV1",
        "job_id": JOB,
        "reservation_id": case.reservation["reservation_id"],
        "spec_sha256": case.reservation["config_fingerprint"],
        "owner_id": "untrusted-reader-fixture",
    }
    claim = {
        **common,
        "owner_pid": -1,
        "owner_birth": "untrusted-reader-fixture",
        "host": {"fixture": "untrusted-reader-only"},
        "lock_device": 0,
        "lock_inode": 0,
        "runtime_sha256": "0" * 64,
        "fixture": "wait",
        "seconds": 1,
        "cleanup_scope": "posix_process_group",
    }
    return [
        ("native_claim", claim),
        ("native_started", {**common, "leader_pid": -1}),
        (
            "native_outcome",
            {
                **common,
                "reason": "exit",
                "returncode": 0,
                "elapsed_seconds": 0.25,
                "cleanup_scope": "posix_process_group",
                "scientific_acceptance": "not_admitted",
            },
        ),
    ]


def _seed_untrusted_rows(case: InertCase, rows: list[tuple[str, object]]) -> None:
    # Only _events reads these rows. Never pass them to claim/record/status/dispatch APIs.
    with case.store._transaction(write=True) as connection:
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM job_events WHERE job_id=?", (JOB,)
        ).fetchone()[0]
        for kind, payload in rows:
            sequence += 1
            connection.execute(
                "INSERT INTO job_events VALUES (?, ?, ?, ?, ?)",
                (JOB, sequence, kind, START.isoformat(), json.dumps(payload)),
            )
        connection.execute("UPDATE jobs SET last_sequence=? WHERE job_id=?", (sequence, JOB))


def _events_read(case: InertCase) -> dict[str, dict[str, object]]:
    with case.store._transaction(write=False) as connection:
        return lifecycle._events(connection, JOB)


@pytest.mark.parametrize("no_spawn", [False, True])
def test_journal_reader_parses_bound_rows_without_issuing_or_changing_state(
    inert: InertCase, no_spawn: bool
) -> None:
    rows = _journal_rows(inert)
    if no_spawn:
        rows.pop(1)
        rows[-1][1].update(
            reason="owner_error", returncode=None, cleanup_scope="no_payload_spawn_attempted"
        )
    _seed_untrusted_rows(inert, [(kind, payload) for kind, payload in rows])
    before = _snapshot(inert)
    assert _events_read(inert) == dict(rows)
    returned = _events_read(inert)
    returned["native_claim"]["owner_id"] = "caller-mutated-copy"
    assert _events_read(inert) == dict(rows)
    assert _snapshot(inert) == before
    assert before[1] == inert.budget


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("duplicate", "duplicate protected events"),
        ("before_claim", "changed its claim binding"),
        ("schema", "invalid schema"),
        ("non_object", "invalid schema"),
        ("extra_field", "closed contract"),
        ("claim_job", "identity/order"),
        ("claim_reservation", "matching reserved invocation"),
        ("claim_spec", "matching reserved invocation"),
        ("later_owner", "changed its claim binding"),
        ("missing_start", "no observed start"),
        ("negative_elapsed", "invalid process evidence"),
        ("bool_elapsed", "invalid process evidence"),
        ("scientific_acceptance", "invalid process evidence"),
        ("missing_returncode", "invalid process evidence"),
        ("rule_result", "rule result observation binding is invalid"),
    ],
)
def test_journal_reader_denies_corruption_without_repair_or_charge_release(
    inert: InertCase, defect: str, message: str
) -> None:
    rows: list[tuple[str, object]] = [(kind, payload) for kind, payload in _journal_rows(inert)]
    claim = cast(dict[str, object], rows[0][1])
    outcome = cast(dict[str, object], rows[-1][1])
    if defect == "duplicate":
        rows.append(deepcopy(rows[-1]))
    elif defect == "before_claim":
        rows[0], rows[1] = rows[1], rows[0]
    elif defect == "schema":
        claim["schema"] = "UntrustedOtherSchema"
    elif defect == "non_object":
        rows[0] = ("native_claim", [])
    elif defect == "extra_field":
        claim["extra"] = True
    elif defect == "claim_job":
        claim["job_id"] = "foreign-job"
    elif defect == "claim_reservation":
        claim["reservation_id"] = "foreign-reservation"
    elif defect == "claim_spec":
        claim["spec_sha256"] = "0" * 64
    elif defect == "later_owner":
        outcome["owner_id"] = "foreign-owner"
    elif defect == "missing_start":
        rows.pop(1)
    elif defect == "negative_elapsed":
        outcome["elapsed_seconds"] = -1
    elif defect == "bool_elapsed":
        outcome["elapsed_seconds"] = True
    elif defect == "scientific_acceptance":
        outcome["scientific_acceptance"] = "admitted"
    elif defect == "missing_returncode":
        outcome["returncode"] = None
    else:
        assert defect == "rule_result"
        outcome["rule_result"] = {
            "schema": "SyntheticNativeRuleObservationV1",
            "receipt_sha256": "0" * 64,
        }
    _seed_untrusted_rows(inert, rows)
    before = _snapshot(inert)
    with pytest.raises(DataError, match=message):
        _events_read(inert)
    assert _snapshot(inert) == before
    assert before[1] == inert.budget


def test_reservation_reader_reconstructs_the_real_inert_invocation(inert: InertCase) -> None:
    before = _snapshot(inert)
    reservation = _reservation_read(inert)
    assert reservation["reservation_id"] == inert.reservation["reservation_id"]
    assert reservation["config_fingerprint"] == inert.reservation["config_fingerprint"]
    assert (
        json.loads(str(reservation["budget_reserved_json"])) == inert.reservation["budget_reserved"]
    )
    assert _snapshot(inert) == before


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("absent", "exactly one admitted reservation"),
        ("job_status", "running reservation/execution binding"),
        ("job_project", "running reservation/execution binding"),
        ("execution", "running reservation/execution binding"),
        ("terminal", "already has a terminal attempt"),
        ("phase", "active approved D1 contract"),
        ("review", "active approved D1 contract"),
        ("request_shape", "request must be an object"),
        ("request_binding", "request changed its invocation binding"),
        ("spec", "reserved invocation changed"),
    ],
)
def test_reservation_reader_rejects_stale_bindings_without_state_changes(
    inert: InertCase, defect: str, message: str
) -> None:
    store = inert.store
    if defect == "terminal":
        store.record_research_attempt(
            PROJECT_ID,
            inert.contract,
            kind="d1-deep-research",
            status="failed",
            config_fingerprint=str(inert.reservation["config_fingerprint"]),
            budget_used={},
            error="Inert portable terminal accounting fixture",
            details={"attempt_number": 1, "evidence_zone": "D1"},
            launch_reservation_id=str(inert.reservation["reservation_id"]),
        )
    else:
        with store._transaction(write=True) as connection:
            if defect == "absent":
                # Keep the charged reservation intact, but remove this job from its execution.
                connection.execute(
                    "UPDATE research_execution_events SET active_job_id=NULL WHERE active_job_id=?",
                    (JOB,),
                )
            elif defect == "job_status":
                connection.execute("UPDATE jobs SET status='failed' WHERE job_id=?", (JOB,))
            elif defect == "job_project":
                connection.execute("UPDATE jobs SET project_id=NULL WHERE job_id=?", (JOB,))
            elif defect == "execution":
                connection.execute(
                    "UPDATE research_execution_events SET state='paused' WHERE active_job_id=?",
                    (JOB,),
                )
            elif defect == "phase":
                connection.execute(
                    "UPDATE research_phase_events SET phase='confirmation_review' "
                    "WHERE project_id=? AND phase='deep_research'",
                    (PROJECT_ID,),
                )
            elif defect == "review":
                connection.execute(
                    "DELETE FROM research_contract_review_events WHERE contract_id=?",
                    (inert.contract,),
                )
            else:
                request = json.loads(
                    connection.execute(
                        "SELECT request_json FROM jobs WHERE job_id=?", (JOB,)
                    ).fetchone()[0]
                )
                if defect == "request_shape":
                    request = []
                elif defect == "request_binding":
                    request["job_id"] = "foreign-job"
                else:
                    assert defect == "spec"
                    request["native_invocation_spec"]["analysis_plan_sha256"] = "0" * 64
                connection.execute(
                    "UPDATE jobs SET request_json=? WHERE job_id=?", (json.dumps(request), JOB)
                )
    before = _snapshot(inert)
    with pytest.raises(DataError, match=message):
        _reservation_read(inert)
    assert _snapshot(inert) == before
    assert before[1] == inert.budget


@pytest.mark.parametrize("cancelled", [False, True])
def test_sql_failure_closure_is_once_only_and_retains_full_charge(
    inert: InertCase, cancelled: bool
) -> None:
    # Separate from untrusted journal fixtures: test the transactional helper, not process evidence.
    original = _reservation_read(inert)
    prior_sequence = inert.store.get_job(JOB)["last_sequence"]
    assert isinstance(prior_sequence, int)
    with inert.store._transaction(write=True) as connection:
        lifecycle._failure_close(connection, JOB, {"reason": "owner_error"}, cancelled=cancelled)
    job = inert.store.get_job(JOB)
    assert job["status"] == ("cancelled" if cancelled else "failed")
    assert job["terminal_error"] == (
        None if cancelled else "Synthetic native process only: owner_error"
    )
    with inert.store._transaction(write=False) as connection:
        reservation = dict(
            connection.execute("SELECT * FROM research_launch_reservations").fetchone()
        )
        assert reservation == original
        links = connection.execute("SELECT * FROM research_launch_attempt_links").fetchall()
        assert len(links) == 1 and links[0]["reservation_id"] == original["reservation_id"]
        attempt = connection.execute(
            "SELECT * FROM research_attempt_records WHERE attempt_id=?", (links[0]["attempt_id"],)
        ).fetchone()
        assert attempt["status"] == "failed" and attempt["run_id"] is None
        assert json.loads(attempt["budget_used_json"]) == {}
        assert json.loads(attempt["details_json"]) == {
            "attempt_number": 1,
            "evidence_zone": "D1",
            "native_process_only": True,
        }
        execution = ControlStore._latest_research_execution(connection, PROJECT_ID)
        assert execution is not None and execution["state"] == "failed"
        assert execution["active_job_id"] is None
        sequence = original["execution_sequence"]
        assert isinstance(sequence, int)
        assert execution["sequence"] == sequence + 1
        events = connection.execute(
            "SELECT * FROM job_events WHERE job_id=? ORDER BY sequence", (JOB,)
        ).fetchall()
        assert events[-1]["event_type"] == "status"
        assert job["last_sequence"] == events[-1]["sequence"] == prior_sequence + 1
        assert job["updated_at"] == job["heartbeat_at"] == events[-1]["occurred_at"]
        assert json.loads(events[-1]["payload_json"]) == {
            "from": "running",
            "to": "cancelled" if cancelled else "failed",
        }
        assert not any(str(row["event_type"]).startswith("native_") for row in events)
    closed = _snapshot(inert)
    assert closed[1] == inert.budget
    with (
        pytest.raises(DataError, match="running reservation/execution binding"),
        inert.store._transaction(write=True) as connection,
    ):
        lifecycle._failure_close(connection, JOB, {"reason": "owner_error"}, cancelled=cancelled)
    assert _snapshot(inert) == closed


@pytest.mark.parametrize("fault", ["after_status_append", "after_closure"])
def test_failure_closure_transaction_rolls_back_all_partial_writes(
    inert: InertCase, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    original = lifecycle._append

    def interrupted(
        connection: sqlite3.Connection, job: str, kind: str, payload: dict[str, object]
    ) -> None:
        original(connection, job, kind, payload)
        raise RuntimeError("injected portable closure interruption")

    if fault == "after_status_append":
        monkeypatch.setattr(lifecycle, "_append", interrupted)
    before = _snapshot(inert)
    with (
        pytest.raises(RuntimeError, match="injected portable closure interruption"),
        inert.store._transaction(write=True) as connection,
    ):
        lifecycle._failure_close(connection, JOB, {"reason": "owner_error"}, cancelled=False)
        raise RuntimeError("injected portable closure interruption")
    assert _snapshot(inert) == before
    assert before[1] == inert.budget
    assert _reservation_read(inert)["reservation_id"] == inert.reservation["reservation_id"]
