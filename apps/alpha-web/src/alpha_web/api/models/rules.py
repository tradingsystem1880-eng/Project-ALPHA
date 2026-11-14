"""Rules and daily rule evidence."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, JsonValue

from ._base import StrictModel


class DailyRuleAccountingPage(StrictModel):
    role: Literal["baseline", "control"]
    rows: list[dict[str, JsonValue]]
    total: int
    has_more: bool
    next_offset: int | None


class DailyRuleTerminalEvidence(StrictModel):
    valuation_basis: Literal["last_admitted_open_quote"]
    valuation_at: str
    opening_quote_at: str
    terminal_liquidation: Literal[False]
    terminal_decision: Literal["unfilled_without_next_admitted_quote"]
    final_decision_at: str


class DailyRuleRoleSummary(StrictModel):
    run_id: str
    starting_equity: float
    final_equity: float
    orders: int
    fills: int
    rejected: int
    n_trades: int
    fees_total: float
    net_pnl: float
    gross_pnl: float
    terminal: DailyRuleTerminalEvidence | None = None


class DailyRuleEvidenceResponse(StrictModel):
    schema_name: Literal["DailyRuleEvidenceV1"] = Field(alias="schema")
    run_id: str
    parent_run_id: str | None = None
    available: bool
    outcome: Literal["exploratory_complete", "accounting_rejection_inconclusive"] | None
    watermark: str | None
    claim_scope: str | None
    data_origin: Literal["artificial_fixture", "captured_provider_history"] | None
    provenance: dict[str, JsonValue]
    roles: dict[str, DailyRuleRoleSummary]
    accounting: DailyRuleAccountingPage
    selectors: dict[str, JsonValue]
    artifact_sha256: dict[str, str]


class RuleSummary(StrictModel):
    name: str
    path: str
    sha256: str | None = None
    spec_name: str | None = None
    history: int | None = None
    warmup: int | None = None
    long_conditions: list[str] | None = None
    short_conditions: list[str] | None = None
    spec: dict[str, Any] | None = None
    error: str | None = None


class RuleList(StrictModel):
    rules: list[RuleSummary]
    authority: Literal["none"]


class RuleRecord(StrictModel):
    name: str
    sha256: str
    path: str
    spec_name: str
    history: int
    warmup: int
    long_conditions: list[str]
    short_conditions: list[str]
    spec: dict[str, Any]


class RuleSaveRequest(StrictModel):
    name: str
    spec: dict[str, Any]


class RuleValidateRequest(StrictModel):
    spec: dict[str, Any]


class RuleValidation(StrictModel):
    valid: bool
    error: str | None
    name: str | None = None
    sha256: str | None = None
    spec_name: str | None = None
    history: int | None = None
    warmup: int | None = None
    long_conditions: list[str] | None = None
    short_conditions: list[str] | None = None
    spec: dict[str, Any] | None = None


class RuleDeleted(StrictModel):
    name: str
    deleted: bool
