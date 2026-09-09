"""``/api/scans`` and ``/api/alerts`` — rule scans over stored symbols, via ``alpha scan``."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from alpha_web import _scans
from alpha_web.api._common import data_dir
from alpha_web.api.models import (
    ScanAlerts,
    ScanCheckResult,
    ScanDeleted,
    ScanList,
    ScanRecord,
    ScanRunRequest,
    ScanRunResult,
    ScanSaveRequest,
)

router = APIRouter(prefix="/api", tags=["scans"])


@router.get("/scans", response_model=ScanList)
def list_scans() -> dict[str, Any]:
    return _scans.list_scans(data_dir=data_dir())


@router.post("/scans", response_model=ScanRecord)
def save_scan(body: ScanSaveRequest) -> dict[str, Any]:
    """Save (or overwrite) a scan naming a saved rule set and a universe."""
    try:
        return _scans.save(body.name, body.rules, body.symbols, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scans/check", response_model=ScanCheckResult)
def check_all() -> dict[str, Any]:
    """Check every saved scan; only changed signals become alerts (the live desk's `alerts`)."""
    try:
        return _scans.check(None, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scans/{name}", response_model=ScanRecord)
def show_scan(name: str) -> dict[str, Any]:
    try:
        return _scans.show(name, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/scans/{name}", response_model=ScanDeleted)
def delete_scan(name: str) -> dict[str, Any]:
    try:
        return _scans.delete(name, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scans/{name}/run", response_model=ScanRunResult)
def run_scan(name: str, body: ScanRunRequest | None = None) -> dict[str, Any]:
    """Evaluate the scan on point-in-time bars (optionally as of a date); writes nothing."""
    try:
        return _scans.run(name, body.as_of if body else None, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scans/{name}/check", response_model=ScanCheckResult)
def check_scan(name: str) -> dict[str, Any]:
    try:
        return _scans.check(name, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/alerts", response_model=ScanAlerts)
def alerts(limit: Annotated[int, Query(ge=1, le=5000)] = 200) -> dict[str, Any]:
    """The newest scan alerts, oldest first within the tail."""
    return _scans.alerts(limit, data_dir=data_dir())
