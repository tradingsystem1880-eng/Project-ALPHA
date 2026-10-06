"""Bounded CLI-resolved evidence; no model or browser supplied data can become a source."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

from alpha_cli.artifact_contract import verify_manifest_artifacts
from alpha_cli.assistant_contracts import AssistantContext
from alpha_cli.run_store import find_run_dir


def projection(args: list[str], root: Path) -> dict[str, Any]:
    env = {**os.environ, "ALPHA_DATA_DIR": str(root), "TYPER_USE_RICH": "0"}
    proc = subprocess.run(
        [sys.executable, "-m", "alpha_cli.main", *args, "--json"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode:
        raise ValueError("Context unavailable: " + (proc.stderr or proc.stdout)[-1000:])
    value: dict[str, Any] = json.loads(proc.stdout)
    if not isinstance(value, dict):
        raise ValueError("Context projection must be an object")
    return value


def assemble_context(context: AssistantContext, root: Path) -> list[dict[str, Any]]:
    from alpha_cli._runner import load_bars
    from alpha_data.store import ParquetStore

    sources: list[dict[str, Any]]
    if context.run_id:
        sources = _run_sources(context, root)
    else:
        provenance: dict[str, Any] | None
        if context.manifest_id:
            from alpha_cli._chart_data import load_chart_dataset
            from alpha_cli.crypto_data_cmds import _bulk_store

            bars, provenance = load_chart_dataset(
                _bulk_store(), context.manifest_id, symbol=context.symbol, as_of=context.as_of
            )
        else:
            bars, _ = load_bars(
                context.symbol, data_dir=root, snapshot_id=context.snapshot_id, as_of=context.as_of
            )
            store_root = (
                root / "snapshots" / context.snapshot_id if context.snapshot_id else root / "store"
            )
            provenance = ParquetStore(store_root).read_provenance(context.symbol)
        chart = {
            "symbol": context.symbol,
            "snapshot_id": context.snapshot_id,
            "manifest_id": context.manifest_id,
            "as_of": context.as_of.isoformat(),
            "provenance": provenance,
            "total_bars": len(bars),
            "attached_bars": min(120, len(bars)),
            "bars": [
                {
                    "t": b.ts.timestamp(),
                    "o": b.open,
                    "h": b.high,
                    "l": b.low,
                    "c": b.close,
                    "v": b.volume,
                }
                for b in bars[-120:]
            ],
        }
        label = (
            "Integrity-verified archive chart"
            if context.manifest_id
            else "Integrity-verified snapshot chart"
            if context.snapshot_id
            else "Stored chart"
        )
        sources = [{"ref": "chart", "label": label + " · last 120 bars maximum", "data": chart}]
    if context.project_id:
        sources.append(
            {
                "ref": "research:" + context.project_id,
                "label": "Research decision projection",
                "data": projection(["research", "decision-view", context.project_id], root),
            }
        )
    if context.rules_name:
        if context.snapshot_id or context.run_id:
            raise ValueError(
                "Rule explanations currently require canonical stored data without a run context"
            )
        if context.as_of.astimezone(UTC).time().replace(tzinfo=None) < time(23, 59, 59):
            raise ValueError("Rule explanations require an explicit UTC end-of-day cutoff")
        args = [
            "rules",
            "explain",
            context.rules_name,
            context.symbol,
            "--as-of",
            context.as_of.astimezone(UTC).date().isoformat(),
        ]
        explanation = projection(args, root)
        if (
            context.rules_sha256 is not None
            and explanation.get("rules_sha256") != context.rules_sha256
        ):
            raise ValueError(
                "Saved rules changed since the selected scan; rerun the scan or choose "
                "an intentional current-rule context."
            )
        sources.append(
            {
                "ref": "rules:" + context.rules_name,
                "label": "Rule conditions",
                "data": explanation,
            }
        )
    if len(json.dumps(sources).encode()) > 100_000:
        raise ValueError("Attached context exceeds 100 KB; choose a smaller context")
    return sources


def _run_sources(context: AssistantContext, root: Path) -> list[dict[str, Any]]:
    import polars as pl

    from alpha_cli._runner import load_bars

    assert context.run_id is not None
    directory = find_run_dir(root, context.run_id)
    if directory is None:
        raise ValueError("Unknown run")
    path = directory / "manifest.json"
    if path.stat().st_size > 1_000_000:
        raise ValueError("Run manifest exceeds assistant context limit")
    manifest = json.loads(path.read_text())
    if manifest.get("schema_version") != 3:
        raise ValueError("Legacy run cannot supply verified assistant evidence; choose a v3 run")
    verify_manifest_artifacts(directory, manifest)
    if manifest.get("symbol") != context.symbol:
        raise ValueError("Run symbol does not match the attached chart")
    snapshot = manifest.get("snapshot_id")
    if context.snapshot_id is not None and snapshot != context.snapshot_id:
        raise ValueError("Run snapshot does not match the attached chart")
    chart: dict[str, Any] = {
        "symbol": context.symbol,
        "snapshot_id": snapshot,
        "run_id": context.run_id,
        "bars": [],
        "as_of": None,
        "status": "unavailable",
        "reason": "Run has no recorded snapshot; current stored bars are not substituted.",
    }
    curve = directory / "equity_curve.parquet"
    if not curve.is_file():
        raise ValueError("Run cutoff is unavailable; cannot attach results to an exact context")
    end = pl.scan_parquet(curve).select(pl.col("ts").max()).collect().item()
    if not isinstance(end, datetime) or end.tzinfo is None:
        raise ValueError("Run cutoff is unavailable; cannot attach results to an exact context")
    if end > context.as_of:
        raise ValueError("Run results extend beyond the requested cutoff")
    chart["as_of"] = end.isoformat()
    if isinstance(snapshot, str):
        from alpha_cli._runner import verified_snapshot_hash

        if verified_snapshot_hash(root, snapshot) != manifest.get("snapshot_hash"):
            raise ValueError("Run snapshot identity changed")
        bars, _ = load_bars(context.symbol, data_dir=root, snapshot_id=snapshot, as_of=end)
        chart.update(
            status="available",
            reason=None,
            total_bars=len(bars),
            attached_bars=min(120, len(bars)),
            bars=[
                {
                    "t": bar.ts.timestamp(),
                    "o": bar.open,
                    "h": bar.high,
                    "l": bar.low,
                    "c": bar.close,
                    "v": bar.volume,
                }
                for bar in bars[-120:]
            ],
        )
    return [
        {
            "ref": "chart",
            "label": (
                "Run snapshot chart through " + end.isoformat() + " · last 120 bars maximum"
                if isinstance(snapshot, str)
                else "Run chart unavailable (no recorded snapshot)"
            ),
            "data": chart,
        },
        {"ref": "run:" + context.run_id, "label": "Verified run manifest", "data": manifest},
    ]
