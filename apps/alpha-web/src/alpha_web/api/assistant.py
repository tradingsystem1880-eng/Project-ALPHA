"""Local advisory assistant; actions are subprocess CLI jobs, never engine calls."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from alpha_cli.assistant_contracts import (
    AssistantContextCheck,
    AssistantReadiness,
    AssistantSession,
    AssistantSessionRequest,
    AssistantTurnRequest,
)
from alpha_web import _assistant, _invoke
from alpha_web.api._common import data_dir
from alpha_web.api.models import JobStatus
from alpha_web.api.owner_auth import _require_owner_origin

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/readiness", response_model=AssistantReadiness)
def readiness() -> dict[str, Any]:
    return _assistant.readiness(data_dir=data_dir())


@router.post(
    "/sessions", response_model=AssistantSession, dependencies=[Depends(_require_owner_origin)]
)
def create(body: AssistantSessionRequest) -> dict[str, Any]:
    try:
        return _assistant.create(body.context.model_dump(mode="json"), data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sessions/{session_id}", response_model=AssistantSession)
def show(session_id: str) -> dict[str, Any]:
    try:
        body = _assistant.show(session_id, data_dir=data_dir())
        body["active_job_id"] = next(
            (
                job.job_id
                for job in _invoke.JOBS.values()
                if job.args[:3] == ["assistant", "turn", session_id] and job.status == "running"
            ),
            None,
        )
        return body
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/turns",
    response_model=JobStatus,
    dependencies=[Depends(_require_owner_origin)],
)
def turn(session_id: str, body: AssistantTurnRequest) -> dict[str, Any]:
    show(session_id)
    if any(
        job.args[:2] == ["assistant", "turn"] and job.status == "running"
        for job in _invoke.JOBS.values()
    ):
        raise HTTPException(status_code=409, detail="An assistant turn is already active.")
    job = _invoke.launch(
        ["assistant", "turn", session_id, "--request", json.dumps(body.model_dump()), "--json"],
        data_dir=data_dir(),
        run_type=None,
    )
    return {"job_id": job.job_id, "status": job.status, "session_id": job.session_id}


@router.post(
    "/sessions/{session_id}/check",
    response_model=AssistantContextCheck,
    dependencies=[Depends(_require_owner_origin)],
)
def check(session_id: str) -> dict[str, Any]:
    try:
        return _assistant.check(session_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
