"""Contract tests that drive the REAL hook entrypoint as Claude Code does.

`python3 scripts/claude_hooks.py <name>` with a JSON payload on stdin, in a
throwaway git repo. These cover the dispatcher (`main`), which the pure
function tests cannot: exit codes, stdout/stderr routing, fail-open on
crashes, the emergency disable switch, and the audit line every block leaves.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import gate
import pytest

from tests.unit._harness_support import REPO_ROOT

HOOK_SCRIPT = REPO_ROOT / "scripts" / "claude_hooks.py"


@pytest.fixture()
def repo(harness_repo: Path) -> Path:
    return harness_repo


def _run(
    hook: str, payload: dict[str, Any], cwd: Path, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged = {k: v for k, v in os.environ.items() if k != "ALPHA_HARNESS_DISABLE"}
    merged.pop(gate.OWNER_TOKEN_ENV, None)
    merged.update(env or {})
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), hook],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
        env=merged,
        check=False,
        timeout=60,
    )


def _payload(cwd: Path, **kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"session_id": "sub1", "cwd": str(cwd)}
    base.update(kwargs)
    return base


def _blocked_pre_edit_guard(repo: Path) -> tuple[str, dict[str, Any]]:
    target = repo / ".claude" / "agents" / "x.md"
    return "pre-edit-guard", _payload(repo, tool_input={"file_path": str(target), "content": "x"})


def _blocked_pre_mcp_guard(repo: Path) -> tuple[str, dict[str, Any]]:
    return "pre-mcp-guard", _payload(repo, tool_name="mcp__alpha__override_research_gate")


def _blocked_stop_guard(repo: Path) -> tuple[str, dict[str, Any]]:
    edit = _payload(repo, tool_input={"file_path": str(repo / "tracked.py")})
    _run("post-edit", edit, repo)
    return "stop-guard", _payload(repo)


class TestDispatcher:
    def test_unknown_hook_name_is_usage_error(self, repo: Path) -> None:
        result = _run("no-such-hook", {}, repo)
        assert result.returncode == 1
        assert "usage" in result.stderr

    def test_no_args_is_usage_error(self, repo: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 1

    def test_malformed_stdin_fails_open(self, repo: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT), "pre-bash-guard"],
            input="{not json",
            capture_output=True,
            text=True,
            cwd=repo,
            check=False,
        )
        assert result.returncode == 0

    def test_outside_git_repo_never_blocks(self, tmp_path: Path) -> None:
        bare = tmp_path / "nogit"
        bare.mkdir()
        payload = {"cwd": str(bare), "tool_input": {"command": "git commit -m 'bad message'"}}
        assert _run("pre-bash-guard", payload, bare).returncode == 0

    def test_disable_switch_bypasses_everything(self, repo: Path) -> None:
        payload = _payload(repo, tool_input={"command": "git commit --amend"})
        result = _run("pre-bash-guard", payload, repo, env={"ALPHA_HARNESS_DISABLE": "1"})
        assert result.returncode == 0

    def test_every_hook_name_dispatches(self, repo: Path) -> None:
        # Names that need no side-effect payload run cleanly end to end.
        for name in gate.HOOK_NAMES:
            if name in ("task-completed",):
                continue  # spawns pytest; covered by unit tests with a fake runner
            result = _run(name, _payload(repo), repo)
            assert result.returncode in (0, 2), (name, result.stderr)
            assert "crashed" not in result.stderr, (name, result.stderr)


class TestBlockContract:
    def test_block_goes_to_stderr_with_exit_2_and_audit(self, repo: Path) -> None:
        payload = _payload(repo, tool_input={"command": "git reset --hard HEAD"})
        result = _run("pre-bash-guard", payload, repo)
        assert result.returncode == 2
        assert "BLOCKED" in result.stderr
        assert result.stdout == ""
        events = gate.read_audit(repo, kind="blocked_pre-bash-guard")
        assert len(events) == 1
        assert "reset --hard" in events[0]["detail"]
        assert events[0]["session_id"] == "sub1"

    # Each decision below (block, ack/stamp/owner-token allow, one-shot
    # consumption) is already proven in-process in test_claude_harness_hooks.py
    # (TestPreBashGuard, TestPreEditGuard, TestHiddenHoldout.test_owner_may_edit,
    # TestMcpGuard, TestStopGuard). This parametrized test only needs to prove
    # the shell-layer property: the block reaches the real subprocess as exit 2,
    # once per hook category not already covered above.
    @pytest.mark.parametrize(
        "build",
        [_blocked_pre_edit_guard, _blocked_pre_mcp_guard, _blocked_stop_guard],
        ids=["pre-edit-guard", "pre-mcp-guard", "stop-guard"],
    )
    def test_block_reaches_shell_with_exit_2(
        self, repo: Path, build: Callable[[Path], tuple[str, dict[str, Any]]]
    ) -> None:
        hook, payload = build(repo)
        assert _run(hook, payload, repo).returncode == 2


class TestContextContract:
    def test_session_start_prints_brief_to_stdout(self, repo: Path) -> None:
        result = _run("session-start", _payload(repo), repo)
        assert result.returncode == 0
        assert "KARPATHY GUIDELINES" in result.stdout
        assert "OWNER TOKEN NOT CONFIGURED" in result.stdout

    def test_prompt_context_flags(self, repo: Path) -> None:
        result = _run("prompt-context", _payload(repo), repo)
        assert result.returncode == 0
        assert "[harness]" in result.stdout
        assert "owner-token:UNSET" in result.stdout

    def test_post_compact_reinjects(self, repo: Path) -> None:
        result = _run("post-compact", _payload(repo), repo)
        assert "POST-COMPACTION" in result.stdout
        assert "KARPATHY GUIDELINES" in result.stdout

    def test_audit_chain_survives_many_hook_writes(self, repo: Path) -> None:
        for _ in range(3):
            _run("pre-bash-guard", _payload(repo, tool_input={"command": "git stash drop"}), repo)
        _run("tool-log", _payload(repo, tool_name="Skill", tool_input={"skill": "x"}), repo)
        ok, detail = gate.verify_audit_chain(repo)
        assert ok, detail
        assert detail.startswith("4 events")
