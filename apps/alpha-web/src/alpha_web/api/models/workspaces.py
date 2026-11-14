"""Workspace documents and linked contexts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ._base import StrictModel


class WorkspaceMeta(StrictModel):
    slug: str
    name: str
    updated: float | None


class WorkspaceSaved(StrictModel):
    slug: str
    name: str


class WorkspaceGroupLinkedContext(StrictModel):
    projectId: str | None = None
    versionId: str | None = None
    symbol: str | None = None
    universe: str | None = None
    timeframe: Literal["1D"] = "1D"
    start: str | None = None
    end: str | None = None
    snapshotId: str | None = None
    runId: str | None = None


class WorkspaceLinkedContext(WorkspaceGroupLinkedContext):
    schemaVersion: Literal[3] = 3
    linkGroup: Literal["A", "B", "C", "D"] = "A"
    groups: dict[Literal["A", "B", "C", "D"], WorkspaceGroupLinkedContext] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class WorkspaceDocument(StrictModel):
    name: str
    linked_context: WorkspaceLinkedContext
    #: Retired. A workspace used to be a window arrangement; it is now the research
    #: context you were working in. Documents saved by the old shell still carry a
    #: layout blob, so the field is read and ignored rather than rejected.
    dockview: dict[str, Any] | None = None
    updated: float | None = None


class Deleted(StrictModel):
    deleted: str
