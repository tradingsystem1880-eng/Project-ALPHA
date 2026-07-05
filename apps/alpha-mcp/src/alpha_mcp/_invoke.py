"""Subprocess core: run the `alpha` CLI and return the run it produced.

Every action tool funnels through :func:`run_alpha`. It runs ``alpha <args>`` as a child process
(sharing the server's ``data_dir`` via the environment), fails loud on a non-zero exit by
surfacing the CLI's stderr, and on success parses the ``-> run <id>`` token the action commands
print, then reads back the byte-stable ``manifest.json`` the CLI wrote. Commands that write no
manifest (``data pull``) pass ``run_type=None`` and get their stdout summary instead.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

_ALPHA_BIN = "alpha"  # console script; resolvable on PATH inside the workspace venv
_RUN_ID_RE = re.compile(r"->\s+run\s+([0-9a-f]{16})\b")
_TIMEOUT_S = 3600.0  # generous ceiling for a full gauntlet; a hung child must not hang the server


def run_alpha(args: list[str], *, data_dir: Path, run_type: str | None) -> dict[str, Any]:
    """Run ``alpha <args>`` and return the resulting run's manifest (or its stdout summary).

    ``run_type`` is the artifact subdirectory the command writes to (``"runs"``, ``"optim"``,
    ``"propfirm"``, …) or ``None`` for commands that persist nothing. Raises ``RuntimeError`` on a
    non-zero exit (carrying stderr), when no run id can be parsed from a run-producing command, or
    when the expected manifest is missing.
    """
    env = {**os.environ, "ALPHA_DATA_DIR": str(data_dir)}
    try:
        proc = subprocess.run(
            [_ALPHA_BIN, *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"`alpha {' '.join(args)}` exceeded {_TIMEOUT_S:.0f}s and was killed - a hung data "
            "pull or runaway run must not hang the MCP server"
        ) from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "(no output)"
        raise RuntimeError(f"`alpha {' '.join(args)}` failed (exit {proc.returncode}): {detail}")

    if run_type is None:
        return {"stdout": proc.stdout.strip()}

    match = _RUN_ID_RE.search(proc.stdout)
    if match is None:
        raise RuntimeError(
            f"could not parse a run id from `alpha {' '.join(args)}` output:\n{proc.stdout.strip()}"
        )
    run_id = match.group(1)
    manifest_path = data_dir / run_type / run_id / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"run {run_id} produced no manifest at {manifest_path}")
    result: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return result
