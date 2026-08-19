"""Lightweight public run-store discovery seam for MCP and web surfaces."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from alpha_core import DataError

RUN_DIRS = ("runs", "portfolio", "cross_sectional", "optim", "propfirm", "forecast")
_RUN_ID_RE = re.compile(r"[0-9a-f]{16}")

# spec §15 / ADR-0026: the permanent marker on any run launched under an owner
# research-gate override. Polars-free here so the suite planner and web/MCP readers
# share one source of truth without importing the artifact layer.
RESEARCH_GATE_OVERRIDE_WATERMARK = "EXPLORATORY / RESEARCH GATE NOT COMPLETED"
STANDALONE_UNQUALIFIED_WATERMARK = "STANDALONE_UNQUALIFIED"
LEGACY_CONTEXT_UNKNOWN_WATERMARK = "LEGACY_CONTEXT_UNKNOWN"


def research_gate_watermark(manifest: Any) -> str | None:
    """The EXPLORATORY watermark recorded on a run launched under an overridden gate, if any."""
    if not isinstance(manifest, dict):
        return None
    block = manifest.get("research_gate")
    if isinstance(block, dict) and isinstance(block.get("watermark"), str):
        return str(block["watermark"])
    return None


def run_context_projection(manifest: Any) -> dict[str, str | None]:
    """Project the permanent launch classification for current and historical run manifests."""
    if not isinstance(manifest, dict):
        return {
            "run_context_kind": "legacy_context_unknown",
            "run_context_project_id": None,
            "run_context_watermark": LEGACY_CONTEXT_UNKNOWN_WATERMARK,
        }
    context = manifest.get("run_context")
    if not isinstance(context, dict):
        return {
            "run_context_kind": "legacy_context_unknown",
            "run_context_project_id": None,
            "run_context_watermark": LEGACY_CONTEXT_UNKNOWN_WATERMARK,
        }
    if context.get("kind") == "standalone_sandbox":
        return {
            "run_context_kind": "standalone_sandbox",
            "run_context_project_id": None,
            "run_context_watermark": STANDALONE_UNQUALIFIED_WATERMARK,
        }
    if context.get("kind") == "governed_project" and isinstance(context.get("project_id"), str):
        return {
            "run_context_kind": "governed_project",
            "run_context_project_id": str(context["project_id"]),
            "run_context_watermark": (
                RESEARCH_GATE_OVERRIDE_WATERMARK
                if context.get("research_gate_state") == "overridden"
                else None
            ),
        }
    return {
        "run_context_kind": "legacy_context_unknown",
        "run_context_project_id": None,
        "run_context_watermark": LEGACY_CONTEXT_UNKNOWN_WATERMARK,
    }


def valid_run_id(run_id: str) -> bool:
    return _RUN_ID_RE.fullmatch(run_id) is not None


def find_run_dir(data_dir: Path, run_id: str) -> Path | None:
    if not valid_run_id(run_id):
        return None
    for subdir in RUN_DIRS:
        candidate = data_dir / subdir / run_id
        if (candidate / "manifest.json").is_file():
            return candidate
    return None


def read_manifest(rdir: Path) -> dict[str, Any]:
    path = rdir / "manifest.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise DataError(f"corrupt run manifest at {path}") from exc
    if not isinstance(raw, dict):
        raise DataError(f"invalid run manifest at {path}: expected a JSON object")
    result: dict[str, Any] = raw
    return result
