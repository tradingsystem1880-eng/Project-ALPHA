"""Read-only paper-session monitoring over the public CLI journal seam."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from alpha_cli import paper_store
from alpha_web.api._common import data_dir
from alpha_web.api.models import PaperEvent, PaperSession

router = APIRouter(prefix="/api/paper", tags=["paper"])


def _validate_session_id(session_id: str) -> None:
    if not paper_store.valid_session_id(session_id):
        raise HTTPException(status_code=422, detail=f"invalid paper session id {session_id!r}")


@router.get("/sessions", response_model=list[PaperSession])
def list_paper_sessions() -> list[dict[str, object]]:
    """Every complete paper session, newest first, with computed heartbeat staleness."""
    return paper_store.list_sessions(data_dir())


@router.get("/sessions/{session_id}", response_model=PaperSession)
def get_paper_session(session_id: str) -> dict[str, object]:
    """One validated paper session. Reading a stale session never signals its recorded PID."""
    _validate_session_id(session_id)
    try:
        return paper_store.read_session(data_dir(), session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/events", response_model=list[PaperEvent])
def get_paper_events(
    session_id: str, after: Annotated[int, Query(ge=0)] = 0
) -> list[dict[str, object]]:
    """Validated operational events whose sequence is strictly greater than ``after``."""
    _validate_session_id(session_id)
    try:
        return paper_store.read_events(data_dir(), session_id, after=after)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
