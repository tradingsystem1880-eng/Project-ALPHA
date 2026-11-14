"""Research gate packets and decisions."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from ._base import StrictModel
from .projects import AuthorKindValue, JsonObject
from .research_cases import ResearchCase, ResearchReadinessProjection, ResearchScorecard


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
