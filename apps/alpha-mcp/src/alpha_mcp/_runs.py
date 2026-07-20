"""Filesystem reads over the run store — the read-only tools that need no subprocess.

``alpha`` already writes a byte-stable ``manifest.json`` per run under one of a few run-type
directories; ``get_run`` / ``list_runs`` just read them back. This mirrors how ``alpha report``
locates a run, so the MCP read tools and the CLI agree on what exists.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from alpha_cli.artifact_contract import verify_manifest_artifacts
from alpha_cli.run_store import RUN_DIRS, find_run_dir, read_manifest, valid_run_id

MAX_MANIFEST_BYTES = 1_000_000
MAX_MANIFEST_DEPTH = 32
MAX_RUN_PAGE = 500


def _validate_json(value: object, *, depth: int = 0) -> None:
    if depth > MAX_MANIFEST_DEPTH:
        raise ValueError(f"run manifest JSON exceeds {MAX_MANIFEST_DEPTH} levels")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("run manifest contains a non-finite number")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json(item, depth=depth + 1)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _validate_json(item, depth=depth + 1)
        return
    raise ValueError("run manifest contains a non-JSON value")


def read_bounded_manifest(rdir: Path) -> dict[str, Any]:
    """Read one manifest under the MCP payload cap and verify every declared v3 artifact."""
    path = rdir / "manifest.json"
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise FileNotFoundError(f"run manifest is unavailable at {path}") from exc
    if size > MAX_MANIFEST_BYTES:
        raise ValueError(f"run manifest exceeds {MAX_MANIFEST_BYTES} bytes")
    manifest = read_manifest(rdir)
    verify_manifest_artifacts(rdir, manifest)
    _validate_json(manifest)
    return manifest


def get_run(run_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Return a stored run's manifest by id, searching every run-type dir. Fail loud if absent."""
    if not valid_run_id(run_id):
        raise FileNotFoundError(f"invalid run id {run_id!r} (expected 16 hex chars)")
    rdir = find_run_dir(data_dir, run_id)
    if rdir is not None:
        return read_bounded_manifest(rdir)
    raise FileNotFoundError(f"no run {run_id!r} under {data_dir} ({'/'.join(RUN_DIRS)})")


def list_runs(*, data_dir: Path, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """Return one deterministic bounded page of legacy run summaries."""
    if isinstance(limit, bool) or not 1 <= limit <= MAX_RUN_PAGE:
        raise ValueError(f"limit must be in 1..{MAX_RUN_PAGE}")
    if isinstance(offset, bool) or offset < 0:
        raise ValueError("offset must be non-negative")
    candidates: list[Path] = []
    for sub in RUN_DIRS:
        base = data_dir / sub
        if not base.is_dir():
            continue
        candidates.extend(
            sorted(
                p for p in base.iterdir() if valid_run_id(p.name) and (p / "manifest.json").exists()
            )
        )
    runs: list[dict[str, Any]] = []
    for rdir in candidates[offset : offset + limit]:
        manifest = read_bounded_manifest(rdir)
        symbols = manifest.get("symbols")
        if symbols is not None and (
            not isinstance(symbols, list) or not all(isinstance(symbol, str) for symbol in symbols)
        ):
            raise ValueError(f"run {rdir.name} has invalid symbols metadata")
        label = (
            manifest.get("symbol")
            or (", ".join(symbols) if symbols else None)
            or manifest.get("source")
        )
        command = manifest.get("command")
        if command is not None and not isinstance(command, str):
            raise ValueError(f"run {rdir.name} has invalid command metadata")
        if label is not None and not isinstance(label, str):
            raise ValueError(f"run {rdir.name} has invalid label metadata")
        runs.append({"run_id": rdir.name, "command": command, "label": label})
    return runs
