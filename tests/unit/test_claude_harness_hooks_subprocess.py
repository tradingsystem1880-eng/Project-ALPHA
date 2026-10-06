"""Drive the thin adapter as Claude does: stdin, exit status and no state writes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.unit._harness_support import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts/claude_hooks.py"


def _run(name: str, payload: object, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), name],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
        timeout=10,
    )


@pytest.mark.parametrize("name", ["pre-bash-guard", "stop-guard", "post-edit", "unknown"])
def test_retired_ceremony_is_not_dispatched(tmp_path: Path, name: str) -> None:
    result = _run(name, {}, tmp_path)
    assert result.returncode == 1
    assert "usage" in result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "payload", [[], {}, {"tool_input": None}, {"tool_input": {"file_path": 3}}]
)
def test_malformed_file_inputs_fail_closed(tmp_path: Path, payload: object) -> None:
    result = _run("pre-file-guard", payload, tmp_path)
    assert result.returncode == 2
    assert "unavailable" in result.stderr
    assert not result.stdout


def test_invalid_json_safety_fails_closed_but_orientation_is_advisory(tmp_path: Path) -> None:
    for name, code in (("pre-file-guard", 2), ("session-start", 0)):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), name],
            input="{bad json",
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )
        assert result.returncode == code


def test_block_reaches_stderr_without_telemetry_or_disable_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_HARNESS_DISABLE", "1")
    result = _run(
        "pre-file-guard",
        {
            "cwd": str(tmp_path),
            "tool_input": {"file_path": "tests/holdout/fake.py"},
        },
        tmp_path,
    )
    assert result.returncode == 2
    assert "HIDDEN HOLDOUT" in result.stderr
    assert not result.stdout
    assert list(tmp_path.iterdir()) == []


def test_owner_mcp_denial_does_not_depend_on_git(tmp_path: Path) -> None:
    result = _run("pre-mcp-guard", {"tool_name": "mcp__alpha__reveal_holdout"}, tmp_path)
    assert result.returncode == 2
    assert "owner-authority" in result.stderr


def test_owner_action_guard_blocks_through_the_adapter_process(tmp_path: Path) -> None:
    route = "/api/" + "owner-auth" + "/actions/perform"
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": f"curl -X POST localhost:8801{route}"},
    }
    result = _run("pre-owner-action-guard", payload, tmp_path)
    assert result.returncode == 2
    assert "BLOCKED" in result.stderr


def test_session_orientation_is_bounded_and_side_effect_free(tmp_path: Path) -> None:
    result = _run("session-start", {"cwd": str(tmp_path)}, tmp_path)
    assert result.returncode == 0
    assert "gate.py orient" in result.stdout
    assert "CLAUDE.md" in result.stdout
    assert not result.stderr
    assert list(tmp_path.iterdir()) == []


def test_missing_adapter_blocks_safety_and_allows_session_guidance(tmp_path: Path) -> None:
    settings: dict[str, Any] = json.loads((REPO_ROOT / ".claude/settings.json").read_text())
    for event, expected in (("PreToolUse", 2), ("SessionStart", 0)):
        for group in settings["hooks"][event]:
            for hook in group["hooks"]:
                result = subprocess.run(
                    ["/bin/sh", "-c", hook["command"]],
                    cwd=tmp_path,
                    env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert result.returncode == expected, result.stderr
