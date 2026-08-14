"""Typed, bounded Crypto Data Center routes over the authoritative CLI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from alpha_web import _catalog, _invoke
from alpha_web.api._common import data_dir
from alpha_web.api.models import (
    CryptoAcquisitionRequest,
    CryptoAssetIdentityResponse,
    CryptoCacheCleanRequest,
    CryptoCacheCleanResponse,
    CryptoCapabilitiesResponse,
    CryptoCatalogResponse,
    CryptoCoverageResponse,
    CryptoEstimateRequest,
    CryptoEstimateResponse,
    CryptoQualityResponse,
    CryptoSnapshotCreateRequest,
    CryptoSnapshotCreateResponse,
    CryptoSnapshotRegisterRequest,
    CryptoSnapshotRegisterResponse,
    CryptoSnapshotVerifyRequest,
    CryptoSnapshotVerifyResponse,
    CryptoStorageInventoryResponse,
    CryptoStorageResponse,
    CryptoStorageVerifyResponse,
    JobStatus,
)

router = APIRouter(prefix="/api/crypto-data", tags=["crypto-data"])


def _project(args: list[str]) -> Any:
    try:
        return _catalog._run_json(args, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/catalog", response_model=CryptoCatalogResponse)
def catalog() -> Any:
    return _project(["crypto-data", "catalog", "--json"])


@router.get("/capabilities", response_model=CryptoCapabilitiesResponse)
def capabilities() -> Any:
    return _project(["crypto-data", "capabilities", "--json"])


@router.get("/storage", response_model=CryptoStorageResponse)
def storage() -> Any:
    return _project(["crypto-data", "storage", "--json"])


@router.get("/storage/inventory", response_model=CryptoStorageInventoryResponse)
def storage_inventory() -> Any:
    return _project(["crypto-data", "storage-inventory", "--json"])


@router.post("/storage/verify", response_model=CryptoStorageVerifyResponse)
def storage_verify() -> Any:
    return _project(["crypto-data", "storage-verify", "--json"])


@router.post("/storage/cache/clean", response_model=CryptoCacheCleanResponse)
def cache_clean(req: CryptoCacheCleanRequest) -> Any:
    if req.confirm is not True:  # pragma: no cover - Literal validation owns false inputs
        raise HTTPException(status_code=422, detail="cache cleanup requires confirmation")
    return _project(["crypto-data", "cache-clean", "--confirm", "--json"])


@router.get("/coverage", response_model=CryptoCoverageResponse)
def coverage() -> Any:
    return _project(["crypto-data", "coverage", "--json"])


@router.get("/assets/{symbol}", response_model=CryptoAssetIdentityResponse)
def asset(symbol: str, as_of: str) -> Any:
    normalized = symbol.strip().upper()
    if not normalized or len(normalized) > 32 or not normalized.replace("-", "").isalnum():
        raise HTTPException(status_code=422, detail="crypto asset symbol is invalid")
    if not as_of or len(as_of) > 64:
        raise HTTPException(status_code=422, detail="crypto asset as-of time is invalid")
    return _project(["crypto-data", "asset", normalized, "--as-of", as_of, "--json"])


@router.get("/quality/{manifest_id}", response_model=CryptoQualityResponse)
def quality(manifest_id: str) -> Any:
    if len(manifest_id) != 64 or any(char not in "0123456789abcdef" for char in manifest_id):
        raise HTTPException(status_code=422, detail="crypto manifest id is invalid")
    return _project(["crypto-data", "quality", manifest_id, "--json"])


@router.post("/estimate", response_model=CryptoEstimateResponse)
def estimate(req: CryptoEstimateRequest) -> Any:
    return _project(
        [
            "crypto-data",
            "estimate",
            req.family,
            "--instruments",
            str(req.instruments),
            "--days",
            str(req.days),
            "--frequency",
            req.frequency,
            "--json",
        ]
    )


@router.post("/acquisitions", response_model=JobStatus)
def acquire(req: CryptoAcquisitionRequest) -> dict[str, object]:
    args = [
        "crypto-data",
        "acquire",
        req.provider,
        req.family,
        req.instrument,
        "--base",
        req.base,
        "--quote",
        req.quote,
        "--category",
        req.category,
        "--frequency",
        req.frequency,
    ]
    for flag, value in (
        ("--period", req.period),
        ("--network", req.network),
        ("--pool-address", req.pool_address),
        ("--metrics", ",".join(req.metrics) if req.metrics else None),
        ("--start", req.start),
        ("--end", req.end),
    ):
        if value is not None:
            args.extend((flag, value))
    args.append("--json")
    try:
        job = _invoke.launch(args, data_dir=data_dir(), run_type=None)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"job_id": job.job_id, "status": job.status, "session_id": job.session_id}


@router.post("/snapshots", response_model=CryptoSnapshotCreateResponse)
def snapshot_create(req: CryptoSnapshotCreateRequest) -> Any:
    if len(set(req.manifest_ids)) != len(req.manifest_ids):
        raise HTTPException(status_code=422, detail="snapshot members must be unique")
    args = ["crypto-data", "snapshot-create"]
    for manifest_id in req.manifest_ids:
        if len(manifest_id) != 64 or any(char not in "0123456789abcdef" for char in manifest_id):
            raise HTTPException(status_code=422, detail="snapshot manifest id is invalid")
        args.extend(("--manifest-id", manifest_id))
    args.append("--json")
    return _project(args)


@router.post(
    "/snapshots/{snapshot_id}/verify",
    response_model=CryptoSnapshotVerifyResponse,
)
def snapshot_verify(snapshot_id: str, req: CryptoSnapshotVerifyRequest) -> Any:
    if len(snapshot_id) != 64 or any(char not in "0123456789abcdef" for char in snapshot_id):
        raise HTTPException(status_code=422, detail="crypto snapshot id is invalid")
    args = ["crypto-data", "snapshot-verify", snapshot_id]
    for family in req.required_families:
        args.extend(("--required-family", family))
    args.extend(("--purpose", req.purpose, "--json"))
    return _project(args)


@router.post(
    "/snapshots/{snapshot_id}/register",
    response_model=CryptoSnapshotRegisterResponse,
)
def snapshot_register(snapshot_id: str, req: CryptoSnapshotRegisterRequest) -> Any:
    if len(snapshot_id) != 64 or any(char not in "0123456789abcdef" for char in snapshot_id):
        raise HTTPException(status_code=422, detail="crypto snapshot id is invalid")
    return _project(
        [
            "research",
            "data",
            "register-crypto",
            snapshot_id,
            "--symbol",
            req.symbol.upper(),
            "--json",
        ]
    )
