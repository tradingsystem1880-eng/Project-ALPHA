"""One fail-closed resolver for empirical Workstation launch context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from alpha_web import _development

type RequestedRunContextKind = Literal["governed_project", "standalone_sandbox"]


@dataclass(frozen=True, slots=True)
class RunContextDenied(Exception):
    status_code: int
    detail: str


def resolve_run_context(
    *,
    kind: RequestedRunContextKind,
    project_id: str | None,
    data_dir: Path,
) -> dict[str, object]:
    """Resolve a caller request to the canonical context inherited by an empirical child."""
    if kind == "standalone_sandbox":
        if project_id is not None:
            raise RunContextDenied(422, "standalone run context cannot name a project")
        return {
            "schema_version": 1,
            "kind": "standalone_sandbox",
            "watermark": "STANDALONE_UNQUALIFIED",
        }
    if not project_id:
        raise RunContextDenied(422, "governed-project run context requires a project ID")
    try:
        project = _development.project_detail(project_id, data_dir=data_dir, lineage_limit=1)
    except (RuntimeError, ValueError, OSError) as exc:
        raise RunContextDenied(
            409,
            "project research gate could not be verified; no job was launched",
        ) from exc
    gate_state = project.get("research_gate_state")
    if gate_state == "open":
        raise RunContextDenied(
            409,
            "project research gate is open; no empirical job was launched",
        )
    if gate_state not in {"passed", "not_required", "overridden"}:
        raise RunContextDenied(
            409,
            "project research gate returned an unknown state; no job was launched",
        )
    context: dict[str, object] = {
        "schema_version": 1,
        "kind": "governed_project",
        "project_id": project_id,
        "research_gate_state": gate_state,
    }
    if gate_state == "overridden":
        context["watermark"] = "EXPLORATORY"
    return context
