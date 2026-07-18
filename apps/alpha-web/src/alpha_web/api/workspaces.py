"""``/api/workspaces`` — save / list / load / delete named Dockview layouts."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from alpha_core import DataError
from alpha_web import _workspaces
from alpha_web.api._common import data_dir
from alpha_web.api.models import (
    Deleted,
    WorkspaceDocument,
    WorkspaceLinkedContext,
    WorkspaceMeta,
    WorkspaceSaved,
)

router = APIRouter(prefix="/api", tags=["workspaces"])


class WorkspaceBody(BaseModel):
    """A workspace to save: a display name, the linked context, and the Dockview layout."""

    name: str
    linked_context: WorkspaceLinkedContext = WorkspaceLinkedContext()
    dockview: dict[str, Any]


@router.get("/workspaces", response_model=list[WorkspaceMeta])
def list_workspaces() -> list[dict[str, Any]]:
    """Every saved workspace (``{slug, name, updated}``)."""
    return _workspaces.list_workspaces(data_dir=data_dir())


@router.post("/workspaces", response_model=WorkspaceSaved)
def save_workspace(body: WorkspaceBody) -> dict[str, Any]:
    """Save (upsert) a workspace under a slug derived from its name."""
    try:
        slug = _workspaces.slugify(body.name)
    except DataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    doc = {
        "name": body.name,
        "linked_context": body.linked_context.model_dump(),
        "dockview": body.dockview,
        "updated": time.time(),  # UI state, not a run manifest — a wall-clock stamp is fine
    }
    return _workspaces.save_workspace(slug, doc, data_dir=data_dir())


@router.get("/workspaces/{slug}", response_model=WorkspaceDocument)
def get_workspace(slug: str) -> dict[str, Any]:
    """The full workspace document to restore."""
    try:
        return _workspaces.get_workspace(slug, data_dir=data_dir())
    except DataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/workspaces/{slug}", response_model=Deleted)
def delete_workspace(slug: str) -> dict[str, str]:
    """Delete a workspace (idempotent)."""
    try:
        _workspaces.delete_workspace(slug, data_dir=data_dir())
    except DataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"deleted": slug}
