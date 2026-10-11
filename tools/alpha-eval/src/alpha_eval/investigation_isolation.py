"""Read-only measurement workers; model reasoning uses a separate empty workspace."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from alpha_eval.platform import repo_root


def permission_args(read_roots: list[Path]) -> list[str]:
    rules = {
        "/": "deny",
        "/private/tmp": "deny",
        "/tmp": "deny",
        str(Path.home()): "deny",
        ":minimal": "read",
        "/opt/homebrew": "read",
        "/usr/local": "read",
    }
    rules.update({str(p.resolve()): "read" for p in read_roots})
    entries = ",".join(f"{json.dumps(k)}={json.dumps(v)}" for k, v in rules.items())
    settings = [
        'default_permissions="investigation"',
        "permissions.investigation.network.enabled=false",
        "permissions.investigation.filesystem={" + entries + "}",
    ]
    return [item for setting in settings for item in ("-c", setting)]


def worker_roots(runtime: Path, inputs: Path) -> list[Path]:
    root = repo_root()
    return [
        runtime,
        inputs,
        root / ".venv",
        root / "packages/alpha-core/src",
        root / "packages/alpha-validation/src",
    ]


def command(runtime: Path, inputs: Path, argv: list[str]) -> list[str]:
    return [
        shutil.which("codex") or "codex",
        "sandbox",
        "-C",
        str(runtime),
        "-P",
        "investigation",
        *permission_args(worker_roots(runtime, inputs)),
        "--",
        *argv,
    ]


def worker_env(runtime: Path) -> dict[str, str]:
    return {
        "HOME": str(runtime),
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "LC_ALL": "C",
        "TZ": "UTC",
    }


def preflight(runtime: Path, inputs: Path) -> dict[str, Any]:
    """Probe synthetic canaries only, through the identical worker permission policy."""
    forbidden = runtime.parent / "forbidden-canary.txt"
    forbidden.write_text("synthetic hidden future sibling source canary")
    link = runtime / "escape-link"
    link.symlink_to(forbidden)
    probe = inputs / "probe.txt"
    probe.write_text("read-only")
    script = """import pathlib,socket,sys
from alpha_validation.metrics import drawdown_episodes
runtime,inputs,forbidden=map(pathlib.Path,sys.argv[1:])
p=inputs/'probe.txt'
assert p.read_text()=='read-only'
checks=[lambda: p.write_text('bad'),lambda:p.unlink(),lambda:p.chmod(0o777),
 lambda:p.rename(inputs/'changed'),lambda:(inputs/'new').write_text('bad'),
 lambda:forbidden.read_text(),lambda:(runtime/'escape-link').read_text(),
 lambda:(runtime/'../forbidden-canary.txt').read_text(),
 lambda:(runtime/'write.txt').write_text('bad')]
for index,check in enumerate(checks):
 try: check()
 except PermissionError: pass
 else: raise SystemExit('filesystem boundary not enforced: '+str(index))
s=socket.socket()
try:
 try:s.connect(('127.0.0.1',9))
 except PermissionError:pass
 else:raise SystemExit('network boundary not enforced')
finally:s.close()
assert len(drawdown_episodes([100.,40.]))==1
print('verified')
"""
    try:
        result = subprocess.run(
            command(
                runtime,
                inputs,
                [
                    str(repo_root() / ".venv/bin/python"),
                    "-c",
                    script,
                    str(runtime),
                    str(inputs),
                    str(forbidden),
                ],
            ),
            cwd=runtime,
            env=worker_env(runtime),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode or result.stdout.strip() != "verified":
            raise RuntimeError(
                "isolation preflight failed: " + (result.stderr + result.stdout)[-1500:]
            )
    finally:
        link.unlink(missing_ok=True)
        probe.unlink(missing_ok=True)
        forbidden.unlink(missing_ok=True)
    return dict(
        verified=True,
        mechanism="codex-permission-profile",
        probes=[
            "input_read",
            "input_write_unlink_chmod_rename_create_denied",
            "outside_absolute_relative_symlink_read_denied",
            "runtime_write_denied",
            "network_connect_denied",
            "measurement_import",
        ],
        profile_args=permission_args(worker_roots(runtime, inputs)),
    )
