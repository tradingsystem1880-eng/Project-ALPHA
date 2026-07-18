"""``/api/runs`` — the run store as JSON.

Index, detail, equity, trades, forecast cone + sampled paths, null distributions, optim trials,
propfirm paths, and forecast-eval origins — all read-only projections over the artifact store.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from alpha_web import _runs
from alpha_web.api._common import data_dir
from alpha_web.api.models import (
    EquitySeries,
    ForecastOrigins,
    ForecastPaths,
    ForecastSeries,
    NullTiers,
    OptimTrials,
    PropfirmPaths,
    RunDetail,
    RunList,
)

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs", response_model=RunList)
def list_runs(
    kind: str | None = None,
    symbol: str | None = None,
    verdict: str | None = None,
    passed: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
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


@router.get("/runs/{run_id}", response_model=RunDetail)
def run_detail(run_id: str) -> dict[str, Any]:
    """Full manifest + kind/mtime + artifact-presence flags."""
    try:
        return _runs.run_detail(run_id, data_dir=data_dir())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ensure_run(run_id: str) -> None:
    try:
        _runs.run_detail(run_id, data_dir=data_dir())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/equity", response_model=EquitySeries)
def run_equity(run_id: str) -> dict[str, list[float]]:
    """The run's equity curve as ``{ts, equity, drawdown}`` (empty lists when it wrote none)."""
    _ensure_run(run_id)
    return _runs.equity_series(run_id, data_dir=data_dir())


@router.get("/runs/{run_id}/trades", response_model=list[dict[str, Any]])
def run_trades(run_id: str) -> list[dict[str, Any]]:
    """The run's trade-log rows (``[]`` when it wrote none)."""
    _ensure_run(run_id)
    return _runs.trades(run_id, data_dir=data_dir())


@router.get("/runs/{run_id}/forecast", response_model=ForecastSeries)
def run_forecast(run_id: str) -> dict[str, Any]:
    """A forecast run's history + forecast series (+ quantile bands). 404 otherwise."""
    _ensure_run(run_id)
    series = _runs.forecast_series(run_id, data_dir=data_dir())
    if series is None:
        raise HTTPException(status_code=404, detail="no forecast for this run")
    return series


@router.get("/runs/{run_id}/forecast/paths", response_model=ForecastPaths)
def run_forecast_paths(
    run_id: str, n: Annotated[int, Query(ge=1, le=_runs.MAX_FORECAST_PATHS)] = 20
) -> dict[str, Any]:
    """The first ``n`` (clamped to 40) sampled close paths of a forecast run. 404 otherwise."""
    _ensure_run(run_id)
    body = _runs.forecast_paths(run_id, data_dir=data_dir(), n=n)
    if body is None:
        raise HTTPException(status_code=404, detail="no sampled forecast paths for this run")
    return body


@router.get("/runs/{run_id}/nulls", response_model=NullTiers)
def run_nulls(run_id: str) -> dict[str, Any]:
    """A gauntlet run's raw per-tier null distributions. 404 when it wrote none."""
    _ensure_run(run_id)
    body = _runs.null_distributions(run_id, data_dir=data_dir())
    if body is None:
        raise HTTPException(status_code=404, detail="no null distributions for this run")
    return body


@router.get("/runs/{run_id}/trials", response_model=OptimTrials)
def run_trials(run_id: str) -> dict[str, Any]:
    """A sweep's per-config OOS return streams. 404 when it wrote none."""
    _ensure_run(run_id)
    body = _runs.optim_trials(run_id, data_dir=data_dir())
    if body is None:
        raise HTTPException(status_code=404, detail="no trials for this run")
    return body


@router.get("/runs/{run_id}/propfirm-paths", response_model=PropfirmPaths)
def run_propfirm_paths(run_id: str) -> dict[str, Any]:
    """A prop-firm run's per-path Monte-Carlo outcomes, columnar. 404 when it wrote none."""
    _ensure_run(run_id)
    body = _runs.propfirm_paths(run_id, data_dir=data_dir())
    if body is None:
        raise HTTPException(status_code=404, detail="no propfirm paths for this run")
    return body


@router.get("/runs/{run_id}/origins", response_model=ForecastOrigins)
def run_origins(run_id: str) -> dict[str, Any]:
    """A forecast-eval run's per-origin skill scores, columnar. 404 when it wrote none."""
    _ensure_run(run_id)
    body = _runs.forecast_origins(run_id, data_dir=data_dir())
    if body is None:
        raise HTTPException(status_code=404, detail="no eval origins for this run")
    return body


@router.get("/runs/{run_id}/tearsheet")
def run_tearsheet(run_id: str) -> FileResponse:
    """The run's rendered quantstats tear sheet (embedded in Run Detail via an iframe)."""
    _ensure_run(run_id)
    path = _runs.tearsheet_file(run_id, data_dir=data_dir())
    if path is None:
        raise HTTPException(status_code=404, detail="no tear sheet for this run")
    return FileResponse(path, media_type="text/html")
