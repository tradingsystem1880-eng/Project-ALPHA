"""Explicit Codex configuration: one scoped MCP service, no ambient agent tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DISABLED = (
    "shell_tool",
    "unified_exec",
    "view_image",
    "sleep_tool",
    "skill_search",
    "skill_mcp_dependency_install",
    "tool_suggest",
    "code_mode",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "in_app_browser",
    "in_app_local_automation",
    "goals",
    "multi_agent_v2",
    "request_permissions_tool",
    "default_mode_request_user_input",
    "workspace_dependencies",
    "shell_snapshot",
    "plugins",
    "apps",
    "memories",
    "multi_agent",
    "browser_use",
    "computer_use",
    "hooks",
    "image_generation",
)


def permission_settings(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve(strict=True)
    if workspace in (Path("/"), Path.home(), Path("/private/tmp"), Path("/tmp")):
        raise ValueError("Codex needs a dedicated investigation workspace")
    return {
        "default_permissions": "investigation",
        "permissions": {
            "investigation": {
                "network": {"enabled": False},
                "filesystem": {
                    "/": "deny",
                    "/private/tmp": "deny",
                    "/tmp": "deny",
                    str(Path.home()): "deny",
                    str(workspace.parent): "deny",
                    ":minimal": "read",
                    "/opt/homebrew": "read",
                    "/usr/local": "read",
                    str(workspace): "read",
                },
            }
        },
    }


def launch_config(case: Path, workspace: Path, *, python: Path) -> dict[str, Any]:
    return {
        **permission_settings(workspace),
        "approval_policy": "never",
        "web_search": "disabled",
        "project_doc_max_bytes": 0,
        "model_reasoning_effort": "medium",
        "shell_environment_policy": {"inherit": "none"},
        "features": {
            **dict.fromkeys(_DISABLED, False),
            "skip_host_skill_discovery": True,
            # 0.159 uses this host for native MCP discovery even with code_mode disabled.
            "code_mode_host": True,
        },
        "mcp_servers": {
            "alpha_investigation": {
                "command": str(python),
                "args": ["-m", "alpha_mcp.investigation_server", str(case.resolve(strict=True))],
                "required": True,
                "startup_timeout_sec": 30,
                "tool_timeout_sec": 30,
                "enabled_tools": ["inspect_execution", "inspect_losses", "suggest_followups"],
                "tools": {
                    action: {"approval_mode": "approve"}
                    for action in ("inspect_execution", "inspect_losses", "suggest_followups")
                },
            }
        },
    }


def toml_value(value: object) -> str:
    """Encode only the closed JSON-compatible configuration emitted above."""
    if isinstance(value, dict):
        return "{" + ",".join(f"{json.dumps(k)}={toml_value(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(map(toml_value, value)) + "]"
    return json.dumps(value, allow_nan=False)


def config_text(config: dict[str, Any]) -> str:
    return "\n".join(f"{json.dumps(k)} = {toml_value(v)}" for k, v in config.items()) + "\n"
