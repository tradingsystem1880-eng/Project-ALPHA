"""Pydantic schemas for Claude Code harness artifacts.

Every artifact the harness persists (gate stamps, attestations, review
verdicts, audit events, doctor reports) is validated by one of these models
at write time. Hooks never import this module — they are stdlib-only readers
of already-validated JSON; only ``gate.py`` write paths import it lazily so
the hooks keep working before ``uv sync`` has run.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GateStep(_Strict):
    name: str
    seconds: float
    ok: bool


class GateStamp(_Strict):
    schema_version: Literal[1] = 1
    tier: Literal["fast", "full"]
    created_at: str
    head: str
    tree_hash: str
    duration_seconds: float
    steps: list[GateStep]


class SessionState(_Strict):
    session_id: str
    edited_files: list[str] = []
    stop_blocks_used: int = 0


class QuantClaim(_Strict):
    claim: str
    source: str
    location: str
    verdict: Literal["VERIFIED", "DISCREPANCY", "UNVERIFIABLE"]


class DocstringCitations(_Strict):
    ok: bool
    missing: list[str]


class QuantVerificationReport(_Strict):
    claims: list[QuantClaim]
    docstring_citations: DocstringCitations
    overall: Literal["PASS", "FAIL"]

    @model_validator(mode="after")
    def _pass_requires_clean_evidence(self) -> QuantVerificationReport:
        if self.overall == "PASS":
            bad = [c for c in self.claims if c.verdict != "VERIFIED"]
            if bad:
                raise ValueError(
                    "overall=PASS but non-VERIFIED claims exist: " + "; ".join(c.claim for c in bad)
                )
            if not self.docstring_citations.ok or self.docstring_citations.missing:
                raise ValueError("overall=PASS but docstring citations are missing")
        return self


class QuantAttestation(_Strict):
    schema_version: Literal[1] = 1
    created_at: str
    bound_quant_diff_hash: str
    report: QuantVerificationReport


class ReviewFinding(_Strict):
    severity: Literal["high", "medium", "low"]
    file: str
    line: int
    summary: str


class ReviewVerdict(_Strict):
    verdict: Literal["APPROVE", "BLOCK"]
    findings: list[ReviewFinding]
    plan_ref: str | None = None
    reviewed_tree_hash: str


class ReviewAttestation(_Strict):
    schema_version: Literal[1] = 1
    created_at: str
    verdict: ReviewVerdict


class AuditEvent(_Strict):
    ts: str
    session_id: str
    event: str
    detail: str
    tree_hash: str


class OnceToken(_Strict):
    created_at: str
    reason: str


class DoctorCheck(_Strict):
    name: str
    ok: bool
    detail: str


class DoctorReport(_Strict):
    created_at: str
    checks: list[DoctorCheck]
    ok: bool
