"""Typed, bounded Crypto Data Center routes over the authoritative CLI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from alpha_web import _catalog, _invoke, _research
from alpha_web.api._common import data_dir
from alpha_web.api.models import (
    CryptoAcquisitionRequest,
    CryptoAssetIdentityResponse,
    CryptoAssetMasterCreateRequest,
    CryptoAssetMasterListResponse,
    CryptoAssetMasterResponse,
    CryptoCacheCleanRequest,
    CryptoCacheCleanResponse,
    CryptoCapabilitiesResponse,
    CryptoCatalogResponse,
    CryptoCoverageBatchListResponse,
    CryptoCoverageBatchRequest,
    CryptoCoverageBatchResumeRequest,
    CryptoCoverageProfileCreateRequest,
    CryptoCoverageProfileCreateResponse,
    CryptoCoverageProfileListResponse,
    CryptoCoverageProfilePageResponse,
    CryptoCoverageResponse,
    CryptoEstimateRequest,
    CryptoEstimateResponse,
    CryptoFeatureCreateRequest,
    CryptoFeatureListResponse,
    CryptoFeatureResponse,
    CryptoLiquidityFreezeRequest,
    CryptoLiquidityFreezeResponse,
    CryptoOneMinuteSelectionRequest,
    CryptoOneMinuteSelectionResponse,
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

_FEATURE_INPUT_ORDER = {
    "funding": ("funding",),
    "open_interest_change": ("open_interest",),
    "basis": ("mark", "index", "premium"),
    "volatility_surface": ("quotes", "instruments"),
    "liquidity": ("pools",),
    "onchain_change": ("onchain",),
}


def _project(args: list[str]) -> Any:
    try:
        return _catalog._run_json(args, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _digest(value: str, label: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise HTTPException(status_code=422, detail=f"crypto {label} id is invalid")
    return value


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


@router.get("/profiles", response_model=CryptoCoverageProfileListResponse)
def profiles() -> Any:
    return _project(["crypto-data", "profiles", "--json"])


@router.post("/profiles", response_model=CryptoCoverageProfileCreateResponse)
def profile_create(req: CryptoCoverageProfileCreateRequest) -> Any:
    args = ["crypto-data", "profile-create"]
    if req.as_of is not None:
        args.extend(("--as-of", req.as_of))
    args.append("--json")
    return _project(args)


@router.get("/profiles/{profile_id}", response_model=CryptoCoverageProfilePageResponse)
def profile_show(
    profile_id: str,
    offset: int = Query(default=0, ge=0, le=10_000),
    limit: int = Query(default=50, ge=1, le=100),
    provider: str | None = Query(default=None, max_length=40),
    family: str | None = Query(default=None, max_length=80),
    category: str | None = Query(default=None, max_length=20),
    frequency: str | None = Query(default=None, max_length=40),
    cadence: str | None = Query(default=None, max_length=40),
) -> Any:
    args = [
        "crypto-data",
        "profile-show",
        _digest(profile_id, "coverage profile"),
        "--offset",
        str(offset),
        "--limit",
        str(limit),
    ]
    for flag, value in (
        ("--provider", provider),
        ("--family", family),
        ("--category", category),
        ("--frequency", frequency),
        ("--cadence", cadence),
    ):
        if value is not None:
            args.extend((flag, value))
    args.append("--json")
    return _project(args)


@router.post("/profiles/{profile_id}/batches", response_model=JobStatus)
def profile_run(profile_id: str, req: CryptoCoverageBatchRequest) -> dict[str, object]:
    args = [
        "crypto-data",
        "profile-run",
        _digest(profile_id, "coverage profile"),
        "--cadence",
        req.cadence,
        "--offset",
        str(req.offset),
        "--limit",
        str(req.limit),
        "--confirm",
        "--json",
    ]
    try:
        job = _invoke.launch(args, data_dir=data_dir(), run_type=None)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"job_id": job.job_id, "status": job.status, "session_id": job.session_id}


@router.get("/batches", response_model=CryptoCoverageBatchListResponse)
def profile_batches() -> Any:
    return _project(["crypto-data", "profile-batches", "--json"])


@router.post("/batches/{batch_id}/resume", response_model=JobStatus)
def profile_resume(batch_id: str, req: CryptoCoverageBatchResumeRequest) -> dict[str, object]:
    if req.confirm is not True:  # pragma: no cover - Literal validation owns false inputs
        raise HTTPException(status_code=422, detail="coverage-batch resume requires confirmation")
    args = [
        "crypto-data",
        "profile-resume",
        _digest(batch_id, "coverage batch"),
        "--confirm",
        "--json",
    ]
    try:
        job = _invoke.launch(args, data_dir=data_dir(), run_type=None)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"job_id": job.job_id, "status": job.status, "session_id": job.session_id}


@router.post(
    "/profiles/{profile_id}/liquidity-membership",
    response_model=CryptoLiquidityFreezeResponse,
)
def liquidity_freeze(profile_id: str, req: CryptoLiquidityFreezeRequest) -> Any:
    expected_quote = "USD" if req.category == "inverse" else "USDT"
    if req.quote_asset != expected_quote:
        raise HTTPException(
            status_code=422,
            detail=f"{req.category} liquidity membership requires exact {expected_quote} quote",
        )
    return _project(
        [
            "crypto-data",
            "liquidity-freeze",
            _digest(profile_id, "coverage profile"),
            "--category",
            req.category,
            "--quote-asset",
            req.quote_asset,
            "--session",
            req.session,
            "--limit",
            str(req.limit),
            "--json",
        ]
    )


@router.post(
    "/profiles/{profile_id}/one-minute-selection",
    response_model=CryptoOneMinuteSelectionResponse,
)
def one_minute_selection(profile_id: str, req: CryptoOneMinuteSelectionRequest) -> Any:
    args = [
        "crypto-data",
        "profile-select-one-minute",
        _digest(profile_id, "coverage profile"),
        "--case-id",
        req.case_id,
        "--expected-case-revision",
        req.expected_case_revision,
    ]
    for market in req.markets:
        args.extend(("--market", market))
    args.extend(("--reason", req.reason, "--json"))
    return _project(args)


@router.get("/assets/{symbol}", response_model=CryptoAssetIdentityResponse)
def asset(symbol: str, as_of: str) -> Any:
    normalized = symbol.strip().upper()
    if not normalized or len(normalized) > 32 or not normalized.replace("-", "").isalnum():
        raise HTTPException(status_code=422, detail="crypto asset symbol is invalid")
    if not as_of or len(as_of) > 64:
        raise HTTPException(status_code=422, detail="crypto asset as-of time is invalid")
    return _project(["crypto-data", "asset", normalized, "--as-of", as_of, "--json"])


@router.get(
    "/assets/contracts/{network}/{contract_address}",
    response_model=CryptoAssetIdentityResponse,
)
def asset_contract(
    network: str, contract_address: str, asset_master_version: str, as_of: str
) -> Any:
    if (
        not network
        or len(network) > 80
        or not network.replace("-", "").isalnum()
        or not contract_address
        or len(contract_address) > 160
        or not contract_address.replace("_", "").isalnum()
    ):
        raise HTTPException(status_code=422, detail="crypto contract identity is invalid")
    if len(asset_master_version) != 64 or any(
        char not in "0123456789abcdef" for char in asset_master_version
    ):
        raise HTTPException(status_code=422, detail="crypto asset-master version is invalid")
    if not as_of or len(as_of) > 64:
        raise HTTPException(status_code=422, detail="crypto asset as-of time is invalid")
    return _project(
        [
            "crypto-data",
            "asset-contract",
            network,
            contract_address,
            "--asset-master-version",
            asset_master_version,
            "--as-of",
            as_of,
            "--json",
        ]
    )


@router.post("/asset-masters", response_model=CryptoAssetMasterResponse)
def asset_master_create(req: CryptoAssetMasterCreateRequest) -> Any:
    if len(set(req.geckoterminal_manifest_ids)) != len(req.geckoterminal_manifest_ids):
        raise HTTPException(status_code=422, detail="asset-master pool manifests must be unique")
    args = [
        "crypto-data",
        "asset-master-create",
        "--coingecko-manifest-id",
        req.coingecko_manifest_id,
    ]
    for manifest_id in req.geckoterminal_manifest_ids:
        args.extend(("--geckoterminal-manifest-id", manifest_id))
    args.append("--json")
    return _project(args)


@router.get("/asset-masters", response_model=CryptoAssetMasterListResponse)
def asset_masters() -> Any:
    return _project(["crypto-data", "asset-masters", "--json"])


@router.post(
    "/asset-masters/{asset_master_version}/verify",
    response_model=CryptoAssetMasterResponse,
)
def asset_master_verify(asset_master_version: str) -> Any:
    if len(asset_master_version) != 64 or any(
        char not in "0123456789abcdef" for char in asset_master_version
    ):
        raise HTTPException(status_code=422, detail="crypto asset-master version is invalid")
    return _project(["crypto-data", "asset-master-verify", asset_master_version, "--json"])


@router.get("/quality/{manifest_id}", response_model=CryptoQualityResponse)
def quality(manifest_id: str) -> Any:
    if len(manifest_id) != 64 or any(char not in "0123456789abcdef" for char in manifest_id):
        raise HTTPException(status_code=422, detail="crypto manifest id is invalid")
    return _project(["crypto-data", "quality", manifest_id, "--json"])


@router.post("/features", response_model=CryptoFeatureResponse)
def feature_create(req: CryptoFeatureCreateRequest) -> Any:
    expected = _FEATURE_INPUT_ORDER[req.feature_name]
    if set(req.inputs) != set(expected):
        raise HTTPException(
            status_code=422,
            detail=f"{req.feature_name} requires inputs: {', '.join(expected)}",
        )
    args = ["crypto-data", "feature-create", req.feature_name]
    for name in expected:
        manifest_id = req.inputs[name]
        if len(manifest_id) != 64 or any(char not in "0123456789abcdef" for char in manifest_id):
            raise HTTPException(status_code=422, detail="feature input manifest id is invalid")
        args.extend(("--input", f"{name}={manifest_id}"))
    args.append("--json")
    return _project(args)


@router.get("/features", response_model=CryptoFeatureListResponse)
def features() -> Any:
    return _project(["crypto-data", "features", "--json"])


@router.get("/features/{manifest_id}", response_model=CryptoFeatureResponse)
def feature_show(manifest_id: str) -> Any:
    if len(manifest_id) != 64 or any(char not in "0123456789abcdef" for char in manifest_id):
        raise HTTPException(status_code=422, detail="crypto feature manifest id is invalid")
    return _project(["crypto-data", "feature-show", manifest_id, "--json"])


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
    case_bound_event = req.family in {"derivative_trades", "derivative_book_snapshots"}
    scope_fields = (req.case_id, req.expected_case_revision, req.reason)
    if case_bound_event and not all(scope_fields):
        raise HTTPException(
            status_code=422,
            detail=(
                "derivative trades and books require a current research case, revision, and reason"
            ),
        )
    if not case_bound_event and any(value is not None for value in scope_fields):
        raise HTTPException(
            status_code=422,
            detail="research-case event scope is only valid for derivative trades and books",
        )
    if case_bound_event:
        assert req.case_id is not None and req.expected_case_revision is not None
        try:
            current = _research.proposal_options(req.case_id, data_dir=data_dir())
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if current.get("case_revision") != req.expected_case_revision:
            raise HTTPException(
                status_code=409,
                detail="research case changed before derivative event capture; refresh and retry",
            )
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
        ("--case-id", req.case_id),
        ("--expected-case-revision", req.expected_case_revision),
        ("--reason", req.reason),
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
    args.extend(("--asset-master-version", req.asset_master_version, "--json"))
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
