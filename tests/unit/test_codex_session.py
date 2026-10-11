"""Durable attempt budgets and explicit recovery for advisory Codex sessions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from alpha_cli.codex_session import Session

IDENTITY = "a" * 64


def test_budget_survives_reopen_and_thread_binding(tmp_path: Path) -> None:
    for number in range(1, 5):
        with Session(tmp_path, IDENTITY, "codex-model") as session:
            session.bind_thread("thread-1")
            assert session.reserve_turn() == number
            session.start_turn(f"turn-{number}")
            session.finish_turn("completed", report={"number": number})
    with Session(tmp_path, IDENTITY, "codex-model") as session:
        assert session.state["thread_id"] == "thread-1"
        assert session.state["latest_report"] == {"number": 4}
        with pytest.raises(ValueError, match="budget"):
            session.reserve_turn()


def test_reserved_attempt_cannot_be_replayed(tmp_path: Path) -> None:
    session = Session(tmp_path, IDENTITY, "codex-model")
    with session:
        assert session.reserve_turn() == 1
    with session:
        with pytest.raises(ValueError, match="ambiguous"):
            session.reserve_turn()
        with pytest.raises(ValueError, match="locally reserved"):
            session.finish_turn("failed")


def test_known_failure_consumes_attempt_and_resume_is_explicit(tmp_path: Path) -> None:
    with (
        pytest.raises(RuntimeError, match="connection lost"),
        Session(tmp_path, IDENTITY, "codex-model") as session,
    ):
        session.bind_thread("thread-1")
        session.reserve_turn()
        session.start_turn("turn-1")
        raise RuntimeError("connection lost")
    with Session(tmp_path, IDENTITY, "codex-model") as session:
        assert session.state["turns"][0]["status"] == "interrupted"
        assert session.reserve_turn() == 2
        session.finish_turn("failed")


@pytest.mark.parametrize("identity,model", [("b" * 64, "codex-model"), (IDENTITY, "other")])
def test_identity_and_model_cannot_change(tmp_path: Path, identity: str, model: str) -> None:
    with Session(tmp_path, IDENTITY, "codex-model"):
        pass
    with pytest.raises(ValueError, match="binding"), Session(tmp_path, identity, model):
        pass


def test_another_process_cannot_acquire_active_session(tmp_path: Path) -> None:
    with Session(tmp_path, IDENTITY, "codex-model"):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
from pathlib import Path
from alpha_cli.codex_session import Session
try:
    with Session(Path(sys.argv[1]), "a" * 64, "codex-model"): pass
except ValueError as exc:
    assert "active" in str(exc)
else:
    raise AssertionError("concurrent owner acquired session")
""",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_corrupt_missing_or_reset_state_does_not_reset_attempts(tmp_path: Path) -> None:
    with Session(tmp_path, IDENTITY, "codex-model") as session:
        session.reserve_turn()
        session.finish_turn("failed")
    path = tmp_path / "codex-session.json"
    original = path.read_text()
    payload = json.loads(original)
    payload["turns"] = []
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="reservation"), Session(tmp_path, IDENTITY, "codex-model"):
        pass
    path.unlink()
    with pytest.raises(ValueError, match="reservation"), Session(tmp_path, IDENTITY, "codex-model"):
        pass


@pytest.mark.parametrize("name", ["codex-session.json", "codex-session.lock"])
def test_symlink_files_rejected(tmp_path: Path, name: str) -> None:
    target = tmp_path / "unrelated"
    target.write_text("preserve")
    (tmp_path / name).symlink_to(target)
    with pytest.raises((ValueError, OSError)), Session(tmp_path, IDENTITY, "codex-model"):
        pass
    assert target.read_text() == "preserve"


def test_process_crash_leaves_running_turn_ambiguous(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os, sys
from pathlib import Path
from alpha_cli.codex_session import Session
with Session(Path(sys.argv[1]), "a" * 64, "codex-model") as session:
    session.bind_thread("thread")
    session.reserve_turn()
    session.start_turn("turn")
    os._exit(0)
""",
            str(tmp_path),
        ],
        check=False,
    )
    assert result.returncode == 0
    with Session(tmp_path, IDENTITY, "codex-model") as session:
        assert session.state["turns"][0]["status"] == "running"
        with pytest.raises(ValueError, match="ambiguous"):
            session.reserve_turn()


@pytest.mark.parametrize("raw", ["{", "[]", '{"schema_version":1,"schema_version":1}'])
def test_corrupt_json_is_never_reinitialized(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "codex-session.json"
    path.write_text(raw)
    with pytest.raises(ValueError), Session(tmp_path, IDENTITY, "codex-model"):
        pass
    assert path.read_text() == raw
