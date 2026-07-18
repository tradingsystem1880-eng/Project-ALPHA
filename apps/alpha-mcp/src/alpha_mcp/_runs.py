"""Filesystem reads over the run store — the read-only tools that need no subprocess.

``alpha`` already writes a byte-stable ``manifest.json`` per run under one of a few run-type
directories; ``get_run`` / ``list_runs`` just read them back. This mirrors how ``alpha report``
locates a run, so the MCP read tools and the CLI agree on what exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_cli.run_store import RUN_DIRS, find_run_dir, read_manifest, valid_run_id


def get_run(run_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Return a stored run's manifest by id, searching every run-type dir. Fail loud if absent."""
    if not valid_run_id(run_id):
        raise FileNotFoundError(f"invalid run id {run_id!r} (expected 16 hex chars)")
    rdir = find_run_dir(data_dir, run_id)
    if rdir is not None:
        return read_manifest(rdir)
    raise FileNotFoundError(f"no run {run_id!r} under {data_dir} ({'/'.join(RUN_DIRS)})")


def list_runs(*, data_dir: Path) -> list[dict[str, Any]]:
    """Index every stored run as ``{run_id, command, label}`` across all run-type dirs."""
    runs: list[dict[str, Any]] = []
    for sub in RUN_DIRS:
        base = data_dir / sub
        if not base.is_dir():
            continue
        for rdir in sorted(p for p in base.iterdir() if (p / "manifest.json").exists()):
            manifest = read_manifest(rdir)
            symbols = manifest.get("symbols")
            label = (
                manifest.get("symbol")
                or (", ".join(symbols) if symbols else None)
                or manifest.get("source")
            )
            runs.append({"run_id": rdir.name, "command": manifest.get("command"), "label": label})
    return runs
