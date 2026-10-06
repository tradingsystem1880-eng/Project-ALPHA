"""Local confirmation has no biometric credential and cannot be replayed or substituted."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import owner_auth
from alpha_cli.control_store import ControlStore, research_case_revision
from alpha_core import DataError

NOW = datetime(2026, 9, 30, tzinfo=UTC)
PROJECT = "6f14da94-55fc-470a-b11a-d009f5ea15d9"
CASE = dict(
    project_id=PROJECT,
    active_contract_id="rc_" + "a" * 64,
    phase="exploration_review",
    execution_state="idle",
    source_pack_id=None,
)


def challenge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], dict[str, Any]]:
    store = ControlStore(tmp_path)
    store.create_project(
        name="Local confirmation",
        hypothesis="Test",
        falsification_criterion="Contradiction",
        project_id=PROJECT,
        at=NOW,
    )
    monkeypatch.setattr(ControlStore, "research_case_summary", lambda *_: CASE)
    monkeypatch.setattr(
        ControlStore, "_research_case_revision_locked", lambda *_: research_case_revision(CASE)
    )
    payload = {"contract_id": CASE["active_contract_id"]}
    binding = owner_auth.action_binding(
        data_dir=tmp_path,
        action_type="approve_exploration",
        project_id=PROJECT,
        artifact_hash="a" * 64,
        expected_case_revision=research_case_revision(CASE),
        consequence_summary="Approve this contract",
        reason="Reviewed",
        payload=payload,
    )
    return owner_auth.local_confirmation_options(
        data_dir=tmp_path, binding=binding, now=NOW
    ), payload


def test_unenrolled_local_confirmation_is_honest_and_single_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope, payload = challenge(tmp_path, monkeypatch)
    kwargs: dict[str, Any] = dict(
        data_dir=tmp_path,
        challenge_id=envelope["challenge_id"],
        confirmation_token=envelope["confirmation_token"],
        payload=payload,
        now=NOW,
    )
    result = owner_auth.verify_local_confirmation(**kwargs)
    assert result["actor"] == "owner:local-confirmation"
    assert result["authorization_method"] == "local_confirmation"
    assert not ControlStore(tmp_path).list_active_owner_credentials()
    with pytest.raises(DataError):
        owner_auth.verify_local_confirmation(**kwargs)


@pytest.mark.parametrize("failure", ["token", "payload", "expiry", "revision"])
def test_local_confirmation_rejects_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    envelope, payload = challenge(tmp_path, monkeypatch)
    token, now = envelope["confirmation_token"], NOW
    if failure == "token":
        token = "f" * 64
    if failure == "payload":
        payload = {"contract_id": "rc_" + "b" * 64}
    if failure == "expiry":
        now += timedelta(seconds=61)
    if failure == "revision":
        monkeypatch.setattr(
            ControlStore, "research_case_summary", lambda *_: {**CASE, "phase": "closed"}
        )
    with pytest.raises(DataError):
        owner_auth.verify_local_confirmation(
            data_dir=tmp_path,
            challenge_id=envelope["challenge_id"],
            confirmation_token=token,
            payload=payload,
            now=now,
        )


@pytest.mark.parametrize("origin", [None, "null", "https://evil.example", "http://localhost:8802"])
def test_confirmation_api_rejects_wrong_origin(
    origin: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from alpha_web.app import create_app

    monkeypatch.setenv("ALPHA_WEB_PORT", "8801")
    headers = {} if origin is None else {"Origin": origin}
    with TestClient(create_app(), base_url="http://localhost:8801") as client:
        for route in ("challenge", "perform"):
            result = client.post("/api/owner-auth/actions/" + route, headers=headers, json={})
            assert result.status_code == 403


def test_local_semantic_confirmation_is_atomic_and_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_owner_auth import _semantic_owner_fixture

    store, _, payload, _, binding = _semantic_owner_fixture(tmp_path, monkeypatch)
    envelope = owner_auth.local_confirmation_options(data_dir=tmp_path, binding=binding, now=NOW)
    kwargs: dict[str, Any] = dict(
        data_dir=tmp_path,
        challenge_id=envelope["challenge_id"],
        confirmation_token=envelope["confirmation_token"],
        payload=payload,
        now=NOW,
    )
    first = owner_auth.verify_local_confirmation(**kwargs)
    second = owner_auth.verify_local_confirmation(**kwargs)
    assert first["receipt_id"] == second["receipt_id"]
    assert first["actor"] == "owner:local-confirmation"
    assert isinstance(first["outcome"], dict)
    assert first["outcome"]["status"] == "semantic_event_recorded"
    with store._transaction(write=False) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM research_semantic_events").fetchone()[0] == 1
        )
        receipt = connection.execute("SELECT * FROM owner_action_receipts").fetchone()
        assert receipt["credential_id"] is None
        assert receipt["authorization_method"] == "local_confirmation"


def test_populated_v5_migration_preserves_semantic_receipt_and_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3
    from types import SimpleNamespace

    import alpha_cli.control_store as module
    from tests.unit.test_owner_auth import NOW as AUTH_NOW
    from tests.unit.test_owner_auth import _semantic_owner_fixture

    store, credential, payload, envelope, _ = _semantic_owner_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        owner_auth, "verify_authentication_response", lambda **_: SimpleNamespace(new_sign_count=2)
    )
    owner_auth.verify_action_assertion(
        data_dir=tmp_path,
        challenge_id=str(envelope["challenge_id"]),
        credential={"id": credential},
        payload=payload,
        now=AUTH_NOW,
    )
    database = tmp_path / "control" / "workstation.sqlite3"
    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT * FROM owner_action_receipts").fetchone()[:-1]
        event = connection.execute("SELECT * FROM research_semantic_events").fetchone()
        connection.execute("PRAGMA foreign_keys = OFF")
        module._drop_owner_receipt_support(connection)
        module._execute_static_sql_script(
            connection,
            module._SCHEMA_V5_RECEIPT.replace("owner_action_receipts (", "old_receipts ("),
        )
        connection.execute(
            "INSERT INTO old_receipts VALUES (" + ",".join("?" for _ in before) + ")", before
        )
        connection.execute("DROP TABLE owner_action_receipts")
        connection.execute("ALTER TABLE old_receipts RENAME TO owner_action_receipts")
        module._execute_static_sql_script(connection, module._SCHEMA_V5)
        connection.execute("PRAGMA user_version = 5")
    assert store.list_projects()
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT * FROM owner_action_receipts").fetchone()
        assert row[:-1] == before and row[-1] == "webauthn"
        assert connection.execute("SELECT * FROM research_semantic_events").fetchone() == event
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM owner_action_receipts")
    with sqlite3.connect(str(database) + ".v5.bak") as backup:
        assert backup.execute("PRAGMA user_version").fetchone() == (5,)
        assert backup.execute("SELECT * FROM owner_action_receipts").fetchone() == before
        assert backup.execute("SELECT * FROM research_semantic_events").fetchone() == event


def test_v6_schema_missing_method_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3

    import alpha_cli.control_store as module

    challenge(tmp_path, monkeypatch)
    database = tmp_path / "control" / "workstation.sqlite3"
    with sqlite3.connect(database) as connection:
        module._drop_owner_receipt_support(connection)
        connection.execute("DROP TABLE owner_action_receipts")
        module._execute_static_sql_script(connection, module._SCHEMA_V5)
    with pytest.raises(DataError, match="v6 is invalid"):
        ControlStore(tmp_path).list_projects()


def test_simultaneous_local_confirmations_consume_only_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    from concurrent.futures import ThreadPoolExecutor

    envelope, payload = challenge(tmp_path, monkeypatch)
    barrier = threading.Barrier(2)

    def confirm() -> str:
        barrier.wait(timeout=5)
        try:
            owner_auth.verify_local_confirmation(
                data_dir=tmp_path,
                challenge_id=envelope["challenge_id"],
                confirmation_token=envelope["confirmation_token"],
                payload=payload,
                now=NOW,
            )
            return "consumed"
        except DataError:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: confirm(), range(2))) == ["consumed", "denied"]


def test_revision_change_at_consumption_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope, payload = challenge(tmp_path, monkeypatch)
    monkeypatch.setattr(ControlStore, "_research_case_revision_locked", lambda *_: "f" * 64)
    with pytest.raises(DataError, match="changed before confirmation"):
        owner_auth.verify_local_confirmation(
            data_dir=tmp_path,
            challenge_id=envelope["challenge_id"],
            confirmation_token=envelope["confirmation_token"],
            payload=payload,
            now=NOW,
        )


@pytest.mark.parametrize(
    "host,fetch,content",
    [
        ("evil.example", "same-origin", "application/json"),
        ("localhost:8801", "cross-site", "application/json"),
        ("localhost:8801", "same-origin", "text/plain"),
    ],
)
def test_local_confirmation_rejects_host_fetch_and_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, host: str, fetch: str, content: str
) -> None:
    from fastapi.testclient import TestClient

    from alpha_web.app import create_app

    monkeypatch.setenv("ALPHA_WEB_PORT", "8801")
    with TestClient(create_app(), base_url="http://localhost:8801") as client:
        result = client.post(
            "/api/owner-auth/actions/perform",
            content="{}",
            headers={
                "origin": "http://localhost:8801",
                "host": host,
                "sec-fetch-site": fetch,
                "content-type": content,
            },
        )
    assert result.status_code == 403


def _empty_v5(tmp_path: Path) -> Path:
    import sqlite3

    import alpha_cli.control_store as module

    store = ControlStore(tmp_path)
    store.list_projects()
    database = tmp_path / "control" / "workstation.sqlite3"
    with sqlite3.connect(database) as connection:
        module._drop_owner_receipt_support(connection)
        connection.execute("DROP TABLE owner_action_receipts")
        module._execute_static_sql_script(connection, module._SCHEMA_V5)
        connection.execute("PRAGMA user_version = 5")
    return database


def test_v5_migration_rolls_back_on_ddl_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3

    import alpha_cli.control_store as module

    database = _empty_v5(tmp_path)
    original = module._execute_static_sql_script

    def fail_new_table(connection: sqlite3.Connection, script: str) -> None:
        if "owner_action_receipts_v6_new" in script:
            raise sqlite3.OperationalError("injected migration failure")
        original(connection, script)

    monkeypatch.setattr(module, "_execute_static_sql_script", fail_new_table)
    with pytest.raises(DataError, match="initialize control store"):
        ControlStore(tmp_path).list_projects()
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (5,)
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='owner_action_receipts_no_update'"
        ).fetchone()
    monkeypatch.setattr(module, "_execute_static_sql_script", original)
    assert ControlStore(tmp_path).list_projects() == []


def test_v5_concurrent_migration_is_serialized(tmp_path: Path) -> None:
    import sqlite3
    import threading
    from concurrent.futures import ThreadPoolExecutor

    database = _empty_v5(tmp_path)
    barrier = threading.Barrier(2)

    def migrate(_: int) -> list[dict[str, object]]:
        barrier.wait(timeout=5)
        return ControlStore(tmp_path).list_projects()

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(migrate, range(2))) == [[], []]
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (6,)
    assert database.with_name(database.name + ".v5.bak").is_file()
