"""The thin Claude adapter protects file/tool boundaries without engineering ceremony."""

from pathlib import Path

import claude_hooks
import pytest


@pytest.mark.parametrize(
    "target",
    [
        "tests/holdout/hidden.py",
        "./tests/holdout/hidden.py",
        "apps/../tests/holdout/hidden.py",
    ],
)
def test_hidden_file_access_is_denied(tmp_path: Path, target: str) -> None:
    code, message = claude_hooks.hook_pre_file_guard(
        {"tool_input": {"file_path": target}}, tmp_path
    )
    assert code == 2
    assert "HIDDEN HOLDOUT" in message


def test_resolved_symlink_and_nested_edit_cannot_escape(tmp_path: Path) -> None:
    # Synthetic directory only; never inspect the repository hidden suite.
    hidden = tmp_path / "tests/holdout"
    hidden.mkdir(parents=True)
    (tmp_path / "alias").symlink_to(hidden, target_is_directory=True)
    for payload in (
        {"tool_input": {"file_path": str(tmp_path / "alias/fake.py")}},
        {"tool_input": {"file_path": "safe.py", "edits": [{"file_path": str(hidden / "fake.py")}]}},
    ):
        assert claude_hooks.hook_pre_file_guard(payload, tmp_path)[0] == 2


@pytest.mark.parametrize("agent", ["independent-reviewer", "navigator", None])
def test_no_agent_role_or_disable_token_bypasses_holdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: str | None
) -> None:
    monkeypatch.setenv("ALPHA_HARNESS_DISABLE", "1")
    monkeypatch.setenv("ALPHA_OWNER_TOKEN", "unused")
    payload = {"agent_type": agent, "tool_input": {"file_path": "tests/holdout/fake.py"}}
    assert claude_hooks.hook_pre_file_guard(payload, tmp_path)[0] == 2


@pytest.mark.parametrize(
    "path",
    [
        "CLAUDE.md",
        "scripts/gate.py",
        ".claude/settings.json",
        "tests/holdout_seed/proposal.py",
    ],
)
def test_normal_file_access_needs_no_ack_or_state(tmp_path: Path, path: str) -> None:
    assert claude_hooks.hook_pre_file_guard({"tool_input": {"file_path": path}}, tmp_path) == (
        0,
        "",
    )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "tool",
    [
        "mcp__alpha__research_approve",
        "mcp__alpha__research_reject",
        "mcp__alpha__research_decide",
        "mcp__alpha__override_research_gate",
        "mcp__alpha__reveal_holdout",
    ],
)
def test_owner_mcp_actions_remain_denied(tmp_path: Path, tool: str) -> None:
    assert claude_hooks.hook_pre_mcp_guard({"tool_name": tool}, tmp_path)[0] == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("tool", ["mcp__alpha__research_status", "mcp__codex__codex"])
def test_advisory_tools_do_not_create_telemetry(tmp_path: Path, tool: str) -> None:
    assert claude_hooks.hook_pre_mcp_guard({"tool_name": tool}, tmp_path) == (0, "")
    assert list(tmp_path.iterdir()) == []


def test_session_points_to_shared_orientation_and_instructions(tmp_path: Path) -> None:
    code, message = claude_hooks.hook_session_start({}, tmp_path)
    assert code == 0
    assert "CLAUDE.md" in message
    assert "gate.py orient" in message
    assert "karpathy-guidelines" in message
    assert len(message.encode()) < 2_000
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        (
            "Bash",
            {"command": "curl -s -X POST http://localhost:8801/api/owner-auth/actions/challenge"},
        ),
        (
            "Bash",
            {"command": "wget --post-data='{}' 127.0.0.1:8801/api/owner-auth/actions/perform"},
        ),
        (
            "Bash",
            {
                "command": "python -c \"import httpx; httpx.post('http://[::1]:8801/api/Owner-Auth/x')\""
            },
        ),
        ("WebFetch", {"url": "http://localhost:8801/api/owner-auth/actions/perform", "prompt": ""}),
        (
            "mcp__claude-in-chrome__javascript_tool",
            {"text": "fetch('/api/owner-auth/actions/challenge', {method: 'POST'})", "tabId": 1},
        ),
        ("mcp__claude-in-chrome__navigate", {"url": "localhost:8801/owner-auth/enroll"}),
        (
            "mcp__plugin_playwright_playwright__browser_evaluate",
            {"function": "() => fetch('/api/owner%2Dauth/actions/perform')"},
        ),
        (
            "Bash",
            {"command": "uv run alpha owner-auth recover --reason test"},
        ),
    ],
)
def test_agent_tools_cannot_reach_owner_action_endpoints(
    tmp_path: Path, tool: str, tool_input: dict[str, object]
) -> None:
    code, message = claude_hooks.hook_pre_owner_action_guard(
        {"tool_name": tool, "tool_input": tool_input}, tmp_path
    )
    assert code == 2
    assert "owner" in message.lower()


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Bash", {"command": "uv run pytest -q tests/unit/test_owner_local_confirmation.py"}),
        ("Bash", {"command": "curl -s http://localhost:8801/api/research/cases"}),
        ("mcp__claude-in-chrome__navigate", {"url": "http://localhost:8801/#page=research"}),
        ("WebFetch", {"url": "https://example.org/owner", "prompt": "owner auth docs"}),
    ],
)
def test_ordinary_tool_calls_pass_the_owner_action_guard(
    tmp_path: Path, tool: str, tool_input: dict[str, object]
) -> None:
    assert claude_hooks.hook_pre_owner_action_guard(
        {"tool_name": tool, "tool_input": tool_input}, tmp_path
    ) == (0, "")


def test_source_paths_named_owner_auth_remain_inspectable(tmp_path: Path) -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git diff -- apps/alpha-cli/src/alpha_cli/owner_auth.py"},
    }
    assert claude_hooks.hook_pre_owner_action_guard(payload, tmp_path) == (0, "")
