"""Fresh tools-disabled Codex decisions, with raw events retained and unexpected tools fatal."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from alpha_eval.investigation_demo import Decision, write_once
from alpha_eval.investigation_isolation import permission_args
from alpha_eval.stream import stream_process


def model_argv(workspace: Path, schema: Path, result: Path, model: str, prompt: str) -> list[str]:
    argv = [
        shutil.which("codex") or "codex",
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--skip-git-repo-check",
        "--json",
        "--color",
        "never",
        "-C",
        str(workspace),
        "-m",
        model,
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(result),
        *permission_args([workspace]),
        "--enable",
        "skip_host_skill_discovery",
    ]
    for flag in (
        "shell_tool",
        "unified_exec",
        "view_image",
        "sleep_tool",
        "skill_search",
        "skill_mcp_dependency_install",
        "tool_suggest",
        "code_mode",
        "code_mode_host",
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
    ):
        argv += ["--disable", flag]
    for setting in (
        'approval_policy="never"',
        'web_search="disabled"',
        'model_reasoning_effort="medium"',
        'shell_environment_policy.inherit="none"',
        "project_doc_max_bytes=0",
        "suppress_unstable_features_warning=true",
    ):
        argv += ["-c", setting]
    return [*argv, prompt]


class CodexProposer:
    def __init__(self, workspace: Path, model: str) -> None:
        if not model or ":" in model:
            raise ValueError("supply a Codex model slug, not a provider-prefixed identifier")
        self.workspace = workspace
        self.model = model
        workspace.mkdir(exist_ok=False)
        self.version = subprocess.run(
            ["codex", "--version"], capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()

    def __call__(self, prompt: str, slot: Path, seconds: float) -> dict[str, Any]:
        schema = slot.with_suffix(".schema.json")
        result = slot.with_suffix(".final.json")
        write_once(schema, Decision.model_json_schema())
        argv = model_argv(self.workspace, schema, result, self.model, prompt)
        write_once(
            slot.with_suffix(".invocation.json"),
            dict(argv=argv, client=self.version, model=self.model, effort="medium"),
        )
        completed = False
        bad_event = False
        usage: list[object] = []

        def consume(line: str) -> bool:
            nonlocal completed, bad_event
            try:
                event = json.loads(line)
                if event.get("type") == "turn.completed":
                    completed = True
                    usage.append(event.get("usage"))
                if event.get("type") in ("error", "turn.failed"):
                    bad_event = True
                item = event.get("item")
                disabled_host_notice = (
                    item
                    and item.get("type") == "error"
                    and str(item.get("message", "")).startswith(
                        "Code Mode is unavailable because code-mode host is disabled."
                    )
                )
                if (
                    item
                    and not disabled_host_notice
                    and item.get("type") not in ("agent_message", "reasoning")
                ):
                    bad_event = True
            except (ValueError, AttributeError):
                bad_event = True
            return not bad_event

        env = {"HOME": str(Path.home()), "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"}
        if os.environ.get("CODEX_HOME"):
            env["CODEX_HOME"] = os.environ["CODEX_HOME"]
        with slot.with_suffix(".raw.jsonl").open("x") as raw:
            meta = stream_process(argv, self.workspace, env, seconds, raw, consume)
        write_once(
            slot.with_suffix(".transport.json"),
            dict(
                **meta, usage=usage, turn_completed=completed, unexpected_or_failed_event=bad_event
            ),
        )
        if bad_event or not completed or meta["stop"] != "completed":
            raise RuntimeError(
                "Codex turn incomplete or unexpected tool event; inspect transport receipt"
            )
        if not result.is_file() or result.stat().st_size > 65536:
            raise ValueError("missing or oversized model output")
        value: dict[str, Any] = json.loads(result.read_text())
        return value
