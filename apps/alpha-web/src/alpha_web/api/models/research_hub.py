"""Research reports and evidence hub."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ._base import StrictModel
from .projects import JsonObject
from .research_cases import (
    HypothesisCard,
    ResearchD2StateValue,
    ResearchD3StateValue,
    ResearchExecutionStateValue,
    ResearchPhaseValue,
    ResearchScorecard,
)


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
