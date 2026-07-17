"""``/api/candles/{symbol}`` — PIT-adjusted OHLCV for the price chart."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from alpha_web import _candles
from alpha_web.api._common import data_dir

router = APIRouter(prefix="/api", tags=["candles"])


@router.get("/candles/{symbol:path}")
def candles(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    snapshot: str | None = None,
) -> dict[str, Any]:
    """Point-in-time candles for ``symbol`` (``{symbol:path}`` so ``BTC/USD`` works)."""
    try:
        return _candles.candles(
            symbol, data_dir=data_dir(), start=start, end=end, snapshot=snapshot
        )
    except RuntimeError as exc:  # CLI failed (unknown symbol / empty window) — surface as 404
        raise HTTPException(status_code=404, detail=str(exc)) from exc
