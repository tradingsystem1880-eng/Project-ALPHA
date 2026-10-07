"""Native safety permissions and the thin Claude adapter must stay wired."""

from __future__ import annotations

import json
import re
from typing import Any

import claude_hooks
import gate
import pytest

from tests.unit._harness_support import REPO_ROOT

SETTINGS = REPO_ROOT / ".claude/settings.json"


def _settings() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SETTINGS.read_text())
    return data


def test_only_orientation_and_safety_hooks_are_wired() -> None:
    settings = _settings()
    assert set(settings["hooks"]) == {"PreToolUse", "SessionStart"}
    wired = {
        match.group(1)
        for groups in settings["hooks"].values()
        for group in groups
        for hook in group["hooks"]
        if (match := re.search(r'python3 "\$h" ([a-z-]+)', hook["command"]))
    }
    assert wired == set(claude_hooks._HOOKS) == set(gate.HOOK_NAMES)
    assert wired == {"pre-file-guard", "pre-mcp-guard", "pre-owner-action-guard", "session-start"}
    assert all(
        hook["type"] == "command"
        for groups in settings["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    )


def test_safety_matchers_cover_file_tools_alpha_mcp_and_owner_action_routes() -> None:
    groups = _settings()["hooks"]["PreToolUse"]
    assert {group["matcher"] for group in groups} == {
        "Read|Edit|Write|MultiEdit",
        "mcp__alpha__.*",
        "Bash|WebFetch|mcp__.*",
    }
    for group in groups:
        for hook in group["hooks"]:
            assert "exit 2" in hook["command"], "missing safety adapter must fail closed"
            assert hook["timeout"] <= 15


@pytest.mark.parametrize("tool", ["Read", "Edit", "Write"])
def test_hidden_holdout_has_native_deny_rules(tool: str) -> None:
    denied = _settings()["permissions"]["deny"]
    assert f"{tool}(tests/holdout/**)" in denied
    assert f"{tool}(./tests/holdout/**)" in denied


@pytest.mark.parametrize(
    "rule",
    [
        "Read(.env)",
        "Read(.env.*)",
        "Bash(git push --force*)",
        "Bash(git push -f*)",
        "Bash(git commit --amend*)",
        "Bash(git commit --no-verify*)",
        "Bash(git reset --hard*)",
        "Bash(git clean -f*)",
        "Bash(git stash drop*)",
        "Bash(security find-generic-password *-w*)",
        "Bash(security dump-keychain*)",
    ],
)
def test_existing_destructive_and_secret_denials_remain(rule: str) -> None:
    assert rule in _settings()["permissions"]["deny"]


@pytest.mark.parametrize(
    "verb",
    [
        "alpha research approve",
        "alpha research reject",
        "alpha research decide",
        "alpha project override-research-gate",
        "alpha project reveal-holdout",
        "alpha owner-auth enroll",
        "alpha owner-auth recover",
        "alpha paper ibkr-run",
        "alpha paper ibkr-what-if-execute",
    ],
)
def test_owner_actions_remain_denied_in_native_command_forms(verb: str) -> None:
    settings = _settings()
    for prefix in ("uv run ", "", ".venv/bin/"):
        assert f"Bash({prefix}{verb}*)" in settings["permissions"]["deny"]
    assert not any(verb in rule for rule in settings["permissions"]["allow"])
