"""Strict response contracts for the workstation's stable JSON API."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    mtime: float


class RunList(StrictModel):
    total: int
    items: list[RunListItem]


class RunDetail(StrictModel):
    run_id: str
    kind: str
    mtime: float
    manifest: dict[str, Any]
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


type JsonScalar = str | int | float | bool | None
type JsonObject = dict[str, JsonValue]


type ProjectStatusValue = Literal["active", "accepted", "rejected", "archived"]
type DevelopmentStageValue = Literal[
    "hypothesis",
    "data",
    "strategy",
    "baseline",
    "oos",
    "robustness",
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
type ResearchChartConstructionValue = Literal["spy_rth_60m_four_hour_window",]
type ResearchEventAvailabilityValue = Literal["second_trough_confirmable"]
type ResearchPrimaryOutcomeValue = Literal["four_trading_hour_return_25bp"]


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


class ProjectTruncation(StrictModel):
    versions: bool
    experiments: bool
    stage_states: bool
    stage_run_links: bool
    attempts: bool
    holdouts: bool
    holdout_audit: bool
    decision_packets: bool


class ProjectDetail(ProjectSummary):
    versions: list[StrategyVersion]
    experiments: list[ExperimentSpec]
    stage_states: list[ExperimentStageState]
    stage_run_links: list[StageRunLink]
    attempts: list[AttemptRecord]
    holdouts: list[HoldoutState]
    holdout_audit: list[HoldoutAuditEvent]
    decision_packets: list[DecisionPacket]
    truncated: ProjectTruncation


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
    owner_actor: str | None = Field(default=None, min_length=1, max_length=200)
    owner_reason: str | None = Field(default=None, min_length=1, max_length=8192)


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


class AgentBrief(StrictModel):
    schema_version: Literal[1]
    project_id: str
    project_name: str
    hypothesis: str
    falsification_criterion: str
    allowed_scope: AgentScope
    strategy_version: StrategyVersion | None
    experiment: ExperimentSpec | None
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
    schema_version: Literal[1]
    status: Literal["passed", "pending"]
    paper_passed: bool
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
    dockview: dict[str, Any]
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


class ResearchCaptureRequest(StrictModel):
    idea: str = Field(min_length=1, max_length=8192, pattern=r"^[^\x00]+$")
    name: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^[^\x00]+$")


class ResearchMaterialAnswers(StrictModel):
    chart_construction: ResearchChartConstructionValue
    event_availability: ResearchEventAvailabilityValue
    primary_outcome: ResearchPrimaryOutcomeValue


class ResearchProposalRequest(StrictModel):
    source_pack_id: str = Field(min_length=1, max_length=80)
    answers: ResearchMaterialAnswers


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
