"""Run contexts, listings, details and job status."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from ._base import StrictModel


class GovernedRunContextV1(StrictModel):
    schema_version: Literal[1] = 1
    kind: Literal["governed_project"]
    project_id: str = Field(min_length=1)


class StandaloneRunContextV1(StrictModel):
    schema_version: Literal[1] = 1
    kind: Literal["standalone_sandbox"]


type RunContextV1 = Annotated[
    GovernedRunContextV1 | StandaloneRunContextV1,
    Field(discriminator="kind"),
]


class JobLaunchRequest(StrictModel):
    command: str = ""
    args: str = ""
    run_context: RunContextV1 | None = None


class RunListItem(StrictModel):
    run_id: str
    kind: str
    command: str | None
    label: str | None
    # spec 2026-09-01 §4.4: `<strategy> D1 — <symbol> · <venue> · <start> → <end> · run <8 hex>`
    display_name: str
    # spec 2026-09-01 §4.1: decided server-side from source, then the pair convention
    market: Literal["crypto", "equities", "unknown"]
    symbol: str | None
    symbols: list[str] | None
    snapshot_id: str | None
    snapshot_hash: str | None
    passed: bool | None
    verdict: str | None
    # spec §15 / ADR-0026: EXPLORATORY marker for runs launched under a research-gate override
    research_gate_watermark: str | None
    run_context_kind: Literal["governed_project", "standalone_sandbox", "legacy_context_unknown"]
    run_context_project_id: str | None
    run_context_watermark: str | None
    mtime: float


class RunList(StrictModel):
    total: int
    items: list[RunListItem]


class RunDetail(StrictModel):
    run_id: str
    kind: str
    mtime: float
    display_name: str
    market: Literal["crypto", "equities", "unknown"]
    manifest: dict[str, Any]
    # spec §15 / ADR-0026: EXPLORATORY marker for runs launched under a research-gate override
    research_gate_watermark: str | None
    run_context_kind: Literal["governed_project", "standalone_sandbox", "legacy_context_unknown"]
    run_context_project_id: str | None
    run_context_watermark: str | None
    has_equity: bool
    has_trades: bool
    has_tearsheet: bool
    has_forecast: bool
    has_nulls: bool
    has_trials: bool
    has_forecast_paths: bool
    has_propfirm_paths: bool
    has_origins: bool
    has_portfolio_analytics: bool


class JobStatus(StrictModel):
    job_id: str
    status: str
    session_id: str | None


class JobSummary(StrictModel):
    job_id: str
    command: str
    kind: str | None
    status: str
    created_at: float
    finished_at: float | None
    elapsed_seconds: float
    command_path: str
    current_step: str
    progress_mode: Literal["indeterminate", "estimated", "terminal"]
    progress_fraction: float | None
    eta_seconds: float | None
    eta_sample_count: int
    run_id: str | None
    session_id: str | None
    returncode: int | None
    n_lines: int


class JobDetail(JobSummary):
    lines: list[str]
