"""Portable pre-effect admission guards on ordinary, inert synthetic D1 records."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest

import tests.unit.test_research_control_store as fixtures
from alpha_cli.control_store import ControlStore, _d1_native_budget
from alpha_core import DataError
from tests.unit.test_native_rule_authority import _pilot
from tests.unit.test_research_control_store import (
    PROJECT_ID,
    START,
    _approved_native_d1,
    _native_d1_job,
    _project,
    _record_completed_d0,
)

JOB = "4c657d82-fc1a-44d8-b49b-bfdcfe93c52c"
MANIFEST = hashlib.sha256(b"pinned native manifest fixture").hexdigest()


@dataclass
class ApprovedCase:
    store: ControlStore
    contract_id: str
    payload: dict[str, object]


@pytest.fixture
def approved(tmp_path: Path) -> ApprovedCase:
    store = ControlStore(tmp_path)
    _project(store)
    contract, payload = _approved_native_d1(store)
    return ApprovedCase(store, contract, payload)


def _snapshot(case: ApprovedCase) -> tuple[tuple[str, ...], object]:
    with case.store._transaction(write=False) as connection:
        rows = tuple(connection.iterdump())
    return rows, case.store.research_case_summary(PROJECT_ID)["elapsed_budget"]


def _build(case: ApprovedCase, manifest: str, attempt: int = 1) -> dict[str, object]:
    return case.store.build_d1_native_invocation_spec(
        PROJECT_ID,
        case.contract_id,
        JOB,
        attempt_number=attempt,
        native_manifest_sha256=manifest,
    )


def _reserve(case: ApprovedCase, manifest: str = MANIFEST) -> dict[str, object]:
    return case.store.reserve_d1_native_research_launch(
        PROJECT_ID, case.contract_id, JOB, native_manifest_sha256=manifest
    )


@pytest.mark.parametrize(
    ("manifest", "attempt", "message"),
    [
        ("not-a-sha256", 1, "manifest fingerprint must be a SHA-256"),
        (MANIFEST, True, "attempt_number must be in 1..3"),
        (MANIFEST, 0, "attempt_number must be in 1..3"),
        (MANIFEST, 4, "attempt_number must be in 1..3"),
    ],
)
def test_public_spec_builder_rejects_invalid_identity_without_persisting_effects(
    approved: ApprovedCase, manifest: str, attempt: int, message: str
) -> None:
    before = _snapshot(approved)
    valid = _build(approved, MANIFEST)
    assert valid["project_id"] == PROJECT_ID
    assert valid["contract_id"] == approved.contract_id
    assert valid["job_id"] == JOB
    assert valid["native_manifest_sha256"] == MANIFEST
    assert valid["approved_budget"] == approved.payload["budget"]
    assert approved.store.list_jobs() == []
    with pytest.raises(DataError, match=message):
        _build(approved, manifest, attempt)
    assert _snapshot(approved) == before


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("execution", "active approved running job"),
        ("job", "requires its running research job"),
        ("request_binding", "invalid invocation binding"),
        ("missing_spec", "missing its typed invocation spec"),
        ("changed_spec", "does not match the approved contract"),
    ],
)
def test_reservation_denial_precedes_charge_for_stale_job_or_request(
    approved: ApprovedCase, defect: str, message: str
) -> None:
    store = approved.store
    _native_d1_job(store, approved.contract_id, job_id=JOB, reserve=False)
    if defect == "execution":
        store.transition_research_execution(
            PROJECT_ID,
            to_state="paused",
            contract_id=approved.contract_id,
            actor="synthetic-test-agent",
            reason="Pause the inert job before reservation",
            next_action="No native dispatch is permitted",
            responsibility="owner",
            active_job_id=JOB,
        )
    elif defect == "job":
        store.set_job_status(JOB, "failed", terminal_error="Inert pre-reservation failure")
    else:
        request = cast(dict[str, Any], deepcopy(store.get_job(JOB)["request"]))
        if defect == "request_binding":
            request["job_id"] = "foreign-job"
        elif defect == "missing_spec":
            request.pop("native_invocation_spec")
        else:
            assert defect == "changed_spec"
            request["native_invocation_spec"]["analysis_plan_sha256"] = "f" * 64
        # Corrupt only the inert request; no owner/observation/launch object is fabricated.
        with store._transaction(write=True) as connection:
            connection.execute(
                "UPDATE jobs SET request_json=? WHERE job_id=?", (json.dumps(request), JOB)
            )
    with store._transaction(write=False) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM research_launch_reservations").fetchone()[0]
            == 0
        )
    before = _snapshot(approved)
    assert cast(dict[str, object], before[1])["variants"] == 1  # Existing synthetic D0 only.
    with pytest.raises(DataError, match=message):
        _reserve(approved)
    assert _snapshot(approved) == before


def test_changed_consistent_replay_cannot_replace_or_refund_a_charged_invocation(
    approved: ApprovedCase,
) -> None:
    store = approved.store
    _, reservation = _native_d1_job(store, approved.contract_id, job_id=JOB)
    reserved = cast(dict[str, object], reservation["budget_reserved"])
    assert reserved["variants"] == 127 and reserved["rdagent_native_v1_loop_steps"] == 3
    assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == approved.payload["budget"]
    assert _reserve(approved) == reservation  # Genuine same-identity replay is allowed.
    changed_manifest = hashlib.sha256(b"different inert proposal manifest").hexdigest()
    changed_spec = _build(approved, changed_manifest)
    assert changed_spec["spec_sha256"] != reservation["config_fingerprint"]
    request = cast(dict[str, object], deepcopy(store.get_job(JOB)["request"]))
    request["native_invocation_spec"] = changed_spec
    with store._transaction(write=True) as connection:
        connection.execute(
            "UPDATE jobs SET request_json=? WHERE job_id=?", (json.dumps(request), JOB)
        )
    before = _snapshot(approved)
    # The new request/spec agree internally; the already-charged reservation must still win.
    with pytest.raises(DataError, match="replay changed its reserved invocation identity"):
        _reserve(approved, changed_manifest)
    assert _snapshot(approved) == before
    assert before[1] == approved.payload["budget"]
    with store._transaction(write=False) as connection:
        rows = connection.execute("SELECT * FROM research_launch_reservations").fetchall()
        assert len(rows) == 1
        assert rows[0]["reservation_id"] == reservation["reservation_id"]
        assert rows[0]["config_fingerprint"] == reservation["config_fingerprint"]
        assert json.loads(rows[0]["budget_reserved_json"]) == reserved


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("unknown_dimension", "unsupported native resource dimensions"),
        ("fractional_count", "must be a non-negative integer"),
        ("overflow_count", "must be a non-negative integer"),
    ],
)
def test_native_budget_validator_rejects_invalid_counts_without_rewriting_inputs(
    approved: ApprovedCase, defect: str, message: str
) -> None:
    budget = cast(dict[str, object], deepcopy(approved.payload["budget"]))
    assert _d1_native_budget(budget) == budget
    if defect == "unknown_dimension":
        budget["rdagent_native_v99_unapproved_work"] = 1
    elif defect == "fractional_count":
        budget["rdagent_native_v1_loop_steps"] = 1.5
    else:
        assert defect == "overflow_count"
        budget["rdagent_native_v1_cpu_milliseconds"] = 2**63
    unchanged_input = deepcopy(budget)
    before = _snapshot(approved)
    with pytest.raises(DataError, match=message):
        _d1_native_budget(budget)
    assert budget == unchanged_input
    assert _snapshot(approved) == before


def test_native_budget_validator_accepts_the_largest_signed_64_bit_count(
    approved: ApprovedCase,
) -> None:
    # The inclusive signed 64-bit bound; the overflow case above rejects 2**63.
    budget = cast(dict[str, object], deepcopy(approved.payload["budget"]))
    budget["rdagent_native_v1_cpu_milliseconds"] = 2**63 - 1
    unchanged_input = deepcopy(budget)
    assert _d1_native_budget(budget) == unchanged_input
    assert budget == unchanged_input


def _reservation_count(store: ControlStore) -> int:
    with store._transaction(write=False) as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM research_launch_reservations WHERE phase='deep_research'"
            ).fetchone()[0]
        )


def test_native_job_cannot_claim_a_retry_slot_before_its_initial_launch(
    approved: ApprovedCase,
) -> None:
    _native_d1_job(
        approved.store, approved.contract_id, job_id=JOB, attempt_number=2, reserve=False
    )
    before = _snapshot(approved)
    with pytest.raises(DataError, match="does not match the next launch slot"):
        _reserve(approved)
    assert _snapshot(approved) == before
    assert _reservation_count(approved.store) == 0


def test_unlinked_legacy_d1_attempts_count_toward_the_three_launch_cap(
    approved: ApprovedCase,
) -> None:
    store = approved.store
    for number in range(1, 4):
        # Ordinary pre-reservation direct attempts; each carries a small honest debit.
        store.record_research_attempt(
            PROJECT_ID,
            approved.contract_id,
            kind="d1-deep-research",
            status="failed",
            config_fingerprint=str(number) * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={"attempt_number": number, "evidence_zone": "D1"},
            error=f"legacy unreserved failure {number}",
            at=START + timedelta(minutes=9, seconds=10 + number),
        )
    _native_d1_job(store, approved.contract_id, job_id=JOB, reserve=False)
    before = _snapshot(approved)
    with pytest.raises(DataError, match="deep research stopped after the initial attempt"):
        _reserve(approved)
    assert _snapshot(approved) == before
    assert _reservation_count(store) == 0


def test_native_spec_requires_the_exact_approved_fingerprint_set(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    # Approval checks named hashes only; native admission also rejects an extra dimension.
    contract_id, _ = _approved_native_d1(
        store, implementation_fingerprints={"model": "sha256:" + "a" * 64}
    )
    case = ApprovedCase(store, contract_id, {})
    before = _snapshot(case)
    with pytest.raises(DataError, match="exact approved fingerprint set"):
        _build(case, MANIFEST)
    assert _snapshot(case) == before
    assert store.list_jobs() == []


def test_native_spec_rejects_an_unapproved_inactive_draft_contract(approved: ApprovedCase) -> None:
    # The draft is both unreviewed and not the active phase contract: this pins the combined
    # active-approved guard, not each of its clauses separately.
    payload = deepcopy(approved.payload)
    cast(dict[str, object], payload["budget"])["variants"] = 64
    draft = approved.store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=9, seconds=30),
    )
    before = _snapshot(approved)
    with pytest.raises(DataError, match="requires the active approved D1 contract"):
        _build(ApprovedCase(approved.store, str(draft["contract_id"]), payload), MANIFEST)
    assert _snapshot(approved) == before
    assert _build(approved, MANIFEST)["contract_id"] == approved.contract_id


def test_native_reservation_rejects_an_approved_fractional_exposure_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = fixtures._payload

    def fractional_requests(*args: Any, **kwargs: Any) -> dict[str, object]:
        payload = original(*args, **kwargs)
        cast(dict[str, object], payload["budget"])["source_requests"] = 2.5
        return payload

    # Approval accepts any finite non-negative budget; only native admission requires integers.
    monkeypatch.setattr(fixtures, "_payload", fractional_requests)
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_native_d1(store)
    assert cast(dict[str, object], payload["budget"])["source_requests"] == 2.5
    case = ApprovedCase(store, contract_id, payload)
    _native_d1_job(store, contract_id, job_id=JOB, reserve=False)
    before = _snapshot(case)
    with pytest.raises(DataError, match="integer exposure budgets"):
        _reserve(case)
    assert _snapshot(case) == before
    assert _reservation_count(store) == 0


def test_fixed_rule_study_reservation_admits_only_its_first_trial(tmp_path: Path) -> None:
    _pilot(tmp_path)
    store = ControlStore(tmp_path)
    contract_id = str(store.research_case_summary(PROJECT_ID)["active_contract_id"])
    case = ApprovedCase(store, contract_id, {})
    _native_d1_job(
        store,
        contract_id,
        job_id=JOB,
        attempt_number=2,
        reserve=False,
        started_at=START + timedelta(minutes=12),
    )
    before = _snapshot(case)
    with pytest.raises(DataError, match="fixed rule study permits exactly one trial"):
        _reserve(case)
    assert _snapshot(case) == before
    assert _reservation_count(store) == 0


@pytest.mark.parametrize(
    ("revised_cpu_milliseconds", "reserved_cpu_milliseconds"),
    [(5_000, None), (30_000, 20_000)],
)
def test_revised_contract_inherits_its_parent_native_reservation_charge(
    approved: ApprovedCase,
    revised_cpu_milliseconds: int,
    reserved_cpu_milliseconds: int | None,
) -> None:
    store = approved.store
    parent_id = approved.contract_id
    _, charged = _native_d1_job(store, parent_id, job_id=JOB)
    assert (
        cast(dict[str, object], charged["budget_reserved"])["rdagent_native_v1_cpu_milliseconds"]
        == 10_000
    )
    store.set_job_status(
        JOB, "failed", terminal_error="Inert synthetic failure", at=START + timedelta(minutes=11)
    )
    store.record_research_attempt(
        PROJECT_ID,
        parent_id,
        kind="d1-deep-research",
        status="failed",
        config_fingerprint=str(charged["config_fingerprint"]),
        budget_used={},
        details={"attempt_number": 1, "evidence_zone": "D1"},
        error="Inert synthetic failure",
        launch_reservation_id=str(charged["reservation_id"]),
        at=START + timedelta(minutes=11, seconds=1),
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="idle",
        contract_id=parent_id,
        actor="system",
        reason="The inert reservation remains fully charged.",
        next_action="Decide the parent contract.",
        responsibility="owner",
        at=START + timedelta(minutes=11, seconds=2),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="research_decision",
        contract_id=parent_id,
        actor="codex",
        reason="Stop the inert parent.",
        next_action="Owner decision.",
        responsibility="owner",
        at=START + timedelta(minutes=12),
    )
    store.record_research_decision(
        PROJECT_ID,
        parent_id,
        outcome="INCONCLUSIVE",
        disposition="revise",
        actor="owner",
        actor_kind="human",
        reason="Revise the synthetic protocol.",
        at=START + timedelta(minutes=13),
    )
    revised = deepcopy(approved.payload)
    budget = cast(dict[str, int], revised["budget"])
    for key in tuple(budget):
        budget[key] *= 2  # Leaves D0 headroom; CPU below is set independently.
    budget["rdagent_native_v1_cpu_milliseconds"] = revised_cpu_milliseconds
    protocol = cast(dict[str, Any], revised["protocol"])
    protocol["evidence_topology"]["D2"]["relation_to_prior"] = "unopened_sealed_reuse"
    revision_id = str(
        store.create_research_contract(
            PROJECT_ID,
            scope="exploration",
            parent_contract_id=parent_id,
            payload=revised,
            created_by="codex",
            author_kind="agent",
            at=START + timedelta(minutes=14),
        )["contract_id"]
    )
    store.reopen_research_revision(
        PROJECT_ID,
        revision_id,
        actor="codex",
        reason="Select the revision.",
        next_action="Owner review.",
        at=START + timedelta(minutes=15),
    )
    store.review_research_contract(
        PROJECT_ID,
        revision_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approve the revised synthetic protocol.",
        at=START + timedelta(minutes=16),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=revision_id,
        actor="owner",
        reason="Approved.",
        next_action="Run D0.",
        responsibility="codex",
        at=START + timedelta(minutes=17),
    )
    _record_completed_d0(store, revision_id, revised, at=START + timedelta(minutes=18))
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=revision_id,
        actor="codex",
        reason="D0 completed.",
        next_action="Reserve the native D1 envelope.",
        responsibility="codex",
        at=START + timedelta(minutes=19),
    )
    second_job = "86a846b0-3d66-4fc0-a3b1-c1f63a900882"
    _native_d1_job(
        store,
        revision_id,
        job_id=second_job,
        reserve=False,
        started_at=START + timedelta(minutes=20),
    )
    with store._transaction(write=False) as connection:
        before = tuple(connection.iterdump())

    def reserve() -> dict[str, object]:
        return store.reserve_d1_native_research_launch(
            PROJECT_ID, revision_id, second_job, native_manifest_sha256=MANIFEST
        )

    if reserved_cpu_milliseconds is None:
        with pytest.raises(
            DataError, match="exceeds approved 'rdagent_native_v1_cpu_milliseconds' budget"
        ):
            reserve()
        with store._transaction(write=False) as connection:
            assert tuple(connection.iterdump()) == before
        assert _reservation_count(store) == 1
        return
    reservation = reserve()
    reserved = cast(dict[str, object], reservation["budget_reserved"])
    # The parent's full native charge is debited from the revision's own approval.
    assert reserved["rdagent_native_v1_cpu_milliseconds"] == reserved_cpu_milliseconds
    assert reserved["rdagent_native_v1_loop_steps"] == 3
    assert reservation["launch_number"] == 1
    assert _reservation_count(store) == 2
