"""Test-only helpers for control-store states that production can create only by migration."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path

import polars as pl

from alpha_cli import _artifacts
from alpha_cli.control_store import DATABASE_NAME, ControlStore

_RESEARCH_PROGRAM_LAUNCH = "2026-08-06T00:00:00.000000Z"


def mark_project_as_migrated_legacy(store: ControlStore, project_id: str) -> None:
    """Model a verified v1->v2 legacy row without adding a production bypass."""
    database = store._data_dir / "control" / DATABASE_NAME  # noqa: SLF001
    connection = sqlite3.connect(database)
    try:
        project = connection.execute(
            "SELECT created_at FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise AssertionError(f"unknown fixture project {project_id!r}")
        if not isinstance(project[0], str) or project[0] >= _RESEARCH_PROGRAM_LAUNCH:
            raise AssertionError("legacy fixture project must predate the research program")
        updated = connection.execute(
            """UPDATE project_research_governance
            SET research_required = 0, origin = 'legacy_import'
            WHERE project_id = ?""",
            (project_id,),
        )
        if updated.rowcount != 1:
            raise AssertionError(f"missing governance row for fixture project {project_id!r}")
        connection.commit()
    finally:
        connection.close()


def publish_decision_grade_run(
    data_dir: Path,
    *,
    run_id: str = "0123456789abcdef",
    manifest_fields: Mapping[str, object] | None = None,
) -> Path:
    """Publish a minimal immutable v3 optimization run for evidence-ledger tests."""
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"trial_id": [0]}).write_parquet(run_dir / "trials.parquet")
    pl.DataFrame({"trial_id": [0]}).write_parquet(run_dir / "trial_ledger.parquet")
    manifest: dict[str, object] = {
        "run_id": run_id,
        "run_identity_version": 3,
        "command": "optim_grid",
        "snapshot_id": None,
        "snapshot_hash": None,
        "execution_fingerprint": "a" * 64,
        "strategy_fingerprint": "b" * 64,
        "source_fingerprint": "c" * 64,
    }
    if manifest_fields is not None:
        manifest.update(manifest_fields)
    _artifacts.write_manifest(run_dir, manifest)
    return run_dir


__all__ = ["mark_project_as_migrated_legacy", "publish_decision_grade_run"]
