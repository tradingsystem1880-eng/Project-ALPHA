"""Only opaque native job identity crosses this read-only HTTP boundary."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from alpha_web._native_results import (
    NativeResultDeployment,
    native_result_deployment,
    read_native_result,
    unavailable,
)
from alpha_web.api.native_result_models import NativeJobResultV1

router = APIRouter(prefix="/api/native-jobs", tags=["native-results"])


@router.get("/{job_id}/result", response_model=NativeJobResultV1, response_model_exclude_none=True)
async def native_result(
    job_id: UUID,
    request: Request,
    deployment: Annotated[NativeResultDeployment | None, Depends(native_result_deployment)],
) -> dict[str, object]:
    """Read owner-observed synthetic result; no paths, launch or resume selectors."""
    if request.scope.get("query_string"):
        raise HTTPException(status_code=422, detail="Native result reads accept only job identity.")
    async for chunk in request.stream():
        if chunk:
            raise HTTPException(
                status_code=422, detail="Native result reads accept no request body."
            )
    if deployment is None:
        return unavailable("native_result_configuration_unavailable")
    return await run_in_threadpool(read_native_result, deployment, str(job_id))
