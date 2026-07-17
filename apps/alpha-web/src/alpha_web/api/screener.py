"""``/api/screener/{quote,news}`` — finnhub quotes & news (opt-in, key-gated)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from alpha_web import _screener
from alpha_web.api._common import data_dir

router = APIRouter(prefix="/api", tags=["screener"])


@router.get("/screener/quote")
def screener_quote(symbol: str) -> dict[str, Any]:
    """A live quote for ``symbol`` (503 when the finnhub key/network is missing)."""
    try:
        return _screener.quote(data_dir=data_dir(), symbol=symbol)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/screener/news")
def screener_news(symbol: str, days: int = 7, limit: int = 20) -> dict[str, Any]:
    """Recent company news for ``symbol`` (503 when unconfigured)."""
    try:
        return _screener.news(data_dir=data_dir(), symbol=symbol, days=days, limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
