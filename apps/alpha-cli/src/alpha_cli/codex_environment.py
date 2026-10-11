"""Dedicated App Server home and probes of its actual command execution policy."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from alpha_cli.codex_policy import config_text, launch_config
from alpha_core import DataError


class _Rpc(Protocol):
    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...


def _directory(path: Path) -> None:
    if path.is_symlink():
        raise DataError("Codex runtime directory cannot be a symlink")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir():
        raise DataError("Codex runtime path must be a directory")


def prepare(case: Path) -> tuple[list[str], Path, dict[str, str]]:
    """Never read credential bytes or inherit the owner's Codex configuration."""
    source_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    source_auth = source_home / "auth.json"
    if not source_auth.is_file():
        raise DataError("Codex blocked: existing local auth.json is required; run codex login")
    source_auth = source_auth.resolve(strict=True)
    executable = shutil.which("codex")
    if executable is None:
        raise DataError("Codex blocked: codex executable is unavailable")
    _directory(case)
    case = case.resolve(strict=True)
    workspace, home, temporary = (
        case / name for name in ("workspace", "codex-home", "runtime-tmp")
    )
    for directory in (workspace, home, temporary):
        _directory(directory)
    if any(workspace.iterdir()):
        raise DataError("Codex workspace must remain empty before launch")
    linked = home / "auth.json"
    if linked.is_symlink():
        if not linked.is_file() or linked.resolve(strict=True) != source_auth:
            raise DataError("Codex auth reference does not match the configured credential")
    elif linked.exists():
        raise DataError("Codex auth reference must be a symlink, never copied credentials")
    else:
        linked.symlink_to(source_auth)
    config = home / "config.toml"
    expected = config_text(launch_config(case, workspace, python=Path(sys.executable)))
    if config.is_symlink():
        raise DataError("Codex config cannot be a symlink")
    try:
        with config.open("x", encoding="utf-8") as handle:
            handle.write(expected)
    except FileExistsError:
        if not config.is_file() or config.read_text(encoding="utf-8") != expected:
            raise DataError(
                "Codex config drift: existing configuration does not match policy"
            ) from None
    bins = [str(Path(sys.executable).parent), str(Path(executable).parent)]
    alpha = shutil.which("alpha")
    if alpha is not None:
        bins.append(str(Path(alpha).parent))
    bins.extend(("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"))
    env = {
        "HOME": str(home),
        "CODEX_HOME": str(home),
        "TMPDIR": str(temporary),
        "PATH": ":".join(dict.fromkeys(bins)),
        "LANG": "en_US.UTF-8",
    }
    return [executable, "app-server"], workspace, env


async def preflight(rpc: _Rpc, workspace: Path) -> dict[str, Any]:
    """Verify App Server restrictions before a thread is allowed to run."""
    if workspace.is_symlink() or not workspace.is_dir():
        raise DataError("Codex isolation preflight requires a real workspace directory")
    workspace = workspace.resolve(strict=True)
    suffix = uuid4().hex
    visible = workspace / f"probe-visible-{suffix}"
    forbidden = workspace.parent / f"probe-forbidden-{suffix}"
    linked = workspace / f"probe-link-{suffix}"
    write_target = workspace / f"probe-write-{suffix}"
    owner_canary = Path.home() / f".alpha-probe-home-{suffix}"
    common_tmp = Path("/private/tmp") if Path("/private/tmp").is_dir() else Path("/tmp")
    temporary_canary = common_tmp / f"alpha-probe-tmp-{suffix}"
    script = """import pathlib,socket,sys
workspace,visible,forbidden,linked,target,owner,temporary=map(pathlib.Path,sys.argv[1:])
assert visible.read_text()=='synthetic visible canary'
checks=[lambda:forbidden.read_text(),
 lambda:(workspace/'..'/forbidden.name).read_text(),
 lambda:linked.read_text(),lambda:target.write_text('unexpected'),
 lambda:owner.read_text(),lambda:temporary.read_text()]
for index,check in enumerate(checks):
 try:check()
 except PermissionError:pass
 else:raise SystemExit('filesystem isolation failed '+str(index))
s=socket.socket()
s.settimeout(2)
try:
 try:s.connect(('127.0.0.1',9))
 except PermissionError:pass
 else:raise SystemExit('network isolation failed')
finally:s.close()
print('alpha-isolation-verified')
"""
    created: list[Path] = []
    try:
        with visible.open("x") as handle:
            created.append(visible)
            handle.write("synthetic visible canary")
        with forbidden.open("x") as handle:
            created.append(forbidden)
            handle.write("synthetic forbidden canary")
        for canary in (owner_canary, temporary_canary):
            with canary.open("x") as handle:
                created.append(canary)
                handle.write("synthetic forbidden canary")
        linked.symlink_to(forbidden)
        created.append(linked)
        if write_target.exists() or write_target.is_symlink():
            raise DataError("Codex isolation preflight path collision")
        created.append(write_target)
        try:
            result = await rpc.request(
                "command/exec",
                {
                    "command": [
                        "/usr/bin/python3",
                        "-c",
                        script,
                        str(workspace),
                        str(visible),
                        str(forbidden),
                        str(linked),
                        str(write_target),
                        str(owner_canary),
                        str(temporary_canary),
                    ],
                    "cwd": str(workspace),
                    "timeoutMs": 10_000,
                    "outputBytesCap": 2000,
                },
            )
        except (OSError, RuntimeError, ValueError):
            raise DataError("Codex isolation preflight transport failed") from None
        if (
            type(result.get("exitCode")) is not int
            or result["exitCode"] != 0
            or result.get("stdout") != "alpha-isolation-verified\n"
        ):
            raise DataError("Codex isolation preflight failed; restricted execution unverified")
    finally:
        for path in reversed(created):
            path.unlink(missing_ok=True)
    return {
        "verified": True,
        "mechanism": "app-server-command-exec-configured-permissions",
        "probes": [
            "visible_read",
            "sibling_absolute_read_denied",
            "sibling_relative_read_denied",
            "symlink_read_denied",
            "workspace_write_denied",
            "network_denied",
            "owner_home_read_denied",
            "common_tmp_read_denied",
        ],
    }
