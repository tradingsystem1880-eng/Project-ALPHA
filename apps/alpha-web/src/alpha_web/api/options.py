"""``/api/options/{greeks,iv,curve}`` — Black-Scholes analytics for the Options panel."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from alpha_web import _options
from alpha_web.api._common import data_dir

router = APIRouter(prefix="/api", tags=["options"])


@router.get("/options/greeks")
def options_greeks(
    spot: float,
    strike: float,
    vol: float,
    days: float = 30.0,
    rate: float = 0.05,
    kind: str = "call",
) -> dict[str, Any]:
    """Price + delta/gamma/vega/theta/rho for one European option."""
    try:
        return _options.greeks(
            data_dir=data_dir(), spot=spot, strike=strike, vol=vol, days=days, rate=rate, kind=kind
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/options/iv")
def options_iv(
    spot: float,
    strike: float,
    price: float,
    days: float = 30.0,
    rate: float = 0.05,
    kind: str = "call",
) -> dict[str, Any]:
    """The implied volatility that reprices the option to ``price`` (+ greeks at that vol)."""
    try:
        return _options.iv(
            data_dir=data_dir(),
            spot=spot,
            strike=strike,
            price=price,
            days=days,
            rate=rate,
            kind=kind,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/options/curve")
def options_curve(
    strike: float,
    vol: float,
    days: float = 30.0,
    rate: float = 0.05,
    kind: str = "call",
    width: float = 0.5,
    points: int = 41,
) -> dict[str, Any]:
    """Price + greeks across a spot range for the greeks-vs-spot chart."""
    try:
        return _options.curve(
            data_dir=data_dir(),
            strike=strike,
            vol=vol,
            days=days,
            rate=rate,
            kind=kind,
            width=width,
            points=points,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
