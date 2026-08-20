"""Drift guards for `.claude/settings.json` ↔ hook dispatcher ↔ gate registry.

The harness is only as strong as its wiring: a hook that exists in
`claude_hooks._HOOKS` but is not wired in settings never runs, and a deny rule
that quietly disappears re-opens an owner-authority path. These tests pin the
three-way agreement and the mandatory deny entries.
"""

from __future__ import annotations

import json
import re
from typing import Any

import claude_hooks
import gate
import pytest

from tests.unit._harness_support import REPO_ROOT

SETTINGS = REPO_ROOT / ".claude" / "settings.json"

MANDATORY_DENY = (
    "Read(.env)",
    "Read(.env.*)",
    "Bash(git push --force*)",
    "Bash(git push -f*)",
    "Bash(git commit --amend*)",
    "Bash(git commit --no-verify*)",
    "Bash(git reset --hard*)",
    "Bash(git clean -f*)",
    "Bash(git stash drop*)",
)
OWNER_VERBS = (
    "alpha research approve",
    "alpha research reject",
    "alpha research decide",
    "alpha project override-research-gate",
    "alpha project reveal-holdout",
)
OWNER_VERB_FORMS = ("uv run {v}*", "{v}*", ".venv/bin/{v}*")

_HOOK_NAME_RE = re.compile(r'python3 "\$h" ([a-z-]+)')


def _settings() -> dict[str, Any]:
    data = json.loads(SETTINGS.read_text())
    assert isinstance(data, dict)
    return data


def _wired_hooks() -> dict[str, list[str]]:
    """event -> hook script names wired for it (command hooks only)."""
    wired: dict[str, list[str]] = {}
    for event, groups in _settings()["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                if hook.get("type") != "command":
                    continue
                match = _HOOK_NAME_RE.search(hook["command"])
                assert match, f"{event}: hook command does not name a hook: {hook['command']}"
                wired.setdefault(event, []).append(match.group(1))
    return wired


class TestHookWiring:
    def test_settings_hook_names_exist_in_dispatcher(self) -> None:
        for event, names in _wired_hooks().items():
            for name in names:
                assert name in claude_hooks._HOOKS, f"{event} wires unknown hook {name}"

    def test_dispatcher_hooks_are_all_wired(self) -> None:
        wired = {n for names in _wired_hooks().values() for n in names}
        assert set(claude_hooks._HOOKS) == wired, (
            f"dispatcher/settings drift: {set(claude_hooks._HOOKS) ^ wired}"
        )

    def test_gate_registry_matches_dispatcher(self) -> None:
        assert set(gate.HOOK_NAMES) == set(claude_hooks._HOOKS)

    @pytest.mark.parametrize(
        ("event", "hook"),
        [
            ("PreToolUse", "pre-edit-guard"),
            ("PreToolUse", "pre-read-guard"),
            ("PreToolUse", "pre-bash-guard"),
            ("PreToolUse", "pre-mcp-guard"),
            ("PostToolUse", "post-edit"),
            ("PostToolUse", "post-bash"),
            ("PostToolUse", "tool-log"),
            ("PostToolUseFailure", "post-tool-failure"),
            ("SubagentStop", "subagent-stop"),
            ("TaskCompleted", "task-completed"),
            ("ConfigChange", "config-change"),
            ("Stop", "stop-guard"),
            ("SessionStart", "session-start"),
            ("UserPromptSubmit", "prompt-context"),
            ("PreCompact", "pre-compact"),
            ("PostCompact", "post-compact"),
        ],
    )
    def test_hook_on_expected_event(self, event: str, hook: str) -> None:
        assert hook in _wired_hooks().get(event, []), f"{hook} not wired on {event}"

    def test_pre_tool_matchers_cover_edit_read_bash_mcp(self) -> None:
        matchers = {g.get("matcher") for g in _settings()["hooks"]["PreToolUse"]}
        assert "Edit|Write|MultiEdit" in matchers
        assert "Read" in matchers
        assert "Bash" in matchers
        assert any(m and "mcp__alpha__" in m and "mcp__codex__" in m for m in matchers)

    def test_no_hook_timeout_exceeds_120s(self) -> None:
        for event, groups in _settings()["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    assert hook.get("timeout", 0) <= 120, f"{event}: timeout > 120s"

    def test_hook_commands_fail_open_when_script_missing(self) -> None:
        # Every command hook must degrade to `exit 0` if the script is absent, so a
        # checkout without scripts/ never wedges the session.
        for groups in _settings()["hooks"].values():
            for group in groups:
                for hook in group["hooks"]:
                    if hook.get("type") == "command":
                        assert "|| exit 0" in hook["command"]

    def test_stop_has_advisory_prompt_judge(self) -> None:
        stop_hooks = [h for g in _settings()["hooks"]["Stop"] for h in g["hooks"]]
        prompts = [h for h in stop_hooks if h.get("type") == "prompt"]
        assert len(prompts) == 1
        text = prompts[0]["prompt"].lower()
        assert "unverified" in text
        assert "assumptions" in text or "simpler alternative" in text


class TestDenyList:
    def test_mandatory_deny_entries_present(self) -> None:
        deny = set(_settings()["permissions"]["deny"])
        missing = [d for d in MANDATORY_DENY if d not in deny]
        assert not missing, f"mandatory deny rules missing: {missing}"

    @pytest.mark.parametrize("verb", OWNER_VERBS)
    def test_owner_verbs_denied_in_all_forms(self, verb: str) -> None:
        deny = set(_settings()["permissions"]["deny"])
        for form in OWNER_VERB_FORMS:
            rule = f"Bash({form.format(v=verb)})"
            assert rule in deny, f"missing deny rule {rule}"

    def test_allow_list_never_grants_owner_verbs(self) -> None:
        for rule in _settings()["permissions"]["allow"]:
            for verb in OWNER_VERBS:
                assert verb not in rule, f"allow rule grants owner verb: {rule}"

    def test_baseline_deny_rules_are_a_subset(self) -> None:
        baseline = gate.read_json(REPO_ROOT / gate.BASELINE_FILE)
        assert baseline, "harness baseline missing — run gate.py baseline"
        deny = set(_settings()["permissions"]["deny"])
        assert set(baseline["deny_rules"]) <= deny


class TestStatusline:
    def test_statusline_wired_and_present(self) -> None:
        line = _settings()["statusLine"]
        assert line["type"] == "command"
        assert ".claude/statusline.py" in line["command"]
        assert (REPO_ROOT / ".claude" / "statusline.py").is_file()
