"""``/api/runs`` — the run store as JSON (index, detail, equity, trades, forecast)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from alpha_web import _runs
from alpha_web.api._common import data_dir

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs")
def list_runs(
    kind: str | None = None,
    symbol: str | None = None,
    verdict: str | None = None,
    passed: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Filtered, newest-first, paginated run index for the run browser."""
    return _runs.query_runs(
        data_dir=data_dir(),
        kind=kind,
        symbol=symbol,
        verdict=verdict,
        passed=passed,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    """Full manifest + kind/mtime + artifact-presence flags."""
    try:
        return _runs.run_detail(run_id, data_dir=data_dir())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/equity")
def run_equity(run_id: str) -> dict[str, list[float]]:
    """The run's equity curve as ``{ts, equity, drawdown}`` (empty lists when it wrote none)."""
    return _runs.equity_series(run_id, data_dir=data_dir())


@router.get("/runs/{run_id}/trades")
def run_trades(run_id: str) -> list[dict[str, Any]]:
    """The run's trade-log rows (``[]`` when it wrote none)."""
    return _runs.trades(run_id, data_dir=data_dir())


@router.get("/runs/{run_id}/forecast")
def run_forecast(run_id: str) -> dict[str, Any]:
    """A forecast run's history + forecast series (+ optional p10/p90 band). 404 otherwise."""
    series = _runs.forecast_series(run_id, data_dir=data_dir())
    if series is None:
        raise HTTPException(status_code=404, detail="no forecast for this run")
    return series
