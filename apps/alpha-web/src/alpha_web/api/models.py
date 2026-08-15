"""Strict response contracts for the workstation's stable JSON API."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiFieldErrorV1(StrictModel):
    field: str
    message: str


class ApiErrorV1(StrictModel):
    schema_version: Literal[1] = 1
    code: str
    message: str
    recovery_action: str
    field_errors: list[ApiFieldErrorV1]
    request_id: str


class GovernedRunContextV1(StrictModel):
    schema_version: Literal[1] = 1
    kind: Literal["governed_project"]
    project_id: str = Field(min_length=1)


class StandaloneRunContextV1(StrictModel):
    schema_version: Literal[1] = 1
    kind: Literal["standalone_sandbox"]


type RunContextV1 = Annotated[
    GovernedRunContextV1 | StandaloneRunContextV1,
    Field(discriminator="kind"),
]


class JobLaunchRequest(StrictModel):
    command: str = ""
    args: str = ""
    run_context: RunContextV1 | None = None


class RunListItem(StrictModel):
    run_id: str
    kind: str
    command: str | None
    label: str | None
    symbol: str | None
    symbols: list[str] | None
    snapshot_id: str | None
    snapshot_hash: str | None
    passed: bool | None
    verdict: str | None
    # spec §15 / ADR-0026: EXPLORATORY marker for runs launched under a research-gate override
    research_gate_watermark: str | None
    run_context_kind: Literal["governed_project", "standalone_sandbox", "legacy_context_unknown"]
    run_context_project_id: str | None
    run_context_watermark: str | None
    mtime: float


class RunList(StrictModel):
    total: int
    items: list[RunListItem]


class RunDetail(StrictModel):
    run_id: str
    kind: str
    mtime: float
    manifest: dict[str, Any]
    # spec §15 / ADR-0026: EXPLORATORY marker for runs launched under a research-gate override
    research_gate_watermark: str | None
    run_context_kind: Literal["governed_project", "standalone_sandbox", "legacy_context_unknown"]
    run_context_project_id: str | None
    run_context_watermark: str | None
    has_equity: bool
    has_trades: bool
    has_tearsheet: bool
    has_forecast: bool
    has_nulls: bool
    has_trials: bool
    has_forecast_paths: bool
    has_propfirm_paths: bool
    has_origins: bool
    has_portfolio_analytics: bool


class EquitySeries(StrictModel):
    ts: list[float]
    equity: list[float]
    drawdown: list[float]


class ForecastHistoryBar(StrictModel):
    t: float
    o: float
    h: float
    low: float = Field(alias="l", serialization_alias="l")
    c: float
    v: float


class ForecastSeries(StrictModel):
    history_ts: list[float]
    history: list[float]
    history_bars: list[ForecastHistoryBar]
    history_ohlcv_available: bool
    forecast_ts: list[float]
    forecast: list[float]
    p10: list[float]
    q25: list[float]
    q75: list[float]
    p90: list[float]
    mean: list[float]


class ForecastPath(StrictModel):
    sample: int
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]


class ForecastPaths(StrictModel):
    samples: list[ForecastPath]
    ts: list[float]


class ChartTrade(StrictModel):
    instrument_id: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_ts: float
    exit_ts: float
    realized_pnl: float
    realized_return: float


class ChartTraceEvent(StrictModel):
    sequence_id: int
    event_type: Literal["decision", "order", "fill", "trade"]
    ts: float
    parent_sequence_id: int | None
    instrument_id: str
    side: str | None
    quantity: float | None
    filled_quantity: float | None
    price: float | None
    status: str | None
    signal: int | None
    decision_reason: str | None
    entry_ts: float | None
    exit_ts: float | None
    entry_price: float | None
    exit_price: float | None
    realized_pnl: float | None
    realized_return: float | None


class ChartIndicator(StrictModel):
    sequence_id: int
    decision_sequence_id: int | None
    ts: float
    instrument_id: str
    name: str
    value: float
    unit: str


class ChartAnnotationAnchor(StrictModel):
    anchor_index: int
    ts: float
    value: float


class ChartAnnotation(StrictModel):
    annotation_id: int
    decision_sequence_id: int | None
    kind: Literal["line", "polyline", "zone"]
    label: str
    unit: str
    reason: str
    anchors: list[ChartAnnotationAnchor]


class ChartTruncation(StrictModel):
    bars: bool
    equity: bool
    trades: bool
    trace: bool
    indicators: bool
    annotations: bool


class ChartProvenance(StrictModel):
    command: str | None
    symbol: str | None
    symbols: list[str] | None
    snapshot_id: str | None
    snapshot_hash: str | None
    timezone: Literal["UTC"]
    price_unit: Literal["native_quote"]
    artifact_contract_version: int | None
    as_of: float | None
    artifact_sha256: dict[str, str]


class ChartBar(StrictModel):
    t: float
    o: float
    h: float
    low: float = Field(alias="l", serialization_alias="l")
    c: float
    v: float


class ChartFold(StrictModel):
    fold: int
    semantics: Literal["fixed_rule_evaluation_no_refit", "fold_by_fold_refit"]
    train_start: float | int
    train_end: float | int
    validation_start: float | None = None
    validation_end: float | None = None
    test_start: float | int
    test_end: float | int


class ChartBundle(StrictModel):
    run_id: str
    trace_status: Literal["available", "trace_unavailable"]
    bars_status: Literal["available", "snapshot_unavailable", "not_applicable"]
    provenance: ChartProvenance
    bars: list[ChartBar]
    equity: EquitySeries
    trades: list[ChartTrade]
    trace: list[ChartTraceEvent]
    decisions: list[ChartTraceEvent]
    orders: list[ChartTraceEvent]
    fills: list[ChartTraceEvent]
    indicators: list[ChartIndicator]
    annotations: list[ChartAnnotation]
    folds: list[ChartFold]
    forecast: ForecastSeries | None
    truncated: ChartTruncation


class NativeCalendarReturn(StrictModel):
    year: int
    month: int
    return_value: float


class NativeYearlyReturn(StrictModel):
    year: int
    return_value: float


class NativeHistogramBin(StrictModel):
    left: float
    right: float
    count: int


class NativeQQPoint(StrictModel):
    probability: float
    theoretical: float
    sample: float


class NativeRollingMetric(StrictModel):
    ts: float
    window: int
    return_value: float
    volatility: float
    sharpe: float | None
    gross_exposure: float | None
    net_exposure: float | None
    turnover: float | None
    exposure_available: bool
    turnover_available: bool


class NativeExposureTurnover(StrictModel):
    start_ts: float
    end_ts: float
    gross_exposure: float | None
    net_exposure: float | None
    turnover: float | None
    exposure_available: bool
    turnover_available: bool
    exposure_unavailable_reason: str | None
    turnover_unavailable_reason: str | None


class NativeBenchmarkComparison(StrictModel):
    ts: float
    strategy_equity: float
    benchmark_equity: float | None
    strategy_return: float | None
    benchmark_return: float | None
    excess_return: float | None
    available: bool
    benchmark_kind: str | None
    unavailable_reason: str | None


class NativeTradeStatistic(StrictModel):
    metric: str
    value: float | None
    unit: str
    available: bool
    unavailable_reason: str | None


class NativeSeriesBound(StrictModel):
    original: int
    returned: int
    truncated: bool
    sampling: Literal["all", "endpoint_uniform"]


class NativeTearSheetBounds(StrictModel):
    point_limit: int
    qq: NativeSeriesBound
    rolling: NativeSeriesBound
    exposure_turnover: NativeSeriesBound
    benchmark: NativeSeriesBound


class NativeTearSheetResponse(StrictModel):
    available: bool
    calendar_returns: list[NativeCalendarReturn]
    yearly_returns: list[NativeYearlyReturn]
    histogram: list[NativeHistogramBin]
    qq: list[NativeQQPoint]
    rolling: list[NativeRollingMetric]
    exposure_turnover: list[NativeExposureTurnover]
    benchmark: list[NativeBenchmarkComparison]
    trade_statistics: list[NativeTradeStatistic]
    exposure_available: bool
    turnover_available: bool
    benchmark_available: bool
    trade_statistics_available: bool
    provenance: dict[str, Any]
    bounds: NativeTearSheetBounds


class PortfolioAllocationRow(StrictModel):
    start_ts: float
    ts: float
    symbol: str
    weight: float
    leg_return: float
    contribution: float
    leg_gross_exposure: float
    leg_net_exposure: float
    weighted_gross_exposure: float
    weighted_net_exposure: float


class PortfolioCorrelationRow(StrictModel):
    asset_a: str
    asset_b: str
    metric_name: Literal["pearson_correlation"]
    metric_unit: Literal["coefficient"]
    correlation: float | None
    sample_count: int
    aligned_oos: Literal[True]
    frequency: Literal["1d"]
    oos_start: str | None
    oos_end: str | None
    association_not_causation: Literal[True]


class PortfolioProjectionBound(StrictModel):
    original: int
    returned: int
    truncated: bool
    sampling: Literal["all", "endpoint_uniform", "canonical_prefix"]


class PortfolioAnalyticsBounds(StrictModel):
    timestamp_limit: int
    symbol_limit: int
    allocation_timestamps: PortfolioProjectionBound
    symbols: PortfolioProjectionBound


class PortfolioAnalyticsProvenance(StrictModel):
    source_run_id: str
    source_command: Literal["backtest_portfolio"]
    snapshot_id: str | None
    snapshot_hash: str | None
    research_cutoff: str | None
    as_of: float | None
    timezone: Literal["UTC"]
    frequency: Literal["1d"]
    metric_namespace: Literal["alpha_validation.portfolio"]
    correlation_alignment: Literal["exact_pairwise_oos_timestamp_intersection"]
    allocation_semantics: Literal["causal_sleeve_weight_at_interval_start"]
    association_label: Literal["association, not causation"]
    artifact_contract_version: int | None
    artifact_sha256: dict[str, str]


class PortfolioAnalyticsResponse(StrictModel):
    symbols: list[str]
    allocations: list[PortfolioAllocationRow]
    correlations: list[PortfolioCorrelationRow]
    exposure: list[NativeExposureTurnover]
    provenance: PortfolioAnalyticsProvenance
    bounds: PortfolioAnalyticsBounds


class NullTier(StrictModel):
    tier: str
    statistics: list[float]


class NullTiers(StrictModel):
    tiers: list[NullTier]


class OptimTrial(StrictModel):
    trial: int
    returns: list[float]


class OptimTrials(StrictModel):
    trials: list[OptimTrial]


class PropfirmPathColumns(StrictModel):
    passed: list[bool]
    busted: list[bool]
    days_to_pass: list[float | None]
    payout: list[float]


class PropfirmPaths(StrictModel):
    paths: PropfirmPathColumns


class ForecastOrigins(StrictModel):
    origin_ts: list[float]
    pre_cutoff: list[bool]
    crps: list[float]
    crps_rw: list[float]
    crps_bootstrap: list[float]
    realized_end_return: list[float]
    median_end_return: list[float]
    hit: list[bool]
    cover50: list[bool]
    cover80: list[bool]
    cover90: list[bool]


class Candle(StrictModel):
    t: float
    o: float
    h: float
    low: float = Field(alias="l", serialization_alias="l")
    c: float
    v: float


class CandleProvenance(StrictModel):
    source: str
    venue: str | None
    timeframe: Literal["1D"]
    snapshot_id: str | None
    provenance_sha256: str | None
    receipt_id: str | None
    knowledge_cutoff: str | None
    quality_status: Literal["legacy_unqualified", "qualified", "passed", "owner_approved"]


class PaperCandleMarker(StrictModel):
    session_id: str
    sequence: int
    t: int
    exact_ts: int
    event_type: Literal["intent", "order", "fill", "cancel", "expired"]
    execution_mode: Literal["local_sandbox", "ibkr_paper"]
    side: str | None
    quantity: float | None
    price: float | None
    intent_id: str | None


class Candles(StrictModel):
    symbol: str
    snapshot_id: str | None
    provenance: CandleProvenance
    bars: list[Candle]
    paper_markers: list[PaperCandleMarker]


class ParamDefinition(StrictModel):
    name: str
    type: str
    default: float
    min: float | None
    max: float | None
    min_exclusive: bool
    max_exclusive: bool
    help: str


class StrategyDefinition(StrictModel):
    name: str
    params: list[ParamDefinition]
    has_tier1_surrogate: bool
    supports_live_paper: bool


class CredentialStatus(StrictModel):
    name: str
    present: bool


class ProviderOption(StrictModel):
    label: str
    choices: list[str]
    default: str


class ProviderDefinition(StrictModel):
    id: str
    label: str
    capabilities: list[str]
    network_required: bool
    credential_env: list[CredentialStatus]
    options: dict[str, ProviderOption]
    limitations: list[str]
    asset_classes: list[str]
    timeframes: list[str]
    research_authority: bool
    paper_execution: bool
    budget_tier: str
    installed: bool
    configured: bool
    configuration_state: Literal[
        "not_installed",
        "optional_disabled",
        "needs_process_injection",
        "process_injected_unverified",
        "available_without_credentials",
    ]
    verification_state: Literal[
        "verified",
        "unverified",
        "authentication_failed",
        "entitlement_denied",
        "rate_limited",
        "connectivity_failed",
        "schema_drift",
        "optional_disabled",
    ]
    verified_at: str | None
    last_receipt_id: str | None
    granted_capabilities: list[str]
    recovery_action: str


class ProviderCheckReceipt(StrictModel):
    schema_version: Literal[1]
    provider_id: str
    verification_state: Literal[
        "verified",
        "unverified",
        "authentication_failed",
        "entitlement_denied",
        "rate_limited",
        "connectivity_failed",
        "schema_drift",
        "optional_disabled",
    ]
    checked_at: str
    granted_capabilities: list[str]
    recovery_action: str
    details: dict[str, object]
    receipt_id: str
    content_sha256: str


class SystemDataDirectory(StrictModel):
    path: str
    exists: bool
    readable: bool
    writable: bool
    free_bytes: int


class SystemCounts(StrictModel):
    symbols: int
    snapshots: int


class NautilusStatus(StrictModel):
    pinned_version: str
    installed_version: str | None
    matches_pin: bool


class KronosCacheStatus(StrictModel):
    configured: bool
    path: str | None
    exists: bool
    local_only: bool


class SystemStatus(StrictModel):
    data_dir: SystemDataDirectory
    counts: SystemCounts
    nautilus: NautilusStatus
    kronos_cache: KronosCacheStatus
    paper_enabled: bool
    ibkr_paper_enabled: bool


class CommandOption(StrictModel):
    name: str
    flag: str | None
    type: str
    default: str | int | float | bool | list[str] | None
    required: bool
    multiple: bool
    help: str
    choices: list[str] | None


class CommandArgument(StrictModel):
    name: str
    type: str
    required: bool
    nargs: int


class CommandDefinition(StrictModel):
    id: str
    run_type: str | None
    args: list[CommandArgument]
    options: list[CommandOption]


class Symbols(StrictModel):
    symbols: list[str]


class JobStatus(StrictModel):
    job_id: str
    status: str
    session_id: str | None


class JobSummary(StrictModel):
    job_id: str
    command: str
    kind: str | None
    status: str
    created_at: float
    finished_at: float | None
    elapsed_seconds: float
    command_path: str
    current_step: str
    progress_mode: Literal["indeterminate", "estimated", "terminal"]
    progress_fraction: float | None
    eta_seconds: float | None
    eta_sample_count: int
    run_id: str | None
    session_id: str | None
    returncode: int | None
    n_lines: int


class JobDetail(JobSummary):
    lines: list[str]


type CryptoFamilyValue = Literal[
    "market_bars",
    "trades",
    "aggregate_trades",
    "book_snapshots",
    "market_membership",
    "instrument_catalog",
    "derivative_bars",
    "derivative_trades",
    "derivative_book_snapshots",
    "funding",
    "open_interest",
    "long_short_ratio",
    "mark_bars",
    "index_bars",
    "premium_bars",
    "option_instruments",
    "option_quotes",
    "historical_volatility",
    "asset_metadata",
    "market_reference",
    "onchain_catalog",
    "onchain_metrics",
    "dex_pools",
    "dex_ohlcv",
    "dex_transactions",
    "comparison_bars",
]
type CryptoProviderValue = Literal[
    "binance", "bybit", "coingecko", "geckoterminal", "coinmetrics", "ccxt:coinbase"
]
type CryptoQualificationStateValue = Literal[
    "unverified", "unavailable", "qualified", "warning", "quarantined"
]


class CryptoAuthorityRow(StrictModel):
    family: CryptoFamilyValue
    provider: str
    role: Literal["primary_acquisition", "diagnostic_comparison"]


class CryptoCatalogResponse(StrictModel):
    families: list[CryptoAuthorityRow]
    automatic_fallback: Literal[False]
    execution_authority: Literal[False]
    next_action: str


class CryptoCapabilityItem(StrictModel):
    schema_version: Literal[1]
    provider: str
    family: CryptoFamilyValue
    authentication: Literal["none", "demo_key"]
    earliest: str | None
    latest: str | None
    frequencies: list[str]
    limits: list[str]
    verification_state: Literal["not_verified", "receipt_verified"]
    qualification_state: CryptoQualificationStateValue


class CryptoCapabilitiesResponse(StrictModel):
    items: list[CryptoCapabilityItem]
    count: int = Field(ge=0)
    receipt_verified_count: int = Field(ge=0)
    qualified_count: int = Field(ge=0)
    provider_probe_performed: Literal[False]
    automatic_fallback: Literal[False]
    execution_authority: Literal[False]
    canonical_next_action: str


class CryptoStorageResponse(StrictModel):
    state: Literal["ready", "blocked"]
    blocker: str | None
    bulk_root_label: str
    manifest_count: int = Field(ge=0)
    next_action: str
    free_bytes: int | None = Field(default=None, ge=0)
    total_bytes: int | None = Field(default=None, ge=0)
    reserve_fraction: float | None = Field(default=None, ge=0, lt=1)
    minimum_free_bytes: int | None = Field(default=None, ge=0)
    cache_bytes: int = Field(ge=0)


class CryptoStorageInventoryResponse(StrictModel):
    manifest_count: int = Field(ge=0)
    snapshot_count: int = Field(ge=0)
    counts_by_kind: dict[str, int]
    bytes_by_kind: dict[str, int]
    cache_bytes: int = Field(ge=0)
    staging_count: int = Field(ge=0)
    private_paths_exposed: Literal[False]
    next_action: str


class CryptoStorageVerifyResponse(StrictModel):
    state: Literal["verified"]
    manifest_count: int = Field(ge=0)
    snapshot_count: int = Field(ge=0)
    research_eligible_snapshot_count: int = Field(ge=0)
    asset_master_count: int = Field(ge=0)
    cache_bytes: int = Field(ge=0)
    private_paths_exposed: Literal[False]
    next_action: str


class CryptoCacheCleanRequest(StrictModel):
    confirm: Literal[True]


class CryptoCacheCleanResponse(StrictModel):
    state: Literal["cleaned"]
    removed_bytes: int = Field(ge=0)
    immutable_artifacts_removed: Literal[0]
    private_paths_exposed: Literal[False]
    next_action: str


class CryptoEstimateRequest(StrictModel):
    family: CryptoFamilyValue
    instruments: int = Field(default=1, ge=1, le=250)
    days: int = Field(default=30, ge=1, le=3_650)
    frequency: Literal["1d", "4h", "1h", "30m", "15m", "5m", "1m", "tick"] = "1d"


class CryptoEstimateResponse(StrictModel):
    family: CryptoFamilyValue
    provider: str
    instruments: int
    days: int
    frequency: str
    estimated_rows: int = Field(ge=0)
    estimated_bytes: int = Field(ge=0)
    bounded: Literal[True]
    estimate_only: Literal[True]
    next_action: str


class CryptoCoverageItem(StrictModel):
    manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: str
    venue: str
    market_type: Literal["spot", "linear", "inverse", "option", "dex", "network", "reference"]
    family: CryptoFamilyValue
    instrument: str
    base_asset: str | None
    quote_asset: str | None
    frequency: str
    units: str
    timestamp_convention: str
    state: CryptoQualificationStateValue
    failures: list[str]
    warnings: list[str]
    observed_start: str | None
    observed_end: str | None
    row_count: int = Field(ge=0)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_version: str
    fetched_at: str | None


class CryptoCoverageResponse(StrictModel):
    items: list[CryptoCoverageItem]
    count: int = Field(ge=0)
    canonical_next_action: str
    automatic_fallback: Literal[False]
    execution_authority: Literal[False]


class CryptoAssetIdentityResponse(StrictModel):
    schema_version: Literal[1]
    coingecko_id: str
    network: str
    contract_address: str | None
    native_asset: bool
    provider_symbols: list[tuple[str, str]]
    valid_from: str
    valid_to: str | None
    migration_lineage: list[str]


class CryptoQualityReportResponse(StrictModel):
    schema_version: Literal[1]
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_version: str
    state: CryptoQualificationStateValue
    failures: list[str]
    warnings: list[str]
    observed_start: str | None
    observed_end: str | None
    row_count: int = Field(ge=0)
    correction_lineage: list[str]


class CryptoDatasetIdentityResponse(StrictModel):
    provider: str
    venue: str
    market_type: Literal["spot", "linear", "inverse", "option", "dex", "network", "reference"]
    family: CryptoFamilyValue
    instrument: str
    base_asset: str | None
    quote_asset: str | None
    frequency: str
    units: str
    timestamp_convention: str


class CryptoQualityResponse(StrictModel):
    manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset: CryptoDatasetIdentityResponse
    quality: CryptoQualityReportResponse
    next_action: str


type CryptoFeatureNameValue = Literal[
    "funding",
    "open_interest_change",
    "basis",
    "volatility_surface",
    "liquidity",
    "onchain_change",
]


class CryptoFeatureCreateRequest(StrictModel):
    feature_name: CryptoFeatureNameValue
    inputs: dict[str, str] = Field(min_length=1, max_length=3)


class CryptoFeatureResponse(StrictModel):
    manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    feature_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    feature_name: CryptoFeatureNameValue
    method_version: str
    available_at: str
    row_count: int = Field(ge=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_count: int = Field(ge=1, le=3)
    state: Literal["frozen", "verified"]
    research_authority: Literal[False]
    execution_authority: Literal[False]
    next_action: str | None = None


class CryptoFeatureListResponse(StrictModel):
    items: list[CryptoFeatureResponse]
    count: int = Field(ge=0)
    research_authority: Literal[False]
    execution_authority: Literal[False]
    next_action: str


type CryptoCoverageCadenceValue = Literal["daily", "hourly", "five_minute", "funding_interval"]


class CryptoCoverageTaskResponse(StrictModel):
    schema_version: Literal[1]
    task_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: str
    family: CryptoFamilyValue
    instrument: str
    base_asset: str | None
    quote_asset: str | None
    category: str | None
    frequency: str
    cadence: CryptoCoverageCadenceValue
    network: str | None
    metrics: list[str]
    lookback_days: int | None
    execution_authority: Literal[False]


class CryptoCoverageProfileSummaryResponse(StrictModel):
    profile_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    as_of: str
    source_manifest_ids: list[str]
    task_count: int = Field(ge=1, le=10_000)
    counts_by_provider: dict[str, int]
    counts_by_cadence: dict[str, int]
    counts_by_family: dict[str, int]
    execution_authority: Literal[False]


class CryptoCoverageProfileListResponse(StrictModel):
    items: list[CryptoCoverageProfileSummaryResponse]
    count: int = Field(ge=0)
    execution_authority: Literal[False]
    next_action: str


class CryptoCoverageProfileCreateRequest(StrictModel):
    as_of: str | None = Field(default=None, max_length=64)


class CryptoCoverageProfileCreateResponse(CryptoCoverageProfileSummaryResponse):
    state: Literal["frozen"]
    binance_hourly_scopes: list[list[str]]
    binance_hourly_missing_scopes: list[list[str]]
    next_action: str


class CryptoCoverageProfileFiltersResponse(StrictModel):
    provider: str | None
    family: str | None
    category: str | None
    frequency: str | None
    cadence: str | None


class CryptoCoverageProfilePageResponse(CryptoCoverageProfileSummaryResponse):
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    filtered_count: int = Field(ge=0, le=10_000)
    filters: CryptoCoverageProfileFiltersResponse
    items: list[CryptoCoverageTaskResponse]
    has_more: bool
    next_offset: int | None
    next_action: str


class CryptoCoverageBatchRequest(StrictModel):
    cadence: CryptoCoverageCadenceValue
    offset: int = Field(default=0, ge=0, le=10_000)
    limit: int = Field(default=10, ge=1, le=25)
    confirm: Literal[True]


class CryptoCoverageBatchResumeRequest(StrictModel):
    confirm: Literal[True]


class CryptoCoverageBatchResponse(StrictModel):
    batch_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    cadence: CryptoCoverageCadenceValue
    profile_offset: int = Field(ge=0)
    task_count: int = Field(ge=1, le=25)
    completed_count: int = Field(ge=0, le=25)
    state: Literal["pending", "running", "failed", "completed"]
    error: str | None
    recovery_action: str | None
    updated_at: str
    execution_authority: Literal[False]


class CryptoCoverageBatchListResponse(StrictModel):
    items: list[CryptoCoverageBatchResponse]
    count: int = Field(ge=0)
    execution_authority: Literal[False]
    next_action: str


class CryptoLiquidityFreezeRequest(StrictModel):
    category: Literal["spot", "linear", "inverse"]
    quote_asset: Literal["USD", "USDT"]
    session: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    limit: int = Field(default=250, ge=1, le=250)


class CryptoLiquidityFreezeResponse(StrictModel):
    manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    session: str
    category: Literal["spot", "linear", "inverse"]
    quote_asset: Literal["USD", "USDT"]
    universe_count: int = Field(ge=1)
    selected_count: int = Field(ge=1, le=250)
    state: Literal["frozen"]
    execution_authority: Literal[False]
    next_action: str


class CryptoOneMinuteSelectionRequest(StrictModel):
    case_id: str = Field(min_length=1, max_length=128)
    expected_case_revision: str = Field(min_length=1, max_length=128)
    markets: list[str] = Field(min_length=1, max_length=50)
    reason: str = Field(min_length=1, max_length=500)


class CryptoOneMinuteSelectionResponse(StrictModel):
    profile_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    base_profile_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_id: str
    case_revision: str
    selected_count: int = Field(ge=1, le=50)
    frequency: Literal["1m"]
    acquisition_window: Literal["previous_complete_hour"]
    state: Literal["frozen"]
    execution_authority: Literal[False]
    next_action: str


class CryptoAcquisitionRequest(StrictModel):
    provider: CryptoProviderValue
    family: CryptoFamilyValue
    instrument: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:/-]+$")
    base: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    quote: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    category: Literal["spot", "linear", "inverse", "option"] = "linear"
    frequency: Literal["1d", "4h", "1h", "30m", "15m", "5m", "1m"] = "1h"
    period: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    network: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    pool_address: str | None = Field(default=None, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")
    metrics: list[str] = Field(default_factory=list, max_length=32)
    start: str | None = Field(default=None, max_length=64)
    end: str | None = Field(default=None, max_length=64)
    case_id: str | None = Field(default=None, min_length=1, max_length=80)
    expected_case_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reason: str | None = Field(default=None, min_length=1, max_length=500)


class CryptoSnapshotCreateRequest(StrictModel):
    manifest_ids: list[str] = Field(min_length=1, max_length=128)
    asset_master_version: str = Field(
        default="reviewed-native-v1", pattern=r"^(?:reviewed-native-v1|[0-9a-f]{64})$"
    )


class CryptoSnapshotCreateResponse(StrictModel):
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    member_count: int = Field(ge=1)
    families: list[CryptoFamilyValue]
    providers: list[str]
    asset_master_version: str
    state: Literal["frozen"]
    next_action: str
    execution_authority: Literal[False]


class CryptoAssetMasterCreateRequest(StrictModel):
    coingecko_manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    geckoterminal_manifest_ids: list[str] = Field(min_length=1, max_length=5)


class CryptoAssetMasterResponse(StrictModel):
    asset_master_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_count: int = Field(ge=2)
    contract_identity_count: int = Field(ge=0)
    ticker_join_allowed: Literal[False]
    state: Literal["frozen", "verified"]
    next_action: str
    source_manifest_ids: list[str] | None = None


class CryptoAssetMasterListItem(StrictModel):
    asset_master_version: str
    identity_count: int = Field(ge=2)
    contract_identity_count: int = Field(ge=0)
    builtin: bool
    state: Literal["verified"]


class CryptoAssetMasterListResponse(StrictModel):
    items: list[CryptoAssetMasterListItem]
    count: int = Field(ge=1)
    ticker_join_allowed: Literal[False]
    next_action: str


class CryptoSnapshotVerifyRequest(StrictModel):
    required_families: list[CryptoFamilyValue] = Field(default_factory=list, max_length=20)
    purpose: Literal["research", "validation", "execution_price"] = "research"


class CryptoSnapshotVerifyResponse(StrictModel):
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligible: bool
    purpose: Literal["research", "validation", "execution_price"]
    qualified_families: list[CryptoFamilyValue]
    supplemental_families: list[CryptoFamilyValue]
    blockers: list[str]
    next_action: str
    execution_authority: Literal[False]


class CryptoSnapshotRegisterRequest(StrictModel):
    symbol: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9-]+$")


class CryptoSnapshotRegisterResponse(StrictModel):
    ref_id: str = Field(pattern=r"^rd_[0-9a-f]{64}$")
    dataset_kind: Literal["snapshot"]
    instrument: str
    provider: Literal["crypto-data-house"]
    start_ts: str
    end_ts: str
    bar_duration_minutes: int | None
    origin: JsonObject
    research_only: Literal[True]
    registered_by: str
    registered_at: str


type JsonScalar = str | int | float | bool | None
type JsonObject = dict[str, JsonValue]


type ProjectStatusValue = Literal["active", "accepted", "rejected", "archived"]
type ResearchGateStateValue = Literal["not_required", "open", "passed", "overridden"]
type DevelopmentStageValue = Literal[
    "hypothesis",
    "data",
    "strategy",
    "baseline",
    "oos",
    "robustness",
    "monte_carlo",
    "optimization",
    "portfolio",
    "candidate",
    "holdout",
    "paper",
    "decision",
    "kronos",
    "ml",
]
type StageStateValue = Literal[
    "not_started", "ready", "queued", "running", "pass", "warning", "fail", "stale"
]
type PublicStageStateValue = Literal["not_started", "ready", "queued", "running", "stale"]
type AttemptStatusValue = Literal[
    "queued",
    "running",
    "completed",
    "passed",
    "warning",
    "failed",
    "pruned",
    "rejected",
    "cancelled",
]
type ControlJobStatusValue = Literal["queued", "running", "succeeded", "failed", "cancelled"]
type SuiteActionValue = Literal[
    "baseline",
    "inner_oos",
    "three_null_families",
    "monte_carlo",
    "optimize_grid",
    "fixed_stress",
    "portfolio_cross_asset",
    "qlib",
    "kronos",
    "holdout_reveal",
    "paper_preflight",
]
type EvidenceStatusValue = Literal["draft", "corroborated", "rejected", "superseded"]
type AuthorKindValue = Literal["human", "agent"]
type ResearchPhaseValue = Literal[
    "captured",
    "triage",
    "exploration_review",
    "pilot",
    "deep_research",
    "confirmation_review",
    "sealed_confirmation",
    "research_decision",
    "closed",
]
type ResearchExecutionStateValue = Literal[
    "idle", "queued", "running", "paused", "blocked", "failed"
]
type ResearchD2StateValue = Literal["sealed", "authorized", "consumed", "contaminated"]
type ResearchD3StateValue = Literal["not_sealed", "sealed", "consumed", "contaminated"]
type ResearchChartConstructionValue = Literal[
    "spy_rth_60m_four_hour_window",
    "tiingo_daily_fallback",
    "bybit_btcusdt_linear_hourly",
]
type ResearchEventAvailabilityValue = Literal[
    "second_trough_confirmable", "bybit_funding_event_point_in_time"
]
type ResearchPrimaryOutcomeValue = Literal[
    "four_trading_hour_return_25bp",
    "next_regular_session_return_50bp",
    "next_funding_mark_minus_index_5bp",
]


class ProjectCreateRequest(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str = Field(min_length=1, max_length=8192)
    falsification_criterion: str = Field(min_length=1, max_length=8192)


class ProjectSummary(StrictModel):
    project_id: str
    name: str
    hypothesis: str
    falsification_criterion: str
    status: ProjectStatusValue
    current_version_id: str | None
    current_experiment_id: str | None
    created_at: str
    updated_at: str
    research_gate_state: ResearchGateStateValue


class ResearchGateOverride(StrictModel):
    project_id: str
    sequence: int
    actor: str
    reason: str
    recorded_at: str


class ActiveResearchGateOverride(ResearchGateOverride):
    project_name: str


class ProjectPage(StrictModel):
    items: list[ProjectSummary]
    limit: int
    offset: int
    has_more: bool


class StrategyVersionCreateRequest(StrictModel):
    strategy_name: str = Field(min_length=1, max_length=200)
    source_fingerprint: str = Field(min_length=1, max_length=512)
    definition: JsonObject = Field(default_factory=dict)
    parameter_space: JsonObject = Field(default_factory=dict)


class StrategyVersion(StrictModel):
    version_id: str
    strategy_name: str
    source_fingerprint: str
    definition: JsonObject
    parameter_space: JsonObject
    created_at: str


class ExperimentCreateRequest(StrictModel):
    version_id: str
    snapshot_id: str = Field(min_length=1, max_length=8192)
    universe: list[str] = Field(min_length=1, max_length=512)
    split_policy: JsonObject
    costs: JsonObject
    seeds: JsonObject
    stage_config: JsonObject = Field(default_factory=dict)


class ExperimentSpec(StrictModel):
    experiment_id: str
    strategy_version_id: str
    snapshot_id: str
    universe: list[str]
    split_policy: JsonObject
    costs: JsonObject
    seeds: JsonObject
    stage_config: JsonObject
    created_at: str


class StageLinkCreateRequest(StrictModel):
    experiment_id: str
    stage: DevelopmentStageValue
    state: PublicStageStateValue
    run_id: str = Field(pattern=r"^[0-9a-f]{16}$")


class StageStateRequest(StrictModel):
    state: PublicStageStateValue
    reason: str = Field(min_length=1, max_length=8192)


class ExperimentStageTransitionRequest(StrictModel):
    state: Literal["ready", "queued", "running", "pass", "warning", "fail", "stale"]
    reason: str = Field(min_length=1, max_length=8192)


class StageStateEvent(StrictModel):
    sequence: int
    state: StageStateValue
    occurred_at: str
    reason: str


class ExperimentStageState(StrictModel):
    project_id: str
    experiment_id: str
    stage: DevelopmentStageValue
    state: StageStateValue
    state_history: list[StageStateEvent]
    state_history_truncated: bool = False


class StageRunLink(StrictModel):
    link_id: str
    project_id: str
    experiment_id: str
    stage: str
    run_id: str
    linked_at: str
    state: StageStateValue
    state_history: list[StageStateEvent]
    state_history_truncated: bool = False


class AttemptRecord(StrictModel):
    attempt_id: str
    project_id: str
    experiment_id: str
    stage: str
    status: AttemptStatusValue
    config_fingerprint: str
    run_id: str | None
    error: str | None
    details: JsonObject
    recorded_at: str


class AttemptCreateRequest(StrictModel):
    experiment_id: str
    stage: DevelopmentStageValue
    status: AttemptStatusValue
    config_fingerprint: str = Field(min_length=1, max_length=512)
    run_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    error: str | None = Field(default=None, max_length=8192)
    details: JsonObject = Field(default_factory=dict)


class HoldoutState(StrictModel):
    project_id: str
    experiment_id: str
    sealed_at: str
    sealed_by: str
    sealed_version_id: str
    seal_reason: str
    revealed_at: str | None
    revealed_by: str | None
    revealed_version_id: str | None
    reveal_reason: str | None
    contaminated_at: str | None
    contamination_reason: str | None
    holdout_spec_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    start_date: str | None = None
    end_date: str | None = None


class HoldoutSealRequest(StrictModel):
    experiment_id: str
    actor: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=8192)
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class HoldoutAuditEvent(StrictModel):
    audit_id: int
    project_id: str
    experiment_id: str
    event: Literal["sealed", "revealed", "contaminated"]
    actor: str
    occurred_at: str
    reason: str
    version_id: str


class DecisionRequest(StrictModel):
    verdict: Literal["accept", "reject", "revise"]
    actor: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=8192)
    negative_results_acknowledged: Literal[True]


class DecisionPacket(StrictModel):
    packet_id: str
    packet_hash: str
    schema_version: Literal[1]
    project_id: str
    experiment_id: str
    strategy_version_id: str
    verdict: Literal["accept", "reject", "revise"]
    actor: str
    reason: str
    negative_results_acknowledged: Literal[True]
    negative_result_attempt_ids: list[str]
    stage_evidence: JsonObject
    deployment_scope: Literal["sandbox_only"]
    places_real_orders: Literal[False]
    created_at: str


class MonteCarloReview(StrictModel):
    review_id: str
    schema_version: Literal[1]
    project_id: str
    experiment_id: str
    decision: Literal["continue", "revise", "reject"]
    actor: str
    rationale: str
    evidence_hashes_json: str
    evidence_hashes: list[tuple[str, str]]
    recorded_at: str


class ProjectTruncation(StrictModel):
    versions: bool
    experiments: bool
    stage_states: bool
    stage_run_links: bool
    attempts: bool
    holdouts: bool
    holdout_audit: bool
    decision_packets: bool
    monte_carlo_reviews: bool
    research_gate_overrides: bool


class ProjectDetail(ProjectSummary):
    versions: list[StrategyVersion]
    experiments: list[ExperimentSpec]
    stage_states: list[ExperimentStageState]
    stage_run_links: list[StageRunLink]
    attempts: list[AttemptRecord]
    holdouts: list[HoldoutState]
    holdout_audit: list[HoldoutAuditEvent]
    decision_packets: list[DecisionPacket]
    monte_carlo_reviews: list[MonteCarloReview]
    truncated: ProjectTruncation
    research_gate_overrides: list[ResearchGateOverride]


class ControlJobCreateRequest(StrictModel):
    kind: str = Field(min_length=1, max_length=100)
    request: JsonObject = Field(default_factory=dict)
    project_id: str | None = None
    experiment_id: str | None = None


class ControlJob(StrictModel):
    job_id: str
    kind: str
    status: ControlJobStatusValue
    project_id: str | None
    experiment_id: str | None
    request: JsonObject
    created_at: str
    updated_at: str
    heartbeat_at: str
    result_run_id: str | None
    terminal_error: str | None
    last_sequence: int


class ControlJobEvent(StrictModel):
    job_id: str
    sequence: int
    event_type: Literal[
        "created", "status", "heartbeat", "progress", "log", "result", "cancel_requested"
    ]
    occurred_at: str
    payload: JsonObject


class ControlJobDetail(ControlJob):
    events: list[ControlJobEvent]
    event_total: int
    events_has_more: bool
    events_truncated: bool
    event_limit: int
    event_offset: int
    event_tail: bool


class ControlJobPage(StrictModel):
    items: list[ControlJob]
    limit: int
    offset: int
    has_more: bool


class SuiteStep(StrictModel):
    index: int
    label: str
    command: list[str]
    evidence_role: str


class SuitePlan(StrictModel):
    schema_version: Literal[1]
    project_id: str
    experiment_id: str
    action: SuiteActionValue
    stage: DevelopmentStageValue
    ready: bool
    blockers: list[str]
    resolved_experiment: ExperimentSpec
    resolved_strategy_version: StrategyVersion
    current_stage_state: StageStateValue
    estimated_workload: JsonObject
    steps: list[SuiteStep]
    governance: JsonObject


class SuiteRunRequest(StrictModel):
    """Empty by design: the web suite launcher accepts no caller-asserted authority."""


class SuiteLaunch(StrictModel):
    job_id: str
    status: Literal["starting"]
    plan: SuitePlan


class SuiteCancelResponse(StrictModel):
    job_id: str
    status: Literal["cancellation_requested", "already_terminal"]


class JobReconcileResponse(StrictModel):
    items: list[ControlJob]
    count: int


class EvidenceDraftRequest(StrictModel):
    claim: str = Field(min_length=1, max_length=8192)
    assets: list[str] = Field(min_length=1, max_length=512)
    frozen_universe: list[str] = Field(min_length=1, max_length=512)
    timeframe: str = Field(default="1d", min_length=1, max_length=32)
    method: str = Field(min_length=1, max_length=200)
    knowledge_at: str
    market_data_cutoff: str | None = None
    author: str = Field(min_length=1, max_length=200)
    author_kind: AuthorKindValue
    project_id: str | None = None
    strategy_version_id: str | None = None
    experiment_id: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    metric_unit: str | None = None
    source_run_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    source_artifact: str = Field(min_length=1, max_length=80)
    source_field: str = Field(min_length=1, max_length=8192)
    row_selector: JsonObject = Field(default_factory=dict)
    counterevidence: list[str] = Field(default_factory=list, max_length=256)
    contradiction_ids: list[str] = Field(default_factory=list, max_length=256)


class EvidenceReviewRequest(StrictModel):
    status: EvidenceStatusValue
    author: str = Field(min_length=1, max_length=200)
    author_kind: AuthorKindValue
    claim: str | None = Field(default=None, max_length=8192)
    counterevidence: list[str] | None = Field(default=None, min_length=1, max_length=256)
    contradiction_ids: list[str] | None = Field(default=None, min_length=1, max_length=256)
    source_run_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    source_artifact: str | None = Field(default=None, max_length=80)
    source_field: str | None = Field(default=None, max_length=8192)
    row_selector: JsonObject | None = None


class EvidenceRecord(StrictModel):
    evidence_id: str
    revision: int
    parent_revision: int | None
    status: EvidenceStatusValue
    claim: str
    assets: list[str]
    frozen_universe: list[str]
    timeframe: str
    method: str
    market_data_cutoff: str | None
    knowledge_at: str
    project_id: str | None
    strategy_version_id: str | None
    experiment_id: str | None
    metric_name: str | None
    metric_value: float | None
    metric_unit: str | None
    source_run_id: str
    source_artifact: str
    source_field: str
    row_selector: JsonObject
    counterevidence: list[str]
    contradiction_ids: list[str]
    author: str
    author_kind: AuthorKindValue
    created_at: str
    interpretation_label: Literal["association, not causation"] | None


class EvidenceDetail(EvidenceRecord):
    revisions: list[EvidenceRecord]
    revisions_truncated: bool
    revision_limit: int
    revision_offset: int


class EvidencePage(StrictModel):
    items: list[EvidenceRecord]
    limit: int
    offset: int
    has_more: bool


class AgentScope(StrictModel):
    version_id: str | None
    experiment_id: str | None
    snapshot_id: str | None
    universe: list[str]


class AgentStageStatus(StrictModel):
    stage: str
    state: StageStateValue
    run_id: str | None


class ResearchPromotionReference(StrictModel):
    packet_id: str
    contract_id: str
    gate_packet_id: str | None
    gate_packet_hash: str | None
    recorded_at: str


class AgentBrief(StrictModel):
    schema_version: Literal[1]
    project_id: str
    project_name: str
    hypothesis: str
    falsification_criterion: str
    allowed_scope: AgentScope
    strategy_version: StrategyVersion | None
    experiment: ExperimentSpec | None
    research_promotion: ResearchPromotionReference | None
    stage_statuses: list[AgentStageStatus]
    evidence: list[EvidenceRecord]
    evidence_truncated: bool
    knowledge_cutoff: str | None
    required_tests: list[str]
    warnings: list[str]


class PaperSession(StrictModel):
    schema_version: int
    session_id: str
    status: Literal["starting", "running", "stopping", "completed", "cancelled", "failed"]
    provider: str
    paper: Literal[True]
    sandbox: bool
    execution_mode: Literal["local_sandbox", "ibkr_paper"]
    account_alias: str | None
    risk_profile_id: str
    decision_artifact_id: str | None
    reconciliation_state: Literal["not_applicable", "pending", "matched", "mismatch", "halted"]
    symbol: str
    instrument_id: str
    strategy: str
    strategy_params: dict[str, JsonScalar]
    snapshot_id: str
    pid: int | None
    heartbeat_at: str
    started_at: str
    ended_at: str | None
    last_sequence: int
    terminal_error: str | None
    stale: bool


class PaperEvent(StrictModel):
    schema_version: int
    session_id: str
    sequence: int
    event_type: Literal[
        "lifecycle",
        "intent",
        "risk_check",
        "connection",
        "account_snapshot",
        "order",
        "fill",
        "cancel",
        "expired",
        "rejection",
        "position",
        "reconciliation",
        "reconciliation_warning",
    ]
    recorded_at: str
    ts_event_ns: int | None
    payload: dict[str, JsonScalar]


class PaperReadinessEvidence(StrictModel):
    session_id: str
    sequence: int
    event_type: str
    execution_mode: Literal["local_sandbox", "ibkr_paper"]


class PaperReadinessRequirement(StrictModel):
    id: str
    passed: bool
    evidence: list[PaperReadinessEvidence]


class PaperReadinessBlocker(StrictModel):
    session_id: str
    sequence: int
    event_type: str


class PaperReadinessReport(StrictModel):
    schema_version: Literal[2]
    status: Literal["passed", "pending"]
    paper_passed: bool
    plans: list[dict[str, object]]
    predicates: dict[str, bool]
    tamper_detected: bool
    legacy_journals: Literal["monitoring_only"]
    what_if_credit: Literal[False]
    requirements: list[PaperReadinessRequirement]
    blocking_events: list[PaperReadinessBlocker]
    futures_research_supported: Literal[False]
    live_capital_routing: Literal["absent"]
    derived_from_elapsed_time: Literal[False]


class WorkspaceMeta(StrictModel):
    slug: str
    name: str
    updated: float | None


class WorkspaceSaved(StrictModel):
    slug: str
    name: str


class WorkspaceGroupLinkedContext(StrictModel):
    projectId: str | None = None
    versionId: str | None = None
    symbol: str | None = None
    universe: str | None = None
    timeframe: Literal["1D"] = "1D"
    start: str | None = None
    end: str | None = None
    snapshotId: str | None = None
    runId: str | None = None


class WorkspaceLinkedContext(WorkspaceGroupLinkedContext):
    schemaVersion: Literal[3] = 3
    linkGroup: Literal["A", "B", "C", "D"] = "A"
    groups: dict[Literal["A", "B", "C", "D"], WorkspaceGroupLinkedContext] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class WorkspaceDocument(StrictModel):
    name: str
    linked_context: WorkspaceLinkedContext
    #: Retired. A workspace used to be a window arrangement; it is now the research
    #: context you were working in. Documents saved by the old shell still carry a
    #: layout blob, so the field is read and ignored rather than rejected.
    dockview: dict[str, Any] | None = None
    updated: float | None = None


class Deleted(StrictModel):
    deleted: str


class RiskScenario(StrictModel):
    name: str
    sharpe: float | None
    annual_vol: float
    max_drawdown: float
    value_at_risk: float
    expected_shortfall: float
    total_return: float


class RiskProvenance(StrictModel):
    source_run_id: str
    source_command: str | None
    source_artifact: Literal["equity_curve.parquet"]
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str | None
    snapshot_hash: str | None
    research_cutoff: str | None
    as_of: str | None
    timezone: Literal["UTC"]
    derived_projection: Literal[True]
    metric_namespace: Literal["alpha_validation.scenario"]
    periods_per_year: int
    confidence: float


class RiskReport(StrictModel):
    run_id: str
    confidence: float
    scenarios: list[RiskScenario]
    provenance: RiskProvenance


class ScreenerQuote(StrictModel):
    symbol: str
    current: float
    change: float
    percent_change: float
    high: float
    low: float
    open: float
    prev_close: float


class ScreenerNewsItem(StrictModel):
    headline: str
    source: str
    url: str
    datetime: int
    summary: str


class ScreenerNews(StrictModel):
    symbol: str
    items: list[ScreenerNewsItem]


class ResearchRow(StrictModel):
    strategy: str
    total_return: float | None
    final_equity: float | None = None
    n_trades: int | None = None
    error: str | None


class ResearchReport(StrictModel):
    symbol: str
    n_bars: int
    ranked: list[ResearchRow]
    comparison_status: Literal["preferred", "tie", "no_trades", "not_comparable"]
    preferred_strategy: str | None
    preference_reason: str | None


class ResearchCaptureRequest(StrictModel):
    idea: str = Field(min_length=1, max_length=8192, pattern=r"^[^\x00]+$")
    name: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^[^\x00]+$")


class ResearchMaterialAnswers(StrictModel):
    chart_construction: ResearchChartConstructionValue
    event_availability: ResearchEventAvailabilityValue
    primary_outcome: ResearchPrimaryOutcomeValue


class ResearchProposalRequest(StrictModel):
    source_pack_id: str = Field(min_length=1, max_length=80)
    answer_bundle_id: str = Field(min_length=1, max_length=80)
    dataset_ref_id: str | None = Field(default=None, min_length=1, max_length=80)
    expected_case_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResearchMaterialChoiceV1(StrictModel):
    id: str
    label: str
    consequence: str
    availability: Literal["available", "unavailable"]
    blocked_reason: str | None


class ResearchMaterialQuestionV1(StrictModel):
    id: str
    prompt: str
    blocking_reason: str
    choices: list[ResearchMaterialChoiceV1]
    recommended_answer_bundle_id: str | None


class ResearchAnswerBundleV1(StrictModel):
    bundle_id: str
    label: str
    answers: ResearchMaterialAnswers
    requires_dataset: bool
    compatible_dataset_ids: list[str]
    available: bool
    blocked_reason: str | None


class ResearchSourcePackOptionV1(StrictModel):
    pack_id: str
    project_id: str
    source_ids: list[str]
    definition: JsonObject
    created_at: str


class ResearchProposalBlockerV1(StrictModel):
    code: str
    message: str
    recovery_action: str


class ResearchProposalOptionsV1(StrictModel):
    proposal_schema: Literal["ResearchProposalOptionsV1"]
    project_id: str
    case_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    material_questions: list[ResearchMaterialQuestionV1]
    recommended_answer_bundle_id: str | None
    valid_answer_bundles: list[ResearchAnswerBundleV1]
    compatible_source_packs: list[ResearchSourcePackOptionV1]
    compatible_datasets: list[ResearchDatasetRefRow]
    blockers: list[ResearchProposalBlockerV1]
    approval_ready: bool


class ResearchLaunchRequest(StrictModel):
    stage: Literal["pilot"]


class ResearchReviewEvent(StrictModel):
    contract_id: str
    sequence: int
    project_id: str
    scope: Literal["exploration", "confirmation"]
    decision: Literal["approve", "reject"]
    actor: str
    actor_kind: AuthorKindValue
    occurred_at: str
    reason: str


class ResearchContract(StrictModel):
    contract_id: str
    project_id: str
    scope: Literal["exploration", "confirmation"]
    parent_contract_id: str | None
    payload: JsonObject
    created_by: str
    author_kind: AuthorKindValue
    created_at: str
    review_state: Literal["pending", "approved", "rejected"]
    latest_review: ResearchReviewEvent | None


class ResearchReviewSummary(StrictModel):
    state: Literal["pending", "approved", "rejected"]
    event: ResearchReviewEvent | None


class ResearchDecisionEvent(StrictModel):
    project_id: str
    sequence: int
    contract_id: str
    outcome: Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"]
    disposition: Literal["advance_to_strategy", "revise", "park", "reject"]
    actor: str
    actor_kind: AuthorKindValue
    occurred_at: str
    reason: str


class ResearchMilestone(StrictModel):
    phase: ResearchPhaseValue
    contract_id: str
    occurred_at: str
    reason: str


class ResearchD2Event(StrictModel):
    contract_id: str
    state: ResearchD2StateValue
    boundary_hash: str
    actor: str
    occurred_at: str
    reason: str


class ResearchPriority(StrictModel):
    falsifiability: float = Field(ge=0)
    data_readiness: float = Field(ge=0)
    novelty: float = Field(ge=0)
    information_gain_per_cost: float = Field(ge=0)


class ResearchBudgetProjection(StrictModel):
    approved_units: float = Field(ge=0)
    consumed_units: float = Field(ge=0)
    unit: Literal["minutes", "compute_units"]


class ResearchCaseSummaryRow(StrictModel):
    case_id: str
    title: str
    original_idea: str
    phase: ResearchPhaseValue
    execution_state: ResearchExecutionStateValue
    outcome: Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"] | None
    disposition: Literal["advance_to_strategy", "revise", "park", "reject"] | None
    next_action: str
    responsibility: Literal["owner", "codex"]
    latest_finding: str | None
    blocker: str | None
    recovery_action: str | None
    completed_milestones: int = Field(ge=0)
    total_milestones: int = Field(ge=0)
    owner_pinned: bool
    priority: ResearchPriority
    budget: ResearchBudgetProjection
    updated_at: str


class ResearchCasePage(StrictModel):
    items: list[ResearchCaseSummaryRow]
    limit: int
    offset: int
    has_more: bool


class HypothesisCardField(StrictModel):
    field_id: Literal[
        "research_question",
        "phenomenon",
        "population",
        "condition_event",
        "dependent_variable",
        "horizon",
        "expected_direction",
        "economic_mechanism",
        "null_hypothesis",
        "alternative_hypothesis",
        "baseline",
        "confounders",
        "falsification_criteria",
        "success_criteria",
    ]
    label: str
    value: str | None
    status: Literal["complete", "partial", "missing"]


class HypothesisCardPlanFamily(StrictModel):
    family: str
    multiplicity: str


class HypothesisCardPlan(StrictModel):
    family_count: int = Field(ge=1)
    families: list[HypothesisCardPlanFamily]


class HypothesisCard(StrictModel):
    card_schema: Literal["HypothesisCardV1"]
    fields: list[HypothesisCardField]
    complete_fields: int = Field(ge=0)
    total_fields: Literal[14]
    analysis_plan: HypothesisCardPlan | None = None


class ResearchScorecardDimension(StrictModel):
    dimension_id: Literal[
        "hypothesis_definition",
        "data_quality",
        "sample_adequacy",
        "effect_existence",
        "effect_size",
        "temporal_stability",
        "cross_asset_stability",
        "regime_robustness",
        "falsification",
        "mechanism",
        "literature",
        "data_mining_risk",
    ]
    label: str
    state: str
    basis: str


class ResearchScorecardQuestions(StrictModel):
    count: int = Field(ge=0)
    items: list[str]


class ResearchScorecardRecommendation(StrictModel):
    value: Literal[
        "READY FOR STRATEGY RESEARCH",
        "MORE RESEARCH REQUIRED",
        "REFORMULATE HYPOTHESIS",
        "EVIDENCE DOES NOT SUPPORT CONTINUATION",
    ]
    reasons: list[str]


class ResearchReadinessBlocker(StrictModel):
    code: str
    evidence_refs: list[str] = Field(min_length=1)


class ResearchReadinessProjection(StrictModel):
    state: Literal["ready", "blocked"]
    blockers: list[ResearchReadinessBlocker]


class ResearchScorecard(StrictModel):
    scorecard_schema: Literal["ResearchReadinessScorecardV1"]
    dimensions: list[ResearchScorecardDimension]
    unresolved_questions: ResearchScorecardQuestions
    recommendation: ResearchScorecardRecommendation
    confirmation_readiness: ResearchReadinessProjection
    promotion_readiness: ResearchReadinessProjection


class ResearchContextPacket(StrictModel):
    packet_id: str = Field(pattern=r"^cp_[0-9a-f]{64}$")
    project_id: str
    packet_kind: Literal[
        "asset", "research_case", "experiment", "chart", "validation", "strategy_promotion"
    ]
    protocol_id: str | None
    protocol_content_hash: str | None
    payload: JsonObject
    created_by: str
    created_at: str


class ResearchContextPacketPage(StrictModel):
    items: list[ResearchContextPacket]
    limit: int
    offset: int


class ResearchNote(StrictModel):
    note_id: str = Field(pattern=r"^rn_[0-9a-f]{64}$")
    project_id: str
    sequence: int = Field(ge=1)
    note_kind: Literal[
        "critique", "confounder_review", "test_design", "completeness_review", "synthesis"
    ]
    body: str
    author: str
    author_kind: Literal["owner", "agent"]
    context_packet_id: str | None
    created_at: str


class ResearchNotePage(StrictModel):
    items: list[ResearchNote]
    limit: int
    offset: int


class ResearchDatasetRefRow(StrictModel):
    ref_id: str = Field(pattern=r"^rd_[0-9a-f]{64}$")
    dataset_kind: Literal["store_slice", "snapshot", "quantpad_receipt"]
    instrument: str
    provider: str
    start_ts: str
    end_ts: str
    bar_duration_minutes: int | None
    origin: JsonObject
    research_only: Literal[True]
    registered_by: str
    registered_at: str
    latest_audit: JsonObject | None


class ResearchDatasetPage(StrictModel):
    items: list[ResearchDatasetRefRow]
    limit: int
    offset: int


class ResearchProtocolEntry(StrictModel):
    id: str
    title: str
    purpose: str
    packet_kind: Literal[
        "asset", "research_case", "experiment", "chart", "validation", "strategy_promotion"
    ]
    output_contract: str
    file: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResearchProtocolLibrary(StrictModel):
    protocols: list[ResearchProtocolEntry]


class HubSource(StrictModel):
    source_id: str
    title: str
    locator: str
    provider: str
    access_mode: str
    screening: str | None
    extraction_id: str | None
    extraction_status: str | None
    page_count: int | None
    character_count: int | None
    extraction_warnings: list[str]


class HubFinding(StrictModel):
    finding_id: str
    status: str
    summary: str | None


class HubFindings(StrictModel):
    findings: list[HubFinding]


class HubConfounder(StrictModel):
    text: str
    status: Literal["resolved", "unresolved"]


class HubFalsifier(StrictModel):
    text: str
    result: str


class HubOverview(StrictModel):
    original_idea: str
    phase: ResearchPhaseValue
    execution_state: ResearchExecutionStateValue
    next_action: str
    responsibility: Literal["owner", "codex"]
    latest_finding: str | None
    outstanding_questions: list[str]
    hypothesis_card: HypothesisCard
    scorecard: ResearchScorecard


class HubData(StrictModel):
    registered_datasets: list[JsonObject]
    status: str
    note: str


class HubLiterature(StrictModel):
    claims: list[JsonObject]
    sources: list[HubSource]
    source_packs: list[JsonObject]
    recommendation: JsonObject
    status: str


class LiteratureDiscoveryRequest(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    unpaywall_email: str = Field(min_length=3, max_length=320)
    max_candidates: int = Field(default=20, ge=1, le=20)
    max_full_texts: int = Field(default=5, ge=0, le=5)


class LiteratureAcquisitionRequest(StrictModel):
    discovery_id: str = Field(pattern=r"^ld_[0-9a-f]{64}$")
    candidate_id: str = Field(pattern=r"^lc_[0-9a-f]{64}$")


class HubMechanism(StrictModel):
    mechanism: str | None
    interpretation: str | None
    alternatives: list[str]
    confounders: list[HubConfounder]


class HubExploration(StrictModel):
    charts: list[JsonObject]
    watermark: Literal["EXPLORATORY"]
    status: str


class HubAttempt(StrictModel):
    attempt_id: str
    phase: str
    kind: str
    status: str
    config_fingerprint: str
    run_id: str | None
    recorded_at: str


class HubExperiments(StrictModel):
    attempts: list[HubAttempt]


class HubFalsification(StrictModel):
    falsifiers: list[HubFalsifier]
    stop_rules: list[str]


class HubRobustness(StrictModel):
    findings: list[HubFinding]
    status: str


class HubDecision(StrictModel):
    outcome: Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"] | None
    disposition: Literal["advance_to_strategy", "revise", "park", "reject"] | None
    d2_state: ResearchD2StateValue
    d3_state: ResearchD3StateValue
    packet_id: str | None
    packet_hash: str | None


class ResearchEvidenceHubSections(StrictModel):
    overview: HubOverview
    data: HubData
    literature: HubLiterature
    mechanism: HubMechanism
    exploration: HubExploration
    experiments: HubExperiments
    evidence_for: HubFindings
    evidence_against: HubFindings
    falsification: HubFalsification
    robustness: HubRobustness
    decision: HubDecision


class ResearchEvidenceHub(StrictModel):
    hub_schema: Literal["ResearchEvidenceHubV1"]
    project_id: str
    sections: ResearchEvidenceHubSections


class ResearchCase(StrictModel):
    schema_version: Literal[1]
    project_id: str
    project_name: str
    phase: ResearchPhaseValue
    execution_state: ResearchExecutionStateValue
    active_contract_id: str
    active_contract: ResearchContract
    exploration_contract_id: str
    confirmation_contract_id: str | None
    exploration_review: ResearchReviewSummary
    confirmation_review: ResearchReviewSummary
    research_decision: ResearchDecisionEvent | None
    next_action: str
    responsibility: Literal["owner", "codex"]
    blocker: str | None
    recovery: str | None
    latest_finding: str | None
    milestones: list[ResearchMilestone]
    completed_milestones: list[ResearchMilestone]
    remaining_milestones: list[ResearchPhaseValue]
    elapsed_time_seconds: float = Field(ge=0)
    elapsed_budget: JsonObject
    remaining_budget: JsonObject
    active_job_id: str | None
    checkpoint: str | None
    hashes: JsonObject
    source_pack_id: str | None
    attempt_count: int = Field(ge=0)
    terminal_attempt_count: int = Field(ge=0)
    unfinalized_launch_count: int = Field(ge=0)
    remaining_launches: int = Field(ge=0)
    latest_launch_reservation_id: str | None
    latest_launch_number: int | None = Field(ge=1, le=3)
    latest_attempt_id: str | None
    latest_run_id: str | None
    latest_run_fingerprint: str | None
    d2_state: ResearchD2StateValue
    d2_boundary_hash: str
    d2_history: list[ResearchD2Event]
    d3_state: ResearchD3StateValue
    # Additive projections present on the status read; store-level case payloads
    # (capture/proposal/launch responses) omit them, so they default to None.
    hypothesis_card: HypothesisCard | None = None
    scorecard: ResearchScorecard | None = None
    confirmation_readiness: ResearchReadinessProjection | None = None
    promotion_readiness: ResearchReadinessProjection | None = None


class ResearchCaptureResponse(StrictModel):
    project: ProjectSummary
    contract: ResearchContract
    case: ResearchCase


class ResearchProposalResponse(StrictModel):
    contract: ResearchContract
    case: ResearchCase


class ResearchAttempt(StrictModel):
    attempt_id: str
    project_id: str
    contract_id: str
    phase: ResearchPhaseValue
    kind: str
    status: AttemptStatusValue
    config_fingerprint: str
    budget_used: JsonObject
    run_id: str | None
    error: str | None
    details: JsonObject
    recorded_at: str
    launch_reservation_id: str | None = None


class ResearchLaunchResponse(StrictModel):
    manifest: JsonObject
    attempt: ResearchAttempt
    case: ResearchCase


class ResearchProgressReport(StrictModel):
    report_schema: Literal["ResearchProgressReportV1"]
    terminal: Literal[False]
    case: ResearchCase
    warning: str


class ResearchGateAuthority(StrictModel):
    evidence_claim: Literal["point-in-time-valid predictive association"]
    strategy_validated: Literal[False]
    paper_ready: Literal[False]
    places_orders: Literal[False]
    uses_final_strategy_holdout: Literal[False]


class ResearchGateUncertainty(StrictModel):
    lower: float
    upper: float
    level: float = Field(gt=0, lt=1)
    method: str


class ResearchGatePracticalMagnitude(StrictModel):
    status: Literal["CLEARS_HURDLE", "BELOW_HURDLE", "INCONCLUSIVE", "NOT_TESTED"]
    value: float | None
    unit: str | None
    interpretation: str


class ResearchGatePrimaryResult(StrictModel):
    status: Literal["TESTED", "NOT_TESTED"]
    estimate: float | None
    unit: str | None
    sample_size: int | None = Field(default=None, ge=1)
    effective_sample_size: float | None = Field(default=None, gt=0)
    uncertainty: ResearchGateUncertainty | None
    practical_magnitude: ResearchGatePracticalMagnitude


class ResearchGateFinding(StrictModel):
    status: Literal[
        "PASSED",
        "FAILED",
        "STABLE",
        "UNSTABLE",
        "SUPPORTED",
        "CONTRADICTED",
        "INCONCLUSIVE",
        "NOT_TESTED",
        "OBSERVED",
    ]
    summary: str | None


class ResearchGateConfounders(StrictModel):
    resolved: list[str]
    unresolved: list[str]


class ResearchGateStability(StrictModel):
    parameter: ResearchGateFinding
    temporal: ResearchGateFinding
    transportability: ResearchGateFinding


class ResearchGateConfirmationChecks(StrictModel):
    corrected_primary_test_passed: bool
    interval_registered_direction: bool
    economic_hurdle_cleared: bool
    interval_wholly_against_direction: bool


class ResearchGateConclusion(StrictModel):
    project_name: str
    thesis: str
    thesis_answer: str
    scientific_outcome: Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"]
    recommended_disposition: Literal["advance_to_strategy", "revise", "park", "reject"]
    owner_decision_reason: str
    evidence_basis: Literal["SEALED_D2", "EXPLORATORY_D1", "NO_TYPED_NON_SYNTHETIC_EVIDENCE"]
    primary_estimate: float | None
    uncertainty: ResearchGateUncertainty | None
    effective_sample_size: float | None
    practical_magnitude: ResearchGatePracticalMagnitude
    strongest_caveat: str


class ResearchGateGuidedEvidence(StrictModel):
    primary_result: ResearchGatePrimaryResult
    confirmation_classification: (
        Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"] | None
    )
    confirmation_checks: ResearchGateConfirmationChecks | None
    mechanism: ResearchGateFinding
    strongest_support: ResearchGateFinding
    strongest_contradiction: ResearchGateFinding
    confounders: ResearchGateConfounders
    stability: ResearchGateStability
    multiplicity: ResearchGateFinding
    power: ResearchGateFinding
    negative_controls: ResearchGateFinding
    untested_work: list[str]
    what_would_change_conclusion: list[str]
    teaching_note: str


class ResearchGateAuditLedgers(StrictModel):
    phase_events: list[JsonObject]
    review_events: list[JsonObject]
    execution_events: list[JsonObject]
    d2_events: list[JsonObject]
    decision_events: list[JsonObject]


class ResearchGateLedgerCounts(StrictModel):
    contracts: int = Field(ge=0)
    source_packs: int = Field(ge=0)
    sources: int = Field(ge=0)
    attempts: int = Field(ge=0)
    launch_reservations: int = Field(ge=0)
    launch_attempt_links: int = Field(ge=0)
    phase_events: int = Field(ge=0)
    review_events: int = Field(ge=0)
    execution_events: int = Field(ge=0)
    d2_events: int = Field(ge=0)
    decision_events: int = Field(ge=0)
    artifact_links: int = Field(ge=0)


class ResearchGateLedgerBounds(StrictModel):
    maximum_rows_per_input_ledger: Literal[10_000]
    truncated: Literal[False]
    counts: ResearchGateLedgerCounts


class ResearchGateTechnicalAppendix(StrictModel):
    project: JsonObject
    contract_lineage: list[JsonObject]
    source_pack_ledger: list[JsonObject]
    source_ledger: list[JsonObject]
    variant_ledger: list[JsonObject]
    attempt_ledger: list[JsonObject]
    launch_reservation_ledger: list[JsonObject]
    launch_attempt_link_ledger: list[JsonObject]
    budget_ledger: list[JsonObject]
    phase_review_d2_ledgers: ResearchGateAuditLedgers
    immutable_artifact_links: list[JsonObject]
    selected_evidence: JsonObject | None
    ledger_bounds: ResearchGateLedgerBounds


class ResearchGateLayers(StrictModel):
    conclusion_90_seconds: ResearchGateConclusion
    guided_evidence: ResearchGateGuidedEvidence
    technical_appendix: ResearchGateTechnicalAppendix


class ResearchGatePacket(StrictModel):
    report_schema: Literal["ResearchGatePacketV1"]
    schema_version: Literal[1]
    terminal: Literal[True]
    packet_id: str = Field(pattern=r"^rgp_[0-9a-f]{64}$")
    packet_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_id: str
    active_contract_id: str
    scientific_outcome: Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"]
    recommended_disposition: Literal["advance_to_strategy", "revise", "park", "reject"]
    authority: ResearchGateAuthority
    layers: ResearchGateLayers


type ResearchCaseReport = Annotated[
    ResearchProgressReport | ResearchGatePacket,
    Field(discriminator="report_schema"),
]


class ResearchChecklistQuestion(StrictModel):
    question_id: str
    number: int = Field(ge=1, le=14)
    question: str
    binding: str
    status: str
    answer: str


class ResearchEdgeChecklist(StrictModel):
    checklist_schema: Literal["ResearchEdgeChecklistV1"]
    questions: list[ResearchChecklistQuestion] = Field(min_length=14, max_length=14)


class ResearchDecisionHistoryEvent(StrictModel):
    sequence: int
    contract_id: str
    outcome: Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"]
    disposition: Literal["advance_to_strategy", "revise", "park", "reject"]
    actor: str
    actor_kind: AuthorKindValue
    occurred_at: str
    reason: str


class ResearchDecisionView(StrictModel):
    view_schema: Literal["ResearchDecisionViewV1"]
    project_id: str
    phase: str
    d2_state: str
    next_action: str
    checklist: ResearchEdgeChecklist
    scorecard: ResearchScorecard
    confirmation_readiness: ResearchReadinessProjection
    promotion_readiness: ResearchReadinessProjection
    gate_packet: ResearchGatePacket | None
    decision_history: list[ResearchDecisionHistoryEvent]


class OptionGreeks(StrictModel):
    spot: float
    strike: float
    rate: float
    vol: float
    days: float
    kind: str
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    implied_vol: float | None = None
    market_price: float | None = None


class OptionCurvePoint(StrictModel):
    spot: float
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float


class OptionCurve(StrictModel):
    strike: float
    vol: float
    days: float
    rate: float
    kind: str
    points: list[OptionCurvePoint] = Field(min_length=2)


class FigureCatalogueItem(StrictModel):
    """One catalogue entry as it applies to a specific run."""

    figure_id: str
    title: str
    summary: str
    section: str
    panel_count: int
    available: bool
    unavailable_reason: str | None


class FigureCatalogue(StrictModel):
    run_id: str
    kind: str | None
    renderer_version: int
    items: list[FigureCatalogueItem]


class FigurePanelMeta(StrictModel):
    panel_id: str
    y_label: str
    y_unit: str
    note: str | None
    legend: list[str]


class FigureMetadata(StrictModel):
    """A figure's text and structure, served without its bytes.

    ``alt_text`` and the four teaching strings are the accessibility path for figures
    whose SVG text is embedded as glyph outlines and therefore invisible to a screen
    reader; the page renders them as real HTML beside the image.
    """

    figure_id: str
    title: str
    subtitle: str
    caption: str
    alt_text: str
    x_label: str
    question: str
    plain_language_answer: str
    uncertainty: str
    caveat: str
    truncation_note: str | None
    source_artifacts: list[str]
    panels: list[FigurePanelMeta]
    renderer_version: int
    cache_key: str
    format: str
    width_in: float
    height_in: float
    image_url: str
    etag: str
