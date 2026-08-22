"""WebAuthn ceremony bindings and exact-origin verification."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from urllib.parse import parse_qs, urlparse

import pytest
from webauthn.helpers import bytes_to_base64url

import alpha_cli.control_store as control_store_module
from alpha_cli import owner_auth
from alpha_cli.control_store import ControlStore, research_case_revision
from alpha_core import DataError

PROJECT_ID = "6f14da94-55fc-470a-b11a-d009f5ea15d9"
NOW = datetime(2026, 8, 13, 2, 0, tzinfo=UTC)
CASE = {
    "project_id": PROJECT_ID,
    "active_contract_id": "rc_" + "a" * 64,
    "phase": "exploration_review",
    "execution_state": "idle",
    "source_pack_id": "sp_" + "b" * 64,
}


def _semantic_source(case_revision: str) -> dict[str, object]:
    return {
        "project_id": PROJECT_ID,
        "case_contract_id": "rc_" + "1" * 64,
        "source_contract_id": "rc_" + "2" * 64,
        "case_revision": case_revision,
        "verified_read_sha256": "b" * 64,
        "projection_sha256": "c" * 64,
        "run_id": "0123456789abcdef",
        "cutoff_confirmed_at": "2026-08-13T00:00:00.000000Z",
    }


def _semantic_payload(source: dict[str, object], head: str) -> dict[str, object]:
    return {
        "schema": "SemanticOwnerActionV1",
        "schema_version": 1,
        "event_type": "definition",
        "verified_read_sha256": source["verified_read_sha256"],
        "projection_sha256": source["projection_sha256"],
        "run_id": source["run_id"],
        "cutoff_confirmed_at": source["cutoff_confirmed_at"],
        "expected_semantic_head_sha256": head,
        "definition_label": "Bounded semantic definition",
        "definition_text": "A definition committed by the owner.",
    }


def _semantic_owner_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[ControlStore, str, dict[str, object], dict[str, object], dict[str, object]]:
    store = ControlStore(tmp_path)
    _project(store)
    with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
        for contract_id in ("rc_" + "1" * 64, "rc_" + "2" * 64):
            connection.execute(
                """INSERT INTO research_contracts
                (contract_id, project_id, scope, parent_contract_id, payload_json,
                 created_by, author_kind, created_at)
                VALUES (?, ?, 'exploration', NULL, '{}', 'owner', 'human', ?)""",
                (contract_id, PROJECT_ID, NOW.isoformat().replace("+00:00", "Z")),
            )
    credential_id = _enroll_credential(store)
    revision = research_case_revision(CASE)
    source = _semantic_source(revision)
    head = control_store_module._semantic_empty_head_sha256(PROJECT_ID)
    payload = _semantic_payload(source, head)
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    monkeypatch.setattr(
        ControlStore,
        "_research_case_revision_locked",
        lambda self, _connection, _project_id: revision,
    )
    monkeypatch.setattr(
        ControlStore,
        "_verified_semantic_source_locked",
        lambda self, _connection, _project_id: source,
    )
    binding = owner_auth.action_binding(
        data_dir=tmp_path,
        action_type="record_semantic_event",
        project_id=PROJECT_ID,
        artifact_hash="browser-commitment",
        expected_case_revision=revision,
        consequence_summary="Record the exact semantic event.",
        reason="owner reviewed the semantic definition.",
        payload=payload,
    )
    challenge = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"s" * 32,
        binding=binding,
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    return store, credential_id, payload, challenge, binding


def _project(store: ControlStore) -> None:
    store.create_project(
        name="Touch ID test",
        hypothesis="A bounded research question.",
        falsification_criterion="Reject when evidence contradicts it.",
        project_id=PROJECT_ID,
        at=NOW,
    )


def _enroll_credential(store: ControlStore) -> str:
    token_hash = hashlib.sha256(b"trusted-test-token").hexdigest()
    request = store.create_owner_enrollment_request(
        token_hash=token_hash,
        reason="initial enrollment",
        replace_existing=False,
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    registration = store.create_owner_auth_challenge(
        ceremony="registration",
        challenge=b"r" * 32,
        binding={"token_hash": token_hash},
        enrollment_request_id=str(request["request_id"]),
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    credential_id = bytes_to_base64url(b"touch-id-credential")
    store.complete_owner_registration(
        token_hash=token_hash,
        challenge_id=str(registration["challenge_id"]),
        credential_id=credential_id,
        public_key=b"public-key",
        sign_count=1,
        transports=["internal"],
        now=NOW + timedelta(seconds=1),
    )
    return credential_id


def test_registration_requires_exact_origin_and_user_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    token = "trusted-token-with-enough-entropy"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    request = store.create_owner_enrollment_request(
        token_hash=token_hash,
        reason="initial enrollment",
        replace_existing=False,
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    challenge = store.create_owner_auth_challenge(
        ceremony="registration",
        challenge=b"r" * 32,
        binding={"token_hash": token_hash},
        enrollment_request_id=str(request["request_id"]),
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    captured: dict[str, object] = {}

    def verify(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            credential_id=b"touch-id-credential",
            credential_public_key=b"verified-public-key",
            sign_count=1,
        )

    monkeypatch.setattr(owner_auth, "verify_registration_response", verify)
    result = owner_auth.finish_registration(
        data_dir=tmp_path,
        token=token,
        challenge_id=str(challenge["challenge_id"]),
        credential={
            "id": bytes_to_base64url(b"touch-id-credential"),
            "response": {"transports": ["internal"]},
        },
        now=NOW + timedelta(seconds=1),
    )

    assert str(result["actor"]).startswith("owner:")
    assert captured["expected_origin"] == "http://localhost:8801"
    assert captured["expected_rp_id"] == "localhost"
    assert captured["require_user_verification"] is True


def test_modified_action_payload_fails_before_assertion_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    credential_id = "touch-id-credential"
    token_hash = hashlib.sha256(b"token").hexdigest()
    request = store.create_owner_enrollment_request(
        token_hash=token_hash,
        reason="initial enrollment",
        replace_existing=False,
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    registration = store.create_owner_auth_challenge(
        ceremony="registration",
        challenge=b"r" * 32,
        binding={"token_hash": token_hash},
        enrollment_request_id=str(request["request_id"]),
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    store.complete_owner_registration(
        token_hash=token_hash,
        challenge_id=str(registration["challenge_id"]),
        credential_id=credential_id,
        public_key=b"public-key",
        sign_count=1,
        transports=["internal"],
        now=NOW + timedelta(seconds=1),
    )
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    binding = {
        "action_type": "approve_exploration",
        "project_id": PROJECT_ID,
        "artifact_hash": "a" * 64,
        "expected_case_revision": research_case_revision(CASE),
        "consequence_summary": "Approve exact exploration.",
        "reason": "reviewed",
        "request_hash": hashlib.sha256(b'{"contract_id":"rc_' + b"a" * 64 + b'"}').hexdigest(),
    }
    challenge = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"a" * 32,
        binding=binding,
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    called = False

    def verify(**_: object) -> SimpleNamespace:
        nonlocal called
        called = True
        return SimpleNamespace(new_sign_count=2)

    monkeypatch.setattr(owner_auth, "verify_authentication_response", verify)
    with pytest.raises(DataError, match="payload changed"):
        owner_auth.verify_action_assertion(
            data_dir=tmp_path,
            challenge_id=str(challenge["challenge_id"]),
            credential={"id": credential_id},
            payload={"contract_id": "rc_" + "f" * 64},
            now=NOW + timedelta(seconds=2),
        )
    assert called is False


def test_stale_case_fails_before_assertion_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _enroll_credential(store)
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    binding = owner_auth.action_binding(
        data_dir=tmp_path,
        action_type="approve_exploration",
        project_id=PROJECT_ID,
        artifact_hash="a" * 64,
        expected_case_revision=research_case_revision(CASE),
        consequence_summary="Approve the exact exploration.",
        reason="reviewed",
        payload={"contract_id": "rc_" + "a" * 64},
    )
    challenge = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"a" * 32,
        binding=binding,
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    changed = {**CASE, "phase": "deep_research"}
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: changed)
    called = False

    def verify(**_: object) -> SimpleNamespace:
        nonlocal called
        called = True
        return SimpleNamespace(new_sign_count=2)

    monkeypatch.setattr(owner_auth, "verify_authentication_response", verify)
    with pytest.raises(DataError, match="research case changed"):
        owner_auth.verify_action_assertion(
            data_dir=tmp_path,
            challenge_id=str(challenge["challenge_id"]),
            credential={"id": "not-reached"},
            payload={"contract_id": "rc_" + "a" * 64},
            now=NOW + timedelta(seconds=2),
        )
    assert called is False


def test_one_valid_assertion_is_consumed_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    credential_id = _enroll_credential(store)
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    payload = {"contract_id": "rc_" + "a" * 64}
    binding = owner_auth.action_binding(
        data_dir=tmp_path,
        action_type="approve_exploration",
        project_id=PROJECT_ID,
        artifact_hash="a" * 64,
        expected_case_revision=research_case_revision(CASE),
        consequence_summary="Approve the exact exploration.",
        reason="reviewed",
        payload=payload,
    )
    challenge = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"a" * 32,
        binding=binding,
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    monkeypatch.setattr(
        owner_auth,
        "verify_authentication_response",
        lambda **_: SimpleNamespace(new_sign_count=2),
    )
    credential = {"id": credential_id, "response": {"signature": "redacted-test"}}
    receipt = owner_auth.verify_action_assertion(
        data_dir=tmp_path,
        challenge_id=str(challenge["challenge_id"]),
        credential=credential,
        payload=payload,
        now=NOW + timedelta(seconds=2),
    )
    assert receipt["action_type"] == "approve_exploration"
    assert receipt["outcome"] == {"status": "assertion_consumed"}
    with pytest.raises(DataError, match="already used"):
        owner_auth.verify_action_assertion(
            data_dir=tmp_path,
            challenge_id=str(challenge["challenge_id"]),
            credential=credential,
            payload=payload,
            now=NOW + timedelta(seconds=3),
        )


def test_library_origin_rejection_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    token = "trusted-token-with-enough-entropy"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    request = store.create_owner_enrollment_request(
        token_hash=token_hash,
        reason="initial enrollment",
        replace_existing=False,
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    challenge = store.create_owner_auth_challenge(
        ceremony="registration",
        challenge=b"r" * 32,
        binding={"token_hash": token_hash},
        enrollment_request_id=str(request["request_id"]),
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )

    def reject_wrong_origin(**kwargs: object) -> SimpleNamespace:
        assert kwargs["expected_origin"] == "http://localhost:8801"
        raise ValueError("unexpected client origin http://127.0.0.1:8801")

    monkeypatch.setattr(owner_auth, "verify_registration_response", reject_wrong_origin)
    with pytest.raises(DataError, match="could not be verified"):
        owner_auth.finish_registration(
            data_dir=tmp_path,
            token=token,
            challenge_id=str(challenge["challenge_id"]),
            credential={"id": "wrong-origin", "response": {}},
            now=NOW + timedelta(seconds=1),
        )


def test_trusted_enrollment_issues_options_with_platform_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "alpha_cli.owner_auth.secrets.token_urlsafe", lambda _: "issued-fragment-token"
    )
    monkeypatch.setattr("alpha_cli.owner_auth.secrets.token_bytes", lambda _: b"c" * 32)
    issued = owner_auth.issue_enrollment(
        data_dir=tmp_path,
        reason="initial local enrollment",
        replace_existing=False,
        now=NOW,
    )
    parsed = urlparse(str(issued["url"]))
    token = parse_qs(parsed.fragment)["token"][0]
    options = owner_auth.registration_options(
        data_dir=tmp_path,
        token=token,
        now=NOW + timedelta(seconds=1),
    )
    public_key = options["public_key"]
    assert isinstance(public_key, dict)
    assert public_key["rp"]["id"] == "localhost"
    selection = public_key["authenticatorSelection"]
    assert selection["authenticatorAttachment"] == "platform"
    assert selection["residentKey"] == "required"
    assert selection["userVerification"] == "required"


def test_enrollment_uses_current_utc_when_no_clock_is_injected(tmp_path: Path) -> None:
    issued = owner_auth.issue_enrollment(
        data_dir=tmp_path,
        reason="exercise production clock path",
        replace_existing=False,
    )
    assert str(issued["url"]).startswith("http://localhost:8801/")


def test_authentication_options_are_uv_required_and_credential_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    credential_id = _enroll_credential(store)
    monkeypatch.setattr("alpha_cli.owner_auth.secrets.token_bytes", lambda _: b"a" * 32)
    options = owner_auth.authentication_options(
        data_dir=tmp_path,
        binding={"action_type": "approve_exploration", "project_id": PROJECT_ID},
        now=NOW + timedelta(seconds=2),
    )
    public_key = options["public_key"]
    assert isinstance(public_key, dict)
    assert public_key["rpId"] == "localhost"
    assert public_key["userVerification"] == "required"
    assert public_key["allowCredentials"][0]["id"] == credential_id


@pytest.mark.parametrize(
    ("action_type", "payload", "expected"),
    [
        ("screen_source_claim", {"claim_id": "sc_" + "1" * 64}, "1" * 64),
        ("approve_confirmation", {"contract_id": "rc_" + "2" * 64}, "2" * 64),
        (
            "freeze_source_pack",
            {"source_ids": ["source-1"], "definition": {"purpose": "test"}},
            "fc3062aa9595ce5bfe4cba3ee640a17ab97cee3447cd14e098813a3dfd164be1",
        ),
    ],
)
def test_action_artifact_hash_is_derived_from_closed_payload(
    tmp_path: Path, action_type: str, payload: dict[str, object], expected: str
) -> None:
    assert (
        owner_auth.derive_action_artifact_hash(
            data_dir=tmp_path,
            action_type=action_type,
            project_id=PROJECT_ID,
            payload=payload,
        )
        == expected
    )


def test_active_contract_action_hash_and_invalid_artifacts_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    assert (
        owner_auth.derive_action_artifact_hash(
            data_dir=tmp_path,
            action_type="launch_d1",
            project_id=PROJECT_ID,
            payload={},
        )
        == "a" * 64
    )
    with pytest.raises(DataError, match="unsupported owner action"):
        owner_auth.derive_action_artifact_hash(
            data_dir=tmp_path,
            action_type="place_order",
            project_id=PROJECT_ID,
            payload={},
        )
    with pytest.raises(DataError, match="not content-addressed"):
        owner_auth.derive_action_artifact_hash(
            data_dir=tmp_path,
            action_type="approve_exploration",
            project_id=PROJECT_ID,
            payload={"contract_id": "legacy"},
        )
    with pytest.raises(DataError, match="lowercase SHA-256"):
        owner_auth.derive_action_artifact_hash(
            data_dir=tmp_path,
            action_type="approve_exploration",
            project_id=PROJECT_ID,
            payload={"contract_id": "rc_" + "A" * 64},
        )


def test_action_binding_rejects_wrong_action_revision_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    revision = research_case_revision(CASE)
    with pytest.raises(DataError, match="unsupported owner action"):
        owner_auth.action_binding(
            data_dir=tmp_path,
            action_type="place_order",
            project_id=PROJECT_ID,
            artifact_hash="a" * 64,
            expected_case_revision=revision,
            consequence_summary="exact consequence",
            reason="reviewed",
            payload={"contract_id": "rc_" + "a" * 64},
        )


def test_semantic_action_binding_uses_server_prepared_artifact_and_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    payload = {"event_type": "definition", "definition_text": "bounded"}
    monkeypatch.setattr(
        ControlStore,
        "prepare_semantic_action",
        lambda self, project_id, payload, expected_case_revision: {
            "artifact_hash": "e" * 64,
            "request_hash": "f" * 64,
            "case_revision": expected_case_revision,
        },
        raising=False,
    )
    binding = owner_auth.action_binding(
        data_dir=tmp_path,
        action_type="record_semantic_event",
        project_id=PROJECT_ID,
        artifact_hash="browser-commitment",
        expected_case_revision=research_case_revision(CASE),
        consequence_summary="Record the exact semantic event.",
        reason="owner reviewed the semantic definition.",
        payload=payload,
    )
    assert binding["artifact_hash"] == "e" * 64
    assert binding["request_hash"] == "f" * 64


def test_semantic_assertion_is_atomic_and_idempotently_recoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
        for contract_id in ("rc_" + "1" * 64, "rc_" + "2" * 64):
            connection.execute(
                """INSERT INTO research_contracts
                (contract_id, project_id, scope, parent_contract_id, payload_json,
                 created_by, author_kind, created_at)
                VALUES (?, ?, 'exploration', NULL, '{}', 'owner', 'human', ?)""",
                (contract_id, PROJECT_ID, NOW.isoformat().replace("+00:00", "Z")),
            )
    credential_id = _enroll_credential(store)
    revision = research_case_revision(CASE)
    source = _semantic_source(revision)
    head = control_store_module._semantic_empty_head_sha256(PROJECT_ID)
    payload = _semantic_payload(source, head)
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    monkeypatch.setattr(
        ControlStore,
        "_research_case_revision_locked",
        lambda self, _connection, _project_id: revision,
    )
    monkeypatch.setattr(
        ControlStore,
        "_verified_semantic_source_locked",
        lambda self, _connection, _project_id: source,
    )
    binding = owner_auth.action_binding(
        data_dir=tmp_path,
        action_type="record_semantic_event",
        project_id=PROJECT_ID,
        artifact_hash="browser-commitment",
        expected_case_revision=revision,
        consequence_summary="Record the exact semantic event.",
        reason="owner reviewed the semantic definition.",
        payload=payload,
    )
    challenge = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"s" * 32,
        binding=binding,
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    monkeypatch.setattr(
        owner_auth,
        "verify_authentication_response",
        lambda **_: SimpleNamespace(new_sign_count=2),
    )
    credential = {"id": credential_id, "response": {"signature": "redacted"}}
    result = owner_auth.verify_action_assertion(
        data_dir=tmp_path,
        challenge_id=str(challenge["challenge_id"]),
        credential=credential,
        payload=payload,
        now=NOW + timedelta(seconds=2),
    )
    result_outcome = cast(dict[str, object], result["outcome"])
    assert result_outcome["status"] == "semantic_event_recorded"
    assert str(result_outcome["semantic_event_id"]).startswith("se_")
    with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
        assert connection.execute(
            "SELECT sign_count FROM owner_credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM research_semantic_events").fetchone() == (
            1,
        )
    monkeypatch.setattr(
        owner_auth,
        "verify_authentication_response",
        lambda **_: pytest.fail("recovery must not verify WebAuthn"),
    )
    recovered = owner_auth.verify_action_assertion(
        data_dir=tmp_path,
        challenge_id=str(challenge["challenge_id"]),
        credential=credential,
        payload=payload,
        now=NOW + timedelta(minutes=5),
    )
    assert recovered["outcome"] == result["outcome"]
    with pytest.raises(DataError, match="payload hash"):
        owner_auth.verify_action_assertion(
            data_dir=tmp_path,
            challenge_id=str(challenge["challenge_id"]),
            credential=credential,
            payload={**payload, "definition_text": "different"},
            now=NOW + timedelta(minutes=5),
        )
    with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
        connection.execute(
            "UPDATE owner_auth_challenges SET binding_json = ? WHERE challenge_id = ?",
            (
                owner_auth._canonical_json({**binding, "artifact_hash": "f" * 64}, "binding"),
                challenge["challenge_id"],
            ),
        )
        connection.commit()
    with pytest.raises(DataError, match="recovery receipt binding"):
        owner_auth.verify_action_assertion(
            data_dir=tmp_path,
            challenge_id=str(challenge["challenge_id"]),
            credential=credential,
            payload=payload,
            now=NOW + timedelta(minutes=5),
        )


def test_semantic_assertion_rolls_back_and_retries_after_append_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, credential_id, payload, challenge, _binding = _semantic_owner_fixture(
        tmp_path, monkeypatch
    )
    monkeypatch.setattr(
        owner_auth,
        "verify_authentication_response",
        lambda **_: SimpleNamespace(new_sign_count=2),
    )
    original_append = ControlStore.append_semantic_event

    def fail_append(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise DataError("injected semantic append failure")

    monkeypatch.setattr(ControlStore, "append_semantic_event", fail_append)
    credential = {"id": credential_id, "response": {"signature": "redacted"}}
    with pytest.raises(DataError, match="injected semantic append failure"):
        owner_auth.verify_action_assertion(
            data_dir=tmp_path,
            challenge_id=str(challenge["challenge_id"]),
            credential=credential,
            payload=payload,
            now=NOW + timedelta(seconds=2),
        )
    with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
        assert connection.execute(
            "SELECT sign_count FROM owner_credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT used_at FROM owner_auth_challenges WHERE challenge_id = ?",
            (challenge["challenge_id"],),
        ).fetchone() == (None,)
        assert connection.execute("SELECT COUNT(*) FROM owner_action_receipts").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM research_semantic_events").fetchone() == (
            0,
        )

    monkeypatch.setattr(ControlStore, "append_semantic_event", original_append)
    result = owner_auth.verify_action_assertion(
        data_dir=tmp_path,
        challenge_id=str(challenge["challenge_id"]),
        credential=credential,
        payload=payload,
        now=NOW + timedelta(seconds=3),
    )
    assert cast(dict[str, object], result["outcome"])["status"] == "semantic_event_recorded"


def test_semantic_assertion_rejects_tampered_artifact_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, credential_id, payload, challenge, binding = _semantic_owner_fixture(
        tmp_path, monkeypatch
    )
    tampered = {**binding, "artifact_hash": "f" * 64}
    with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
        connection.execute(
            "UPDATE owner_auth_challenges SET binding_json = ? WHERE challenge_id = ?",
            (owner_auth._canonical_json(tampered, "binding"), challenge["challenge_id"]),
        )
        connection.commit()
    with pytest.raises(DataError, match="artifact binding"):
        store.record_semantic_event_authorization(
            challenge_id=str(challenge["challenge_id"]),
            credential_id=credential_id,
            previous_sign_count=1,
            new_sign_count=2,
            assertion_hash="a" * 64,
            payload=payload,
            now=NOW + timedelta(seconds=2),
            receipt_id="11111111-1111-4111-8111-111111111111",
        )


@pytest.mark.parametrize("failure", ["case", "source", "head", "counter", "challenge"])
def test_semantic_assertion_rechecks_all_atomic_preconditions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    store, credential_id, payload, challenge, binding = _semantic_owner_fixture(
        tmp_path, monkeypatch
    )
    if failure == "case":
        monkeypatch.setattr(
            ControlStore,
            "_research_case_revision_locked",
            lambda self, _connection, _project_id: "f" * 64,
        )
    elif failure == "source":
        changed_source = {**_semantic_source(research_case_revision(CASE)), "run_id": "f" * 16}
        monkeypatch.setattr(
            ControlStore,
            "_verified_semantic_source_locked",
            lambda self, _connection, _project_id: changed_source,
        )
    elif failure == "head":
        changed_payload = {**payload, "expected_semantic_head_sha256": "f" * 64}
        changed_binding = {
            **binding,
            "request_hash": hashlib.sha256(
                owner_auth._canonical_json(changed_payload, "payload").encode()
            ).hexdigest(),
        }
        with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
            connection.execute(
                "UPDATE owner_auth_challenges SET binding_json = ? WHERE challenge_id = ?",
                (
                    owner_auth._canonical_json(changed_binding, "binding"),
                    challenge["challenge_id"],
                ),
            )
            connection.commit()
        payload = changed_payload
    elif failure == "counter":
        with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
            connection.execute(
                "UPDATE owner_credentials SET sign_count = 9 WHERE credential_id = ?",
                (credential_id,),
            )
            connection.commit()
    else:
        with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
            connection.execute(
                "UPDATE owner_auth_challenges SET used_at = ? WHERE challenge_id = ?",
                ("2026-08-13T02:00:01.000000Z", challenge["challenge_id"]),
            )
            connection.commit()
    expected_sign_count = 9 if failure == "counter" else 1
    expected_used_at = "2026-08-13T02:00:01.000000Z" if failure == "challenge" else None
    with pytest.raises(DataError):
        store.record_semantic_event_authorization(
            challenge_id=str(challenge["challenge_id"]),
            credential_id=credential_id,
            previous_sign_count=1,
            new_sign_count=2,
            assertion_hash="a" * 64,
            payload=payload,
            now=NOW + timedelta(seconds=2),
            receipt_id="22222222-2222-4222-8222-222222222222",
        )
    with sqlite3.connect(tmp_path / "control" / "workstation.sqlite3") as connection:
        assert connection.execute(
            "SELECT sign_count FROM owner_credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone() == (expected_sign_count,)
        assert connection.execute(
            "SELECT used_at FROM owner_auth_challenges WHERE challenge_id = ?",
            (challenge["challenge_id"],),
        ).fetchone() == (expected_used_at,)
        assert connection.execute("SELECT COUNT(*) FROM owner_action_receipts").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM research_semantic_events").fetchone() == (
            0,
        )


def test_owner_auth_input_bounds_fail_before_persistence(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="invalid owner auth test"):
        owner_auth._canonical_json(float("nan"), "test")
    with pytest.raises(DataError, match="exceeds"):
        owner_auth._canonical_json({"value": "x" * 65_536}, "test")
    with pytest.raises(DataError, match="must be a JSON object"):
        owner_auth._object([], "test")
    with pytest.raises(DataError, match="token is invalid"):
        owner_auth.registration_options(data_dir=tmp_path, token="", now=NOW)
    with pytest.raises(DataError, match="credential id is missing"):
        owner_auth._credential_id({})
    with pytest.raises(DataError, match="identifier is missing"):
        owner_auth.derive_action_artifact_hash(
            data_dir=tmp_path,
            action_type="approve_exploration",
            project_id=PROJECT_ID,
            payload={},
        )


def test_registration_rejects_challenge_from_another_enrollment(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    first_token = "first-trusted-enrollment-token"
    second_token = "second-trusted-enrollment-token"
    first_hash = hashlib.sha256(first_token.encode()).hexdigest()
    second_hash = hashlib.sha256(second_token.encode()).hexdigest()
    first = store.create_owner_enrollment_request(
        token_hash=first_hash,
        reason="first",
        replace_existing=False,
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    store.create_owner_enrollment_request(
        token_hash=second_hash,
        reason="second",
        replace_existing=False,
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    challenge = store.create_owner_auth_challenge(
        ceremony="registration",
        challenge=b"r" * 32,
        binding={"token_hash": first_hash},
        enrollment_request_id=str(first["request_id"]),
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    with pytest.raises(DataError, match="does not match"):
        owner_auth.finish_registration(
            data_dir=tmp_path,
            token=second_token,
            challenge_id=str(challenge["challenge_id"]),
            credential={},
            now=NOW + timedelta(seconds=1),
        )


def test_assertion_rejects_incomplete_binding_unknown_credential_and_bad_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    credential_id = _enroll_credential(store)
    incomplete = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"i" * 32,
        binding={"action_type": "approve_exploration"},
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    with pytest.raises(DataError, match="binding is incomplete"):
        owner_auth.verify_action_assertion(
            data_dir=tmp_path,
            challenge_id=str(incomplete["challenge_id"]),
            credential={"id": credential_id},
            payload={},
            now=NOW + timedelta(seconds=2),
        )

    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    payload = {"contract_id": "rc_" + "a" * 64}
    binding = owner_auth.action_binding(
        data_dir=tmp_path,
        action_type="approve_exploration",
        project_id=PROJECT_ID,
        artifact_hash="a" * 64,
        expected_case_revision=research_case_revision(CASE),
        consequence_summary="approve exact contract",
        reason="reviewed",
        payload=payload,
    )
    unknown = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"u" * 32,
        binding=binding,
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    with pytest.raises(DataError, match="not enrolled"):
        owner_auth.verify_action_assertion(
            data_dir=tmp_path,
            challenge_id=str(unknown["challenge_id"]),
            credential={"id": "unknown"},
            payload=payload,
            now=NOW + timedelta(seconds=2),
        )

    rejected = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"s" * 32,
        binding=binding,
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    monkeypatch.setattr(
        owner_auth,
        "verify_authentication_response",
        lambda **_: (_ for _ in ()).throw(ValueError("bad signature")),
    )
    with pytest.raises(DataError, match="assertion could not be verified"):
        owner_auth.verify_action_assertion(
            data_dir=tmp_path,
            challenge_id=str(rejected["challenge_id"]),
            credential={"id": credential_id},
            payload=payload,
            now=NOW + timedelta(seconds=2),
        )
    with pytest.raises(DataError, match="research case changed"):
        owner_auth.action_binding(
            data_dir=tmp_path,
            action_type="approve_exploration",
            project_id=PROJECT_ID,
            artifact_hash="a" * 64,
            expected_case_revision="b" * 64,
            consequence_summary="exact consequence",
            reason="reviewed",
            payload={"contract_id": "rc_" + "a" * 64},
        )
    revision = research_case_revision(CASE)
    with pytest.raises(DataError, match="lowercase SHA-256"):
        owner_auth.action_binding(
            data_dir=tmp_path,
            action_type="approve_exploration",
            project_id=PROJECT_ID,
            artifact_hash="INVALID",
            expected_case_revision=revision,
            consequence_summary="exact consequence",
            reason="reviewed",
            payload={"contract_id": "rc_" + "a" * 64},
        )
