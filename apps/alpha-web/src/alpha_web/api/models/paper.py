"""Paper sessions, events, readiness and candle markers."""

from __future__ import annotations

from typing import Literal

from ._base import StrictModel
from .projects import JsonScalar


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
    schema_version: Literal[2]
    status: Literal["passed", "pending"]
    paper_passed: bool
    plans: list[dict[str, object]]
    predicates: dict[str, bool]
    tamper_detected: bool
    legacy_journals: Literal["monitoring_only"]
    what_if_credit: Literal[False]
    requirements: list[PaperReadinessRequirement]
    blocking_events: list[PaperReadinessBlocker]
    futures_research_supported: Literal[False]
    live_capital_routing: Literal["absent"]
    derived_from_elapsed_time: Literal[False]
