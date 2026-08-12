"""Fail-closed owner-presence persistence and additive schema-v3 migration."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alpha_cli.control_store import SCHEMA_VERSION, ControlStore
from alpha_core import DataError

PROJECT_ID = "9f05c1e0-f7e4-46b3-95dc-18d630565e15"
NOW = datetime(2026, 8, 13, 1, 0, tzinfo=UTC)


def _store(tmp_path: Path) -> ControlStore:
    store = ControlStore(tmp_path)
    store.create_project(
        name="Owner auth test",
        hypothesis="The owner action is explicitly bound.",
        falsification_criterion="Reject when the bound state changes.",
        project_id=PROJECT_ID,
        at=NOW,
    )
    return store


def _enroll(store: ControlStore) -> dict[str, object]:
    token_hash = hashlib.sha256(b"trusted-cli-token").hexdigest()
    request = store.create_owner_enrollment_request(
        token_hash=token_hash,
        reason="initial Touch ID enrollment",
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
    return store.complete_owner_registration(
        token_hash=token_hash,
        challenge_id=str(challenge["challenge_id"]),
        credential_id="credential-base64url",
        public_key=b"public-key",
        sign_count=1,
        transports=["internal"],
        now=NOW + timedelta(seconds=1),
    )


def _binding() -> dict[str, object]:
    return {
        "action_type": "approve_exploration",
        "project_id": PROJECT_ID,
        "artifact_hash": "a" * 64,
        "expected_case_revision": "b" * 64,
        "consequence_summary": "Approve this exact exploration contract.",
        "reason": "The frozen contract matches the reviewed research question.",
        "request_hash": "c" * 64,
    }


def test_owner_action_challenge_is_single_use_and_counter_bound(tmp_path: Path) -> None:
    store = _store(tmp_path)
    credential = _enroll(store)
    challenge = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"a" * 32,
        binding=_binding(),
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    receipt = store.record_owner_action_authorization(
        challenge_id=str(challenge["challenge_id"]),
        credential_id=str(credential["credential_id"]),
        previous_sign_count=1,
        new_sign_count=2,
        assertion_hash="d" * 64,
        outcome={"status": "performed", "result_id": "review-1"},
        now=NOW + timedelta(seconds=2),
    )

    assert receipt["actor"] == credential["actor"]
    assert receipt["action_type"] == "approve_exploration"
    with pytest.raises(DataError, match="already used"):
        store.record_owner_action_authorization(
            challenge_id=str(challenge["challenge_id"]),
            credential_id=str(credential["credential_id"]),
            previous_sign_count=2,
            new_sign_count=3,
            assertion_hash="e" * 64,
            outcome={"status": "performed"},
            now=NOW + timedelta(seconds=3),
        )


def test_owner_action_rejects_expiry_and_counter_regression(tmp_path: Path) -> None:
    store = _store(tmp_path)
    credential = _enroll(store)
    expired = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"e" * 32,
        binding=_binding(),
        now=NOW,
        expires_at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(DataError, match="expired"):
        store.get_owner_auth_challenge(
            str(expired["challenge_id"]),
            ceremony="action",
            now=NOW + timedelta(seconds=2),
        )

    current = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"c" * 32,
        binding=_binding(),
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    with pytest.raises(DataError, match="counter regressed"):
        store.record_owner_action_authorization(
            challenge_id=str(current["challenge_id"]),
            credential_id=str(credential["credential_id"]),
            previous_sign_count=1,
            new_sign_count=1,
            assertion_hash="f" * 64,
            outcome={"status": "performed"},
            now=NOW + timedelta(seconds=2),
        )


def test_schema_v2_migrates_once_with_exact_backup(tmp_path: Path) -> None:
    store = _store(tmp_path)
    database = tmp_path / "control" / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    for trigger in (
        "owner_action_receipts_no_update",
        "owner_action_receipts_no_delete",
        "owner_credential_events_no_update",
        "owner_credential_events_no_delete",
        "research_source_claim_owner_events_no_update",
        "research_source_claim_owner_events_no_delete",
    ):
        connection.execute(f"DROP TRIGGER {trigger}")
    for table in (
        "research_source_claim_owner_events",
        "owner_action_receipts",
        "owner_auth_challenges",
        "owner_credential_events",
        "owner_credentials",
        "owner_enrollment_requests",
    ):
        connection.execute(f"DROP TABLE {table}")
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    expected_rows = connection.execute("SELECT * FROM projects").fetchall()
    connection.close()

    assert store.list_projects()[0]["project_id"] == PROJECT_ID
    migrated = sqlite3.connect(database)
    backup = sqlite3.connect(database.with_name("workstation.sqlite3.v2.bak"))
    try:
        assert migrated.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
        assert backup.execute("PRAGMA user_version").fetchone() == (2,)
        assert backup.execute("SELECT * FROM projects").fetchall() == expected_rows
        assert migrated.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'owner_action_receipts'"
        ).fetchone() == (1,)
    finally:
        migrated.close()
        backup.close()


def test_owner_store_rejects_invalid_enrollment_and_challenge_shapes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(DataError, match="token hash"):
        store.create_owner_enrollment_request(
            token_hash="invalid",
            reason="test",
            replace_existing=False,
            now=NOW,
            expires_at=NOW + timedelta(minutes=5),
        )
    with pytest.raises(DataError, match="expiry"):
        store.create_owner_enrollment_request(
            token_hash="a" * 64,
            reason="test",
            replace_existing=False,
            now=NOW,
            expires_at=NOW,
        )
    with pytest.raises(DataError, match="invalid or already used"):
        store.get_owner_enrollment_request(token_hash="b" * 64, now=NOW)

    with pytest.raises(DataError, match="exactly 32"):
        store.create_owner_auth_challenge(
            ceremony="action",
            challenge=b"short",
            binding={},
            now=NOW,
            expires_at=NOW + timedelta(seconds=60),
        )
    with pytest.raises(DataError, match="lifetime"):
        store.create_owner_auth_challenge(
            ceremony="action",
            challenge=b"a" * 32,
            binding={},
            now=NOW,
            expires_at=NOW + timedelta(seconds=61),
        )
    with pytest.raises(DataError, match="requires an enrollment"):
        store.create_owner_auth_challenge(
            ceremony="registration",
            challenge=b"a" * 32,
            binding={},
            now=NOW,
            expires_at=NOW + timedelta(seconds=60),
        )
    with pytest.raises(DataError, match="not enrolled"):
        store.create_owner_auth_challenge(
            ceremony="action",
            challenge=b"a" * 32,
            binding={},
            now=NOW,
            expires_at=NOW + timedelta(seconds=60),
        )


def test_owner_store_expiry_replacement_and_registration_validation(tmp_path: Path) -> None:
    store = _store(tmp_path)
    expired_hash = hashlib.sha256(b"expired").hexdigest()
    store.create_owner_enrollment_request(
        token_hash=expired_hash,
        reason="expired",
        replace_existing=False,
        now=NOW,
        expires_at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(DataError, match="expired"):
        store.get_owner_enrollment_request(token_hash=expired_hash, now=NOW + timedelta(seconds=2))

    credential = _enroll(store)
    with pytest.raises(DataError, match="already enrolled"):
        store.create_owner_enrollment_request(
            token_hash="c" * 64,
            reason="duplicate",
            replace_existing=False,
            now=NOW + timedelta(seconds=2),
            expires_at=NOW + timedelta(minutes=5),
        )

    replacement_hash = hashlib.sha256(b"replacement").hexdigest()
    request = store.create_owner_enrollment_request(
        token_hash=replacement_hash,
        reason="replace device credential",
        replace_existing=True,
        now=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(minutes=5),
    )
    challenge = store.create_owner_auth_challenge(
        ceremony="registration",
        challenge=b"n" * 32,
        binding={"token_hash": replacement_hash},
        enrollment_request_id=str(request["request_id"]),
        now=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(seconds=62),
    )
    with pytest.raises(DataError, match="public key"):
        store.complete_owner_registration(
            token_hash=replacement_hash,
            challenge_id=str(challenge["challenge_id"]),
            credential_id="replacement",
            public_key=b"",
            sign_count=1,
            transports=["internal"],
            now=NOW + timedelta(seconds=3),
        )
    with pytest.raises(DataError, match="counter"):
        store.complete_owner_registration(
            token_hash=replacement_hash,
            challenge_id=str(challenge["challenge_id"]),
            credential_id="replacement",
            public_key=b"key",
            sign_count=-1,
            transports=["internal"],
            now=NOW + timedelta(seconds=3),
        )
    replacement = store.complete_owner_registration(
        token_hash=replacement_hash,
        challenge_id=str(challenge["challenge_id"]),
        credential_id="replacement",
        public_key=b"key",
        sign_count=1,
        transports=["internal"],
        now=NOW + timedelta(seconds=3),
    )
    assert replacement["credential_id"] == "replacement"
    assert [item["credential_id"] for item in store.list_active_owner_credentials()] == [
        "replacement"
    ]
    assert credential["credential_id"] != replacement["credential_id"]


def test_owner_store_rejects_mismatched_challenge_and_bad_assertion_hash(tmp_path: Path) -> None:
    store = _store(tmp_path)
    credential = _enroll(store)
    registration_request = store.create_owner_enrollment_request(
        token_hash="d" * 64,
        reason="replacement",
        replace_existing=True,
        now=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(minutes=5),
    )
    with pytest.raises(DataError, match="cannot carry"):
        store.create_owner_auth_challenge(
            ceremony="action",
            challenge=b"a" * 32,
            binding={},
            enrollment_request_id=str(registration_request["request_id"]),
            now=NOW + timedelta(seconds=2),
            expires_at=NOW + timedelta(seconds=62),
        )
    action = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"a" * 32,
        binding=_binding(),
        now=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(seconds=62),
    )
    with pytest.raises(DataError, match="assertion hash"):
        store.record_owner_action_authorization(
            challenge_id=str(action["challenge_id"]),
            credential_id=str(credential["credential_id"]),
            previous_sign_count=1,
            new_sign_count=2,
            assertion_hash="invalid",
            outcome={"status": "authorized"},
            now=NOW + timedelta(seconds=3),
        )


def test_owner_store_corrupt_bindings_and_nontrusted_replacement_fail_closed(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    pending_hash = hashlib.sha256(b"pending-before-enrollment").hexdigest()
    pending = store.create_owner_enrollment_request(
        token_hash=pending_hash,
        reason="ordinary enrollment",
        replace_existing=False,
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    pending_challenge = store.create_owner_auth_challenge(
        ceremony="registration",
        challenge=b"p" * 32,
        binding={"token_hash": pending_hash},
        enrollment_request_id=str(pending["request_id"]),
        now=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    credential = _enroll(store)
    with pytest.raises(DataError, match="trusted CLI ceremony"):
        store.complete_owner_registration(
            token_hash=pending_hash,
            challenge_id=str(pending_challenge["challenge_id"]),
            credential_id="untrusted-replacement",
            public_key=b"key",
            sign_count=1,
            transports=["internal"],
            now=NOW + timedelta(seconds=2),
        )

    database = tmp_path / "control" / "workstation.sqlite3"
    with sqlite3.connect(database) as connection:
        used = connection.execute(
            "SELECT e.token_hash, c.challenge_id FROM owner_auth_challenges c "
            "JOIN owner_enrollment_requests e ON c.enrollment_request_id = e.request_id "
            "WHERE c.used_at IS NOT NULL LIMIT 1"
        ).fetchone()
    assert used is not None
    with pytest.raises(DataError, match="invalid, expired, or already used"):
        store.complete_owner_registration(
            token_hash=str(used[0]),
            challenge_id=str(used[1]),
            credential_id="replay",
            public_key=b"key",
            sign_count=2,
            transports=["internal"],
            now=NOW + timedelta(seconds=3),
        )

    corrupt_read = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"r" * 32,
        binding=_binding(),
        now=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(seconds=62),
    )
    corrupt_receipt = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"c" * 32,
        binding=_binding(),
        now=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(seconds=62),
    )
    bad_digest = {**_binding(), "artifact_hash": "not-a-digest"}
    invalid_receipt = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=b"d" * 32,
        binding=bad_digest,
        now=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(seconds=62),
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE owner_auth_challenges SET binding_json = '[]' WHERE challenge_id IN (?, ?)",
            (corrupt_read["challenge_id"], corrupt_receipt["challenge_id"]),
        )
        connection.commit()
    with pytest.raises(DataError, match="binding is not an object"):
        store.get_owner_auth_challenge(
            str(corrupt_read["challenge_id"]),
            ceremony="action",
            now=NOW + timedelta(seconds=3),
        )
    with pytest.raises(DataError, match="binding is not an object"):
        store.record_owner_action_authorization(
            challenge_id=str(corrupt_receipt["challenge_id"]),
            credential_id=str(credential["credential_id"]),
            previous_sign_count=1,
            new_sign_count=2,
            assertion_hash="a" * 64,
            outcome={"status": "authorized"},
            now=NOW + timedelta(seconds=3),
        )
    with pytest.raises(DataError, match="artifact_hash"):
        store.record_owner_action_authorization(
            challenge_id=str(invalid_receipt["challenge_id"]),
            credential_id=str(credential["credential_id"]),
            previous_sign_count=1,
            new_sign_count=2,
            assertion_hash="a" * 64,
            outcome={"status": "authorized"},
            now=NOW + timedelta(seconds=3),
        )


def test_owner_store_rejects_symlink_database(tmp_path: Path) -> None:
    control = tmp_path / "control"
    control.mkdir()
    target = tmp_path / "elsewhere.sqlite3"
    target.touch()
    (control / "workstation.sqlite3").symlink_to(target)
    with pytest.raises(DataError, match="database must not be a symlink"):
        ControlStore(tmp_path).list_projects()
