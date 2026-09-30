"""Advisory specialist handoffs and bounded discovery plans; no execution authority."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceSelector(BaseModel):
    """Hash and JSON pointer must be independently resolved by the consuming controller."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    artifact: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pointer: str = Field(pattern=r"^(?:/(?:[^~]|~[01])*)*$")


class SpecialistReview(BaseModel):
    """A schema-valid review remains an unverified advisory claim until evidence is checked."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    role: Literal["research_lead", "data", "overfitting", "economics_market_structure"]
    case_id: str = Field(min_length=1)
    status: Literal[
        "completed_evidence", "honest_block", "method_failure", "infrastructure_invalid"
    ]
    conclusion: str = Field(min_length=1)
    evidence: tuple[EvidenceSelector, ...] = ()
    findings: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    blocker: str = ""
    next_action: str = "stop"
    advisory_only: Literal[True] = True

    @model_validator(mode="after")
    def _evidence_required(self) -> SpecialistReview:
        if self.status == "completed_evidence" and not self.evidence:
            raise ValueError("completed evidence requires artifact selectors")
        if self.status == "honest_block" and not self.blocker.strip():
            raise ValueError("honest block requires an exact blocker")
        return self


class ResearchWorkflowPlan(BaseModel):
    """Fixed search bound; plans and baseline references do not certify completed execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    question: str = Field(min_length=1)
    target: str = Field(min_length=1)
    candidate_limit: int = Field(default=3, ge=1, le=3)
    baseline_evidence: EvidenceSelector | None = None
    candidates: tuple[str, ...] = ()
    stop_rule: str = Field(
        default="Stop at the bound or exact feasibility block; no in-sample rescue.", min_length=1
    )
    model_invocation_limit: int = Field(default=5, ge=1, le=5)
    schema_repair_limit: Literal[1] = 1
    advisory_only: Literal[True] = True

    @model_validator(mode="after")
    def _bounded(self) -> ResearchWorkflowPlan:
        if len(self.candidates) > self.candidate_limit:
            raise ValueError("candidate budget exhausted")
        if self.candidates and self.baseline_evidence is None:
            raise ValueError("baseline evidence required before variants")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError("duplicate candidate identities")
        return self
