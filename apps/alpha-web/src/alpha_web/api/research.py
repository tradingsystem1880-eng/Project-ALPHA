"""Bounded REST projections for comparison and the governed Research Case workflow."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query

from alpha_web import _research
from alpha_web.api._common import data_dir
from alpha_web.api.models import (
    ResearchCaptureRequest,
    ResearchCaptureResponse,
    ResearchCase,
    ResearchCasePage,
    ResearchCaseReport,
    ResearchContextPacket,
    ResearchContextPacketPage,
    ResearchDatasetPage,
    ResearchDecisionView,
    ResearchEvidenceHub,
    ResearchLaunchRequest,
    ResearchLaunchResponse,
    ResearchNotePage,
    ResearchProposalOptionsV1,
    ResearchProposalRequest,
    ResearchProposalResponse,
    ResearchProtocolLibrary,
    ResearchReport,
    ResearchScorecard,
)
from alpha_web.run_authority import RunContextDenied, resolve_run_context

router = APIRouter(prefix="/api", tags=["research"])


@router.get("/research/compare", response_model=ResearchReport)
def research_compare(
    symbol: str,
    strategies: str = "",
    context_kind: Literal["governed_project", "standalone_sandbox"] | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Backtest each strategy on ``symbol`` and rank by total return (slow — runs the engine)."""
    if context_kind is None:
        raise HTTPException(status_code=422, detail="research comparison requires a run context")
    try:
        run_context = resolve_run_context(
            kind=context_kind,
            project_id=project_id,
            data_dir=data_dir(),
        )
        return _research.compare(
            data_dir=data_dir(),
            symbol=symbol,
            strategies=strategies,
            run_context=run_context,
        )
    except RunContextDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/research/cases", response_model=ResearchCaptureResponse)
def research_capture(body: ResearchCaptureRequest) -> dict[str, Any]:
    """Capture exact idea wording and bounded triage; never approve or launch work."""
    try:
        return _research.capture(data_dir=data_dir(), idea=body.idea, name=body.name)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/research/cases", response_model=ResearchCasePage)
def research_cases(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Read the bounded backlog page, newest research activity first (ADR-0021)."""
    try:
        return _research.list_cases(data_dir=data_dir(), limit=limit, offset=offset)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/research/cases/{project_id}/evidence-hub",
    response_model=ResearchEvidenceHub,
)
def research_evidence_hub(project_id: str) -> dict[str, Any]:
    """Read the eleven-section Evidence Hub projection for one case."""
    try:
        return _research.evidence_hub(project_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/research/cases/{project_id}/scorecard",
    response_model=ResearchScorecard,
)
def research_scorecard(project_id: str) -> dict[str, Any]:
    """Read the readiness scorecard: enumerated states, never a numeric aggregate."""
    try:
        return _research.scorecard(project_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/research/cases/{project_id}/decision-view",
    response_model=ResearchDecisionView,
)
def research_decision_view(project_id: str) -> dict[str, Any]:
    """Read the owner decision view: checklist, full scorecard, packet, and history."""
    try:
        return _research.decision_view(project_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/research/cases/{project_id}/context-packets",
    response_model=ResearchContextPacketPage,
)
def research_context_packets(
    project_id: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Read this case's recorded Codex context packets — every byte Codex saw."""
    try:
        return _research.context_packets(
            project_id, data_dir=data_dir(), limit=limit, offset=offset
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/research/context-packets/{packet_id}",
    response_model=ResearchContextPacket,
)
def research_context_packet(packet_id: str) -> dict[str, Any]:
    """Return one recorded packet byte-identically."""
    try:
        return _research.context_packet(packet_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/research/cases/{project_id}/notes", response_model=ResearchNotePage)
def research_notes(
    project_id: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Read the commentary stream — badged as Codex commentary, never evidence."""
    try:
        return _research.notes(project_id, data_dir=data_dir(), limit=limit, offset=offset)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/research/datasets", response_model=ResearchDatasetPage)
def research_datasets(
    symbol: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Read registered research-only dataset refs with their latest audits."""
    try:
        return _research.datasets(data_dir=data_dir(), symbol=symbol, limit=limit, offset=offset)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/research/protocols", response_model=ResearchProtocolLibrary)
def research_protocols() -> dict[str, Any]:
    """Read the Git-owned protocol library index."""
    try:
        return _research.protocols(data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/research/cases/{project_id}", response_model=ResearchCase)
def research_get(project_id: str) -> dict[str, Any]:
    """Read one complete bounded Research Case summary."""
    try:
        return _research.get(project_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/research/cases/{project_id}/proposal-options",
    response_model=ResearchProposalOptionsV1,
)
def research_proposal_options(project_id: str) -> dict[str, Any]:
    """Read executable answer bundles and current pack/data prerequisites."""

    try:
        return _research.proposal_options(project_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/research/cases/{project_id}/proposal",
    response_model=ResearchProposalResponse,
)
def research_propose(project_id: str, body: ResearchProposalRequest) -> dict[str, Any]:
    """Create an owner-reviewable contract; owner approval has no REST route."""
    try:
        return _research.propose(
            project_id,
            data_dir=data_dir(),
            source_pack_id=body.source_pack_id,
            answer_bundle_id=body.answer_bundle_id,
            dataset_ref_id=body.dataset_ref_id,
            expected_case_revision=body.expected_case_revision,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/research/cases/{project_id}/launch",
    response_model=ResearchLaunchResponse,
)
def research_launch(project_id: str, body: ResearchLaunchRequest) -> dict[str, Any]:
    """Run the deterministic D0 pilot after approval performed outside REST."""
    try:
        return _research.launch(
            project_id,
            data_dir=data_dir(),
            stage=body.stage,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/research/cases/{project_id}/status", response_model=ResearchCase)
def research_status(project_id: str) -> dict[str, Any]:
    """Read current phase, execution state, next action, budget, and firewall state."""
    try:
        return _research.status(project_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/research/cases/{project_id}/report",
    response_model=ResearchCaseReport,
)
def research_report(project_id: str) -> dict[str, Any]:
    """Read a progress report or the deterministic packet for an already-closed case."""
    try:
        return _research.report(project_id, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
