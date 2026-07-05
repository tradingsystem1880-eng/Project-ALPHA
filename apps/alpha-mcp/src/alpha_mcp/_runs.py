"""Filesystem reads over the run store — the read-only tools that need no subprocess.

``alpha`` already writes a byte-stable ``manifest.json`` per run under one of a few run-type
directories; ``get_run`` / ``list_runs`` just read them back. This mirrors how ``alpha report``
locates a run, so the MCP read tools and the CLI agree on what exists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# the run-type subdirectories `alpha` writes to (matches report_cmds._RUN_DIRS)
_RUN_DIRS = ("runs", "portfolio", "cross_sectional", "optim", "propfirm")
# run ids are always 16 hex chars (_runner.run_id_for); reject anything else before it touches a
# filesystem path (the id arrives from the MCP client)
_RUN_ID_RE = re.compile(r"^[0-9a-f]{16}$")


def get_run(run_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Return a stored run's manifest by id, searching every run-type dir. Fail loud if absent."""
    if _RUN_ID_RE.fullmatch(run_id) is None:
        raise FileNotFoundError(f"invalid run id {run_id!r} (expected 16 hex chars)")
    for sub in _RUN_DIRS:
        path = data_dir / sub / run_id / "manifest.json"
        if path.exists():
            result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return result
    raise FileNotFoundError(f"no run {run_id!r} under {data_dir} ({'/'.join(_RUN_DIRS)})")


def list_runs(*, data_dir: Path) -> list[dict[str, Any]]:
    """Index every stored run as ``{run_id, command, label}`` across all run-type dirs."""
    runs: list[dict[str, Any]] = []
    for sub in _RUN_DIRS:
        base = data_dir / sub
        if not base.is_dir():
            continue
        for rdir in sorted(p for p in base.iterdir() if (p / "manifest.json").exists()):
            manifest = json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))
            symbols = manifest.get("symbols")
            label = (
                manifest.get("symbol")
                or (", ".join(symbols) if symbols else None)
                or manifest.get("source")
            )
            runs.append({"run_id": rdir.name, "command": manifest.get("command"), "label": label})
    return runs
