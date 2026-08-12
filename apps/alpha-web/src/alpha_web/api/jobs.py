"""``/api/jobs`` — launch `alpha` runs, list/inspect them, stream output, cancel.

Each job is a subprocess (the engine never runs in-process). The registry is in-memory: live and
this-session-finished jobs are here for their streaming console, while the durable record of
completed work is the run store (served by ``/api/runs``). A restart loses the live job list and
orphans any running subprocess — an accepted tradeoff for a loopback single-user tool.
"""

from __future__ import annotations

import shlex
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from alpha_cli.catalog import classify_generic_command
from alpha_web import _invoke
from alpha_web.api._common import data_dir
from alpha_web.api.models import JobDetail, JobLaunchRequest, JobStatus, JobSummary
from alpha_web.run_authority import RunContextDenied, resolve_run_context

router = APIRouter(prefix="/api", tags=["jobs"])


@router.post("/jobs", response_model=JobStatus)
def launch_job(req: JobLaunchRequest) -> dict[str, Any]:
    """Launch a background CLI job after resolving its empirical run context."""
    argv = req.command.split() + shlex.split(req.args)
    if not argv:
        raise HTTPException(status_code=422, detail="empty command")
    command_class = classify_generic_command(argv)
    if command_class == "owner_only":
        raise HTTPException(
            status_code=422,
            detail=(
                "governed research commands are unavailable through the generic job API; "
                "use the bounded research API or trusted-local CLI"
            ),
        )
    if req.run_context is not None and command_class == "unknown":
        raise HTTPException(
            status_code=422,
            detail="unknown command cannot be launched in a governed or standalone run context",
        )
    if command_class == "empirical" and req.run_context is None:
        raise HTTPException(
            status_code=422,
            detail="empirical commands require an explicit governed-project or standalone context",
        )

    run_context: dict[str, object] | None = None
    if req.run_context is not None:
        try:
            run_context = resolve_run_context(
                kind=req.run_context.kind,
                project_id=(
                    req.run_context.project_id
                    if req.run_context.kind == "governed_project"
                    else None
                ),
                data_dir=data_dir(),
            )
        except RunContextDenied as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    run_type = _invoke.RUN_TYPE.get(req.command)
    try:
        job = _invoke.launch(
            argv,
            data_dir=data_dir(),
            run_type=run_type,
            run_context=run_context,
        )
    except RuntimeError as exc:
        if "heavyweight job capacity is occupied" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise
    return {"job_id": job.job_id, "status": job.status, "session_id": job.session_id}


@router.get("/jobs", response_model=list[JobSummary])
def list_jobs() -> list[dict[str, Any]]:
    """All known jobs (live + this-session-finished), newest first."""
    return _invoke.list_jobs()


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str) -> dict[str, Any]:
    """A single job's status + its buffered output lines (for a late-opening panel)."""
    job = _invoke.JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return {**job.summary(), "lines": job.tail(0)}


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str, request: Request) -> EventSourceResponse:
    """SSE of a job's output; a reconnect with ``Last-Event-ID`` replays only the missed lines."""
    job = _invoke.JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    last = request.headers.get("last-event-id")
    start = int(last) + 1 if last is not None and last.isdigit() else 0
    return EventSourceResponse(_invoke.event_stream(job, start))


@router.delete("/jobs/{job_id}", response_model=JobStatus)
def cancel_job(job_id: str) -> dict[str, Any]:
    """Cancel a running job (idempotent no-op if already finished)."""
    job = _invoke.cancel_job(job_id, data_dir=data_dir())
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return {"job_id": job_id, "status": job.status, "session_id": job.session_id}
