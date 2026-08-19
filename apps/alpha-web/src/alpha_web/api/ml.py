"""Typed, bounded REST projections/actions for the isolated Qlib research track."""

from __future__ import annotations

from typing import Annotated, Literal, cast

import polars as pl
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from alpha_web import _ml
from alpha_web.api._common import data_dir

router = APIRouter(prefix="/api/ml", tags=["ml-research"])

type JsonObject = dict[str, JsonValue]

OpaqueId = Annotated[str, Field(pattern=r"^[0-9a-f]{16,64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MlReadiness(StrictModel):
    schema_version: Literal[1]
    worker_project_present: bool
    worker_lock_present: bool
    worker_environment_present: bool
    worker_lock_hash: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    root_qlib_importable: bool
    root_lightgbm_importable: bool
    isolation_ready: bool
    heavy_job_limit: Literal[1]
    heavy_job_busy: bool
    supported_modes: list[Literal["fake", "real"]]


class MlServiceStatus(StrictModel):
    available: bool
    worker_ready: bool
    isolation: str
    concurrency_limit: Literal[1]
    active_job_id: str | None
    min_symbols: Literal[20]
    min_aligned_sessions: Literal[756]
    message: str | None


class MlPreflightCheck(StrictModel):
    check_id: Literal[
        "experiment",
        "snapshot",
        "research_gate",
        "worker",
        "universe",
        "aligned_history",
        "active_job",
    ]
    state: Literal["pass", "blocked"]
    message: str
    recovery_action: str


class MlExperimentPreflight(StrictModel):
    schema_version: Literal[1]
    project_id: str
    experiment_id: str | None
    snapshot_id: str | None
    universe_count: int = Field(ge=0, le=512)
    aligned_sessions: int = Field(ge=0)
    active_job_id: str | None
    ready: bool
    checks: list[MlPreflightCheck]


class MlInputBundle(StrictModel):
    input_bundle_id: OpaqueId
    spec_present: bool
    panel_present: bool
    ready: bool


class MlInputBundlePage(StrictModel):
    items: list[MlInputBundle]
    limit: int
    offset: int
    total: int
    has_more: bool


class MlFeatureRecipe(StrictModel):
    name: Literal["alpha158"]
    version: Literal[1]
    parameters: dict[str, JsonValue]


class MlLabelRecipe(StrictModel):
    name: Literal["next_session_open_to_open"]
    decision: Literal["close_t"]
    fill: Literal["open_t_plus_1"]
    horizon_sessions: Literal[1]


class MlModelRecipe(StrictModel):
    name: Literal["lightgbm"]
    parameters: dict[str, int | float]


class MlPortfolioRecipe(StrictModel):
    selection: Literal["top_quintile"]
    weighting: Literal["equal"]
    long_only: Literal[True]


class MlCosts(StrictModel):
    fee_bps: float = Field(ge=0)
    slippage_bps: float = Field(ge=0)


class MlFold(StrictModel):
    fold: int = Field(ge=0)
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_end: str


class MlExperimentContract(StrictModel):
    schema_version: Literal[1]
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    worker_lock_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    universe: list[str] = Field(min_length=20, max_length=512)
    universe_count: int = Field(ge=20, le=512)
    universe_membership: Literal["point_in_time", "current_membership"]
    survivorship_warning: str | None
    feature_recipe: MlFeatureRecipe
    label_recipe: MlLabelRecipe
    model: MlModelRecipe
    portfolio: MlPortfolioRecipe
    costs: MlCosts
    folds: list[MlFold] = Field(min_length=1, max_length=50)
    purge_sessions: int = Field(ge=0)
    embargo_sessions: int = Field(ge=0)
    seed: int = Field(ge=0)
    panel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    panel_rows: int = Field(ge=1)


class MlWorkerResult(StrictModel):
    status: Literal["succeeded"]
    worker_kind: Literal["fake", "qlib"]
    worker_implementation_version: str
    prediction_rows: int = Field(ge=1)
    prediction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    diagnostic_only: Literal[True]
    counterfactual_refit: Literal[False]


class MlExchangeSummary(StrictModel):
    exchange_id: OpaqueId
    status: Literal["empty", "prepared", "trained", "replay_handoff_prepared"]
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    snapshot_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    worker_kind: Literal["fake", "qlib"] | None
    prediction_rows: int | None
    diagnostic_only: bool | None
    counterfactual_refit: bool | None


class MlExchangeDetail(MlExchangeSummary):
    contract: MlExperimentContract
    result: MlWorkerResult | None


class MlExchangePage(StrictModel):
    items: list[MlExchangeSummary]
    limit: int
    offset: int
    total: int
    has_more: bool


class MlExperimentMetrics(StrictModel):
    ic: float | None
    rank_ic: float | None
    turnover: float | None
    costed_return: float | None


class MlExperimentSummary(StrictModel):
    experiment_id: OpaqueId
    project_id: str | None
    status: str
    universe_size: int = Field(ge=0, le=512)
    aligned_sessions: int = Field(ge=0)
    feature_recipe: str
    model: str
    folds: int = Field(ge=0, le=50)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_run_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    diagnostic_only: bool
    counterfactual_refit: bool
    metrics: MlExperimentMetrics


class MlExperimentPage(StrictModel):
    items: list[MlExperimentSummary]
    limit: int
    offset: int
    has_more: bool


class MlEvaluationScore(StrictModel):
    min: float
    max: float
    mean: float
    std: float


class MlEvaluation(StrictModel):
    schema_version: Literal[1]
    authority: Literal["diagnostic_only"]
    rows: int
    symbols: int
    targets: int
    folds: list[int]
    score: MlEvaluationScore
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    worker_lock_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    counterfactual_refit: Literal[False]
    label: str
    diagnostics: JsonObject
    next_required_step: str


class MlDiagnosticVersions(StrictModel):
    worker: str
    pyqlib: str
    lightgbm: str


class MlDiagnosticFeatureRecipe(StrictModel):
    name: Literal["Alpha158-style"]
    feature_count: int
    names: list[str]
    vwap_source: str


class MlDiagnosticLabelRecipe(StrictModel):
    name: Literal["next_session_open_to_open"]
    definition: str
    decision: Literal["close_t"]
    entry: Literal["open_t_plus_1"]


class MlScoreDistribution(MlEvaluationScore):
    q05: float
    q25: float
    q50: float
    q75: float
    q95: float


class MlIcPoint(StrictModel):
    target_ts: str
    ic: float | None
    rank_ic: float | None
    sample_count: int = Field(ge=1)


class MlIcDiagnostics(StrictModel):
    mean: float | None
    rank_mean: float | None
    by_target: list[MlIcPoint]


class MlQuantileReturn(StrictModel):
    quantile: int = Field(ge=1, le=5)
    mean_return: float | None
    observations: int = Field(ge=0)


class MlPortfolioPoint(StrictModel):
    target_ts: str
    gross_return: float
    costed_return: float
    benchmark_return: float
    excess_return: float
    turnover: float
    gross_equity: float
    costed_equity: float
    benchmark_equity: float


class MlDiagnosticPortfolio(StrictModel):
    selection: Literal["long_only_top_quintile_equal_weight"]
    declared_costs: MlCosts
    periods: int = Field(ge=0)
    gross_total_return: float
    costed_total_return: float
    benchmark_total_return: float
    costed_excess_total_return: float
    mean_turnover: float | None
    timeline: list[MlPortfolioPoint]


class MlFeatureImportance(StrictModel):
    feature: str
    mean_gain: float
    mean_split_count: float


class MlFoldNormalization(StrictModel):
    method: Literal["train_only_median_then_zscore"]
    statistics_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    all_missing_train_features: int = Field(ge=0)


class MlFoldBoundaries(StrictModel):
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_end: str


class MlFoldDiagnostic(StrictModel):
    fold: int
    fit_count: Literal[1]
    train_rows: int
    validation_rows: int
    test_rows: int
    best_iteration: int
    model_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalization: MlFoldNormalization
    training_history: dict[str, dict[str, list[float]]]
    boundaries: MlFoldBoundaries


class MlTearSheet(StrictModel):
    available: bool
    exchange_id: OpaqueId
    authority: str
    label: str
    counterfactual_refit: bool
    versions: MlDiagnosticVersions | None
    feature_recipe: MlDiagnosticFeatureRecipe | None
    label_recipe: MlDiagnosticLabelRecipe | None
    score_distribution: MlScoreDistribution | None
    ic: MlIcDiagnostics | None
    quantile_returns: list[MlQuantileReturn]
    portfolio: MlDiagnosticPortfolio | None
    feature_importance: list[MlFeatureImportance]
    feature_importance_truncated: bool
    folds: list[MlFoldDiagnostic]
    timeline_total: int
    timeline_offset: int
    timeline_limit: int
    timeline_has_more: bool


class MlReplayPeriod(StrictModel):
    fold: int
    target_ts: str
    exit_ts: str
    gross_return: float
    net_return: float
    benchmark_return: float
    excess_return: float
    turnover: float
    fees: float
    slippage_cost: float


class MlReplayTearSheet(StrictModel):
    run_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    authority: Literal["alpha_canonical_execution_and_validation"]
    label: str
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    worker_lock_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    universe: list[str]
    universe_membership: Literal["point_in_time", "current_membership"]
    survivorship_warning: str | None
    metrics: dict[str, float | None]
    validation: JsonObject
    promotion_eligible: bool
    counterfactual_refit: bool
    prediction_rows: int
    signal_rows: int
    selected_signals: int
    folds: list[MlFold]
    periods: list[MlReplayPeriod]
    periods_total: int
    periods_limit: int
    periods_offset: int
    periods_has_more: bool
    artifact_provenance: dict[str, str]


class MlJobScope(StrictModel):
    project_id: str | None = Field(default=None, max_length=64)
    experiment_id: str | None = Field(default=None, max_length=67)


class MlPrepareRequest(MlJobScope):
    input_bundle_id: OpaqueId
    exchange_id: OpaqueId | None = None


class MlInputGenerateRequest(StrictModel):
    project_id: str = Field(min_length=1, max_length=64)
    experiment_id: str = Field(pattern=r"^ex_[0-9a-f]{64}$")
    input_bundle_id: OpaqueId | None = None
    timeout_seconds: int = Field(default=3600, ge=60, le=3600)


class MlInputJobAccepted(StrictModel):
    job_id: str
    status: Literal["queued"]
    action: Literal["export-input"]
    project_id: str
    experiment_id: str = Field(pattern=r"^ex_[0-9a-f]{64}$")
    input_bundle_id: OpaqueId


class MlExperimentGenerateRequest(StrictModel):
    project_id: str = Field(min_length=1, max_length=64)
    experiment_id: str | None = Field(default=None, pattern=r"^ex_[0-9a-f]{64}$")
    timeout_seconds: int = Field(default=3600, ge=60, le=3600)


class MlExperimentJobAccepted(StrictModel):
    job_id: str
    status: Literal["queued"]
    action: Literal["generate-experiment"]
    project_id: str
    experiment_id: str = Field(pattern=r"^ex_[0-9a-f]{64}$")
    input_bundle_id: OpaqueId
    exchange_id: OpaqueId


class MlTrainRequest(MlJobScope):
    mode: Literal["fake", "real"] = "real"
    no_sync: bool = False
    timeout_seconds: int = Field(default=7200, ge=60, le=86400)


class MlReplayRequest(MlJobScope):
    starting_cash: float = Field(default=1_000_000.0, gt=0, le=1_000_000_000.0)
    periods_per_year: int = Field(default=252, ge=1, le=366)
    timeout_seconds: int = Field(default=7200, ge=60, le=86400)


class MlScopedActionRequest(MlJobScope):
    timeout_seconds: int = Field(default=600, ge=60, le=86400)


class MlJobAccepted(StrictModel):
    job_id: str
    status: Literal["queued"]
    action: Literal["prepare", "train", "import", "prepare-replay", "replay"]
    exchange_id: OpaqueId


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, _ml.MlNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, _ml.MlBusyError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/readiness", response_model=MlReadiness)
def get_readiness() -> dict[str, object]:
    """Isolation/readiness status without importing Qlib or probing any network."""
    try:
        return _ml.readiness(data_dir=data_dir())
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.get("/status", response_model=MlServiceStatus)
def get_service_status() -> dict[str, object]:
    """Compact service contract used by the ML Research workstation panel."""
    try:
        return _ml.service_status(data_dir=data_dir())
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.get("/inputs", response_model=MlInputBundlePage)
def get_inputs(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> dict[str, object]:
    """Opaque prepared input bundles; no filesystem paths are returned."""
    return _ml.list_input_bundles(data_dir=data_dir(), limit=limit, offset=offset)


@router.get("/inputs/{input_bundle_id}", response_model=MlInputBundle)
def get_input(input_bundle_id: OpaqueId) -> dict[str, object]:
    try:
        return _ml.input_bundle(input_bundle_id, data_dir=data_dir())
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/inputs/generate",
    response_model=MlInputJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_input(body: MlInputGenerateRequest) -> dict[str, object]:
    """Generate a causal, fully aligned bundle from a verified frozen snapshot via the CLI."""
    try:
        return _ml.launch_input_generation(
            data_dir=data_dir(),
            project_id=body.project_id,
            experiment_id=body.experiment_id,
            input_bundle_id=body.input_bundle_id or _ml.new_input_id(),
            timeout_seconds=body.timeout_seconds,
        )
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.get("/exchanges", response_model=MlExchangePage)
def get_exchanges(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> dict[str, object]:
    return _ml.list_exchanges(data_dir=data_dir(), limit=limit, offset=offset)


@router.get("/experiments", response_model=MlExperimentPage)
def get_experiments(
    project_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> dict[str, object]:
    """Project-aware summaries over immutable worker exchange experiments."""
    try:
        return _ml.list_experiments(
            data_dir=data_dir(), project_id=project_id, limit=limit, offset=offset
        )
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.get("/experiments/preflight", response_model=MlExperimentPreflight)
def get_experiment_preflight(
    project_id: str,
    experiment_id: str | None = None,
) -> dict[str, object]:
    """Recompute project, data, gate, worker, and capacity prerequisites without launching."""
    try:
        return _ml.experiment_preflight(
            project_id=project_id,
            experiment_id=experiment_id,
            data_dir=data_dir(),
        )
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/experiments",
    response_model=MlExperimentJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_experiment(body: MlExperimentGenerateRequest) -> dict[str, object]:
    """One-click verified snapshot export followed by immutable worker-exchange preparation."""
    try:
        preflight = _ml.experiment_preflight(
            data_dir=data_dir(),
            project_id=body.project_id,
            experiment_id=body.experiment_id,
        )
        if preflight.get("ready") is not True:
            checks = cast(list[dict[str, object]], preflight.get("checks", []))
            blocked = [
                str(check.get("message")) for check in checks if check.get("state") == "blocked"
            ]
            raise _ml.MlError("ML experiment preflight blocked: " + " ".join(blocked))
        return _ml.launch_experiment_generation(
            data_dir=data_dir(),
            project_id=body.project_id,
            experiment_id=body.experiment_id,
            timeout_seconds=body.timeout_seconds,
        )
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.get("/exchanges/{exchange_id}", response_model=MlExchangeDetail)
def get_exchange(exchange_id: OpaqueId) -> dict[str, object]:
    try:
        return _ml.exchange_detail(exchange_id, data_dir=data_dir())
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.get("/exchanges/{exchange_id}/result", response_model=MlWorkerResult)
def get_exchange_result(exchange_id: OpaqueId) -> dict[str, object]:
    """Validated portable worker completion metadata; model objects never cross this route."""
    try:
        return _ml.exchange_result(exchange_id, data_dir=data_dir())
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.get("/exchanges/{exchange_id}/evaluation", response_model=MlEvaluation)
def get_evaluation(exchange_id: OpaqueId) -> dict[str, object]:
    """Validated portable score diagnostics; not an ALPHA verdict."""
    try:
        return _ml.evaluate_exchange(exchange_id, data_dir=data_dir())
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.get("/exchanges/{exchange_id}/tear-sheet", response_model=MlTearSheet)
def get_exchange_tearsheet(
    exchange_id: OpaqueId,
    feature_limit: Annotated[int, Query(ge=1, le=158)] = 50,
    timeline_limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    timeline_offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    history_limit: Annotated[int, Query(ge=2, le=500)] = 200,
) -> dict[str, object]:
    try:
        return _ml.exchange_tearsheet(
            exchange_id,
            data_dir=data_dir(),
            feature_limit=feature_limit,
            timeline_limit=timeline_limit,
            timeline_offset=timeline_offset,
            history_limit=history_limit,
        )
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.get("/runs/{run_id}/tear-sheet", response_model=MlReplayTearSheet)
def get_replay_tearsheet(
    run_id: str,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> dict[str, object]:
    """Canonical ALPHA replay metrics and immutable ML artifact lineage."""
    try:
        return _ml.replay_tearsheet(run_id, data_dir=data_dir(), limit=limit, offset=offset)
    except (RuntimeError, OSError, pl.exceptions.PolarsError) as exc:
        raise _http_error(exc) from exc


@router.post("/prepare", response_model=MlJobAccepted, status_code=status.HTTP_202_ACCEPTED)
def prepare_exchange(body: MlPrepareRequest) -> dict[str, object]:
    exchange_id = body.exchange_id or _ml.new_exchange_id()
    try:
        return _ml.launch_action(
            "prepare",
            data_dir=data_dir(),
            input_bundle_id=body.input_bundle_id,
            exchange_id=exchange_id,
            project_id=body.project_id,
            experiment_id=body.experiment_id,
        )
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/exchanges/{exchange_id}/train",
    response_model=MlJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def train_exchange(exchange_id: OpaqueId, body: MlTrainRequest) -> dict[str, object]:
    try:
        return _ml.launch_action(
            "train",
            data_dir=data_dir(),
            exchange_id=exchange_id,
            project_id=body.project_id,
            experiment_id=body.experiment_id,
            mode=body.mode,
            no_sync=body.no_sync,
            timeout_seconds=body.timeout_seconds,
        )
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


def _scoped_action(
    action: Literal["import", "prepare-replay"],
    exchange_id: str,
    body: MlScopedActionRequest,
) -> dict[str, object]:
    try:
        return _ml.launch_action(
            action,
            data_dir=data_dir(),
            exchange_id=exchange_id,
            project_id=body.project_id,
            experiment_id=body.experiment_id,
            timeout_seconds=body.timeout_seconds,
        )
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/exchanges/{exchange_id}/import",
    response_model=MlJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def import_exchange(exchange_id: OpaqueId, body: MlScopedActionRequest) -> dict[str, object]:
    return _scoped_action("import", exchange_id, body)


@router.post(
    "/exchanges/{exchange_id}/prepare-replay",
    response_model=MlJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def prepare_replay(exchange_id: OpaqueId, body: MlScopedActionRequest) -> dict[str, object]:
    return _scoped_action("prepare-replay", exchange_id, body)


@router.post(
    "/exchanges/{exchange_id}/replay",
    response_model=MlJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def replay_exchange(exchange_id: OpaqueId, body: MlReplayRequest) -> dict[str, object]:
    try:
        return _ml.launch_action(
            "replay",
            data_dir=data_dir(),
            exchange_id=exchange_id,
            project_id=body.project_id,
            experiment_id=body.experiment_id,
            starting_cash=body.starting_cash,
            periods_per_year=body.periods_per_year,
            timeout_seconds=body.timeout_seconds,
        )
    except (RuntimeError, OSError) as exc:
        raise _http_error(exc) from exc
