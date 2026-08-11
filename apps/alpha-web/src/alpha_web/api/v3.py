"""OpenAPI-visible versioned aliases for the Workstation-v3 control surface."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from alpha_cli import run_projection
from alpha_core import DataError
from alpha_web.api import development as development_api
from alpha_web.api import ml as ml_api
from alpha_web.api import runs as runs_api
from alpha_web.api._common import data_dir


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


RunId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{16}$")]


class RunComparisonRequest(StrictModel):
    run_ids: list[RunId] = Field(min_length=2, max_length=run_projection.MAX_COMPARE_RUNS)


class RunMetric(StrictModel):
    name: str
    value: float
    unit: str
    source_artifact: Literal["manifest.json"]
    source_field: str


class RunComparisonRow(StrictModel):
    run_id: RunId
    command: str | None
    symbol: str | None
    symbols: list[str] | None
    snapshot_id: str | None
    snapshot_hash: str | None
    passed: bool | None
    metrics: list[RunMetric] = Field(max_length=64)


class RunComparisonResponse(StrictModel):
    run_ids: list[RunId] = Field(min_length=2, max_length=run_projection.MAX_COMPARE_RUNS)
    same_snapshot_hash: bool
    rows: list[RunComparisonRow] = Field(min_length=2, max_length=run_projection.MAX_COMPARE_RUNS)


router = APIRouter(prefix="/api/v3", tags=["workstation-v3"])


@router.post("/runs/compare", response_model=RunComparisonResponse)
def compare_runs(request: RunComparisonRequest) -> dict[str, object]:
    """Compare 2–8 immutable runs using bounded, exactly cited manifest metrics."""
    try:
        return run_projection.compare_runs(request.run_ids, data_dir=data_dir())
    except DataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _clone_route(alias_router: APIRouter, route: APIRoute) -> None:
    legacy_path = route.path
    if not legacy_path.startswith("/api/"):
        raise RuntimeError(f"v3 alias source must be rooted at /api: {legacy_path}")
    description = route.description.rstrip()
    alias_note = f"Versioned Workstation-v3 alias of `{legacy_path}`."
    alias_router.add_api_route(
        legacy_path.removeprefix("/api"),
        route.endpoint,
        response_model=route.response_model,
        status_code=route.status_code,
        tags=route.tags,
        dependencies=route.dependencies,
        summary=route.summary,
        description=f"{description}\n\n{alias_note}" if description else alias_note,
        response_description=route.response_description,
        responses=route.responses,
        deprecated=route.deprecated,
        methods=route.methods,
        response_model_include=route.response_model_include,
        response_model_exclude=route.response_model_exclude,
        response_model_by_alias=route.response_model_by_alias,
        response_model_exclude_unset=route.response_model_exclude_unset,
        response_model_exclude_defaults=route.response_model_exclude_defaults,
        response_model_exclude_none=route.response_model_exclude_none,
        include_in_schema=route.include_in_schema,
        response_class=route.response_class,
        name=f"v3_{route.name}",
        callbacks=route.callbacks,
        openapi_extra=route.openapi_extra,
        strict_content_type=route.strict_content_type,
    )


def _api_routes(source: APIRouter) -> list[APIRoute]:
    return [route for route in source.routes if isinstance(route, APIRoute)]


for source_router in (development_api.router, ml_api.router):
    for source_route in _api_routes(source_router):
        _clone_route(router, source_route)

_VERSIONED_RUN_ENDPOINTS = {
    "/api/runs/{run_id}/chart-bundle",
    "/api/runs/{run_id}/native-tearsheet",
    "/api/runs/{run_id}/portfolio-analytics",
    "/api/runs/{run_id}/forecast/paths",
}
for source_route in _api_routes(runs_api.router):
    if source_route.path in _VERSIONED_RUN_ENDPOINTS:
        _clone_route(router, source_route)


__all__ = ["router"]
