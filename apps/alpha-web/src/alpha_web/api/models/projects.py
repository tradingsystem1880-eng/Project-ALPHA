"""Projects, control-plane jobs, suites and evidence."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from alpha_cli.suite_catalog import SuiteActionValue as SuiteActionValue

from ._base import StrictModel

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
type EvidenceStatusValue = Literal["draft", "corroborated", "rejected", "superseded"]
type AuthorKindValue = Literal["human", "agent"]


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
    # spec 2026-09-01 §4.1: the CLI project projection carries no source yet, so every project
    # is honestly `unknown`; never inferred from the name.
    market: Literal["crypto", "equities", "unknown"] = "unknown"


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


StrategyProjectWorkspaceCategory = Literal[
    "research",
    "sources",
    "datasets",
    "study-state",
    "promotion",
    "strategy-versions",
    "experiments",
    "runs",
    "validation",
    "figures",
    "reports",
    "sandbox-eligibility",
]


class StrategyProjectWorkspaceIndexDescriptor(StrictModel):
    category: StrategyProjectWorkspaceCategory
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_count: int = Field(ge=0, le=10_000)


class StrategyProjectWorkspace(StrictModel):
    schema_name: Literal["StrategyProjectWorkspaceV1"]
    schema_version: Literal[1]
    revision_id: str = Field(pattern=r"^spw_[0-9a-f]{64}$")
    project_id: str
    project_name_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority: Literal["none"]
    execution_authority: Literal[False]
    categories: list[StrategyProjectWorkspaceCategory]
    indexes: list[StrategyProjectWorkspaceIndexDescriptor]
    sandbox_classification: Literal["non-transmitting-sandbox-only"]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StrategyProjectWorkspaceProjection(StrictModel):
    schema_name: Literal["StrategyProjectWorkspaceProjectionV1"]
    schema_version: Literal[1]
    project_id: str
    workspace_root: str
    changed: bool
    recovered: bool
    stale: bool
    workspace: StrategyProjectWorkspace


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
