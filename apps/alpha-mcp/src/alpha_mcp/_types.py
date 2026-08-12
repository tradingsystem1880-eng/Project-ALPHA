"""Stable structured-output contracts for Workstation v3 MCP tools.

The CLI remains authoritative at runtime.  These ``TypedDict`` declarations make FastMCP publish
bounded, named output schemas instead of an opaque ``dict[str, Any]`` contract.
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

type JsonObject = dict[str, Any]
type BoundedJsonValue = (
    None | bool | int | float | str | list[BoundedJsonValue] | dict[str, BoundedJsonValue]
)
type LegacyRunManifestOut = dict[str, BoundedJsonValue]
type ProjectStatus = Literal["active", "accepted", "rejected", "archived"]
type ResearchGateState = Literal["not_required", "open", "passed", "overridden"]
type StageState = Literal[
    "not_started", "ready", "queued", "running", "pass", "warning", "fail", "stale"
]
type AttemptStatus = Literal[
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
type JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
type EvidenceStatus = Literal["draft", "corroborated", "rejected", "superseded"]
type AuthorKind = Literal["human", "agent"]
type SuiteAction = Literal[
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


class LegacyRunSummaryOut(TypedDict):
    run_id: str
    command: str | None
    label: str | None


class ProjectSummaryOut(TypedDict):
    project_id: str
    name: str
    hypothesis: str
    falsification_criterion: str
    status: ProjectStatus
    current_version_id: str | None
    current_experiment_id: str | None
    created_at: str
    updated_at: str
    research_gate_state: ResearchGateState


class ResearchGateOverrideOut(TypedDict):
    project_id: str
    sequence: int
    actor: str
    reason: str
    recorded_at: str


class ProjectPageOut(TypedDict):
    items: list[ProjectSummaryOut]
    limit: int
    offset: int
    has_more: bool


class ResearchCaseOut(TypedDict):
    schema_version: int
    project_id: str
    project_name: str
    phase: str
    execution_state: str
    active_contract_id: str
    active_contract: JsonObject
    exploration_contract_id: str
    confirmation_contract_id: str | None
    exploration_review: JsonObject
    confirmation_review: JsonObject
    research_decision: JsonObject | None
    next_action: str
    responsibility: Literal["owner", "codex"]
    blocker: str | None
    recovery: str | None
    latest_finding: str | None
    milestones: list[JsonObject]
    completed_milestones: list[JsonObject]
    remaining_milestones: list[str]
    elapsed_time_seconds: float
    elapsed_budget: JsonObject
    remaining_budget: JsonObject
    active_job_id: str | None
    checkpoint: str | None
    hashes: JsonObject
    source_pack_id: str | None
    attempt_count: int
    terminal_attempt_count: int
    unfinalized_launch_count: int
    remaining_launches: int
    latest_launch_reservation_id: str | None
    latest_launch_number: int | None
    latest_attempt_id: str | None
    latest_run_id: str | None
    latest_run_fingerprint: str | None
    d2_state: str
    d2_boundary_hash: str
    d2_history: list[JsonObject]
    d3_state: str
    # Additive status-read projections; capture/proposal/launch case payloads omit them.
    hypothesis_card: NotRequired[JsonObject]
    scorecard: NotRequired[JsonObject]


class SourceSearchOut(TypedDict):
    items: list[JsonObject]
    limit: int
    offset: int


class SourceClaimOut(TypedDict):
    claim_id: str
    revision: int
    project_id: str
    source_id: str
    contract_id: str
    claim_text: str
    direction: str
    strength: str
    method_summary: str
    sample_summary: str
    markets: list[str]
    limitations: str
    status: str
    author: str
    author_kind: str
    screened_by: str | None
    created_at: str
    source_anchor: NotRequired[JsonObject | None]
    anchor_state: NotRequired[str]


class DataInventoryOut(TypedDict):
    symbols: list[str]


class DataCandlesOut(TypedDict):
    symbol: str
    snapshot_id: str | None
    provenance: JsonObject
    bars: list[JsonObject]
    truncated: bool


class SnapshotListOut(TypedDict):
    snapshots: list[JsonObject]


class ProviderRegistryOut(TypedDict):
    providers: list[JsonObject]


class ResearchContextPacketOut(TypedDict):
    packet_id: str
    project_id: str
    packet_kind: str
    protocol_id: str | None
    protocol_content_hash: str | None
    payload: JsonObject
    created_by: str
    created_at: str


class ResearchNoteOut(TypedDict):
    note_id: str
    project_id: str
    sequence: int
    note_kind: str
    body: str
    author: str
    author_kind: str
    context_packet_id: str | None
    created_at: str


class ResearchProtocolListOut(TypedDict):
    protocols: list[JsonObject]


class ResearchProtocolOut(TypedDict):
    id: str
    title: str
    purpose: str
    packet_kind: str
    output_contract: str
    file: str
    sha256: str
    content: str


class ResearchBriefOut(TypedDict):
    brief_schema: str
    case: JsonObject
    changes: JsonObject
    next_action: str
    packet_id: str


class ResearchCaptureOut(TypedDict):
    project: ProjectSummaryOut
    contract: JsonObject
    case: ResearchCaseOut


class ResearchProposalOut(TypedDict):
    contract: JsonObject
    case: ResearchCaseOut


class ResearchLaunchOut(TypedDict):
    manifest: JsonObject
    attempt: JsonObject
    case: ResearchCaseOut


class ResearchProgressReportOut(TypedDict):
    report_schema: Literal["ResearchProgressReportV1"]
    terminal: Literal[False]
    case: ResearchCaseOut
    warning: str


class ResearchGatePacketOut(TypedDict):
    report_schema: Literal["ResearchGatePacketV1"]
    schema_version: Literal[1]
    terminal: Literal[True]
    packet_id: str
    packet_hash: str
    project_id: str
    active_contract_id: str
    scientific_outcome: Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"]
    recommended_disposition: Literal["advance_to_strategy", "revise", "park", "reject"]
    authority: JsonObject
    layers: JsonObject


type ResearchReportOut = ResearchProgressReportOut | ResearchGatePacketOut


class StrategyVersionOut(TypedDict):
    version_id: str
    strategy_name: str
    source_fingerprint: str
    definition: JsonObject
    parameter_space: JsonObject
    created_at: str


class ExperimentSpecOut(TypedDict):
    experiment_id: str
    strategy_version_id: str
    snapshot_id: str
    universe: list[str]
    split_policy: JsonObject
    costs: JsonObject
    seeds: JsonObject
    stage_config: JsonObject
    created_at: str


class StageStateEventOut(TypedDict):
    sequence: int
    state: StageState
    occurred_at: str
    reason: str


class ExperimentStageStateOut(TypedDict):
    project_id: str
    experiment_id: str
    stage: str
    state: StageState
    state_history: list[StageStateEventOut]
    state_history_truncated: bool


class StageRunLinkOut(TypedDict):
    link_id: str
    project_id: str
    experiment_id: str
    stage: str
    run_id: str
    linked_at: str
    state: StageState
    state_history: list[StageStateEventOut]
    state_history_truncated: bool


class AttemptRecordOut(TypedDict):
    attempt_id: str
    project_id: str
    experiment_id: str
    stage: str
    status: AttemptStatus
    config_fingerprint: str
    run_id: str | None
    error: str | None
    details: JsonObject
    recorded_at: str


class HoldoutStateOut(TypedDict):
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
    holdout_spec_hash: str | None
    start_date: str | None
    end_date: str | None


class DecisionPacketOut(TypedDict):
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


class MonteCarloReviewOut(TypedDict):
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


class HoldoutAuditEventOut(TypedDict):
    audit_id: int
    project_id: str
    experiment_id: str
    event: Literal["sealed", "revealed", "contaminated"]
    actor: str
    occurred_at: str
    reason: str
    version_id: str


class ProjectTruncationOut(TypedDict):
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


class ProjectDetailOut(ProjectSummaryOut):
    versions: list[StrategyVersionOut]
    experiments: list[ExperimentSpecOut]
    stage_states: list[ExperimentStageStateOut]
    stage_run_links: list[StageRunLinkOut]
    attempts: list[AttemptRecordOut]
    holdouts: list[HoldoutStateOut]
    holdout_audit: list[HoldoutAuditEventOut]
    decision_packets: list[DecisionPacketOut]
    monte_carlo_reviews: list[MonteCarloReviewOut]
    truncated: ProjectTruncationOut
    research_gate_overrides: list[ResearchGateOverrideOut]


class SuiteStepOut(TypedDict):
    index: int
    label: str
    command: list[str]
    evidence_role: str


class SuitePlanOut(TypedDict):
    schema_version: Literal[1]
    project_id: str
    experiment_id: str
    action: SuiteAction
    stage: str
    ready: bool
    blockers: list[str]
    resolved_experiment: ExperimentSpecOut
    resolved_strategy_version: StrategyVersionOut
    current_stage_state: StageState
    estimated_workload: JsonObject
    steps: list[SuiteStepOut]
    governance: JsonObject


class SuiteLaunchOut(TypedDict):
    job_id: str
    status: Literal["starting"]
    plan: SuitePlanOut


class AgentScopeOut(TypedDict):
    version_id: str | None
    experiment_id: str | None
    snapshot_id: str | None
    universe: list[str]


class AgentStageStatusOut(TypedDict):
    stage: str
    state: StageState
    run_id: str | None


class EvidenceRecordOut(TypedDict):
    evidence_id: str
    revision: int
    parent_revision: int | None
    status: EvidenceStatus
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
    author_kind: AuthorKind
    created_at: str
    interpretation_label: Literal["association, not causation"] | None


class ResearchPromotionReferenceOut(TypedDict):
    packet_id: str
    contract_id: str
    gate_packet_id: str | None
    gate_packet_hash: str | None
    recorded_at: str


class AgentBriefOut(TypedDict):
    schema_version: Literal[1]
    project_id: str
    project_name: str
    hypothesis: str
    falsification_criterion: str
    allowed_scope: AgentScopeOut
    strategy_version: StrategyVersionOut | None
    experiment: ExperimentSpecOut | None
    research_promotion: ResearchPromotionReferenceOut | None
    stage_statuses: list[AgentStageStatusOut]
    evidence: list[EvidenceRecordOut]
    evidence_truncated: bool
    knowledge_cutoff: str | None
    required_tests: list[str]
    warnings: list[str]


class ControlJobOut(TypedDict):
    job_id: str
    kind: str
    status: JobStatus
    project_id: str | None
    experiment_id: str | None
    request: JsonObject
    created_at: str
    updated_at: str
    heartbeat_at: str
    result_run_id: str | None
    terminal_error: str | None
    last_sequence: int


class ControlJobEventOut(TypedDict):
    job_id: str
    sequence: int
    event_type: Literal[
        "created", "status", "heartbeat", "progress", "log", "result", "cancel_requested"
    ]
    occurred_at: str
    payload: JsonObject


class ControlJobDetailOut(ControlJobOut):
    events: list[ControlJobEventOut]
    event_total: int
    events_has_more: bool
    events_truncated: bool
    event_limit: int
    event_offset: int
    event_tail: bool


class ControlJobPageOut(TypedDict):
    items: list[ControlJobOut]
    limit: int
    offset: int
    has_more: bool


class JobCancellationOut(TypedDict):
    job_id: str
    status: Literal["cancellation_requested", "already_terminal"]


class JobReconciliationOut(TypedDict):
    items: list[ControlJobOut]
    count: int


class EvidenceDetailOut(EvidenceRecordOut):
    revisions: list[EvidenceRecordOut]
    revisions_truncated: bool


class EvidencePageOut(TypedDict):
    items: list[EvidenceRecordOut]
    limit: int
    offset: int
    has_more: bool


ChartBarOut = TypedDict(  # noqa: UP013 - wire key `l` is required and E741 rejects a class field.
    "ChartBarOut",
    {"t": float, "o": float, "h": float, "l": float, "c": float, "v": float},
)


class EquitySeriesOut(TypedDict):
    ts: list[float]
    equity: list[float]
    drawdown: list[float]


class ChartTradeOut(TypedDict):
    instrument_id: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_ts: float
    exit_ts: float
    realized_pnl: float
    realized_return: float


class ChartTraceEventOut(TypedDict):
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


class ChartIndicatorOut(TypedDict):
    sequence_id: int
    decision_sequence_id: int | None
    ts: float
    instrument_id: str
    name: str
    value: float
    unit: str


class ChartAnnotationAnchorOut(TypedDict):
    anchor_index: int
    ts: float
    value: float


class ChartAnnotationOut(TypedDict):
    annotation_id: int
    decision_sequence_id: int | None
    kind: Literal["line", "polyline", "zone"]
    label: str
    unit: str
    reason: str
    anchors: list[ChartAnnotationAnchorOut]


class ChartFoldOut(TypedDict):
    fold: int
    semantics: Literal["fixed_rule_evaluation_no_refit", "fold_by_fold_refit"]
    train_start: float | int
    train_end: float | int
    validation_start: float | int | None
    validation_end: float | int | None
    test_start: float | int
    test_end: float | int


class ForecastSeriesOut(TypedDict):
    history: list[float]
    forecast: list[float]
    p10: list[float]
    q25: list[float]
    q75: list[float]
    p90: list[float]
    mean: list[float]
    history_ts: list[float]
    forecast_ts: list[float]


class ChartProvenanceOut(TypedDict):
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


class ChartTruncationOut(TypedDict):
    bars: bool
    equity: bool
    trades: bool
    trace: bool
    indicators: bool
    annotations: bool


class ChartBundleOut(TypedDict):
    run_id: str
    trace_status: Literal["available", "trace_unavailable"]
    bars_status: Literal["available", "snapshot_unavailable", "not_applicable"]
    provenance: ChartProvenanceOut
    bars: list[ChartBarOut]
    equity: EquitySeriesOut
    trades: list[ChartTradeOut]
    trace: list[ChartTraceEventOut]
    decisions: list[ChartTraceEventOut]
    orders: list[ChartTraceEventOut]
    fills: list[ChartTraceEventOut]
    indicators: list[ChartIndicatorOut]
    annotations: list[ChartAnnotationOut]
    folds: list[ChartFoldOut]
    forecast: ForecastSeriesOut | None
    truncated: ChartTruncationOut


class PortfolioAllocationOut(TypedDict):
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


class PortfolioCorrelationOut(TypedDict):
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


class PortfolioExposureOut(TypedDict):
    start_ts: float
    end_ts: float
    gross_exposure: float | None
    net_exposure: float | None
    turnover: float | None
    exposure_available: bool
    turnover_available: bool
    exposure_unavailable_reason: str | None
    turnover_unavailable_reason: str | None


class PortfolioProjectionBoundOut(TypedDict):
    original: int
    returned: int
    truncated: bool
    sampling: Literal["all", "endpoint_uniform", "canonical_prefix"]


class PortfolioAnalyticsBoundsOut(TypedDict):
    timestamp_limit: int
    symbol_limit: int
    allocation_timestamps: PortfolioProjectionBoundOut
    symbols: PortfolioProjectionBoundOut


class PortfolioAnalyticsProvenanceOut(TypedDict):
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


class PortfolioAnalyticsOut(TypedDict):
    symbols: list[str]
    allocations: list[PortfolioAllocationOut]
    correlations: list[PortfolioCorrelationOut]
    exposure: list[PortfolioExposureOut]
    provenance: PortfolioAnalyticsProvenanceOut
    bounds: PortfolioAnalyticsBoundsOut


class RunMetricOut(TypedDict):
    name: str
    value: float
    unit: str
    source_artifact: Literal["manifest.json"]
    source_field: str


class RunComparisonRowOut(TypedDict):
    run_id: str
    command: str | None
    symbol: str | None
    symbols: list[str] | None
    snapshot_id: str | None
    snapshot_hash: str | None
    passed: bool | None
    metrics: list[RunMetricOut]


class RunComparisonOut(TypedDict):
    run_ids: list[str]
    same_snapshot_hash: bool
    rows: list[RunComparisonRowOut]


__all__ = [
    "AgentBriefOut",
    "AttemptRecordOut",
    "ControlJobDetailOut",
    "ControlJobOut",
    "ControlJobPageOut",
    "JobCancellationOut",
    "JobReconciliationOut",
    "LegacyRunManifestOut",
    "LegacyRunSummaryOut",
    "ChartBundleOut",
    "EvidenceDetailOut",
    "EvidencePageOut",
    "EvidenceRecordOut",
    "ExperimentSpecOut",
    "ExperimentStageStateOut",
    "HoldoutStateOut",
    "ProjectDetailOut",
    "ProjectPageOut",
    "ProjectSummaryOut",
    "PortfolioAnalyticsOut",
    "RunComparisonOut",
    "SuiteLaunchOut",
    "SuitePlanOut",
    "StageRunLinkOut",
    "StrategyVersionOut",
]
