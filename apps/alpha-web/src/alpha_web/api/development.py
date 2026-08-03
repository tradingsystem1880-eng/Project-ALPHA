"""Bounded REST projections/actions for the Workstation v3 development control plane."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from alpha_web import _development, _invoke
from alpha_web.api._common import data_dir
from alpha_web.api.models import (
    AgentBrief,
    AttemptCreateRequest,
    AttemptRecord,
    ControlJob,
    ControlJobCreateRequest,
    ControlJobDetail,
    ControlJobPage,
    DecisionPacket,
    DecisionRequest,
    DevelopmentStageValue,
    EvidenceDetail,
    EvidenceDraftRequest,
    EvidencePage,
    EvidenceRecord,
    EvidenceReviewRequest,
    EvidenceStatusValue,
    ExperimentCreateRequest,
    ExperimentSpec,
    ExperimentStageState,
    ExperimentStageTransitionRequest,
    HoldoutSealRequest,
    HoldoutState,
    JobReconcileResponse,
    ProjectCreateRequest,
    ProjectDetail,
    ProjectPage,
    ProjectSummary,
    StageLinkCreateRequest,
    StageRunLink,
    StageStateRequest,
    StrategyVersion,
    StrategyVersionCreateRequest,
    SuiteActionValue,
    SuiteCancelResponse,
    SuiteLaunch,
    SuitePlan,
    SuiteRunRequest,
)

router = APIRouter(prefix="/api", tags=["development"])


def _bad_request(exc: RuntimeError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/projects", response_model=ProjectPage)
def list_projects(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    """Newest projects first, with an explicit bounded continuation flag."""
    try:
        return _development.list_projects(data_dir=data_dir(), limit=limit, offset=offset)
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects", response_model=ProjectSummary)
def create_project(body: ProjectCreateRequest) -> dict[str, object]:
    """Create owner-facing hypothesis metadata; no strategy code executes here."""
    try:
        return _development.create_project(
            data_dir=data_dir(),
            name=body.name,
            hypothesis=body.hypothesis,
            falsification_criterion=body.falsification_criterion,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: str,
    lineage_limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, object]:
    """One project with each lineage collection and state history explicitly bounded."""
    try:
        return _development.project_detail(
            project_id, data_dir=data_dir(), lineage_limit=lineage_limit
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/versions/{version_id}", response_model=StrategyVersion)
def get_strategy_version(project_id: str, version_id: str) -> dict[str, object]:
    """Read one immutable version by its stable content identifier."""
    try:
        return _development.strategy_version(project_id, version_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/experiments/{experiment_id}", response_model=ExperimentSpec)
def get_experiment_spec(project_id: str, experiment_id: str) -> dict[str, object]:
    """Read one immutable experiment by its stable content identifier."""
    try:
        return _development.experiment_spec(project_id, experiment_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/experiments/{experiment_id}/suite/{action}/plan",
    response_model=SuitePlan,
)
def plan_suite_action(
    project_id: str,
    experiment_id: str,
    action: SuiteActionValue,
) -> dict[str, object]:
    """Preview exact immutable inputs, readiness, governance, and workload without launching."""
    try:
        return _development.suite_plan(
            project_id,
            experiment_id,
            action,
            data_dir=data_dir(),
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/projects/{project_id}/experiments/{experiment_id}/suite/{action}/run",
    response_model=SuiteLaunch,
)
def run_suite_action(
    project_id: str,
    experiment_id: str,
    action: SuiteActionValue,
    body: SuiteRunRequest,
) -> dict[str, object]:
    """Launch one pre-resolved action; only holdout reveal accepts owner confirmation fields."""
    if action == "holdout_reveal":
        if body.owner_actor is None or body.owner_reason is None:
            raise HTTPException(
                status_code=422,
                detail="holdout reveal requires an explicit owner_actor and owner_reason",
            )
    elif body.owner_actor is not None or body.owner_reason is not None:
        raise HTTPException(
            status_code=422,
            detail="owner confirmation fields apply only to holdout reveal",
        )
    try:
        plan = _development.suite_plan(
            project_id,
            experiment_id,
            action,
            data_dir=data_dir(),
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc
    if plan.get("ready") is not True:
        blockers = plan.get("blockers")
        raise HTTPException(
            status_code=409, detail={"message": "suite plan is blocked", "blockers": blockers}
        )
    job_id = str(uuid.uuid4())
    try:
        reservation = _development.reserve_suite(
            project_id,
            experiment_id,
            action,
            job_id,
            data_dir=data_dir(),
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc
    args = ["suite", "run", project_id, experiment_id, action, "--job-id", job_id, "--json"]
    if action == "holdout_reveal":
        args.extend(
            [
                "--owner-actor",
                str(body.owner_actor),
                "--owner-reason",
                str(body.owner_reason),
            ]
        )
    try:
        _invoke.launch(args, data_dir=data_dir(), run_type=None)
    except OSError as exc:
        failure = "allowlisted alpha suite worker could not be launched"
        try:
            _development.fail_job_launch(job_id, data_dir=data_dir(), error=failure)
        except RuntimeError as mark_exc:
            raise HTTPException(
                status_code=500,
                detail=f"{failure}; durable reservation also could not be failed",
            ) from mark_exc
        raise HTTPException(status_code=500, detail=failure) from exc
    reserved_plan = reservation.get("plan")
    if not isinstance(reserved_plan, dict):
        raise HTTPException(status_code=500, detail="suite reservation returned an invalid plan")
    return {"job_id": job_id, "status": "starting", "plan": reserved_plan}


@router.delete("/development/suite-jobs/{job_id}", response_model=SuiteCancelResponse)
def cancel_suite_action(job_id: str) -> dict[str, str]:
    """Persist a cancellation request for the owning suite worker, including after restart."""
    try:
        result = _development.cancel_suite_job(job_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"job_id": str(result["job_id"]), "status": str(result["status"])}


@router.post("/development/suite-jobs/reconcile", response_model=JobReconcileResponse)
def reconcile_suite_jobs(
    stale_after_seconds: Annotated[int, Query(ge=30, le=86_400)] = 60,
) -> dict[str, object]:
    """Explicitly fail only journals whose worker heartbeat has exceeded the stale cutoff."""
    try:
        return _development.reconcile_jobs(
            data_dir=data_dir(), stale_after_seconds=stale_after_seconds
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.get("/development/suite-jobs/{job_id}", response_model=ControlJobDetail)
def get_suite_action_status(
    job_id: str,
    event_limit: Annotated[int, Query(ge=1, le=200)] = 100,
    event_offset: Annotated[int, Query(ge=0)] = 0,
    event_tail: bool = False,
) -> dict[str, object]:
    """Read the bounded durable journal for a suite job, including after a web restart."""
    try:
        return _development.job_detail(
            job_id,
            data_dir=data_dir(),
            event_limit=event_limit,
            event_offset=event_offset,
            event_tail=event_tail,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/versions", response_model=StrategyVersion)
def create_version(project_id: str, body: StrategyVersionCreateRequest) -> dict[str, object]:
    """Create/reuse an immutable content-addressed strategy version through the CLI."""
    try:
        return _development.create_version(
            project_id,
            data_dir=data_dir(),
            strategy_name=body.strategy_name,
            source_fingerprint=body.source_fingerprint,
            definition=body.definition,
            parameter_space=body.parameter_space,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects/{project_id}/experiments", response_model=ExperimentSpec)
def create_experiment(project_id: str, body: ExperimentCreateRequest) -> dict[str, object]:
    """Create/reuse an immutable experiment specification through the CLI."""
    try:
        return _development.create_experiment(
            project_id,
            data_dir=data_dir(),
            version_id=body.version_id,
            snapshot_id=body.snapshot_id,
            universe=body.universe,
            split_policy=body.split_policy,
            costs=body.costs,
            seeds=body.seeds,
            stage_config=body.stage_config,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects/{project_id}/stage-links", response_model=StageRunLink)
def link_stage_run(project_id: str, body: StageLinkCreateRequest) -> dict[str, object]:
    """Cite one already-completed canonical run at a declared lifecycle stage."""
    try:
        return _development.link_stage_run(
            project_id,
            data_dir=data_dir(),
            experiment_id=body.experiment_id,
            stage=body.stage,
            state=body.state,
            run_id=body.run_id,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post("/stage-links/{link_id}/state", response_model=StageRunLink)
def update_stage_state(link_id: str, body: StageStateRequest) -> dict[str, object]:
    """Append one legal state transition; prior states remain immutable."""
    try:
        return _development.update_stage_state(
            link_id,
            data_dir=data_dir(),
            state=body.state,
            reason=body.reason,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/projects/{project_id}/experiments/{experiment_id}/stages/{stage}/state",
    response_model=ExperimentStageState,
)
def update_experiment_stage_state(
    project_id: str,
    experiment_id: str,
    stage: DevelopmentStageValue,
    body: ExperimentStageTransitionRequest,
) -> dict[str, object]:
    """Append one legal experiment lifecycle transition before a run link exists."""
    try:
        return _development.update_experiment_stage_state(
            project_id,
            experiment_id,
            stage,
            data_dir=data_dir(),
            state=body.state,
            reason=body.reason,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects/{project_id}/attempts", response_model=AttemptRecord)
def record_attempt(project_id: str, body: AttemptCreateRequest) -> dict[str, object]:
    """Record every attempted, failed, pruned, or rejected configuration."""
    try:
        return _development.record_attempt(
            project_id,
            data_dir=data_dir(),
            experiment_id=body.experiment_id,
            stage=body.stage,
            status=body.status,
            config_fingerprint=body.config_fingerprint,
            run_id=body.run_id,
            error=body.error,
            details=body.details,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects/{project_id}/holdouts/seal", response_model=HoldoutState)
def seal_holdout(project_id: str, body: HoldoutSealRequest) -> dict[str, object]:
    """Seal a final holdout before selection; no endpoint reveals the holdout."""
    try:
        return _development.seal_holdout(
            project_id,
            data_dir=data_dir(),
            experiment_id=body.experiment_id,
            actor=body.actor,
            reason=body.reason,
            start_date=body.start_date,
            end_date=body.end_date,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/projects/{project_id}/experiments/{experiment_id}/decision",
    response_model=DecisionPacket,
)
def freeze_decision_packet(
    project_id: str,
    experiment_id: str,
    body: DecisionRequest,
) -> dict[str, object]:
    """Freeze an explicit owner decision; acceptance remains sandbox-only."""
    try:
        return _development.freeze_decision(
            project_id,
            experiment_id,
            body.model_dump(),
            data_dir=data_dir(),
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.get("/projects/{project_id}/agent-brief", response_model=AgentBrief)
def get_agent_brief(
    project_id: str,
    evidence_limit: Annotated[int, Query(ge=1, le=100)] = 50,
    as_of: str | None = None,
) -> dict[str, object]:
    """Typed, point-in-time, cited agent context with no privileged actions or raw paths."""
    try:
        return _development.agent_brief(
            project_id,
            data_dir=data_dir(),
            evidence_limit=evidence_limit,
            as_of=as_of,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/development/jobs", response_model=ControlJobPage)
def list_development_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    """Durable control-plane job journals; distinct from live subprocess `/api/jobs`."""
    try:
        return _development.list_jobs(data_dir=data_dir(), limit=limit, offset=offset)
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post("/development/jobs", response_model=ControlJob)
def create_development_job(body: ControlJobCreateRequest) -> dict[str, object]:
    """Queue a durable journal entry; execution requires a separately resolved stage runner."""
    try:
        return _development.create_job(
            data_dir=data_dir(),
            kind=body.kind,
            request=body.request,
            project_id=body.project_id,
            experiment_id=body.experiment_id,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.get("/development/jobs/{job_id}", response_model=ControlJobDetail)
def get_development_job(
    job_id: str,
    event_limit: Annotated[int, Query(ge=1, le=200)] = 100,
    event_offset: Annotated[int, Query(ge=0)] = 0,
    event_tail: bool = False,
) -> dict[str, object]:
    """One durable job plus a bounded slice of its append-only events."""
    try:
        return _development.job_detail(
            job_id,
            data_dir=data_dir(),
            event_limit=event_limit,
            event_offset=event_offset,
            event_tail=event_tail,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/development/jobs/{job_id}", response_model=SuiteCancelResponse)
def cancel_development_job(job_id: str) -> dict[str, str]:
    """Request audited cancellation for any live CLI-owned durable job."""
    try:
        result = _development.cancel_job(job_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"job_id": str(result["job_id"]), "status": str(result["status"])}


@router.get("/evidence", response_model=EvidencePage)
def search_evidence(
    asset: str | None = None,
    project_id: str | None = None,
    status: EvidenceStatusValue | None = None,
    as_of: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    """Point-in-time latest revisions, bounded and filterable by asset/project/status."""
    try:
        return _development.list_evidence(
            data_dir=data_dir(),
            asset=asset,
            project_id=project_id,
            status=status,
            as_of=as_of,
            limit=limit,
            offset=offset,
        )
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.post("/evidence/draft", response_model=EvidenceRecord)
def draft_evidence(body: EvidenceDraftRequest) -> dict[str, object]:
    """Create revision one; the CLI always assigns draft status, including for agents."""
    try:
        return _development.draft_evidence(body.model_dump(), data_dir=data_dir())
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetail)
def get_evidence(
    evidence_id: str,
    revision_limit: Annotated[int, Query(ge=1, le=200)] = 100,
    revision_offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    """Current evidence plus a bounded immutable revision-history slice."""
    try:
        return _development.evidence_detail(
            evidence_id,
            data_dir=data_dir(),
            revision_limit=revision_limit,
            revision_offset=revision_offset,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evidence/{evidence_id}/review", response_model=EvidenceRecord)
def review_evidence(evidence_id: str, body: EvidenceReviewRequest) -> dict[str, object]:
    """Append a cited review revision; prior revisions are never mutated."""
    try:
        return _development.review_evidence(evidence_id, body.model_dump(), data_dir=data_dir())
    except RuntimeError as exc:
        raise _bad_request(exc) from exc


__all__ = ["router"]
