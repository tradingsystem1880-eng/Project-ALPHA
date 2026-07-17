"""``/api/research/compare`` — multi-strategy leaderboard for the AI Research panel."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from alpha_web import _research
from alpha_web.api._common import data_dir

router = APIRouter(prefix="/api", tags=["research"])


@router.get("/research/compare")
def research_compare(symbol: str, strategies: str = "") -> dict[str, Any]:
    """Backtest each strategy on ``symbol`` and rank by total return (slow — runs the engine)."""
    try:
        return _research.compare(data_dir=data_dir(), symbol=symbol, strategies=strategies)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
