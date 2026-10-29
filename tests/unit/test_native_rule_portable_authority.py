"""Portable reads of genuine synthetic approvals; no native owner or launch capability."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_cli._native_rule_authority import RuleAuthority
from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from tests.unit.test_native_rule_authority import _approve
from tests.unit.test_research_control_store import PROJECT_ID


@pytest.fixture
def approved(tmp_path: Path) -> tuple[ControlStore, RuleAuthority]:
    # This helper consumes a real local confirmation and records the ordinary human review.
    _approve(tmp_path)
    store = ControlStore(tmp_path)
    contract_id = str(store.research_case_summary(PROJECT_ID)["active_contract_id"])
    return store, RuleAuthority(tmp_path, PROJECT_ID, contract_id)


def _snapshot(store: ControlStore) -> tuple[tuple[str, ...], dict[str, object]]:
    # Cover all persisted state, including jobs, reservations, confirmations and accounting.
    assert store.list_jobs() == []
    with store._transaction(write=False) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM research_launch_reservations").fetchone()[0]
            == 0
        )
        rows = tuple(connection.iterdump())
    return rows, store.research_case_summary(PROJECT_ID)


def test_genuine_consumed_approval_verifies_without_creating_execution_state(
    approved: tuple[ControlStore, RuleAuthority],
) -> None:
    store, authority = approved
    before = _snapshot(store)
    payload = store.get_research_contract(authority.contract_id)["payload"]
    assert authority.verify() == payload
    assert authority.verify() == payload
    assert _snapshot(store) == before


@pytest.mark.parametrize("wrong_binding", ["project", "contract"])
def test_authority_rejects_wrong_binding_without_changing_accounting(
    approved: tuple[ControlStore, RuleAuthority], wrong_binding: str
) -> None:
    store, authority = approved
    changed = RuleAuthority(
        authority.root,
        "11111111-1111-4111-8111-111111111111"
        if wrong_binding == "project"
        else authority.project_id,
        "rc_" + "0" * 64 if wrong_binding == "contract" else authority.contract_id,
    )
    before = _snapshot(store)
    with pytest.raises(DataError, match="unknown research contract"):
        changed.verify()
    assert _snapshot(store) == before
    # The valid binding remains usable; a failed read cannot invalidate its approval.
    assert authority.verify() == store.get_research_contract(authority.contract_id)["payload"]
    assert _snapshot(store) == before


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("withdrawn_review", "exact owner-approved contract"),
        ("challenge_request", "one exact consumed owner confirmation"),
        ("unused_challenge", "one exact consumed owner confirmation"),
    ],
)
def test_authority_rechecks_mutated_approval_evidence_without_side_effects(
    approved: tuple[ControlStore, RuleAuthority], mutation: str, message: str
) -> None:
    store, authority = approved
    # Establish the positive control before changing only the disposable fixture records.
    assert authority.verify() == store.get_research_contract(authority.contract_id)["payload"]
    with store._transaction(write=True) as connection:
        receipt = connection.execute("SELECT * FROM owner_action_receipts").fetchone()
        assert receipt is not None
        challenge_id = receipt["challenge_id"]
        challenge = connection.execute(
            "SELECT * FROM owner_auth_challenges WHERE challenge_id = ?", (challenge_id,)
        ).fetchone()
        assert challenge is not None and challenge["used_at"] is not None
        if mutation == "withdrawn_review":
            # Reviews are terminal: this models lost approval evidence, not a withdrawal API.
            connection.execute(
                "DELETE FROM research_contract_review_events WHERE contract_id = ?",
                (authority.contract_id,),
            )
        elif mutation == "challenge_request":
            binding = json.loads(challenge["binding_json"])
            binding["request_hash"] = "0" * 64
            connection.execute(
                "UPDATE owner_auth_challenges SET binding_json = ? WHERE challenge_id = ?",
                (json.dumps(binding), challenge_id),
            )
        else:
            assert mutation == "unused_challenge"
            connection.execute(
                "UPDATE owner_auth_challenges SET used_at = NULL WHERE challenge_id = ?",
                (challenge_id,),
            )
    before = _snapshot(store)
    with pytest.raises(DataError, match=message):
        authority.verify()
    assert _snapshot(store) == before


@pytest.mark.parametrize("field", ["request_hash", "actor"])
def test_consumed_receipt_rejects_mismatch_mutation_before_authority_read(
    approved: tuple[ControlStore, RuleAuthority], field: str
) -> None:
    store, authority = approved
    before = _snapshot(store)
    with (
        pytest.raises(DataError, match="control store transaction failed") as caught,
        store._transaction(write=True) as connection,
    ):
        if field == "request_hash":
            connection.execute("UPDATE owner_action_receipts SET request_hash = ?", ("0" * 64,))
        else:
            connection.execute(
                "UPDATE owner_action_receipts SET actor = ?", ("synthetic-different-owner",)
            )
    assert "owner action receipts are append-only" in str(caught.value.__cause__)
    assert _snapshot(store) == before
    assert authority.verify() == store.get_research_contract(authority.contract_id)["payload"]
    assert _snapshot(store) == before
