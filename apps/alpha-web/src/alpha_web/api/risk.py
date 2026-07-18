"""``/api/risk/scenario`` — stress a stored run's return stream for the Risk panel."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from alpha_cli.run_store import find_run_dir
from alpha_web import _risk
from alpha_web.api._common import data_dir
from alpha_web.api.models import RiskReport

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk/scenario", response_model=RiskReport)
def risk_scenario(
    run_id: str, confidence: Annotated[float, Query(gt=0.5, lt=1.0)] = 0.95
) -> dict[str, Any]:
    """Vol-scaling + tail-shock scenarios for a run (422 if it has no equity curve)."""
    if find_run_dir(data_dir(), run_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown run {run_id!r}")
    try:
        return _risk.scenario(data_dir=data_dir(), run_id=run_id, confidence=confidence)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
