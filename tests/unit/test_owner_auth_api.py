"""Closed WebAuthn action API mapping: no caller actor and no free-form command surface."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from alpha_core import DataError
from alpha_web.api import owner_auth as owner_api
from alpha_web.app import create_app

PROJECT_ID = "6f14da94-55fc-470a-b11a-d009f5ea15d9"
CONTRACT_ID = "rc_" + "a" * 64
SEMANTIC_PAYLOAD = {
    "schema": "SemanticOwnerActionV1",
    "schema_version": 1,
    "event_type": "definition",
    "verified_read_sha256": "a" * 64,
    "projection_sha256": "b" * 64,
    "run_id": "0123456789abcdef",
    "cutoff_confirmed_at": "2024-01-01T00:00:00Z",
    "expected_semantic_head_sha256": "c" * 64,
    "definition_label": "Bounded definition",
    "definition_text": "Exact semantic definition.",
}


def test_action_argv_uses_only_verified_actor_and_closed_mapping() -> None:
    argv = owner_api._action_argv(
        action_type="approve_exploration",
        project_id=PROJECT_ID,
        payload={"contract_id": CONTRACT_ID, "actor": "caller-injected"},
        actor="owner:verified-credential",
        reason="reviewed exact contract",
    )
    assert argv == [
        "research",
        "approve",
        "exploration",
        PROJECT_ID,
        CONTRACT_ID,
        "--actor",
        "owner:verified-credential",
        "--reason",
        "reviewed exact contract",
        "--json",
    ]
    with pytest.raises(DataError, match="unsupported owner action"):
        owner_api._action_argv(
            action_type="reveal_holdout",
            project_id=PROJECT_ID,
            payload={},
            actor="owner:verified-credential",
            reason="not permitted",
        )
    with pytest.raises(DataError, match="semantic owner action is not a CLI action"):
        owner_api._action_argv(
            action_type="record_semantic_event",
            project_id=PROJECT_ID,
            payload={},
            actor="owner:verified-credential",
            reason="not permitted",
        )


def test_every_closed_action_has_a_fixed_cli_mapping() -> None:
    base = {"claim_id": "sc_" + "1" * 64}
    assert (
        owner_api._action_argv(
            action_type="screen_source_claim",
            project_id=PROJECT_ID,
            payload=base,
            actor="owner:verified",
            reason="reviewed",
        )[3]
        == "screen"
    )
    assert (
        owner_api._action_argv(
            action_type="reject_source_claim",
            project_id=PROJECT_ID,
            payload=base,
            actor="owner:verified",
            reason="rejected",
        )[3]
        == "reject"
    )
    revision = owner_api._action_argv(
        action_type="revise_source_claim",
        project_id=PROJECT_ID,
        payload={**base, "revision": {"limitations": "narrow sample"}},
        actor="owner:verified",
        reason="revise",
    )
    assert "--revision-json" in revision
    frozen = owner_api._action_argv(
        action_type="freeze_source_pack",
        project_id=PROJECT_ID,
        payload={"source_ids": ["source-1", "source-2"], "definition": {"purpose": "case"}},
        actor="owner:verified",
        reason="freeze",
    )
    assert frozen.count("--source-id") == 2
    revised = owner_api._action_argv(
        action_type="revise_exploration",
        project_id=PROJECT_ID,
        payload={
            "source_pack_id": "sp_" + "2" * 64,
            "answers": {"outcome": "next_session"},
            "dataset": "rd_" + "3" * 64,
        },
        actor="owner:verified",
        reason="revise",
    )
    assert "--dataset" in revised and "--answer" in revised
    assert owner_api._action_argv(
        action_type="launch_d1",
        project_id=PROJECT_ID,
        payload={},
        actor="owner:verified",
        reason="launch",
    )[:4] == ["research", "run", "deep", PROJECT_ID]
    assert owner_api._action_argv(
        action_type="launch_d2",
        project_id=PROJECT_ID,
        payload={},
        actor="owner:verified",
        reason="launch",
    )[:4] == ["research", "run", "confirm", PROJECT_ID]
    decided = owner_api._action_argv(
        action_type="record_final_disposition",
        project_id=PROJECT_ID,
        payload={"outcome": "INCONCLUSIVE", "disposition": "park"},
        actor="owner:verified",
        reason="complete",
    )
    assert decided[:3] == ["research", "decide", PROJECT_ID]


def test_malformed_closed_action_payloads_fail_before_cli() -> None:
    common = {"project_id": PROJECT_ID, "actor": "owner:verified", "reason": "test"}
    with pytest.raises(DataError, match="claim_id"):
        owner_api._action_argv(action_type="screen_source_claim", payload={}, **common)
    with pytest.raises(DataError, match="revision payload"):
        owner_api._action_argv(
            action_type="revise_source_claim",
            payload={"claim_id": "sc_" + "1" * 64, "revision": []},
            **common,
        )
    with pytest.raises(DataError, match="source_ids"):
        owner_api._action_argv(
            action_type="freeze_source_pack", payload={"source_ids": []}, **common
        )
    with pytest.raises(DataError, match="definition"):
        owner_api._action_argv(
            action_type="freeze_source_pack",
            payload={"source_ids": ["source-1"], "definition": []},
            **common,
        )
    with pytest.raises(DataError, match="answers object"):
        owner_api._action_argv(
            action_type="revise_exploration",
            payload={"source_pack_id": "sp_" + "2" * 64, "answers": []},
            **common,
        )
    with pytest.raises(DataError, match="dataset is invalid"):
        owner_api._action_argv(
            action_type="revise_exploration",
            payload={"source_pack_id": "sp_" + "2" * 64, "answers": {}, "dataset": ""},
            **common,
        )


def test_action_challenge_rejects_caller_actor_and_unknown_action() -> None:
    base = {
        "action_type": "approve_exploration",
        "project_id": PROJECT_ID,
        "artifact_hash": "a" * 64,
        "expected_case_revision": "b" * 64,
        "consequence_summary": "Approve the exact exploration.",
        "reason": "reviewed",
        "payload": {"contract_id": CONTRACT_ID},
    }
    with TestClient(create_app(), base_url="http://localhost:8801") as client:
        actor = client.post("/api/owner-auth/actions/challenge", json={**base, "actor": "owner"})
        unknown = client.post(
            "/api/owner-auth/actions/challenge",
            json={**base, "action_type": "reveal_holdout"},
        )
    assert actor.status_code == 422
    assert unknown.status_code == 422


def test_generic_jobs_cannot_reach_owner_auth_cli() -> None:
    with TestClient(create_app(), base_url="http://localhost:8801") as client:
        response = client.post(
            "/api/jobs",
            json={
                "command": "owner-auth",
                "args": "enroll --reason generic-console-bypass",
            },
        )
    assert response.status_code == 422
    assert "trusted-local CLI" in response.json()["message"]


def test_route_handlers_delegate_only_to_owner_auth_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(owner_api, "registration_options", lambda **_: {"step": "options"})
    assert owner_api.start_registration(owner_api.OwnerRegistrationStart(token="x" * 20)) == {
        "step": "options"
    }
    monkeypatch.setattr(owner_api, "finish_registration", lambda **_: {"step": "finished"})
    assert owner_api.complete_registration(
        owner_api.OwnerRegistrationFinish(
            token="x" * 20, challenge_id="challenge", credential={"id": "credential"}
        )
    ) == {"step": "finished"}

    monkeypatch.setattr(owner_api, "derive_action_artifact_hash", lambda **_: "a" * 64)
    monkeypatch.setattr(owner_api, "action_binding", lambda **_: {"binding": "exact"})
    monkeypatch.setattr(owner_api, "authentication_options", lambda **_: {"step": "assert"})
    challenge = owner_api.OwnerActionChallengeRequest(
        action_type="approve_exploration",
        project_id=PROJECT_ID,
        artifact_hash="a" * 64,
        expected_case_revision="b" * 64,
        consequence_summary="approve exact contract",
        reason="reviewed",
        payload={"contract_id": CONTRACT_ID},
    )
    assert owner_api.start_action(challenge) == {"step": "assert"}
    mismatch = challenge.model_copy(update={"artifact_hash": "b" * 64})
    with pytest.raises(HTTPException, match="409"):
        owner_api.start_action(mismatch)
    monkeypatch.setattr(owner_api, "OWNER_ACTION_TYPES", ())
    with pytest.raises(HTTPException, match="409"):
        owner_api.start_action(challenge)

    authorization = {
        "actor": "owner:verified",
        "binding": {
            "action_type": "approve_exploration",
            "project_id": PROJECT_ID,
            "reason": "reviewed",
        },
    }
    monkeypatch.setattr(owner_api, "verify_action_assertion", lambda **_: authorization)
    monkeypatch.setattr(owner_api, "_run_json", lambda *_, **__: {"status": "recorded"})
    performed = owner_api.perform_action(
        owner_api.OwnerActionPerformRequest(
            challenge_id="challenge",
            credential={"id": "credential"},
            payload={"contract_id": CONTRACT_ID},
        )
    )
    assert performed["authorization"] == authorization
    assert performed["result"] == {"status": "recorded"}


def test_semantic_challenge_uses_server_derived_artifact_and_rejects_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    derived = "e" * 64
    binding = {
        "action_type": "record_semantic_event",
        "project_id": PROJECT_ID,
        "artifact_hash": derived,
        "expected_case_revision": "b" * 64,
        "request_hash": "f" * 64,
        "reason": "record exact semantic event",
    }
    monkeypatch.setattr(owner_api, "derive_action_artifact_hash", lambda **_: derived)
    monkeypatch.setattr(owner_api, "action_binding", lambda **_: binding)
    monkeypatch.setattr(owner_api, "authentication_options", lambda **_: {"step": "assert"})
    body = owner_api.OwnerActionChallengeRequest(
        action_type="record_semantic_event",
        project_id=PROJECT_ID,
        artifact_hash=derived,
        expected_case_revision="b" * 64,
        consequence_summary="Record one exact semantic event.",
        reason="record exact semantic event",
        payload=SEMANTIC_PAYLOAD,
    )
    assert owner_api.start_action(body) == {"step": "assert"}
    with pytest.raises(HTTPException, match="409"):
        owner_api.start_action(body.model_copy(update={"artifact_hash": "f" * 64}))


def test_semantic_perform_returns_atomic_result_without_cli_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorization = {
        "actor": "owner:verified",
        "binding": {
            "action_type": "record_semantic_event",
            "project_id": PROJECT_ID,
            "reason": "record exact semantic event",
        },
        "receipt_id": "receipt",
        "outcome": {
            "status": "semantic_event_recorded",
            "semantic_event_id": "se_" + "a" * 64,
            "semantic_event_sha256": "a" * 64,
        },
    }
    monkeypatch.setattr(owner_api, "verify_action_assertion", lambda **_: authorization)

    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("semantic owner action must not dispatch through CLI")

    monkeypatch.setattr(owner_api, "_action_argv", fail)
    monkeypatch.setattr(owner_api, "_run_json", fail)
    body = owner_api.OwnerActionPerformRequest(
        challenge_id="challenge",
        credential={"id": "credential"},
        payload=SEMANTIC_PAYLOAD,
    )
    assert owner_api.perform_action(body) == {
        "authorization": authorization,
        "result": authorization,
    }

    recovered = {
        **authorization,
        "receipt_id": "receipt",
        "recovered": True,
    }
    monkeypatch.setattr(owner_api, "verify_action_assertion", lambda **_: recovered)
    assert owner_api.perform_action(body) == {
        "authorization": recovered,
        "result": recovered,
    }


def test_route_handlers_convert_safe_domain_failures_to_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**_: object) -> dict[str, object]:
        raise DataError("safe owner-auth denial")

    monkeypatch.setattr(owner_api, "registration_options", fail)
    with pytest.raises(HTTPException, match="409"):
        owner_api.start_registration(owner_api.OwnerRegistrationStart(token="x" * 20))
    monkeypatch.setattr(owner_api, "finish_registration", fail)
    with pytest.raises(HTTPException, match="409"):
        owner_api.complete_registration(
            owner_api.OwnerRegistrationFinish(
                token="x" * 20, challenge_id="challenge", credential={}
            )
        )
    monkeypatch.setattr(owner_api, "derive_action_artifact_hash", fail)
    with pytest.raises(HTTPException, match="409"):
        owner_api.start_action(
            owner_api.OwnerActionChallengeRequest(
                action_type="approve_exploration",
                project_id=PROJECT_ID,
                artifact_hash="a" * 64,
                expected_case_revision="b" * 64,
                consequence_summary="exact consequence",
                reason="reviewed",
                payload={"contract_id": CONTRACT_ID},
            )
        )
    monkeypatch.setattr(owner_api, "verify_action_assertion", fail)
    with pytest.raises(HTTPException, match="409"):
        owner_api.perform_action(
            owner_api.OwnerActionPerformRequest(challenge_id="challenge", credential={}, payload={})
        )
