"""``/api/risk/scenario`` — stress a stored run's return stream for the Risk panel."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from alpha_web import _risk
from alpha_web.api._common import data_dir

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk/scenario")
def risk_scenario(run_id: str, confidence: float = 0.95) -> dict[str, Any]:
    """Vol-scaling + tail-shock scenarios for a run (422 if it has no equity curve)."""
    try:
        return _risk.scenario(data_dir=data_dir(), run_id=run_id, confidence=confidence)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
