"""``/api/{strategies,commands,symbols}`` — the CLI's catalogs, for the workstation's forms."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from alpha_web import _catalog, _invoke
from alpha_web.api._common import data_dir
from alpha_web.api.models import CommandDefinition, FirstBar, StrategyDefinition, Symbols, Ticker

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/strategies", response_model=list[StrategyDefinition])
def strategies() -> list[dict[str, object]]:
    """Registered strategies + their tunable ``--param`` axes."""
    return _catalog.strategies(data_dir=data_dir())


@router.get("/commands", response_model=list[CommandDefinition])
def commands() -> list[dict[str, object]]:
    """The CLI command tree, each annotated with the run-type dir it writes (``None`` = no run)."""
    return [
        {**cmd, "run_type": _invoke.RUN_TYPE.get(cmd["id"])}
        for cmd in _catalog.commands(data_dir=data_dir())
    ]


@router.get("/symbols", response_model=Symbols)
def symbols() -> dict[str, list[str]]:
    """Every symbol with stored bars."""
    return _catalog.symbols(data_dir=data_dir())


@router.get("/data/first-bar", response_model=FirstBar)
def first_bar(
    symbol: Annotated[str, Query(min_length=1)], exchange: Annotated[str, Query(min_length=1)]
) -> dict[str, str]:
    """The venue's earliest daily bar for ``symbol`` (relays ``alpha data first-bar --json``)."""
    try:
        return _catalog.first_bar(data_dir=data_dir(), symbol=symbol, exchange=exchange)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/data/ticker", response_model=Ticker)
def ticker(
    symbol: Annotated[str, Query(min_length=1)], exchange: Annotated[str, Query(min_length=1)]
) -> dict[str, object]:
    """SYMBOL's current last-trade price on EXCHANGE (relays ``alpha data ticker --json``).

    A displayed quote for Market Watch only: the web never stores it and it is never a
    point-in-time series or research evidence.
    """
    try:
        return _catalog.ticker(data_dir=data_dir(), symbol=symbol, exchange=exchange)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
