"""Public workstation contracts: identifiers and advisory evidence, never filesystem paths."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InvestigationCreate(Contract):
    run_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    question: str = Field(min_length=1, max_length=8000, pattern=r"\S")
    parent_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class InvestigationTurnRequest(Contract):
    followup: str | None = Field(default=None, min_length=1, max_length=8000, pattern=r"\S")


class ComparisonProxy(Contract):
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)*$", max_length=40)
    asset_class: Literal["stock", "etf"]
    role: Literal["asset", "market", "sector", "other"]


class ComparisonDraftRequest(Contract):
    series: list[ComparisonProxy] = Field(min_length=1, max_length=4)


class ComparisonAcquireRequest(Contract):
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class InvestigationEligibility(Contract):
    run_id: str
    eligible: bool
    cutoff: str | None = None
    reason: str | None = None


class ComparisonDraft(Contract):
    plan_sha256: str
    start: str
    end: str
    provider: Literal["tiingo"] = "tiingo"
    currency: Literal["USD"] = "USD"
    venue: Literal["US"] = "US"
    calendar: Literal["XNYS"] = "XNYS"
    series: list[ComparisonProxy]
    limitation: str = "Instrument metadata and benchmark suitability are operator-declared."


class InvestigationProgress(Contract):
    stage: Literal["preparing", "tool_started", "tool_completed", "verifying", "acquiring"]
    message: str


class InvestigationFinding(Contract):
    observation: str
    receipt_ids: list[str]


class InvestigationFindings(Contract):
    findings: list[InvestigationFinding]
    hypotheses: list[str]
    next_tests: list[str]
    limitations: list[str]


class InvestigationView(Contract):
    id: str
    run_id: str
    case_id: str
    question: str
    cutoff: str
    parent_id: str | None = None
    created_at: str
    authority: Literal["none"] = "none"
    admitted: Literal[False] = False
    status: Literal["ready", "running", "completed", "failed", "interrupted", "blocked"]
    error: str | None = None
    progress: list[InvestigationProgress] = Field(default_factory=list)
    report: InvestigationFindings | None = None
    receipts: list[dict[str, Any]] = Field(default_factory=list)
    requests_remaining: int
    turns_remaining: int
    can_resume: bool
    can_followup: bool
    comparison_draft: ComparisonDraft | None = None
    acquisition_status: Literal["not_started", "succeeded", "failed", "incomplete"] = "not_started"
    comparison_child_id: str | None = None
    active_job_id: str | None = None
