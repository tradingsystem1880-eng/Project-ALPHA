"""``/api/screener/{quote,news}`` — finnhub quotes & news (opt-in, key-gated)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from alpha_web import _screener
from alpha_web.api._common import data_dir
from alpha_web.api.models import ScreenerNews, ScreenerQuote

router = APIRouter(prefix="/api", tags=["screener"])


@router.get("/screener/quote", response_model=ScreenerQuote)
def screener_quote(symbol: str) -> dict[str, Any]:
    """A live quote for ``symbol`` (503 when the finnhub key/network is missing)."""
    try:
        return _screener.quote(data_dir=data_dir(), symbol=symbol)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/screener/news", response_model=ScreenerNews)
def screener_news(
    symbol: str,
    days: Annotated[int, Query(ge=1, le=365)] = 7,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """Recent company news for ``symbol`` (503 when unconfigured)."""
    try:
        return _screener.news(data_dir=data_dir(), symbol=symbol, days=days, limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
