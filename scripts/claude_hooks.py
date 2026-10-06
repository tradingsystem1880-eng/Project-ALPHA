"""Thin Claude adapter: orientation and native tool-boundary safety only.

Engineering verification lives in the agent-neutral gate and real Git hooks. This adapter never
writes telemetry, consumes acknowledgments or evaluates task completion. Its one inspection of
tool input text is a fail-closed substring guard that keeps agent tools away from the owner-action
endpoints (ADR-0038); it is not a shell parser. Native permissions and process sandboxing remain
separate controls.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote

HookResult = tuple[int, str]
_MCP_OWNER_VERBS = re.compile(
    r"(approve|reject|decide|override_research_gate|reveal_holdout|research_decision)"
)


# Local click confirmation (ADR-0038) is any-local-process confirmable at the HTTP layer, so agent
# tools must never address the owner-action routes or start the CLI credential ceremonies.
_OWNER_ACTION_TEXT = re.compile(r"/owner-auth\b|\bowner-auth\s+(enroll|recover)\b")


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _hidden(path: Path) -> bool:
    return any(
        parts[i : i + 2] == ("tests", "holdout")
        for parts in (path.parts, path.resolve().parts)
        for i in range(len(parts) - 1)
    )


def hook_pre_file_guard(payload: dict[str, Any], root: Path) -> HookResult:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        raise ValueError("file tool input must be an object")
    target = tool_input.get("file_path")
    if not isinstance(target, str) or not target:
        raise ValueError("file tool input requires file_path")
    paths = [target]
    edits = tool_input.get("edits", [])
    if not isinstance(edits, list):
        raise ValueError("file tool edits must be a list")
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("file tool edit must be an object")
        if "file_path" in edit:
            nested = edit["file_path"]
            if not isinstance(nested, str) or not nested:
                raise ValueError("nested edit requires a file_path string")
            paths.append(nested)
    if any(_hidden(root / path) for path in paths):
        return (
            2,
            "BLOCKED: HIDDEN HOLDOUT tests are not readable or editable by agents. "
            "Run tests without inspecting their source; proposals belong in tests/holdout_seed/.",
        )
    return (0, "")


def hook_pre_mcp_guard(payload: dict[str, Any], root: Path) -> HookResult:
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not tool:
        raise ValueError("MCP hook requires tool_name")
    if tool.startswith("mcp__alpha__") and _MCP_OWNER_VERBS.search(tool):
        return (
            2,
            "BLOCKED: owner-authority research decisions, overrides and holdout reveal "
            "are unavailable through agent MCP tools.",
        )
    return (0, "")


def hook_pre_owner_action_guard(payload: dict[str, Any], root: Path) -> HookResult:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        raise ValueError("tool input must be an object")
    for text in _strings(tool_input):
        if _OWNER_ACTION_TEXT.search(unquote(unquote(text)).lower()):
            return (
                2,
                "BLOCKED: owner actions (local confirmation, approvals, D1/D2 launch, decisions, "
                "credential ceremonies) are the owner's own clicks; agent tools may not call them.",
            )
    return (0, "")


def hook_session_start(payload: dict[str, Any], root: Path) -> HookResult:
    return (
        0,
        "Project ALPHA: read CLAUDE.md and applicable .claude/rules before work. "
        "Load .agents/skills/karpathy-guidelines for code work. "
        "Source orientation: uv run python scripts/gate.py orient. "
        "Canonical verification: uv run python scripts/gate.py full. "
        "Engineering checks grant no application owner authority.",
    )


_HOOKS: dict[str, Callable[[dict[str, Any], Path], HookResult]] = {
    "pre-file-guard": hook_pre_file_guard,
    "pre-mcp-guard": hook_pre_mcp_guard,
    "pre-owner-action-guard": hook_pre_owner_action_guard,
    "session-start": hook_session_start,
}


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in _HOOKS:
        print(f"usage: claude_hooks.py {{{'|'.join(_HOOKS)}}}", file=sys.stderr)
        return 1
    name = argv[0]
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be an object")
        cwd = payload.get("cwd", str(Path.cwd()))
        if not isinstance(cwd, str) or not cwd:
            raise ValueError("hook cwd must be a path string")
        code, message = _HOOKS[name](payload, Path(cwd))
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        # Orientation is advisory; safety checks cannot silently allow malformed payloads.
        code = 0 if name == "session-start" else 2
        message = f"Claude adapter {name} unavailable: {exc}"
    if message:
        print(message, file=sys.stderr if code == 2 else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
