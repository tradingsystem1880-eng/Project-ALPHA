"""Enforced read boundaries shared by Codex commands and the MCP subprocess."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def permission_args(workspace: Path, sandbox: Path) -> list[str]:
    rules = {
        str(sandbox.parent.resolve()): "deny",
        str(Path.home()): "deny",
        "/private/tmp": "deny",
        "/tmp": "deny",
        ":minimal": "read",
        str(workspace.resolve()): "read",
        str(sandbox.resolve()): "write",
        "/opt/homebrew": "read",
        "/usr/local": "read",
    }
    settings = ['default_permissions="alpha_eval"', "permissions.alpha_eval.network.enabled=false"]
    entries = ",".join(f"{json.dumps(path)}={json.dumps(access)}" for path, access in rules.items())
    settings.append("permissions.alpha_eval.filesystem={" + entries + "}")
    return [arg for setting in settings for arg in ("-c", setting)]


def sandbox_command(workspace: Path, sandbox: Path, command: list[str]) -> list[str]:
    return [
        shutil.which("codex") or "codex",
        "sandbox",
        "-C",
        str(workspace),
        "-P",
        "alpha_eval",
        *permission_args(workspace, sandbox),
        "--",
        *command,
    ]


def preflight(workspace: Path, sandbox: Path) -> dict[str, object]:
    """Probe real enforcement with synthetic files; never read private owner content."""
    sandbox.mkdir(parents=True, exist_ok=True)
    forbidden = sandbox.parent / "boundary-canary.txt"
    forbidden.write_text("synthetic evaluator-only canary", encoding="utf-8")
    visible = sandbox / "boundary-visible.txt"
    visible.write_text("visible", encoding="utf-8")
    script = """import pathlib,sys
visible,forbidden,workspace=map(pathlib.Path,sys.argv[1:])
assert visible.read_text() == 'visible'
visible.write_text('allowed')
for path,mode in [(forbidden,'r'),(workspace/'boundary-write.txt','w')]:
    try:
        with path.open(mode): pass
    except PermissionError: pass
    else: raise SystemExit('boundary was not enforced: '+str(path))
print('isolation verified')
"""
    cmd = sandbox_command(
        workspace,
        sandbox,
        [
            str(workspace / ".venv/bin/python"),
            "-c",
            script,
            str(visible),
            str(forbidden),
            str(workspace),
        ],
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    if proc.returncode != 0 or "isolation verified" not in proc.stdout:
        raise RuntimeError("Isolation preflight failed: " + (proc.stderr or proc.stdout)[-1500:])
    from alpha_eval.platform import sandbox_env

    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "alpha-eval-preflight", "version": "2"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    server = subprocess.run(
        sandbox_command(workspace, sandbox, [str(workspace / ".venv/bin/alpha-mcp")]),
        env=sandbox_env(sandbox, workspace),
        input="\n".join(map(json.dumps, messages)) + "\n",
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    replies = [json.loads(line) for line in server.stdout.splitlines() if line.startswith("{")]
    tool_names = {
        t["name"] for r in replies if r.get("id") == 2 for t in r.get("result", {}).get("tools", [])
    }
    if server.returncode or not {"get_data_candles", "get_project"} <= tool_names:
        raise RuntimeError("MCP isolation preflight failed: " + server.stderr[-1000:])
    return {
        "verified": True,
        "mcp_tools": len(tool_names),
        "mechanism": "codex-permission-profile",
        "profile_args": permission_args(workspace, sandbox),
    }
