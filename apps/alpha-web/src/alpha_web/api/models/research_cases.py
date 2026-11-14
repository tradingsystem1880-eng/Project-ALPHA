"""Research cases, proposals and study status."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ._base import StrictModel
from .projects import AttemptStatusValue, AuthorKindValue, JsonObject, ProjectSummary

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


class ResearchSourceAddRequest(StrictModel):
    title: str = Field(min_length=1, max_length=512)
    locator: str = Field(min_length=1, max_length=2_048)
    provider: str = Field(min_length=1, max_length=80)
    access_mode: Literal["metadata_only", "open_access", "owner_provided"]
    doi: str | None = None
    year: int | None = Field(default=None, ge=1800, le=2100)
    authors: list[str] = []


class ResearchClaimAddRequest(StrictModel):
    source_id: str = Field(min_length=1, max_length=120)
    contract_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=4_096)
    direction: Literal["supports", "contradicts", "contextualizes", "method"]
    strength: Literal["weak", "moderate", "strong"]
    method: str = Field(min_length=1, max_length=2_048)
    sample: str = Field(min_length=1, max_length=2_048)
    markets: list[str] = []
    limitations: str = Field(min_length=1, max_length=2_048)


class ResearchNoteAddRequest(StrictModel):
    note_kind: Literal[
        "critique", "confounder_review", "test_design", "completeness_review", "synthesis"
    ]
    body: str = Field(min_length=1, max_length=8_192)
    context_packet_id: str | None = None


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


class ResearchSemanticEventViewV1(StrictModel):
    event_id: str
    artifact_id: str
    receipt_id: str
    actor: str
    reason: str
    recorded_at: str
    payload: JsonObject


class ResearchSemanticStateV1(StrictModel):
    state: Literal["definition_required", "review_required", "freeze_required", "frozen", "stale"]
    source_state: Literal["not_recorded", "current", "stale"]
    case_contract_id: str | None
    case_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    verified_read_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    projection_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_id: str | None
    cutoff_confirmed_at: str | None
    event_count: int = Field(ge=0)
    head_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    definition: ResearchSemanticEventViewV1 | None
    review: ResearchSemanticEventViewV1 | None
    freeze: ResearchSemanticEventViewV1 | None
    next_owner_action: str


class ResearchD1AttemptViewV1(StrictModel):
    attempt_id: str
    contract_id: str
    status: Literal["completed", "failed"]
    run_id: str | None
    recorded_at: str


class ResearchD1StateV1(StrictModel):
    launch_authority: Literal["owner_cli_only"]
    status: Literal["not_started", "queued", "running", "paused", "blocked", "completed", "failed"]
    attempts: list[ResearchD1AttemptViewV1]
    elapsed_budget: JsonObject
    remaining_budget: JsonObject


class ResearchPromotionStateV1(StrictModel):
    packet_id: str | None
    readiness: ResearchReadinessProjection


class ResearchStudyStatusV1(StrictModel):
    schema_: Literal["ResearchStudyStatusV1"] = Field(alias="schema", serialization_alias="schema")
    schema_version: Literal[1]
    authority: Literal["none"]
    project_id: str
    active_contract_id: str
    semantic: ResearchSemanticStateV1
    d1: ResearchD1StateV1
    promotion: ResearchPromotionStateV1
    next_action: str
    responsibility: Literal["owner", "codex"]


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
    study_status: ResearchStudyStatusV1 | None = None


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
