"""Typed local investigation endpoints; CLI owns all persisted research state."""

import json
import threading
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from alpha_cli.investigation_workspace_contracts import (
    ComparisonAcquireRequest,
    ComparisonDraft,
    ComparisonDraftRequest,
    InvestigationCreate,
    InvestigationEligibility,
    InvestigationTurnRequest,
    InvestigationView,
)
from alpha_web import _investigations, _invoke
from alpha_web.api._common import data_dir
from alpha_web.api.models import JobStatus

_launch_lock = threading.Lock()

router = APIRouter(prefix="/api/investigations", tags=["investigations"])
Identifier = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]


def same_origin(request: Request) -> None:
    origin = urlsplit(request.headers.get("origin", ""))
    if (
        request.url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or origin.scheme != request.url.scheme
        or origin.netloc != request.url.netloc
        or origin.path
        or origin.query
        or origin.fragment
        or request.headers.get("sec-fetch-site") not in {None, "same-origin"}
    ):
        raise HTTPException(403, "Investigation changes require the local same-origin workstation")


def project(args: list[str]) -> Any:
    try:
        return _investigations.project(args, data_dir=data_dir())
    except (RuntimeError, ValueError, OSError) as exc:
        raise HTTPException(422, "Investigation request could not be verified") from exc


def active(identifier: str) -> str | None:
    return next(
        (
            job.job_id
            for job in _invoke.JOBS.values()
            if job.args[:2] == ["research", "investigations"]
            and job.args[2:3] in (["run"], ["acquire"])
            and job.args[3:4] == [identifier]
            and job.status == "running"
        ),
        None,
    )


@router.get("", response_model=list[InvestigationView])
def listing(run_id: Annotated[str, Query(pattern=r"^[0-9a-f]{16}$")]) -> Any:
    rows = project(["list", "--run-id", run_id])
    for row in rows:
        row["active_job_id"] = active(row["id"])
    return rows


@router.get("/eligibility/{run_id}", response_model=InvestigationEligibility)
def eligibility(run_id: Annotated[str, Path(pattern=r"^[0-9a-f]{16}$")]) -> Any:
    return project(["eligibility", run_id])


@router.post("", response_model=InvestigationView, dependencies=[Depends(same_origin)])
def create(body: InvestigationCreate) -> Any:
    return project(["create", "--request", body.model_dump_json()])


@router.get("/{identifier}", response_model=InvestigationView)
def show(identifier: Identifier) -> Any:
    value = project(["show", identifier])
    value["active_job_id"] = active(identifier)
    return value


def launch(identifier: str, operation: str, body: dict[str, Any]) -> dict[str, Any]:
    show(identifier)
    with _launch_lock:
        if any(
            job.args[:2] == ["research", "investigations"] and job.status == "running"
            for job in _invoke.JOBS.values()
        ):
            raise HTTPException(409, "An investigation operation is already running")
        job = _invoke.launch(
            ["research", "investigations", operation, identifier, "--request", json.dumps(body)],
            data_dir=data_dir(),
            run_type=None,
        )
    return {"job_id": job.job_id, "status": job.status, "session_id": job.session_id}


@router.post("/{identifier}/turns", response_model=JobStatus, dependencies=[Depends(same_origin)])
def turn(identifier: Identifier, body: InvestigationTurnRequest) -> dict[str, Any]:
    return launch(identifier, "run", body.model_dump())


@router.post(
    "/{identifier}/comparison-plan",
    response_model=ComparisonDraft,
    dependencies=[Depends(same_origin)],
)
def draft(identifier: Identifier, body: ComparisonDraftRequest) -> Any:
    return project(["draft", identifier, "--request", body.model_dump_json()])


@router.post(
    "/{identifier}/comparisons", response_model=JobStatus, dependencies=[Depends(same_origin)]
)
def acquire(identifier: Identifier, body: ComparisonAcquireRequest) -> dict[str, Any]:
    return launch(identifier, "acquire", body.model_dump())
