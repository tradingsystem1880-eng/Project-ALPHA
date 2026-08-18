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
from pathlib import Path
from typing import Any

import gate
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SCRIPT = REPO_ROOT / "scripts" / "claude_hooks.py"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text(".claude/state/\n")
    (root / "tracked.py").write_text("x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "chore: init")
    return root


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

    def test_commit_without_stamp_blocks_then_stamp_allows(self, repo: Path) -> None:
        (repo / "tracked.py").write_text("x = 2\n")
        _git(repo, "add", "-A")
        payload = _payload(repo, tool_input={"command": "git commit -m 'feat: x'"})
        assert _run("pre-bash-guard", payload, repo).returncode == 2
        gate.write_stamp(repo, "full", steps=[("all", 1.0, True)], duration=1.0)
        assert _run("pre-bash-guard", payload, repo).returncode == 0

    def test_protected_edit_blocks_then_ack_allows_once(self, repo: Path) -> None:
        target = repo / ".claude" / "agents" / "x.md"
        payload = _payload(repo, tool_input={"file_path": str(target), "content": "x"})
        first = _run("pre-edit-guard", payload, repo)
        assert first.returncode == 2 and "ack" in first.stderr
        gate.write_ack(repo, reason="test")
        assert _run("pre-edit-guard", payload, repo).returncode == 0
        assert _run("pre-edit-guard", payload, repo).returncode == 2, "ack is one-shot"

    def test_owner_token_bypasses_protected_edit(self, repo: Path) -> None:
        gate.owner_init(repo, "owner-secret-token")
        target = repo / ".claude" / "agents" / "x.md"
        payload = _payload(repo, tool_input={"file_path": str(target), "content": "x"})
        assert _run("pre-edit-guard", payload, repo).returncode == 2
        ok = _run("pre-edit-guard", payload, repo, env={gate.OWNER_TOKEN_ENV: "owner-secret-token"})
        assert ok.returncode == 0
        events = gate.read_audit(repo, kind="protected_edit_owner")
        assert events and events[0]["authorized_by"] == "owner"

    def test_mcp_owner_verb_blocked(self, repo: Path) -> None:
        payload = _payload(repo, tool_name="mcp__alpha__override_research_gate")
        result = _run("pre-mcp-guard", payload, repo)
        assert result.returncode == 2 and "owner-authority" in result.stderr

    def test_stop_guard_blocks_unstamped_source_edit(self, repo: Path) -> None:
        # Record an edit through the real post-edit hook, then try to stop.
        edit = _payload(repo, tool_input={"file_path": str(repo / "tracked.py")})
        assert _run("post-edit", edit, repo).returncode == 0
        stop = _run("stop-guard", _payload(repo), repo)
        assert stop.returncode == 2 and "gate.py fast" in stop.stderr
        gate.write_stamp(repo, "fast", steps=[("all", 1.0, True)], duration=1.0)
        assert _run("stop-guard", _payload(repo), repo).returncode == 0

    def test_stop_hook_active_short_circuits(self, repo: Path) -> None:
        edit = _payload(repo, tool_input={"file_path": str(repo / "tracked.py")})
        _run("post-edit", edit, repo)
        payload = _payload(repo, stop_hook_active=True)
        assert _run("stop-guard", payload, repo).returncode == 0


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
