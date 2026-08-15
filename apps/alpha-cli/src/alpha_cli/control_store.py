"""Lightweight, CLI-owned Workstation v3 control-plane store.

The control plane is mutable operational/research metadata, so it deliberately lives outside
``RUN_DIRS``. Deterministic run artifacts remain immutable and authoritative; this database only
links projects, attempts, jobs, and evidence to those completed runs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal, cast

import polars as pl

from alpha_cli.artifact_contract import (
    ARTIFACT_CONTRACT_VERSION,
    MANIFEST_SCHEMA_VERSION,
    sha256_file,
    verify_manifest_artifacts,
)
from alpha_cli.job_capacity import HEAVYWEIGHT_JOB_CAPACITY, HEAVYWEIGHT_JOB_KINDS
from alpha_cli.research_readiness import derive_research_readiness
from alpha_cli.run_store import find_run_dir, read_manifest
from alpha_core import DataError

type ProjectStatus = Literal["active", "accepted", "rejected", "archived"]
type StageState = Literal[
    "not_started", "ready", "queued", "running", "pass", "warning", "fail", "stale"
]
type AttemptStatus = Literal[
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
type MonteCarloReviewDecision = Literal["continue", "revise", "reject"]
type JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
type EvidenceStatus = Literal["draft", "corroborated", "rejected", "superseded"]
type AuthorKind = Literal["human", "agent"]
type DecisionVerdict = Literal["accept", "reject", "revise"]
type ResearchContractScope = Literal["exploration", "confirmation"]
type ResearchReviewDecision = Literal["approve", "reject"]
type ResearchPhase = Literal[
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
type ResearchExecutionState = Literal["idle", "queued", "running", "paused", "blocked", "failed"]
type ResearchResponsibility = Literal["owner", "codex"]
type ResearchD2State = Literal["sealed", "authorized", "consumed", "contaminated"]
type ResearchOutcome = Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"]
type ResearchDisposition = Literal["advance_to_strategy", "revise", "park", "reject"]
type ProjectResearchOrigin = Literal["strategy_development", "research_capture"]
type OwnerActionType = Literal[
    "screen_source_claim",
    "reject_source_claim",
    "revise_source_claim",
    "freeze_source_pack",
    "approve_exploration",
    "reject_exploration",
    "revise_exploration",
    "launch_d1",
    "approve_confirmation",
    "reject_confirmation",
    "launch_d2",
    "record_final_disposition",
]

LEGACY_SCHEMA_VERSION: Final = 1
OWNER_AUTH_PREVIOUS_SCHEMA_VERSION: Final = 2
PREVIOUS_SCHEMA_VERSION: Final = 3
SCHEMA_VERSION: Final = 4
DATABASE_NAME: Final = "workstation.sqlite3"
PROJECT_STATUSES: Final = frozenset({"active", "accepted", "rejected", "archived"})
STAGE_STATES: Final = frozenset(
    {"not_started", "ready", "queued", "running", "pass", "warning", "fail", "stale"}
)
DEVELOPMENT_STAGE_ORDER: Final = (
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
)
DEVELOPMENT_STAGES: Final = frozenset(DEVELOPMENT_STAGE_ORDER)
ATTEMPT_STATUSES: Final = frozenset(
    {
        "queued",
        "running",
        "completed",
        "passed",
        "warning",
        "failed",
        "pruned",
        "rejected",
        "cancelled",
    }
)
JOB_STATUSES: Final = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})
JOB_EVENT_TYPES: Final = frozenset(
    {"created", "status", "heartbeat", "progress", "log", "result", "cancel_requested"}
)
EVIDENCE_STATUSES: Final = frozenset({"draft", "corroborated", "rejected", "superseded"})
ASSOCIATION_METHODS: Final = frozenset(
    {
        "correlation",
        "pearson_correlation",
        "spearman_correlation",
        "kendall_tau",
        "cross_asset_association",
    }
)
AUTHOR_KINDS: Final = frozenset({"human", "agent"})
DECISION_VERDICTS: Final = frozenset({"accept", "reject", "revise"})
RESEARCH_CONTRACT_SCOPES: Final = frozenset({"exploration", "confirmation"})
RESEARCH_REVIEW_DECISIONS: Final = frozenset({"approve", "reject"})
RESEARCH_PHASE_ORDER: Final = (
    "captured",
    "triage",
    "exploration_review",
    "pilot",
    "deep_research",
    "confirmation_review",
    "sealed_confirmation",
    "research_decision",
    "closed",
)
RESEARCH_PHASES: Final = frozenset(RESEARCH_PHASE_ORDER)
RESEARCH_EXECUTION_STATES: Final = frozenset(
    {"idle", "queued", "running", "paused", "blocked", "failed"}
)
RESEARCH_RESPONSIBILITIES: Final = frozenset({"owner", "codex"})
RESEARCH_D2_STATES: Final = frozenset({"sealed", "authorized", "consumed", "contaminated"})
RESEARCH_OUTCOMES: Final = frozenset({"SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"})
RESEARCH_DISPOSITIONS: Final = frozenset({"advance_to_strategy", "revise", "park", "reject"})
RESEARCH_D2_REVISION_RELATIONS: Final = frozenset(
    {"unopened_sealed_reuse", "non_overlapping_future", "external_replication"}
)
RESEARCH_SOURCE_ACCESS_MODES: Final = frozenset({"metadata_only", "open_access", "owner_provided"})
PROJECT_RESEARCH_ORIGINS: Final = frozenset({"strategy_development", "research_capture"})
_MONTE_CARLO_COMMANDS: Final = frozenset({"monte_carlo_classical", "monte_carlo_kronos"})
_CANDIDATE_NULL_COMMANDS: Final = frozenset(
    {"candidate_null_bootstrap", "candidate_null_student_t", "candidate_null_garch"}
)
_CANDIDATE_MONTE_CARLO_COMMANDS: Final = frozenset(
    {"candidate_monte_carlo_classical", "candidate_monte_carlo_kronos"}
)
_CANDIDATE_PORTFOLIO_COMMANDS: Final = frozenset({"candidate_portfolio", "candidate_cross_asset"})
_CANDIDATE_EVIDENCE_COMMANDS: Final = frozenset(
    {
        "candidate_baseline",
        "candidate_oos",
        *_CANDIDATE_NULL_COMMANDS,
        *_CANDIDATE_MONTE_CARLO_COMMANDS,
        "candidate_optim",
        *_CANDIDATE_PORTFOLIO_COMMANDS,
    }
)

_ASSOCIATION_TOKEN_MARKERS: Final = ("associat", "correlat", "kendall", "pearson", "spearman")
_GENERIC_EVIDENCE_COMMANDS: Final = frozenset(
    {
        "backtest_run",
        "backtest_oos",
        "backtest_holdout",
        "validate",
        "backtest_portfolio",
        "cross_sectional",
        "backtest_cross_sectional",
        "optim_grid",
        "propfirm",
        "propfirm_run",
        "forecast_run",
        "forecast_eval",
        *_MONTE_CARLO_COMMANDS,
        "ml_replay",
        *_CANDIDATE_EVIDENCE_COMMANDS,
    }
)
_GENERIC_EVIDENCE_RESEARCH_MARKERS: Final = frozenset(
    {
        "research_contract_id",
        "contract_hash",
        "source_pack_id",
        "research_fingerprints",
        "evidence_zone",
        "eligible_for_holdout_or_execution",
        "real_market_evidence",
        "d0_operator",
        "d0_operator_fingerprint",
        "research_only",
    }
)

_TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
_TERMINAL_STAGE_STATES = frozenset({"pass", "warning", "fail"})
_RESERVED_JOB_PREFIXES = ("suite:", "research:")
_SUITE_JOB_KINDS: Final = frozenset(
    {
        "suite:baseline",
        "suite:inner_oos",
        "suite:three_null_families",
        "suite:monte_carlo",
        "suite:optimize_grid",
        "suite:fixed_stress",
        "suite:portfolio_cross_asset",
        "suite:qlib",
        "suite:kronos",
        "suite:holdout_reveal",
        "suite:paper_preflight",
    }
)
_SUITE_ACTION_STAGE_COMMANDS: Final[dict[str, tuple[str, frozenset[str]]]] = {
    "baseline": ("baseline", frozenset({"backtest_run", "candidate_baseline"})),
    "inner_oos": ("oos", frozenset({"backtest_oos", "candidate_oos"})),
    "three_null_families": (
        "robustness",
        frozenset({"validate", *_CANDIDATE_NULL_COMMANDS}),
    ),
    "monte_carlo": (
        "monte_carlo",
        _MONTE_CARLO_COMMANDS | _CANDIDATE_MONTE_CARLO_COMMANDS,
    ),
    "optimize_grid": ("optimization", frozenset({"optim_grid", "candidate_optim"})),
    "portfolio_cross_asset": (
        "portfolio",
        frozenset(
            {
                "backtest_portfolio",
                "cross_sectional",
                "backtest_cross_sectional",
                *_CANDIDATE_PORTFOLIO_COMMANDS,
            }
        ),
    ),
    "qlib": ("ml", frozenset({"ml_replay"})),
    "kronos": ("kronos", frozenset({"forecast_run", "forecast_eval"})),
    "holdout_reveal": ("holdout", frozenset({"backtest_holdout"})),
}
_PRE_REVEAL_RESEARCH_STAGES: Final = frozenset(
    {
        "baseline",
        "oos",
        "robustness",
        "monte_carlo",
        "optimization",
        "portfolio",
        "kronos",
        "ml",
    }
)
_PRE_REVEAL_RESEARCH_JOB_KINDS: Final = frozenset(
    {
        "suite:baseline",
        "suite:inner_oos",
        "suite:three_null_families",
        "suite:monte_carlo",
        "suite:optimize_grid",
        "suite:fixed_stress",
        "suite:portfolio_cross_asset",
        "suite:qlib",
        "suite:kronos",
    }
)
_JOB_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "queued": frozenset({"running", "failed", "cancelled"}),
    "running": frozenset({"succeeded", "failed", "cancelled"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}
_EVIDENCE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "draft": frozenset({"draft", "corroborated", "rejected"}),
    "corroborated": frozenset({"corroborated", "superseded"}),
    "rejected": frozenset({"rejected", "superseded"}),
    "superseded": frozenset(),
}
_STAGE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "not_started": frozenset({"ready", "stale"}),
    "ready": frozenset({"queued", "stale"}),
    "queued": frozenset({"running", "warning", "fail", "stale"}),
    "running": frozenset({"pass", "warning", "fail", "stale"}),
    "pass": frozenset({"stale"}),
    "warning": frozenset({"stale"}),
    "fail": frozenset({"stale"}),
    "stale": frozenset(),
}
_RESEARCH_EXECUTION_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "idle": frozenset({"queued", "blocked", "failed"}),
    "queued": frozenset({"running", "paused", "blocked", "failed", "idle"}),
    "running": frozenset({"queued", "paused", "blocked", "failed", "idle"}),
    "paused": frozenset({"queued", "running", "blocked", "failed", "idle"}),
    "blocked": frozenset({"queued", "failed", "idle"}),
    "failed": frozenset({"queued", "idle"}),
}
_RESEARCH_PACKET_KINDS: Final = frozenset(
    {"asset", "research_case", "experiment", "chart", "validation", "strategy_promotion"}
)
_RESEARCH_NOTE_KINDS: Final = frozenset(
    {"critique", "confounder_review", "test_design", "completeness_review", "synthesis"}
)
_RESEARCH_NOTE_AUTHOR_KINDS: Final = frozenset({"owner", "agent"})
_RESEARCH_PACKET_COLLECTION_LIMIT: Final = 50
_RESEARCH_DATASET_KINDS: Final = frozenset({"store_slice", "snapshot", "quantpad_receipt"})
# Fail-closed origin bindings (ADR-0023): a registration without its exact receipt or
# provenance hash is refused — research data is either bound to bytes or not registered.
_RESEARCH_DATASET_ORIGIN_FIELDS: Final = {
    "store_slice": ("provenance_sha256",),
    "snapshot": ("snapshot_id", "manifest_sha256"),
    "quantpad_receipt": ("receipt_id", "response_sha256"),
}
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_CONTENT_ID_RE = re.compile(r"(?P<prefix>sv|ex|rs|sp|rc|ra|rl|cp|rn|rd|sc|ld|rx)_[0-9a-f]{64}")
_SOURCE_CLAIM_DIRECTIONS: Final = frozenset({"supports", "contradicts", "contextualizes", "method"})
_SOURCE_CLAIM_STRENGTHS: Final = frozenset({"weak", "moderate", "strong"})
# Columns added to research_source_records after schema v2 shipped (ADR-0024).  The heal
# probe reads PRAGMA table_info (read-only) and only a store actually missing them takes
# the writer lock for the idempotent ALTERs.
_SOURCE_RECORD_ADDITIVE_COLUMNS: Final = (
    ("doi", "TEXT"),
    ("year", "INTEGER"),
    ("authors_json", "TEXT"),
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_SYMBOL_RE = re.compile(r"[A-Z0-9][A-Z0-9._:/-]{0,31}")
_ARTIFACT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}")
_MAX_JSON_BYTES = 65_536
_MAX_TEXT = 8_192
OWNER_ACTION_TYPES: Final = frozenset(
    {
        "screen_source_claim",
        "reject_source_claim",
        "revise_source_claim",
        "freeze_source_pack",
        "approve_exploration",
        "reject_exploration",
        "revise_exploration",
        "launch_d1",
        "approve_confirmation",
        "reject_confirmation",
        "launch_d2",
        "record_final_disposition",
    }
)
_RESEARCH_GATE_EVIDENCE_ARTIFACT: Final = "research_gate_evidence.json"
_D0_RESEARCH_KIND: Final = "d0-synthetic-pilot"
_D0_LAUNCH_BUDGET: Final[dict[str, int]] = {
    "wall_seconds": 1,
    "source_requests": 0,
    "variants": 3,
}
_D0_MAX_LAUNCHES: Final = 3
_D1_RESEARCH_KIND: Final = "d1-deep-research"
_D1_MAX_LAUNCHES: Final = 3
_D2_RESEARCH_KIND: Final = "sealed-confirmation"
_RESEARCH_CAPTURE_NAMESPACE: Final = uuid.UUID("9df1357d-30fe-5c03-9f26-c7d594fdd91e")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    falsification_criterion TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'accepted', 'rejected', 'archived')),
    current_version_id TEXT,
    current_experiment_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS strategy_versions (
    version_id TEXT PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    parameter_space_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS project_versions (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    linked_at TEXT NOT NULL,
    PRIMARY KEY (project_id, version_id)
) STRICT;

CREATE TABLE IF NOT EXISTS experiment_specs (
    experiment_id TEXT PRIMARY KEY,
    strategy_version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    snapshot_id TEXT NOT NULL,
    universe_json TEXT NOT NULL,
    split_policy_json TEXT NOT NULL,
    costs_json TEXT NOT NULL,
    seeds_json TEXT NOT NULL,
    stage_config_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS project_experiments (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    linked_at TEXT NOT NULL,
    PRIMARY KEY (project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS project_scope_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    current_version_id TEXT REFERENCES strategy_versions(version_id),
    current_experiment_id TEXT REFERENCES experiment_specs(experiment_id),
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS stage_run_links (
    link_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    stage TEXT NOT NULL,
    run_id TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    UNIQUE (project_id, experiment_id, stage, run_id)
) STRICT;

CREATE TABLE IF NOT EXISTS stage_state_events (
    link_id TEXT NOT NULL REFERENCES stage_run_links(link_id),
    sequence INTEGER NOT NULL,
    state TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (link_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS experiment_stage_events (
    project_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    state TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (project_id, experiment_id, stage, sequence),
    FOREIGN KEY (project_id, experiment_id)
        REFERENCES project_experiments(project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS attempt_records (
    attempt_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    config_fingerprint TEXT NOT NULL,
    run_id TEXT,
    error TEXT,
    details_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS holdout_state (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    sealed_at TEXT NOT NULL,
    sealed_by TEXT NOT NULL,
    sealed_version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    seal_reason TEXT NOT NULL,
    revealed_at TEXT,
    revealed_by TEXT,
    revealed_version_id TEXT REFERENCES strategy_versions(version_id),
    reveal_reason TEXT,
    contaminated_at TEXT,
    contamination_reason TEXT,
    PRIMARY KEY (project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS holdout_specs (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    spec_hash TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    PRIMARY KEY (project_id, experiment_id),
    FOREIGN KEY (project_id, experiment_id)
        REFERENCES project_experiments(project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS holdout_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    event TEXT NOT NULL CHECK (event IN ('sealed', 'revealed', 'contaminated')),
    actor TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    version_id TEXT NOT NULL REFERENCES strategy_versions(version_id)
) STRICT;

CREATE TABLE IF NOT EXISTS decision_packets (
    packet_id TEXT PRIMARY KEY,
    packet_hash TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    strategy_version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    verdict TEXT NOT NULL CHECK (verdict IN ('accept', 'reject', 'revise')),
    packet_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    project_id TEXT REFERENCES projects(project_id),
    experiment_id TEXT REFERENCES experiment_specs(experiment_id),
    request_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    result_run_id TEXT,
    terminal_error TEXT,
    last_sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS job_events (
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (job_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS evidence_items (
    evidence_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS evidence_revisions (
    evidence_id TEXT NOT NULL REFERENCES evidence_items(evidence_id),
    revision INTEGER NOT NULL,
    parent_revision INTEGER,
    status TEXT NOT NULL,
    claim TEXT NOT NULL,
    assets_json TEXT NOT NULL,
    frozen_universe_json TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    method TEXT NOT NULL,
    market_data_cutoff TEXT,
    knowledge_at TEXT NOT NULL,
    project_id TEXT REFERENCES projects(project_id),
    strategy_version_id TEXT,
    experiment_id TEXT,
    metric_name TEXT,
    metric_value REAL,
    metric_unit TEXT,
    source_run_id TEXT,
    source_artifact TEXT,
    source_field TEXT,
    row_selector_json TEXT NOT NULL,
    counterevidence_json TEXT NOT NULL,
    contradiction_ids_json TEXT NOT NULL,
    author TEXT NOT NULL,
    author_kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (evidence_id, revision)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_project_versions_project ON project_versions(project_id);
CREATE INDEX IF NOT EXISTS idx_project_experiments_project ON project_experiments(project_id);
CREATE INDEX IF NOT EXISTS idx_project_scope_project
    ON project_scope_events(project_id, occurred_at, sequence);
CREATE INDEX IF NOT EXISTS idx_attempt_project ON attempt_records(project_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_experiment_stage
    ON experiment_stage_events(project_id, experiment_id, stage, sequence);
CREATE INDEX IF NOT EXISTS idx_job_project ON jobs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_knowledge ON evidence_revisions(knowledge_at, created_at);
"""

_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS project_research_governance (
    project_id TEXT PRIMARY KEY REFERENCES projects(project_id),
    research_required INTEGER NOT NULL CHECK (research_required IN (0, 1)),
    origin TEXT NOT NULL CHECK (
        origin IN ('strategy_development', 'research_capture', 'legacy_import')
    ),
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_source_records (
    source_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    title TEXT NOT NULL,
    locator TEXT NOT NULL,
    provider TEXT NOT NULL,
    access_mode TEXT NOT NULL
        CHECK (access_mode IN ('metadata_only', 'open_access', 'owner_provided')),
    content_hash TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    doi TEXT,
    year INTEGER,
    authors_json TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS research_source_claims (
    claim_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    source_id TEXT NOT NULL REFERENCES research_source_records(source_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    claim_text TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN (
        'supports', 'contradicts', 'contextualizes', 'method'
    )),
    strength TEXT NOT NULL CHECK (strength IN ('weak', 'moderate', 'strong')),
    method_summary TEXT NOT NULL,
    sample_summary TEXT NOT NULL,
    markets_json TEXT NOT NULL,
    limitations TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'screened')),
    author TEXT NOT NULL,
    author_kind TEXT NOT NULL CHECK (author_kind IN ('owner', 'agent')),
    screened_by TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, revision)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_research_source_claims_project
    ON research_source_claims(project_id, created_at, claim_id);

CREATE TABLE IF NOT EXISTS research_source_packs (
    pack_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    source_ids_json TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_contracts (
    contract_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    scope TEXT NOT NULL CHECK (scope IN ('exploration', 'confirmation')),
    parent_contract_id TEXT REFERENCES research_contracts(contract_id),
    payload_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    author_kind TEXT NOT NULL CHECK (author_kind IN ('human', 'agent')),
    created_at TEXT NOT NULL,
    UNIQUE (project_id, contract_id)
) STRICT;

CREATE TABLE IF NOT EXISTS research_contract_review_events (
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    sequence INTEGER NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    scope TEXT NOT NULL CHECK (scope IN ('exploration', 'confirmation')),
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    actor TEXT NOT NULL,
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('human', 'agent')),
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (contract_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_phase_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    phase TEXT NOT NULL CHECK (phase IN (
        'captured', 'triage', 'exploration_review', 'pilot', 'deep_research',
        'confirmation_review', 'sealed_confirmation', 'research_decision', 'closed'
    )),
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    next_action TEXT NOT NULL,
    responsibility TEXT NOT NULL CHECK (responsibility IN ('owner', 'codex')),
    blocker TEXT,
    recovery TEXT,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_execution_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    state TEXT NOT NULL CHECK (state IN (
        'idle', 'queued', 'running', 'paused', 'blocked', 'failed'
    )),
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    next_action TEXT NOT NULL,
    responsibility TEXT NOT NULL CHECK (responsibility IN ('owner', 'codex')),
    active_job_id TEXT,
    checkpoint TEXT,
    blocker TEXT,
    recovery TEXT,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_d2_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    state TEXT NOT NULL CHECK (state IN ('sealed', 'authorized', 'consumed', 'contaminated')),
    boundary_hash TEXT NOT NULL,
    actor TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_launch_reservations (
    reservation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    phase TEXT NOT NULL CHECK (phase = 'pilot'),
    kind TEXT NOT NULL,
    launch_number INTEGER NOT NULL CHECK (launch_number BETWEEN 1 AND 3),
    config_fingerprint TEXT NOT NULL,
    budget_reserved_json TEXT NOT NULL,
    execution_sequence INTEGER NOT NULL,
    reserved_at TEXT NOT NULL,
    UNIQUE (project_id, contract_id, kind, launch_number),
    UNIQUE (project_id, execution_sequence),
    FOREIGN KEY (project_id, execution_sequence)
        REFERENCES research_execution_events(project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_attempt_records (
    attempt_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    phase TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    config_fingerprint TEXT NOT NULL,
    budget_used_json TEXT NOT NULL,
    run_id TEXT,
    error TEXT,
    details_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_launch_attempt_links (
    reservation_id TEXT PRIMARY KEY
        REFERENCES research_launch_reservations(reservation_id),
    attempt_id TEXT NOT NULL UNIQUE REFERENCES research_attempt_records(attempt_id),
    linked_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_decision_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    outcome TEXT NOT NULL CHECK (
        outcome IN ('SUPPORTED', 'CONTRADICTED', 'INCONCLUSIVE', 'INVALID')
    ),
    disposition TEXT NOT NULL CHECK (
        disposition IN ('advance_to_strategy', 'revise', 'park', 'reject')
    ),
    actor TEXT NOT NULL,
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('human', 'agent')),
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence),
    UNIQUE (project_id, contract_id)
) STRICT;

CREATE TABLE IF NOT EXISTS research_gate_override_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_contract_strategy_links (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    linked_at TEXT NOT NULL,
    PRIMARY KEY (project_id, version_id),
    UNIQUE (project_id, contract_id, version_id)
) STRICT;

CREATE TABLE IF NOT EXISTS research_contract_experiment_links (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    linked_at TEXT NOT NULL,
    PRIMARY KEY (project_id, experiment_id),
    UNIQUE (project_id, contract_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS research_context_packets (
    packet_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    packet_kind TEXT NOT NULL CHECK (packet_kind IN (
        'asset', 'research_case', 'experiment', 'chart', 'validation', 'strategy_promotion'
    )),
    protocol_id TEXT,
    protocol_content_hash TEXT,
    payload_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_case_notes (
    note_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    note_kind TEXT NOT NULL CHECK (note_kind IN (
        'critique', 'confounder_review', 'test_design', 'completeness_review', 'synthesis'
    )),
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    author_kind TEXT NOT NULL CHECK (author_kind IN ('owner', 'agent')),
    context_packet_id TEXT REFERENCES research_context_packets(packet_id),
    created_at TEXT NOT NULL,
    UNIQUE (project_id, sequence)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_research_context_packets_project
    ON research_context_packets(project_id, created_at, packet_id);
CREATE INDEX IF NOT EXISTS idx_research_case_notes_project
    ON research_case_notes(project_id, sequence);

CREATE TABLE IF NOT EXISTS research_dataset_refs (
    ref_id TEXT PRIMARY KEY,
    dataset_kind TEXT NOT NULL CHECK (dataset_kind IN (
        'store_slice', 'snapshot', 'quantpad_receipt'
    )),
    instrument TEXT NOT NULL,
    provider TEXT NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT NOT NULL,
    bar_duration_minutes INTEGER,
    origin_json TEXT NOT NULL,
    research_only INTEGER NOT NULL CHECK (research_only = 1),
    registered_by TEXT NOT NULL,
    registered_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_dataset_audits (
    ref_id TEXT NOT NULL REFERENCES research_dataset_refs(ref_id),
    sequence INTEGER NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    run_id TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (ref_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS monte_carlo_reviews (
    review_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    decision TEXT NOT NULL CHECK (decision IN ('continue', 'revise', 'reject')),
    actor TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_hashes_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE (project_id, experiment_id)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_monte_carlo_reviews_project
    ON monte_carlo_reviews(project_id, recorded_at, review_id);

CREATE INDEX IF NOT EXISTS idx_research_dataset_refs_instrument
    ON research_dataset_refs(instrument, registered_at, ref_id);
CREATE INDEX IF NOT EXISTS idx_research_dataset_audits_project
    ON research_dataset_audits(project_id, recorded_at);

CREATE INDEX IF NOT EXISTS idx_research_source_records_project
    ON research_source_records(project_id, created_at, source_id);
CREATE INDEX IF NOT EXISTS idx_research_packs_project
    ON research_source_packs(project_id, created_at, pack_id);
CREATE INDEX IF NOT EXISTS idx_research_contracts_project
    ON research_contracts(project_id, created_at, contract_id);
CREATE INDEX IF NOT EXISTS idx_research_phase_project
    ON research_phase_events(project_id, occurred_at, sequence);
CREATE INDEX IF NOT EXISTS idx_research_attempt_records_project
    ON research_attempt_records(project_id, recorded_at, attempt_id);
CREATE INDEX IF NOT EXISTS idx_research_launch_reservations_project
    ON research_launch_reservations(project_id, reserved_at, reservation_id);
CREATE INDEX IF NOT EXISTS idx_research_launch_attempt_links_attempt
    ON research_launch_attempt_links(attempt_id);
"""

_SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS owner_enrollment_requests (
    request_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    replace_existing INTEGER NOT NULL CHECK (replace_existing IN (0, 1)),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS owner_credentials (
    credential_id TEXT PRIMARY KEY,
    public_key BLOB NOT NULL,
    sign_count INTEGER NOT NULL CHECK (sign_count >= 0),
    actor TEXT NOT NULL,
    transports_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS owner_credential_events (
    event_id TEXT PRIMARY KEY,
    credential_id TEXT REFERENCES owner_credentials(credential_id),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'enrollment_requested', 'enrolled', 'revoked', 'replaced', 'recovery_failed'
    )),
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS owner_auth_challenges (
    challenge_id TEXT PRIMARY KEY,
    ceremony TEXT NOT NULL CHECK (ceremony IN ('registration', 'action')),
    challenge BLOB NOT NULL,
    enrollment_request_id TEXT REFERENCES owner_enrollment_requests(request_id),
    binding_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    verified_credential_id TEXT REFERENCES owner_credentials(credential_id)
) STRICT;

CREATE TABLE IF NOT EXISTS owner_action_receipts (
    receipt_id TEXT PRIMARY KEY,
    challenge_id TEXT NOT NULL UNIQUE REFERENCES owner_auth_challenges(challenge_id),
    credential_id TEXT NOT NULL REFERENCES owner_credentials(credential_id),
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN (
        'screen_source_claim', 'reject_source_claim', 'revise_source_claim',
        'freeze_source_pack', 'approve_exploration', 'reject_exploration',
        'revise_exploration', 'launch_d1', 'approve_confirmation',
        'reject_confirmation', 'launch_d2', 'record_final_disposition'
    )),
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    artifact_hash TEXT NOT NULL,
    expected_case_revision TEXT NOT NULL,
    consequence_summary TEXT NOT NULL,
    reason TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    assertion_hash TEXT NOT NULL,
    outcome_json TEXT NOT NULL,
    performed_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_source_claim_owner_events (
    claim_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    decision TEXT NOT NULL CHECK (decision IN ('reject', 'revise')),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, sequence)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_owner_credentials_active
    ON owner_credentials(revoked_at, created_at, credential_id);
CREATE INDEX IF NOT EXISTS idx_owner_auth_challenges_expiry
    ON owner_auth_challenges(ceremony, expires_at, used_at);
CREATE INDEX IF NOT EXISTS idx_owner_action_receipts_project
    ON owner_action_receipts(project_id, performed_at, receipt_id);
CREATE INDEX IF NOT EXISTS idx_source_claim_owner_events_project
    ON research_source_claim_owner_events(project_id, occurred_at, claim_id);

CREATE TRIGGER IF NOT EXISTS owner_action_receipts_no_update
BEFORE UPDATE ON owner_action_receipts
BEGIN SELECT RAISE(ABORT, 'owner action receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS owner_action_receipts_no_delete
BEFORE DELETE ON owner_action_receipts
BEGIN SELECT RAISE(ABORT, 'owner action receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS owner_credential_events_no_update
BEFORE UPDATE ON owner_credential_events
BEGIN SELECT RAISE(ABORT, 'owner credential events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS owner_credential_events_no_delete
BEFORE DELETE ON owner_credential_events
BEGIN SELECT RAISE(ABORT, 'owner credential events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_source_claim_owner_events_no_update
BEFORE UPDATE ON research_source_claim_owner_events
BEGIN SELECT RAISE(ABORT, 'source claim owner events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_source_claim_owner_events_no_delete
BEFORE DELETE ON research_source_claim_owner_events
BEGIN SELECT RAISE(ABORT, 'source claim owner events are append-only'); END;
"""

_SCHEMA_V4 = """
CREATE TABLE IF NOT EXISTS literature_discoveries (
    discovery_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    query TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    artifact_relpath TEXT NOT NULL,
    budget_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_document_texts (
    extraction_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL UNIQUE REFERENCES research_source_records(source_id),
    source_sha256 TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    artifact_relpath TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'extracted', 'encrypted', 'image_only', 'truncated', 'parser_failed'
    )),
    page_count INTEGER NOT NULL CHECK (page_count >= 0),
    character_count INTEGER NOT NULL CHECK (character_count >= 0),
    parser_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_source_claim_anchors (
    claim_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    extraction_id TEXT NOT NULL REFERENCES research_document_texts(extraction_id),
    page INTEGER NOT NULL CHECK (page >= 1),
    char_start INTEGER NOT NULL CHECK (char_start >= 0),
    char_end INTEGER NOT NULL CHECK (char_end > char_start),
    exact_text_sha256 TEXT NOT NULL,
    PRIMARY KEY (claim_id, revision),
    FOREIGN KEY (claim_id, revision) REFERENCES research_source_claims(claim_id, revision)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_literature_discoveries_project
    ON literature_discoveries(project_id, created_at, discovery_id);
CREATE INDEX IF NOT EXISTS idx_research_document_texts_source
    ON research_document_texts(source_id, created_at, extraction_id);
CREATE INDEX IF NOT EXISTS idx_research_claim_anchors_extraction
    ON research_source_claim_anchors(extraction_id, claim_id, revision);

CREATE TRIGGER IF NOT EXISTS literature_discoveries_no_update
BEFORE UPDATE ON literature_discoveries
BEGIN SELECT RAISE(ABORT, 'literature discoveries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS literature_discoveries_no_delete
BEFORE DELETE ON literature_discoveries
BEGIN SELECT RAISE(ABORT, 'literature discoveries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_document_texts_no_update
BEFORE UPDATE ON research_document_texts
BEGIN SELECT RAISE(ABORT, 'research document texts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_document_texts_no_delete
BEFORE DELETE ON research_document_texts
BEGIN SELECT RAISE(ABORT, 'research document texts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_source_claim_anchors_no_update
BEFORE UPDATE ON research_source_claim_anchors
BEGIN SELECT RAISE(ABORT, 'research source claim anchors are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_source_claim_anchors_no_delete
BEFORE DELETE ON research_source_claim_anchors
BEGIN SELECT RAISE(ABORT, 'research source claim anchors are append-only'); END;
"""

# Executed exactly once, inside the schema-v2 writer transaction (migration or fresh creation).
# It must never run on a steady-state open: a re-executed backfill would silently re-derive a
# lost governance row from the caller-controlled ``created_at`` date rule, and the write lock it
# takes would make read-only projections contend with concurrent writers.
_GOVERNANCE_BACKFILL = """
INSERT OR IGNORE INTO project_research_governance (
    project_id, research_required, origin, recorded_at
)
SELECT
    project_id,
    CASE WHEN created_at < '2026-08-06T00:00:00.000000Z' THEN 0 ELSE 1 END,
    CASE
        WHEN created_at < '2026-08-06T00:00:00.000000Z' THEN 'legacy_import'
        ELSE 'strategy_development'
    END,
    created_at
FROM projects;
"""

_DDL_OBJECT_NAME = re.compile(r"CREATE (?:TABLE|INDEX|TRIGGER) IF NOT EXISTS (\w+)")
_EXPECTED_SCHEMA_OBJECTS: Final = frozenset(
    _DDL_OBJECT_NAME.findall(_SCHEMA)
    + _DDL_OBJECT_NAME.findall(_SCHEMA_V2)
    + _DDL_OBJECT_NAME.findall(_SCHEMA_V3)
    + _DDL_OBJECT_NAME.findall(_SCHEMA_V4)
)


def _required_text(value: object, field: str, *, max_length: int = _MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise DataError(f"invalid control {field}: expected a string")
    clean = value.strip()
    if not clean or "\x00" in clean or len(clean) > max_length:
        raise DataError(f"invalid control {field}: expected 1..{max_length} safe characters")
    return clean


def _optional_text(value: str | None, field: str) -> str | None:
    return None if value is None else _required_text(value, field)


def _canonical_uuid(value: str, field: str) -> str:
    if _UUID_RE.fullmatch(value) is None:
        raise DataError(f"invalid control {field}: expected a canonical UUID")
    try:
        parsed = str(uuid.UUID(value))
    except ValueError as exc:
        raise DataError(f"invalid control {field}: expected a canonical UUID") from exc
    if parsed != value:
        raise DataError(f"invalid control {field}: expected a canonical UUID")
    return value


def _new_uuid(value: str | None, field: str) -> str:
    return str(uuid.uuid4()) if value is None else _canonical_uuid(value, field)


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataError("control timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_timestamp(value: str, field: str = "timestamp") -> datetime:
    """Parse the canonical UTC timestamps accepted by control-plane CLI projections."""
    if not value.endswith("Z"):
        raise DataError(f"invalid control {field}: expected an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as exc:
        raise DataError(f"invalid control {field}: expected an ISO-8601 UTC timestamp") from exc
    return parsed.astimezone(UTC)


def _iso_date(value: str, field: str) -> str:
    clean = _required_text(value, field, max_length=10)
    try:
        parsed = date.fromisoformat(clean)
    except ValueError as exc:
        raise DataError(f"invalid control {field}: expected YYYY-MM-DD") from exc
    canonical = parsed.isoformat()
    if canonical != clean:
        raise DataError(f"invalid control {field}: expected canonical YYYY-MM-DD")
    return canonical


def _at(value: datetime | None) -> str:
    return _format_timestamp(datetime.now(UTC) if value is None else value)


def _clean_json(value: object, *, label: str, depth: int = 0) -> object:
    if depth > 16:
        raise DataError(f"invalid control {label}: JSON nesting exceeds 16 levels")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DataError(f"invalid control {label}: expected finite JSON values")
        return value
    if isinstance(value, Mapping):
        clean: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or "\x00" in key:
                raise DataError(f"invalid control {label}: JSON keys must be non-empty strings")
            clean[key] = _clean_json(item, label=label, depth=depth + 1)
        return clean
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_clean_json(item, label=label, depth=depth + 1) for item in value]
    raise DataError(f"invalid control {label}: expected finite JSON values")


def _json_object(value: Mapping[str, object], label: str) -> dict[str, object]:
    clean = _clean_json(value, label=label)
    if not isinstance(clean, dict):  # Mapping above makes this defensive branch unreachable.
        raise DataError(f"invalid control {label}: expected a JSON object")
    _canonical_json(clean, label)
    return clean


def _canonical_json(value: object, label: str) -> str:
    try:
        result = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DataError(f"invalid control {label}: expected finite JSON values") from exc
    if len(result.encode("utf-8")) > _MAX_JSON_BYTES:
        raise DataError(f"invalid control {label}: JSON exceeds {_MAX_JSON_BYTES} bytes")
    return result


def research_case_revision(summary: Mapping[str, object]) -> str:
    """Commit to owner-action-relevant mutable research case state."""
    payload = {
        "schema": "ResearchCaseRevisionV1",
        "project_id": summary.get("project_id"),
        "active_contract_id": summary.get("active_contract_id"),
        "phase": summary.get("phase"),
        "execution_state": summary.get("execution_state"),
        "source_pack_id": summary.get("source_pack_id"),
    }
    return hashlib.sha256(_canonical_json(payload, "research case revision").encode()).hexdigest()


def _decode_json(value: object, label: str) -> object:
    if not isinstance(value, str):
        raise DataError(f"corrupt control store: {label} is not text")
    try:
        result: object = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DataError(f"corrupt control store: invalid {label}") from exc
    return _clean_json(result, label=label)


def _content_id(prefix: str, payload: Mapping[str, object]) -> str:
    canonical = _canonical_json(_json_object(payload, f"{prefix} identity"), f"{prefix} identity")
    return f"{prefix}_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _require_content_id(value: str, field: str, *, prefix: str) -> str:
    match = _CONTENT_ID_RE.fullmatch(value)
    if match is None or match.group("prefix") != prefix:
        raise DataError(f"invalid control {field}: expected a content-addressed id")
    return value


def _symbols(values: Sequence[str]) -> list[str]:
    result = sorted({_required_text(value, "symbol", max_length=32).upper() for value in values})
    if not result or len(result) > 512:
        raise DataError("invalid control universe: expected 1..512 unique symbols")
    if any(_SYMBOL_RE.fullmatch(symbol) is None for symbol in result):
        raise DataError("invalid control universe: symbols contain unsupported characters")
    return result


def _strings(values: Sequence[str], field: str, *, limit: int = 256) -> list[str]:
    if len(values) > limit:
        raise DataError(f"invalid control {field}: too many values")
    return [_required_text(value, field) for value in values]


def _evidence_ids(values: Sequence[str]) -> list[str]:
    if len(values) > 256:
        raise DataError("invalid control contradiction_ids: too many values")
    return sorted({_canonical_uuid(value, "contradiction evidence_id") for value in values})


def _is_association_like(value: str) -> bool:
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    return any(marker in token for token in tokens for marker in _ASSOCIATION_TOKEN_MARKERS)


def _page(limit: int, offset: int) -> tuple[int, int]:
    if isinstance(limit, bool) or not 1 <= limit <= 500:
        raise DataError("control query limit must be in 1..500")
    if isinstance(offset, bool) or offset < 0:
        raise DataError("control query offset must be non-negative")
    return limit, offset


def _verified_v1_backup(connection: sqlite3.Connection, database: Path) -> None:
    """Create one atomic, integrity-checked backup before the additive v1->v2 migration."""
    backup = database.with_name(f"{database.name}.v1.bak")
    if backup.is_symlink():
        raise DataError(f"control store migration backup must not be a symlink: {backup}")
    if backup.exists():
        if not backup.is_file():
            raise DataError(f"control store migration backup is not a file: {backup}")
        existing = sqlite3.connect(backup)
        try:
            integrity = existing.execute("PRAGMA integrity_check").fetchone()
            version = existing.execute("PRAGMA user_version").fetchone()
            if integrity != ("ok",) or version != (LEGACY_SCHEMA_VERSION,):
                raise DataError("existing control store v1 migration backup is invalid")
            existing_fingerprint = _logical_database_fingerprint(existing)
        finally:
            existing.close()
        if existing_fingerprint != _logical_database_fingerprint(connection):
            raise DataError(
                "existing control store v1 migration backup does not match the current database"
            )
        return

    fd, raw_tmp = tempfile.mkstemp(prefix=f".{backup.name}.", suffix=".tmp", dir=backup.parent)
    os.close(fd)
    tmp = Path(raw_tmp)
    snapshot: sqlite3.Connection | None = None
    target: sqlite3.Connection | None = None
    try:
        # ``sqlite3.Connection.backup`` cannot make progress when its source connection owns the
        # write transaction that protects this migration.  A separate WAL reader sees the same
        # committed v1 snapshot while the caller's BEGIN IMMEDIATE prevents any writer from
        # changing that snapshot before schema-v2 commits.
        snapshot = sqlite3.connect(database, timeout=5.0, isolation_level=None)
        snapshot.execute("PRAGMA query_only = ON")
        snapshot.execute("PRAGMA busy_timeout = 5000")
        snapshot.execute("BEGIN")
        target = sqlite3.connect(tmp)
        snapshot.backup(target)
        integrity = target.execute("PRAGMA integrity_check").fetchone()
        version = target.execute("PRAGMA user_version").fetchone()
        if integrity != ("ok",) or version != (LEGACY_SCHEMA_VERSION,):
            raise DataError("cannot verify control store v1 migration backup")
        target_fingerprint = _logical_database_fingerprint(target)
        target.close()
        target = None
        if target_fingerprint != _logical_database_fingerprint(connection):
            raise DataError("control store v1 migration backup does not match the current database")
        os.replace(tmp, backup)
    finally:
        if target is not None:
            target.close()
        if snapshot is not None:
            if snapshot.in_transaction:
                snapshot.rollback()
            snapshot.close()
        if tmp.exists():
            tmp.unlink()


def _verified_v2_backup(connection: sqlite3.Connection, database: Path) -> None:
    """Create one atomic, integrity-checked backup before the additive v2->v3 migration."""
    backup = database.with_name(f"{database.name}.v2.bak")
    if backup.is_symlink():
        raise DataError(f"control store migration backup must not be a symlink: {backup}")
    if backup.exists():
        if not backup.is_file():
            raise DataError(f"control store migration backup is not a file: {backup}")
        existing = sqlite3.connect(backup)
        try:
            integrity = existing.execute("PRAGMA integrity_check").fetchone()
            version = existing.execute("PRAGMA user_version").fetchone()
            if integrity != ("ok",) or version != (OWNER_AUTH_PREVIOUS_SCHEMA_VERSION,):
                raise DataError("existing control store v2 migration backup is invalid")
            existing_fingerprint = _logical_database_fingerprint(existing)
        finally:
            existing.close()
        if existing_fingerprint != _logical_database_fingerprint(connection):
            raise DataError(
                "existing control store v2 migration backup does not match the current database"
            )
        return

    fd, raw_tmp = tempfile.mkstemp(prefix=f".{backup.name}.", suffix=".tmp", dir=backup.parent)
    os.close(fd)
    tmp = Path(raw_tmp)
    snapshot: sqlite3.Connection | None = None
    target: sqlite3.Connection | None = None
    try:
        snapshot = sqlite3.connect(database, timeout=5.0, isolation_level=None)
        snapshot.execute("PRAGMA query_only = ON")
        snapshot.execute("PRAGMA busy_timeout = 5000")
        snapshot.execute("BEGIN")
        target = sqlite3.connect(tmp)
        snapshot.backup(target)
        integrity = target.execute("PRAGMA integrity_check").fetchone()
        version = target.execute("PRAGMA user_version").fetchone()
        if integrity != ("ok",) or version != (OWNER_AUTH_PREVIOUS_SCHEMA_VERSION,):
            raise DataError("cannot verify control store v2 migration backup")
        target_fingerprint = _logical_database_fingerprint(target)
        target.close()
        target = None
        if target_fingerprint != _logical_database_fingerprint(connection):
            raise DataError("control store v2 migration backup does not match the current database")
        os.replace(tmp, backup)
    finally:
        if target is not None:
            target.close()
        if snapshot is not None:
            if snapshot.in_transaction:
                snapshot.rollback()
            snapshot.close()
        if tmp.exists():
            tmp.unlink()


def _logical_database_fingerprint(connection: sqlite3.Connection) -> str:
    """Hash schema and row content while ignoring SQLite page-layout differences."""
    digest = hashlib.sha256()
    for statement in connection.iterdump():
        encoded = statement.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _verified_v3_backup(connection: sqlite3.Connection, database: Path) -> None:
    """Create one atomic, integrity-checked backup before the v3->v4 migration."""
    backup = database.with_name(f"{database.name}.v3.bak")
    if backup.is_symlink():
        raise DataError(f"control store migration backup must not be a symlink: {backup}")
    if backup.exists():
        if not backup.is_file():
            raise DataError(f"control store migration backup is not a file: {backup}")
        existing = sqlite3.connect(backup)
        try:
            integrity = existing.execute("PRAGMA integrity_check").fetchone()
            version = existing.execute("PRAGMA user_version").fetchone()
            fingerprint = _logical_database_fingerprint(existing)
        finally:
            existing.close()
        if integrity != ("ok",) or version != (PREVIOUS_SCHEMA_VERSION,):
            raise DataError("existing control store v3 migration backup is invalid")
        if fingerprint != _logical_database_fingerprint(connection):
            raise DataError("existing control store v3 migration backup does not match")
        return
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{backup.name}.", suffix=".tmp", dir=backup.parent)
    os.close(fd)
    temporary = Path(raw_tmp)
    snapshot: sqlite3.Connection | None = None
    target: sqlite3.Connection | None = None
    try:
        snapshot = sqlite3.connect(database, timeout=5.0, isolation_level=None)
        snapshot.execute("PRAGMA query_only = ON")
        snapshot.execute("PRAGMA busy_timeout = 5000")
        snapshot.execute("BEGIN")
        target = sqlite3.connect(temporary)
        snapshot.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise DataError("cannot verify control store v3 migration backup")
        if target.execute("PRAGMA user_version").fetchone() != (PREVIOUS_SCHEMA_VERSION,):
            raise DataError("cannot verify control store v3 migration backup version")
        target_fingerprint = _logical_database_fingerprint(target)
        target.close()
        target = None
        if target_fingerprint != _logical_database_fingerprint(connection):
            raise DataError("control store v3 migration backup does not match")
        os.replace(temporary, backup)
    finally:
        if target is not None:
            target.close()
        if snapshot is not None:
            if snapshot.in_transaction:
                snapshot.rollback()
            snapshot.close()
        if temporary.exists():
            temporary.unlink()


def _execute_static_sql_script(connection: sqlite3.Connection, script: str) -> None:
    """Execute trusted static DDL without ``executescript`` committing the caller's transaction."""

    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            connection.execute(pending)
            pending = ""
    if pending.strip():
        raise sqlite3.OperationalError("incomplete static control-store schema statement")


def _apply_schema_v2_locked(
    connection: sqlite3.Connection, *, include_legacy_schema: bool = False
) -> None:
    """Apply additive DDL and publish the marker inside a caller-owned write transaction."""

    if not connection.in_transaction:
        raise sqlite3.OperationalError("schema-v2 application requires an active transaction")
    if include_legacy_schema:
        _execute_static_sql_script(connection, _SCHEMA)
    _execute_static_sql_script(connection, _SCHEMA_V2)
    _execute_static_sql_script(connection, _SCHEMA_V3)
    _execute_static_sql_script(connection, _SCHEMA_V4)
    _execute_static_sql_script(connection, _GOVERNANCE_BACKFILL)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _apply_schema_v2(
    connection: sqlite3.Connection, *, include_legacy_schema: bool = False
) -> None:
    """Atomically apply additive schema-v2 DDL for a fresh control store."""

    connection.execute("BEGIN IMMEDIATE")
    try:
        _apply_schema_v2_locked(connection, include_legacy_schema=include_legacy_schema)
        connection.commit()
    except sqlite3.Error:
        if connection.in_transaction:
            connection.rollback()
        raise


def _missing_source_record_columns(connection: sqlite3.Connection) -> tuple[str, ...]:
    present = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(research_source_records)")
    }
    if not present:
        # The table itself is missing; the object-level heal recreates it with all columns.
        return ()
    return tuple(name for name, _ in _SOURCE_RECORD_ADDITIVE_COLUMNS if name not in present)


def _missing_schema_objects(connection: sqlite3.Connection) -> bool:
    present = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')"
        )
    }
    return not present >= _EXPECTED_SCHEMA_OBJECTS


def _heal_missing_schema_objects(connection: sqlite3.Connection) -> None:
    """Recreate additively-declared objects a current-version store is missing.

    The probe is read-only, so a steady-state open issues no write statement and never
    contends for the writer lock. Healing applies idempotent DDL only — never the
    governance backfill, which runs exactly once at migration or fresh creation.
    """

    if not _missing_schema_objects(connection) and not _missing_source_record_columns(connection):
        return
    connection.execute("BEGIN IMMEDIATE")
    try:
        if _missing_schema_objects(connection):
            _execute_static_sql_script(connection, _SCHEMA)
            _execute_static_sql_script(connection, _SCHEMA_V2)
            _execute_static_sql_script(connection, _SCHEMA_V3)
            _execute_static_sql_script(connection, _SCHEMA_V4)
        for name, column_type in _SOURCE_RECORD_ADDITIVE_COLUMNS:
            if name in _missing_source_record_columns(connection):
                connection.execute(
                    f"ALTER TABLE research_source_records ADD COLUMN {name} {column_type}"
                )
        connection.commit()
    except sqlite3.Error:
        if connection.in_transaction:
            connection.rollback()
        raise


def _heal_missing_development_stage_rows(connection: sqlite3.Connection) -> None:
    """Add newly declared stage rows without rewriting any existing stage history."""
    experiment_count = int(
        connection.execute("SELECT COUNT(*) FROM project_experiments").fetchone()[0]
    )
    if experiment_count == 0:
        return
    distinct_stage_count = int(
        connection.execute(
            """SELECT COUNT(*) FROM (
            SELECT DISTINCT project_id, experiment_id, stage FROM experiment_stage_events
            )"""
        ).fetchone()[0]
    )
    if distinct_stage_count == experiment_count * len(DEVELOPMENT_STAGE_ORDER):
        return
    experiment_rows = connection.execute(
        """SELECT project_id, experiment_id, linked_at
        FROM project_experiments ORDER BY linked_at, project_id, experiment_id"""
    ).fetchall()
    existing = {
        (str(row["project_id"]), str(row["experiment_id"]), str(row["stage"]))
        for row in connection.execute(
            "SELECT DISTINCT project_id, experiment_id, stage FROM experiment_stage_events"
        ).fetchall()
    }
    missing = [
        (str(row["project_id"]), str(row["experiment_id"]), stage, str(row["linked_at"]))
        for row in experiment_rows
        for stage in DEVELOPMENT_STAGE_ORDER
        if (str(row["project_id"]), str(row["experiment_id"]), stage) not in existing
    ]
    if not missing:
        return
    connection.execute("BEGIN IMMEDIATE")
    try:
        for project_id, experiment_id, stage, linked_at in missing:
            if stage in {"hypothesis", "data", "strategy"}:
                state = "pass"
                reason = "immutable experiment specification created"
            elif stage == "baseline":
                state = "ready"
                reason = "immutable experiment specification is ready for baseline"
            else:
                state = "not_started"
                reason = "stage added additively; awaiting prerequisite stages"
            connection.execute(
                """INSERT OR IGNORE INTO experiment_stage_events
                (project_id, experiment_id, stage, sequence, state, occurred_at, reason)
                VALUES (?, ?, ?, 1, ?, ?, ?)""",
                (project_id, experiment_id, stage, state, linked_at, reason),
            )
        connection.commit()
    except sqlite3.Error:
        if connection.in_transaction:
            connection.rollback()
        raise


def _migrate_schema_v1(connection: sqlite3.Connection, database: Path) -> None:
    """Serialize backup and migration so the retained v1 snapshot cannot become stale."""

    connection.execute("BEGIN IMMEDIATE")
    try:
        version_row = connection.execute("PRAGMA user_version").fetchone()
        locked_version = 0 if version_row is None else int(version_row[0])
        if locked_version == SCHEMA_VERSION:
            # Another process completed the migration while this connection waited for the lock.
            connection.commit()
            return
        if locked_version != LEGACY_SCHEMA_VERSION:
            raise DataError(f"unsupported control store schema version {locked_version}")
        _verified_v1_backup(connection, database)
        _apply_schema_v2_locked(connection, include_legacy_schema=True)
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def _migrate_schema_v2(connection: sqlite3.Connection, database: Path) -> None:
    """Serialize the exact v2 backup and additive owner-auth schema migration."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        version_row = connection.execute("PRAGMA user_version").fetchone()
        locked_version = 0 if version_row is None else int(version_row[0])
        if locked_version == SCHEMA_VERSION:
            connection.commit()
            return
        if locked_version != OWNER_AUTH_PREVIOUS_SCHEMA_VERSION:
            raise DataError(f"unsupported control store schema version {locked_version}")
        _verified_v2_backup(connection, database)
        _execute_static_sql_script(connection, _SCHEMA_V3)
        _execute_static_sql_script(connection, _SCHEMA_V4)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def _migrate_schema_v3(connection: sqlite3.Connection, database: Path) -> None:
    """Serialize the exact v3 backup and additive literature-artifact migration."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        version_row = connection.execute("PRAGMA user_version").fetchone()
        locked_version = 0 if version_row is None else int(version_row[0])
        if locked_version == SCHEMA_VERSION:
            connection.commit()
            return
        if locked_version != PREVIOUS_SCHEMA_VERSION:
            raise DataError(f"unsupported control store schema version {locked_version}")
        _verified_v3_backup(connection, database)
        _execute_static_sql_script(connection, _SCHEMA_V4)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def _enum_value(value: object, field: str, allowed: frozenset[str]) -> str:
    clean = _required_text(value, field, max_length=64)
    if clean not in allowed:
        raise DataError(f"unsupported {field} {clean!r}")
    return clean


def _budget_values(value: object, *, require_minimum: bool) -> dict[str, int | float]:
    if not isinstance(value, Mapping):
        raise DataError("research contract budget must be a JSON object")
    clean = _json_object(value, "research budget")
    required = {"wall_seconds", "source_requests", "variants"}
    if require_minimum and not required <= clean.keys():
        raise DataError(
            "research contract budget requires wall_seconds, source_requests, and variants"
        )
    result: dict[str, int | float] = {}
    for key, item in clean.items():
        if isinstance(item, bool) or not isinstance(item, int | float) or item < 0:
            raise DataError(f"research budget {key!r} must be a non-negative finite number")
        if isinstance(item, float) and not math.isfinite(item):
            raise DataError(f"research budget {key!r} must be a non-negative finite number")
        result[key] = item
    return result


def _research_review_state(row: sqlite3.Row | None) -> str:
    if row is None:
        return "pending"
    return "approved" if row["decision"] == "approve" else "rejected"


def _research_fingerprint(value: object, field: str) -> str:
    clean = _required_text(value, field, max_length=512)
    lowered = clean.casefold()
    blocked = ("placeholder", "todo", "tbd", "unknown", "dummy", "example")
    suffix = clean.rsplit(":", 1)[-1]
    if len(clean) < 12 or any(token in lowered for token in blocked) or len(set(suffix)) < 4:
        raise DataError(f"{field} must be a real, non-placeholder fingerprint")
    return clean


def _research_boundary_from_dict(payload: Mapping[str, object]) -> Any:
    # Keep the heavy analytical package out of the Workstation's narrow owner-auth import path.
    from alpha_research import research_d2_boundary_from_dict

    return research_d2_boundary_from_dict(payload)


def _confirmation_classification(evidence: Mapping[str, object]) -> str:
    # Owner-auth persistence never needs the empirical classifier; research transitions do.
    from alpha_research import confirmation_classification_from_evidence

    return confirmation_classification_from_evidence(evidence)


def _research_d2_topology(payload: Mapping[str, object]) -> tuple[dict[str, object], str]:
    protocol = payload.get("protocol")
    if not isinstance(protocol, dict):
        raise DataError("research contract approval requires a protocol object")
    topology = protocol.get("evidence_topology")
    if not isinstance(topology, dict):
        raise DataError("research contract protocol requires evidence_topology")
    raw_boundary = topology.get("boundary")
    if not isinstance(raw_boundary, dict):
        raise DataError("research contract evidence_topology requires a canonical boundary")
    boundary = _research_boundary_from_dict(raw_boundary)
    d2 = topology.get("D2")
    if not isinstance(d2, dict):
        raise DataError("research contract approval requires sealed D2 and D3 topology")
    boundary_hash = _research_fingerprint(
        d2.get("boundary_hash"), "research contract D2 boundary hash"
    )
    if boundary_hash != boundary.boundary_sha256:
        raise DataError("research contract D2 boundary hash does not match canonical semantics")
    expected_shares = {
        "D0": boundary.shares.d0_percent / 100,
        "D1": boundary.shares.d1_percent / 100,
        "D2": boundary.shares.d2_percent / 100,
        "D3": boundary.shares.d3_percent / 100,
    }
    for zone, expected in expected_shares.items():
        zone_value = topology.get(zone)
        if not isinstance(zone_value, dict):
            raise DataError(f"research contract evidence_topology requires {zone}")
        share = zone_value.get("share")
        if (
            isinstance(share, bool)
            or not isinstance(share, int | float)
            or not math.isclose(float(share), expected, abs_tol=1e-12)
        ):
            raise DataError(f"research contract {zone} share conflicts with canonical boundary")
    chart = protocol.get("chart_fingerprint")
    if chart != boundary.chart_fingerprint.to_dict():
        raise DataError("research contract chart fingerprint conflicts with canonical boundary")
    return d2, boundary_hash


class ControlStore:
    """Typed public seam over ALPHA's local Workstation v3 control database."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)

    def _database_path(self) -> Path:
        root = self._data_dir / "control"
        if root.is_symlink():
            raise DataError(f"control store root must not be a symlink: {root}")
        root.mkdir(parents=True, exist_ok=True)
        database = root / DATABASE_NAME
        if database.is_symlink():
            raise DataError(f"control store database must not be a symlink: {database}")
        if database.exists() and not database.is_file():
            raise DataError(f"control store database is not a file: {database}")
        return database

    def _open(self) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
        try:
            database = self._database_path()
            connection = sqlite3.connect(database, timeout=5.0, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            version_row = connection.execute("PRAGMA user_version").fetchone()
            version = 0 if version_row is None else int(version_row[0])
            if version not in {
                0,
                LEGACY_SCHEMA_VERSION,
                OWNER_AUTH_PREVIOUS_SCHEMA_VERSION,
                PREVIOUS_SCHEMA_VERSION,
                SCHEMA_VERSION,
            }:
                raise DataError(f"unsupported control store schema version {version}")
            if version == LEGACY_SCHEMA_VERSION:
                _migrate_schema_v1(connection, database)
            elif version == OWNER_AUTH_PREVIOUS_SCHEMA_VERSION:
                _migrate_schema_v2(connection, database)
            elif version == PREVIOUS_SCHEMA_VERSION:
                _migrate_schema_v3(connection, database)
            elif version < SCHEMA_VERSION:
                connection.executescript(_SCHEMA)
                _apply_schema_v2(connection)
            else:
                # A store already at SCHEMA_VERSION opens with a read-only completeness
                # probe: no write-bearing statement runs on the steady-state path (reads
                # must not contend for the writer lock, and a lost governance row must
                # fail loud, never regenerate from the created_at date rule). Idempotent
                # DDL healing runs only when a declared object is actually missing.
                _heal_missing_schema_objects(connection)
            _heal_missing_development_stage_rows(connection)
            return connection
        except (OSError, sqlite3.Error) as exc:
            if connection is not None:
                connection.close()
            raise DataError("cannot initialize control store") from exc
        except Exception:
            if connection is not None:
                connection.close()
            raise

    @contextmanager
    def _transaction(self, *, write: bool) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            # ``_open`` uses SQLite autocommit so every transaction, including a read-only
            # projection, must begin explicitly.  A deferred read transaction pins one WAL
            # snapshot at its first query; without it a multi-query AgentBrief can combine
            # control-plane rows from different commits.
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            if connection.in_transaction:
                connection.rollback()
            raise DataError("control store transaction failed") from exc
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _require_project(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        pid = _canonical_uuid(project_id, "project_id")
        row = connection.execute("SELECT * FROM projects WHERE project_id = ?", (pid,)).fetchone()
        if row is None:
            raise DataError(f"unknown strategy project {pid!r}")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _require_research_contract(
        connection: sqlite3.Connection, project_id: str, contract_id: str
    ) -> sqlite3.Row:
        _canonical_uuid(project_id, "project_id")
        cid = _require_content_id(contract_id, "research contract_id", prefix="rc")
        row = connection.execute(
            "SELECT * FROM research_contracts WHERE project_id = ? AND contract_id = ?",
            (project_id, cid),
        ).fetchone()
        if row is None:
            raise DataError(f"unknown research contract {cid!r} for project {project_id!r}")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _latest_research_review(
        connection: sqlite3.Connection, contract_id: str
    ) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            connection.execute(
                """SELECT * FROM research_contract_review_events WHERE contract_id = ?
            ORDER BY sequence DESC LIMIT 1""",
                (contract_id,),
            ).fetchone(),
        )

    @staticmethod
    def _latest_research_phase(
        connection: sqlite3.Connection, project_id: str
    ) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            connection.execute(
                """SELECT * FROM research_phase_events WHERE project_id = ?
            ORDER BY sequence DESC LIMIT 1""",
                (project_id,),
            ).fetchone(),
        )

    @staticmethod
    def _latest_research_execution(
        connection: sqlite3.Connection, project_id: str
    ) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            connection.execute(
                """SELECT * FROM research_execution_events WHERE project_id = ?
            ORDER BY sequence DESC LIMIT 1""",
                (project_id,),
            ).fetchone(),
        )

    @staticmethod
    def _latest_research_d2(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            connection.execute(
                """SELECT * FROM research_d2_events WHERE project_id = ?
            ORDER BY sequence DESC LIMIT 1""",
                (project_id,),
            ).fetchone(),
        )

    @staticmethod
    def _research_source_view(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["metadata"] = _decode_json(result.pop("metadata_json"), "research source metadata")
        authors_raw = result.pop("authors_json", None)
        if authors_raw is None:
            result["authors"] = []
        else:
            authors = _decode_json(authors_raw, "research source authors")
            if not isinstance(authors, list) or any(not isinstance(item, str) for item in authors):
                raise DataError("corrupt research source authors")
            result["authors"] = authors
        return result

    @staticmethod
    def _research_source_pack_view(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["source_ids"] = _decode_json(
            result.pop("source_ids_json"), "research source pack ids"
        )
        result["definition"] = _decode_json(
            result.pop("definition_json"), "research source pack definition"
        )
        return result

    @classmethod
    def _research_contract_view(
        cls, connection: sqlite3.Connection, row: sqlite3.Row
    ) -> dict[str, object]:
        result = dict(row)
        result["payload"] = _decode_json(result.pop("payload_json"), "research contract payload")
        review = cls._latest_research_review(connection, str(row["contract_id"]))
        result["review_state"] = _research_review_state(review)
        result["latest_review"] = None if review is None else dict(review)
        return result

    @staticmethod
    def _require_revision_d2_reuse(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        d2: Mapping[str, object],
        boundary_hash: str,
        exclude_contract_id: str | None,
        subject: str,
    ) -> None:
        """The one revise-reuse authority rule, shared by approval-time and reopen-time gates.

        ``exclude_contract_id`` ignores the candidate's own D2 events at approval time (the
        revision's sealed event already exists by then); reopen runs before the revision has
        any D2 event of its own, so nothing is excluded there.
        """

        if d2.get("relation_to_prior") not in RESEARCH_D2_REVISION_RELATIONS:
            raise DataError(
                f"{subject} requires unopened_sealed_reuse, non_overlapping_future, "
                "or external_replication D2 data"
            )
        if exclude_contract_id is None:
            overlap_rows = connection.execute(
                """SELECT state FROM research_d2_events
                WHERE project_id = ? AND boundary_hash = ?""",
                (project_id, boundary_hash),
            ).fetchall()
        else:
            overlap_rows = connection.execute(
                """SELECT state FROM research_d2_events
                WHERE project_id = ? AND boundary_hash = ? AND contract_id <> ?""",
                (project_id, boundary_hash, exclude_contract_id),
            ).fetchall()
        if d2.get("relation_to_prior") == "unopened_sealed_reuse":
            exposed = connection.execute(
                """SELECT 1 FROM research_d2_events
                WHERE project_id = ? AND state <> 'sealed' LIMIT 1""",
                (project_id,),
            ).fetchone()
            if exposed is not None or any(item["state"] != "sealed" for item in overlap_rows):
                raise DataError(f"{subject} may reuse only a never-authorized sealed D2 boundary")
        elif overlap_rows:
            raise DataError(f"{subject} requires a distinct D2 boundary")

    @classmethod
    def _validate_research_contract_for_approval(
        cls, connection: sqlite3.Connection, row: sqlite3.Row
    ) -> dict[str, object]:
        payload = _decode_json(row["payload_json"], "research contract payload")
        if not isinstance(payload, dict):
            raise DataError("research contract payload must be a JSON object")
        if payload.get("schema") != "ResearchContractV1":
            raise DataError("research contract approval requires schema ResearchContractV1")
        if payload.get("approval_ready") is not True:
            raise DataError("research contract approval requires approval_ready=true")
        if payload.get("blocking_questions") != []:
            raise DataError("research contract approval requires zero blocking_questions")
        thesis = payload.get("thesis")
        if not isinstance(thesis, dict):
            raise DataError("research contract approval requires a thesis object")
        primary_claims = thesis.get("primary_claims")
        if not isinstance(primary_claims, list) or len(primary_claims) != 1:
            raise DataError("research contract approval requires exactly one primary claim")
        primary_claim = primary_claims[0]
        if not isinstance(primary_claim, dict) or not primary_claim:
            raise DataError("research contract primary claim must be a non-empty object")
        d2, d2_boundary = _research_d2_topology(payload)
        protocol = cast(dict[str, object], payload["protocol"])
        boundary_authority = protocol.get("boundary_authority")
        if not isinstance(boundary_authority, dict) or set(boundary_authority) != {
            "kind",
            "real_market_evidence",
            "empirical_confirmation_authorized",
        }:
            raise DataError("research contract requires an exact boundary_authority declaration")
        boundary_kind = boundary_authority.get("kind")
        if boundary_kind not in {"synthetic_acceptance_fixture", "empirical_dataset"}:
            raise DataError("research contract has an unsupported boundary authority kind")
        real_market_evidence = boundary_authority.get("real_market_evidence")
        empirical_confirmation = boundary_authority.get("empirical_confirmation_authorized")
        if not isinstance(real_market_evidence, bool) or not isinstance(
            empirical_confirmation, bool
        ):
            raise DataError("research contract boundary authority flags must be booleans")
        expected_authority = (
            (False, False) if boundary_kind == "synthetic_acceptance_fixture" else (True, True)
        )
        if (real_market_evidence, empirical_confirmation) != expected_authority:
            raise DataError("research contract boundary authority flags conflict with its kind")
        if row["scope"] == "confirmation" and not empirical_confirmation:
            raise DataError("synthetic acceptance boundaries cannot authorize D2 confirmation")
        topology = cast(dict[str, object], protocol["evidence_topology"])
        d3 = topology.get("D3")
        if d2.get("state") != "sealed" or not isinstance(d3, dict) or d3.get("state") != "sealed":
            raise DataError("research contract approval requires sealed D2 and D3 topology")
        d3_share = d3.get("share")
        if (
            isinstance(d3_share, bool)
            or not isinstance(d3_share, int | float)
            or not math.isfinite(float(d3_share))
            or float(d3_share) < 0.20
            or float(d3_share) >= 1.0
        ):
            raise DataError("research contract D3 share must be in [0.20, 1.0)")
        pack_id = payload.get("source_pack_id")
        if not isinstance(pack_id, str):
            raise DataError("research contract approval requires source_pack_id")
        _require_content_id(pack_id, "research source_pack_id", prefix="sp")
        pack = connection.execute(
            """SELECT 1 FROM research_source_packs
            WHERE project_id = ? AND pack_id = ?""",
            (row["project_id"], pack_id),
        ).fetchone()
        if pack is None:
            raise DataError("research contract source pack is not linked to its project")
        budget = _budget_values(payload.get("budget"), require_minimum=True)
        analysis_plan = payload.get("analysis_plan")
        if analysis_plan is not None:
            from alpha_cli.research_analysis_plan import validate_analysis_plan

            if not isinstance(analysis_plan, Mapping):
                raise DataError("research contract analysis_plan must be a JSON object")
            variants = budget["variants"]
            validate_analysis_plan(
                analysis_plan,
                max_grid_cells=int(variants) if int(variants) == variants else 0,
            )
        hashes = payload.get("hashes")
        if not isinstance(hashes, dict):
            raise DataError("research contract approval requires a hashes object")
        for field in ("code", "environment", "evaluator"):
            _research_fingerprint(hashes.get(field), f"research contract {field} hash")
        data_hash = hashes.get("data")
        if data_hash is not None:
            _research_fingerprint(data_hash, "research contract data hash")
        parent_id = row["parent_contract_id"]
        if row["scope"] == "exploration" and isinstance(parent_id, str):
            prior_decision = connection.execute(
                """SELECT decision.disposition
                FROM research_decision_events AS decision
                JOIN research_contracts AS decided
                  ON decided.contract_id = decision.contract_id
                WHERE decision.project_id = ?
                  AND (decision.contract_id = ? OR decided.parent_contract_id = ?)
                ORDER BY decision.sequence DESC LIMIT 1""",
                (row["project_id"], parent_id, parent_id),
            ).fetchone()
            if prior_decision is not None and prior_decision["disposition"] == "revise":
                cls._require_revision_d2_reuse(
                    connection,
                    project_id=str(row["project_id"]),
                    d2=d2,
                    boundary_hash=d2_boundary,
                    exclude_contract_id=str(row["contract_id"]),
                    subject="revised exploration",
                )
        if row["scope"] == "confirmation":
            if not isinstance(parent_id, str):
                raise DataError("confirmation approval requires an exploration parent")
            parent = cls._require_research_contract(connection, str(row["project_id"]), parent_id)
            parent_payload = _decode_json(
                parent["payload_json"], "parent research contract payload"
            )
            if not isinstance(parent_payload, dict):  # pragma: no cover - stored JSON invariant.
                raise DataError("corrupt parent research contract payload")
            _, parent_boundary = _research_d2_topology(parent_payload)
            if d2_boundary != parent_boundary:
                raise DataError(
                    "confirmation D2 boundary must match its approved exploration contract"
                )
            confirmation = payload.get("confirmation")
            if not isinstance(confirmation, dict) or not confirmation:
                raise DataError(
                    "confirmation contract approval requires a non-empty confirmation object"
                )
            if data_hash is None:
                raise DataError("confirmation contract approval requires a frozen data hash")
            variant_count = confirmation.get("variant_count")
            multiplicity_count = confirmation.get("multiplicity_count")
            if (
                isinstance(variant_count, bool)
                or not isinstance(variant_count, int)
                or variant_count < 1
                or isinstance(multiplicity_count, bool)
                or not isinstance(multiplicity_count, int)
                or multiplicity_count != variant_count
            ):
                raise DataError(
                    "confirmation contract requires a complete variant/multiplicity count"
                )
            familywise_alpha = confirmation.get("familywise_alpha")
            target_power = confirmation.get("target_power")
            if (
                isinstance(familywise_alpha, bool)
                or not isinstance(familywise_alpha, int | float)
                or not math.isclose(float(familywise_alpha), 0.05, abs_tol=1e-12)
            ):
                raise DataError("confirmation familywise_alpha must equal 0.05")
            if (
                isinstance(target_power, bool)
                or not isinstance(target_power, int | float)
                or not math.isclose(float(target_power), 0.90, abs_tol=1e-12)
            ):
                raise DataError("confirmation target_power must equal 0.90")
            power_report = confirmation.get("power_report")
            achieved_power = (
                None if not isinstance(power_report, dict) else power_report.get("achieved_power")
            )
            if (
                isinstance(achieved_power, bool)
                or not isinstance(achieved_power, int | float)
                or not math.isfinite(float(achieved_power))
                or float(achieved_power) < 0.90
                or float(achieved_power) > 1.0
            ):
                raise DataError("confirmation power report must clear target_power=0.90")
            fingerprints = confirmation.get("fingerprints")
            if not isinstance(fingerprints, dict) or not fingerprints:
                raise DataError("confirmation contract requires frozen fingerprints")
            for field, value in fingerprints.items():
                _research_fingerprint(value, f"confirmation {field} fingerprint")
        return payload

    @staticmethod
    def _append_research_phase_event(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        contract_id: str,
        phase: str,
        actor: str,
        reason: str,
        next_action: str,
        responsibility: str,
        blocker: str | None,
        recovery: str | None,
        at: str,
    ) -> sqlite3.Row:
        prior = ControlStore._latest_research_phase(connection, project_id)
        sequence = 1 if prior is None else int(prior["sequence"]) + 1
        if prior is not None and (
            not isinstance(prior["occurred_at"], str) or at < prior["occurred_at"]
        ):
            raise DataError("research phase timestamp precedes prior event")
        connection.execute(
            """INSERT INTO research_phase_events (
                project_id, sequence, contract_id, phase, occurred_at, actor, reason,
                next_action, responsibility, blocker, recovery
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                sequence,
                contract_id,
                phase,
                at,
                actor,
                reason,
                next_action,
                responsibility,
                blocker,
                recovery,
            ),
        )
        row = connection.execute(
            "SELECT * FROM research_phase_events WHERE project_id = ? AND sequence = ?",
            (project_id, sequence),
        ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist research phase event")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _append_research_d2_event(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        contract_id: str,
        state: str,
        boundary_hash: str,
        actor: str,
        reason: str,
        at: str,
    ) -> sqlite3.Row:
        clean_boundary = _research_fingerprint(boundary_hash, "research D2 boundary hash")
        prior = ControlStore._latest_research_d2(connection, project_id)
        sequence = 1 if prior is None else int(prior["sequence"]) + 1
        if prior is not None and (
            not isinstance(prior["occurred_at"], str) or at < prior["occurred_at"]
        ):
            raise DataError("research D2 timestamp precedes prior event")
        connection.execute(
            """INSERT INTO research_d2_events (
                project_id, sequence, contract_id, state, boundary_hash, actor,
                occurred_at, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, sequence, contract_id, state, clean_boundary, actor, at, reason),
        )
        row = connection.execute(
            "SELECT * FROM research_d2_events WHERE project_id = ? AND sequence = ?",
            (project_id, sequence),
        ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist research D2 event")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _append_project_scope_event(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        version_id: str | None,
        experiment_id: str | None,
        at: str,
        reason: str,
    ) -> None:
        """Record the exact version/experiment scope selected at one control-plane instant."""
        latest = connection.execute(
            """SELECT sequence, occurred_at FROM project_scope_events
            WHERE project_id = ? ORDER BY sequence DESC LIMIT 1""",
            (project_id,),
        ).fetchone()
        sequence = 1 if latest is None else int(latest["sequence"]) + 1
        if latest is not None:
            occurred_at = latest["occurred_at"]
            if not isinstance(occurred_at, str) or at < occurred_at:
                raise DataError("project scope timestamp precedes prior selection event")
        connection.execute(
            "INSERT INTO project_scope_events VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_id,
                sequence,
                version_id,
                experiment_id,
                at,
                _required_text(reason, "project scope reason", max_length=200),
            ),
        )

    @staticmethod
    def _require_project_experiment(
        connection: sqlite3.Connection, project_id: str, experiment_id: str
    ) -> None:
        _canonical_uuid(project_id, "project_id")
        _require_content_id(experiment_id, "experiment_id", prefix="ex")
        row = connection.execute(
            "SELECT 1 FROM project_experiments WHERE project_id = ? AND experiment_id = ?",
            (project_id, experiment_id),
        ).fetchone()
        if row is None:
            raise DataError(f"experiment {experiment_id!r} is not linked to project {project_id!r}")
        lineage = connection.execute(
            """SELECT src.contract_id AS strategy_contract_id,
                erc.contract_id AS experiment_contract_id
            FROM experiment_specs e
            LEFT JOIN research_contract_strategy_links src
                ON src.project_id = ? AND src.version_id = e.strategy_version_id
            LEFT JOIN research_contract_experiment_links erc
                ON erc.project_id = ? AND erc.experiment_id = e.experiment_id
            WHERE e.experiment_id = ?""",
            (project_id, project_id, experiment_id),
        ).fetchone()
        if lineage is None:
            raise DataError("corrupt control store: linked experiment specification is missing")
        strategy_contract = lineage["strategy_contract_id"]
        experiment_contract = lineage["experiment_contract_id"]
        if (strategy_contract is None) != (experiment_contract is None) or (
            strategy_contract is not None and strategy_contract != experiment_contract
        ):
            raise DataError(
                "research-governed experiment contract lineage is missing or mismatched"
            )

    @staticmethod
    def _require_pre_reveal_holdout(
        connection: sqlite3.Connection,
        project_id: str,
        experiment_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """SELECT h.revealed_at, h.contaminated_at, s.spec_hash, s.start_date
            FROM holdout_state h JOIN holdout_specs s
                ON s.project_id = h.project_id AND s.experiment_id = h.experiment_id
            WHERE h.project_id = ? AND h.experiment_id = ?""",
            (project_id, experiment_id),
        ).fetchone()
        if row is None:
            raise DataError("dated final holdout must be sealed before research begins")
        if row["revealed_at"] is not None:
            raise DataError("research cannot resume after the final holdout is revealed")
        if row["contaminated_at"] is not None:
            raise DataError("final holdout is contaminated for this lineage")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _manifest_research_cutoff(holdout: sqlite3.Row) -> str:
        start = date.fromisoformat(str(holdout["start_date"]))
        return (start - timedelta(days=1)).isoformat()

    @staticmethod
    def _reveal_attempt_matches_job(
        connection: sqlite3.Connection,
        project_id: str,
        experiment_id: str,
        job_id: str,
    ) -> bool:
        rows = connection.execute(
            """SELECT details_json FROM attempt_records
            WHERE project_id = ? AND experiment_id = ? AND stage = 'holdout'
            ORDER BY recorded_at, attempt_id""",
            (project_id, experiment_id),
        ).fetchall()
        for row in rows:
            details = _decode_json(row["details_json"], "holdout attempt details")
            if (
                isinstance(details, dict)
                and details.get("action") == "holdout_reveal"
                and details.get("job_id") == job_id
                and details.get("step") == 1
            ):
                return True
        return False

    def _verified_run(self, run_id: str) -> tuple[Path, dict[str, object]]:
        """Resolve a completed run and verify every declared v3 artifact before trusting it."""
        rdir = find_run_dir(self._data_dir, run_id)
        if rdir is None:
            raise DataError(f"unknown completed run {run_id!r}")
        manifest = read_manifest(rdir)
        verify_manifest_artifacts(rdir, manifest)
        return rdir, cast(dict[str, object], manifest)

    def _read_research_gate_evidence(
        self,
        run_id: str,
        details: Mapping[str, object],
    ) -> dict[str, object]:
        """Read one canonical typed result from its hash-verified immutable run artifact."""
        reference = details.get("gate_packet_evidence_ref")
        if not isinstance(reference, Mapping) or set(reference) != {
            "artifact",
            "content_sha256",
        }:
            raise DataError("research gate evidence requires an exact immutable artifact reference")
        artifact = reference.get("artifact")
        content_sha256 = reference.get("content_sha256")
        if artifact != _RESEARCH_GATE_EVIDENCE_ARTIFACT:
            raise DataError(
                f"research gate evidence artifact must be {_RESEARCH_GATE_EVIDENCE_ARTIFACT}"
            )
        if not isinstance(content_sha256, str) or _SHA256_RE.fullmatch(content_sha256) is None:
            raise DataError("research gate evidence content_sha256 must be a lowercase SHA-256")

        rdir, manifest = self._verified_run(run_id)
        artifacts = manifest.get("artifacts")
        metadata = None if not isinstance(artifacts, dict) else artifacts.get(artifact)
        if not isinstance(metadata, dict):
            raise DataError("research run has no declared immutable artifact for gate evidence")
        if metadata.get("sha256") != content_sha256:
            raise DataError("research gate evidence selector does not match the manifest artifact")
        path = rdir / artifact
        if path.is_symlink() or not path.is_file():
            raise DataError("research gate evidence artifact is not a regular immutable file")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise DataError("research gate evidence artifact cannot be read") from exc
        if len(raw) > _MAX_JSON_BYTES:
            raise DataError("research gate evidence artifact exceeds the bounded JSON size")
        try:
            parsed: object = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DataError("research gate evidence artifact is not valid UTF-8 JSON") from exc
        if not isinstance(parsed, Mapping):
            raise DataError("research gate evidence artifact must contain a JSON object")
        evidence = _json_object(parsed, "research gate evidence artifact")
        canonical = _canonical_json(evidence, "research gate evidence artifact").encode("utf-8")
        if raw != canonical:
            raise DataError("research gate evidence artifact must use canonical JSON bytes")
        return evidence

    def _require_run(self, run_id: str) -> str:
        self._verified_run(run_id)
        return run_id

    def _require_generic_evidence_run(self, run_id: str) -> str:
        _, manifest = self._verified_run(run_id)
        if (
            manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
            or manifest.get("artifact_contract_version") != ARTIFACT_CONTRACT_VERSION
            or manifest.get("run_identity_version") != 3
            or manifest.get("run_id") != run_id
        ):
            raise DataError(
                "generic evidence admission requires an immutable v3 manifest, artifact "
                "contract, run identity, and matching run_id"
            )
        command = manifest.get("command")
        kind = manifest.get("kind")
        research_family = any(
            isinstance(value, str) and value.strip().casefold().startswith("research")
            for value in (command, kind)
        )
        research_marker = bool(_GENERIC_EVIDENCE_RESEARCH_MARKERS.intersection(manifest))
        if manifest.get("scope") == "research_only" or research_family or research_marker:
            raise DataError("research runs cannot enter the generic evidence ledger")
        if command not in _GENERIC_EVIDENCE_COMMANDS:
            raise DataError("generic evidence source does not use a decision-grade command")
        return run_id

    def _require_research_run(
        self,
        run_id: str,
        *,
        project_id: str,
        contract_id: str,
        contract_payload: Mapping[str, object],
        phase: str,
        config_fingerprint: str,
    ) -> str:
        """Verify an immutable run against every frozen research-authority fingerprint."""
        _, manifest = self._verified_run(run_id)
        if (
            manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
            or manifest.get("artifact_contract_version") != ARTIFACT_CONTRACT_VERSION
            or manifest.get("run_identity_version") != 3
            or manifest.get("run_id") != run_id
        ):
            raise DataError(
                "research run admission requires an immutable v3 manifest, artifact contract, "
                "and run identity"
            )
        contract_hash = hashlib.sha256(
            _canonical_json(contract_payload, "research run contract").encode("utf-8")
        ).hexdigest()
        hashes = contract_payload.get("hashes")
        if not isinstance(hashes, dict):  # Approval validation normally catches this first.
            raise DataError("research run contract has no frozen fingerprints")
        expected_zone = {
            "pilot": "D0",
            "deep_research": "D1",
            "sealed_confirmation": "D2",
        }.get(phase)
        expected_command = {
            "pilot": "research_pilot",
            "deep_research": "research_deep",
            "sealed_confirmation": "research_confirm",
        }.get(phase)
        expected: dict[str, object] = {
            "command": expected_command,
            "kind": "research",
            "project_id": project_id,
            "research_contract_id": contract_id,
            "contract_hash": contract_hash,
            "source_pack_id": contract_payload.get("source_pack_id"),
            "research_fingerprints": hashes,
            "evidence_zone": expected_zone,
            "eligible_for_holdout_or_execution": False,
            "places_orders": False,
            "snapshot_id": None,
            "snapshot_hash": None,
            "strategy_fingerprint": None,
            "source_fingerprint": contract_hash,
            "execution_fingerprint": config_fingerprint,
        }
        if phase == "pilot":
            protocol = contract_payload.get("protocol")
            operator = None if not isinstance(protocol, Mapping) else protocol.get("d0_operator")
            fixture = None if not isinstance(operator, Mapping) else operator.get("fixture")
            dataset_hash = (
                None if not isinstance(fixture, Mapping) else fixture.get("definition_fingerprint")
            )
            if not isinstance(dataset_hash, str) or _SHA256_RE.fullmatch(dataset_hash) is None:
                raise DataError("research D0 operator has no content-addressed fixture definition")
            expected["d0_operator"] = operator
            expected["d0_operator_fingerprint"] = (
                None if not isinstance(operator, Mapping) else operator.get("fingerprint")
            )
            expected["d0_acceptance_artifact"] = "d0_acceptance.json"
            expected["dataset_hash"] = dataset_hash
            run_identity = {
                "command": expected_command,
                "project_id": project_id,
                "research_contract_id": contract_id,
                "contract_hash": contract_hash,
                "dataset_hash": dataset_hash,
                "execution_fingerprint": config_fingerprint,
            }
            expected_run_id = hashlib.sha256(
                _canonical_json(run_identity, "research D0 run identity").encode("utf-8")
            ).hexdigest()[:16]
            if run_id != expected_run_id:
                raise DataError("research D0 run_id does not match its content-derived identity")
        if phase == "deep_research":
            manifest_dataset_hash = manifest.get("dataset_hash")
            if (
                not isinstance(manifest_dataset_hash, str)
                or _SHA256_RE.fullmatch(manifest_dataset_hash) is None
            ):
                raise DataError("research D1 run has no content-addressed dataset hash")
            # An empirical contract froze its dataset bytes at approval (hashes.data); the
            # run must claim exactly those bytes. Synthetic lanes carry data=None and are
            # bound through the content-derived run identity below instead.
            frozen_data = hashes.get("data")
            if frozen_data is not None:
                expected["dataset_hash"] = frozen_data
            run_identity = {
                "command": expected_command,
                "project_id": project_id,
                "research_contract_id": contract_id,
                "contract_hash": contract_hash,
                "dataset_hash": manifest_dataset_hash,
                "execution_fingerprint": config_fingerprint,
            }
            expected_run_id = hashlib.sha256(
                _canonical_json(run_identity, "research D1 run identity").encode("utf-8")
            ).hexdigest()[:16]
            if run_id != expected_run_id:
                raise DataError("research D1 run_id does not match its content-derived identity")
        if phase == "sealed_confirmation":
            manifest_dataset_hash = manifest.get("dataset_hash")
            if (
                not isinstance(manifest_dataset_hash, str)
                or _SHA256_RE.fullmatch(manifest_dataset_hash) is None
            ):
                raise DataError("research D2 run has no content-addressed dataset hash")
            # Confirmation approval requires a frozen dataset hash (hashes.data); the sealed
            # one-shot run must claim exactly those approval-frozen bytes.
            expected["dataset_hash"] = hashes.get("data")
            expected["watermark"] = "REGISTERED CONFIRMATORY"
            expected["real_market_evidence"] = True
            run_identity = {
                "command": expected_command,
                "project_id": project_id,
                "research_contract_id": contract_id,
                "contract_hash": contract_hash,
                "dataset_hash": manifest_dataset_hash,
                "execution_fingerprint": config_fingerprint,
            }
            expected_run_id = hashlib.sha256(
                _canonical_json(run_identity, "research D2 run identity").encode("utf-8")
            ).hexdigest()[:16]
            if run_id != expected_run_id:
                raise DataError("research D2 run_id does not match its content-derived identity")
        mismatches = [field for field, value in expected.items() if manifest.get(field) != value]
        if mismatches:
            raise DataError("research run authority mismatch: " + ", ".join(sorted(mismatches)))
        return run_id

    def _require_completed_d0_attempt(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        contract_id: str,
        contract_payload: Mapping[str, object],
    ) -> sqlite3.Row:
        """Require exactly one immutable, passing D0 pilot for phase advancement."""

        rows = connection.execute(
            """SELECT * FROM research_attempt_records
            WHERE project_id = ? AND contract_id = ?
              AND phase = 'pilot' AND kind = 'd0-synthetic-pilot'
              AND status = 'completed'
            ORDER BY recorded_at, attempt_id""",
            (project_id, contract_id),
        ).fetchall()
        if len(rows) != 1 or not isinstance(rows[0]["run_id"], str):
            raise DataError(
                "pilot advancement requires exactly one completed immutable D0 synthetic run"
            )
        row = cast(sqlite3.Row, rows[0])
        self._verify_research_attempt_run(
            project_id=project_id,
            attempt=self._research_attempt_view(row),
            contract_payload=contract_payload,
        )
        return row

    def _require_passing_d0_run(
        self,
        *,
        run_id: str,
        project_id: str,
        contract_id: str,
        contract_payload: Mapping[str, object],
        config_fingerprint: str,
    ) -> dict[str, object]:
        """Reverify one D0 run and every mandatory acceptance outcome."""

        protocol = contract_payload.get("protocol")
        bound_operator = None if not isinstance(protocol, Mapping) else protocol.get("d0_operator")
        crypto_crowding = (
            isinstance(bound_operator, Mapping)
            and bound_operator.get("name") == "bybit_btcusdt_crowding_reversal"
        )
        if crypto_crowding:
            from alpha_cli.research_crypto_runtime import (  # noqa: PLC0415
                validate_crypto_d0_acceptance_artifact,
                validate_crypto_d0_contract,
            )

            operator = validate_crypto_d0_contract(contract_payload)
        else:
            from alpha_cli.research_runtime import (  # noqa: PLC0415
                validate_d0_acceptance_artifact,
                validate_d0_pilot_contract,
            )

            operator = validate_d0_pilot_contract(contract_payload)

        self._require_research_run(
            run_id,
            project_id=project_id,
            contract_id=contract_id,
            contract_payload=contract_payload,
            phase="pilot",
            config_fingerprint=config_fingerprint,
        )
        run_dir, manifest = self._verified_run(run_id)
        contract_hash = hashlib.sha256(
            _canonical_json(contract_payload, "research D0 acceptance contract").encode("utf-8")
        ).hexdigest()
        fixture = operator.get("fixture")
        dataset_hash = (
            None if not isinstance(fixture, Mapping) else fixture.get("definition_fingerprint")
        )
        operator_fingerprint = operator.get("fingerprint")
        if (
            not isinstance(dataset_hash, str)
            or not isinstance(operator_fingerprint, str)
            or _SHA256_RE.fullmatch(dataset_hash) is None
            or _SHA256_RE.fullmatch(operator_fingerprint) is None
        ):
            raise DataError("registered D0 acceptance binding is not content-addressed")
        if crypto_crowding:
            validate_crypto_d0_acceptance_artifact(
                run_dir,
                manifest,
                project_id=project_id,
                contract_id=contract_id,
                contract_hash=contract_hash,
                execution_fingerprint=config_fingerprint,
            )
        else:
            validate_d0_acceptance_artifact(
                run_dir,
                manifest,
                project_id=project_id,
                contract_id=contract_id,
                contract_hash=contract_hash,
                dataset_hash=dataset_hash,
                execution_fingerprint=config_fingerprint,
                d0_operator_fingerprint=operator_fingerprint,
            )
        return manifest

    def _require_d1_verified_evidence(
        self,
        *,
        run_id: str,
        project_id: str,
        contract_id: str,
        contract_payload: Mapping[str, object],
    ) -> dict[str, object]:
        """Reverify D1 typed evidence by exact mechanical recomputation (D0 pattern)."""

        run_dir, manifest = self._verified_run(run_id)
        protocol = contract_payload.get("protocol")
        operator = None if not isinstance(protocol, Mapping) else protocol.get("d0_operator")
        if isinstance(operator, Mapping) and operator.get("name") == (
            "bybit_btcusdt_crowding_reversal"
        ):
            from alpha_cli.research_crypto_binding import load_crypto_empirical_d1
            from alpha_cli.research_crypto_runtime import validate_crypto_d1_evidence_artifacts

            observations, boundary = load_crypto_empirical_d1(self, contract_payload)
            return validate_crypto_d1_evidence_artifacts(
                run_dir,
                manifest,
                project_id=project_id,
                contract_id=contract_id,
                contract=contract_payload,
                observations=observations,
                boundary=boundary,
            )
        from alpha_cli.research_d1 import validate_d1_evidence_artifacts

        return validate_d1_evidence_artifacts(
            run_dir,
            manifest,
            project_id=project_id,
            contract_id=contract_id,
            contract=contract_payload,
        )

    def _require_d2_verified_evidence(
        self,
        *,
        run_id: str,
        project_id: str,
        contract_id: str,
        contract_payload: Mapping[str, object],
    ) -> dict[str, object]:
        """Reverify D2 typed evidence by exact mechanical recomputation (D0/D1 pattern)."""

        run_dir, manifest = self._verified_run(run_id)
        protocol = contract_payload.get("protocol")
        operator = None if not isinstance(protocol, Mapping) else protocol.get("d0_operator")
        if isinstance(operator, Mapping) and operator.get("name") == (
            "bybit_btcusdt_crowding_reversal"
        ):
            from alpha_cli.research_crypto_binding import load_crypto_empirical_d1
            from alpha_cli.research_crypto_d2 import validate_crypto_d2_evidence_artifacts

            observations, boundary = load_crypto_empirical_d1(self, contract_payload)
            return validate_crypto_d2_evidence_artifacts(
                run_dir,
                manifest,
                project_id=project_id,
                contract_id=contract_id,
                contract=contract_payload,
                observations=observations,
                boundary=boundary,
            )
        from alpha_cli.research_d2 import validate_d2_evidence_artifacts

        return validate_d2_evidence_artifacts(
            run_dir,
            manifest,
            project_id=project_id,
            contract_id=contract_id,
            contract=contract_payload,
        )

    @staticmethod
    def _require_d0_acceptance_reference(
        details: Mapping[str, object], manifest: Mapping[str, object]
    ) -> None:
        """Bind one completed D0 attempt to the exact reverified acceptance artifact."""

        acceptance_ref = details.get("d0_acceptance_ref")
        artifacts = manifest.get("artifacts")
        acceptance_metadata = (
            None if not isinstance(artifacts, Mapping) else artifacts.get("d0_acceptance.json")
        )
        expected_sha = (
            None
            if not isinstance(acceptance_metadata, Mapping)
            else acceptance_metadata.get("sha256")
        )
        if (
            not isinstance(acceptance_ref, Mapping)
            or set(acceptance_ref) != {"artifact", "content_sha256"}
            or acceptance_ref.get("artifact") != "d0_acceptance.json"
            or acceptance_ref.get("content_sha256") != expected_sha
            or not isinstance(expected_sha, str)
            or _SHA256_RE.fullmatch(expected_sha) is None
        ):
            raise DataError(
                "completed D0 attempt requires the exact typed acceptance artifact provenance"
            )

    def _verify_research_attempt_run(
        self,
        *,
        project_id: str,
        attempt: Mapping[str, object],
        contract_payload: Mapping[str, object],
    ) -> dict[str, object]:
        """Reverify one attempt run, including mechanical D0 acceptance when applicable."""

        run_id = attempt.get("run_id")
        if not isinstance(run_id, str):
            raise DataError("research attempt has no immutable run to verify")
        contract_id = attempt.get("contract_id")
        phase = attempt.get("phase")
        config_fingerprint = attempt.get("config_fingerprint")
        if not all(isinstance(value, str) for value in (contract_id, phase, config_fingerprint)):
            raise DataError("research attempt has corrupt immutable run lineage")
        if phase == "pilot" and attempt.get("status") == "completed":
            manifest = self._require_passing_d0_run(
                run_id=run_id,
                project_id=project_id,
                contract_id=cast(str, contract_id),
                contract_payload=contract_payload,
                config_fingerprint=cast(str, config_fingerprint),
            )
            details = attempt.get("details")
            if not isinstance(details, Mapping):
                raise DataError("completed D0 attempt has corrupt acceptance details")
            self._require_d0_acceptance_reference(details, manifest)
            return manifest
        self._require_research_run(
            run_id,
            project_id=project_id,
            contract_id=cast(str, contract_id),
            contract_payload=contract_payload,
            phase=cast(str, phase),
            config_fingerprint=cast(str, config_fingerprint),
        )
        if phase == "deep_research" and attempt.get("status") == "completed":
            details = attempt.get("details")
            if not isinstance(details, Mapping) or "gate_packet_evidence_ref" not in details:
                raise DataError("completed D1 attempt has no typed evidence reference")
            self._require_d1_verified_evidence(
                run_id=run_id,
                project_id=project_id,
                contract_id=cast(str, contract_id),
                contract_payload=contract_payload,
            )
        if phase == "sealed_confirmation" and attempt.get("status") == "completed":
            details = attempt.get("details")
            if not isinstance(details, Mapping) or "gate_packet_evidence_ref" not in details:
                raise DataError("completed D2 attempt has no typed evidence reference")
            self._require_d2_verified_evidence(
                run_id=run_id,
                project_id=project_id,
                contract_id=cast(str, contract_id),
                contract_payload=contract_payload,
            )
        _, manifest = self._verified_run(run_id)
        return manifest

    def _mechanical_confirmation_evidence(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        contract_id: str,
        contract_payload: Mapping[str, object],
    ) -> dict[str, object]:
        """Return the one typed D2 artifact after re-verifying its immutable run lineage."""
        rows = connection.execute(
            """SELECT * FROM research_attempt_records
            WHERE project_id = ? AND contract_id = ?
            ORDER BY recorded_at, attempt_id""",
            (project_id, contract_id),
        ).fetchall()
        verified_evidence: list[dict[str, object]] = []
        for row in rows:
            details = _decode_json(row["details_json"], "research confirmation attempt details")
            if not isinstance(details, dict):  # pragma: no cover - stored JSON invariant.
                raise DataError("corrupt research confirmation attempt details")
            if "gate_packet_evidence_ref" not in details:
                continue
            if (
                row["phase"] != "sealed_confirmation"
                or row["status"] != "completed"
                or not isinstance(row["run_id"], str)
            ):
                raise DataError(
                    "typed D2 evidence requires a completed sealed_confirmation immutable run"
                )
            self._require_research_run(
                str(row["run_id"]),
                project_id=project_id,
                contract_id=contract_id,
                contract_payload=contract_payload,
                phase="sealed_confirmation",
                config_fingerprint=str(row["config_fingerprint"]),
            )
            evidence = self._read_research_gate_evidence(str(row["run_id"]), details)
            self._require_d2_verified_evidence(
                run_id=str(row["run_id"]),
                project_id=project_id,
                contract_id=contract_id,
                contract_payload=contract_payload,
            )
            _confirmation_classification(evidence)
            verified_evidence.append(evidence)
        if len(verified_evidence) != 1:
            raise DataError(
                "consumed confirmation requires exactly one completed typed D2 evidence attempt"
            )
        return verified_evidence[0]

    def _mechanical_confirmation_outcome(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        contract_id: str,
        contract_payload: Mapping[str, object],
    ) -> str:
        """Return the one mechanical D2 classification from verified immutable evidence."""
        evidence = self._mechanical_confirmation_evidence(
            connection,
            project_id=project_id,
            contract_id=contract_id,
            contract_payload=contract_payload,
        )
        return _confirmation_classification(evidence)

    def create_project(
        self,
        *,
        name: str,
        hypothesis: str,
        falsification_criterion: str,
        status: ProjectStatus = "active",
        research_origin: ProjectResearchOrigin = "strategy_development",
        project_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Create one owner-facing strategy project."""
        pid = _new_uuid(project_id, "project_id")
        clean_status = _required_text(status, "project status", max_length=16)
        if clean_status not in PROJECT_STATUSES:
            raise DataError(f"unsupported project status {status!r}")
        clean_origin = _enum_value(
            research_origin, "project research origin", PROJECT_RESEARCH_ORIGINS
        )
        timestamp = _at(at)
        row: dict[str, object] = {
            "project_id": pid,
            "name": _required_text(name, "project name", max_length=200),
            "hypothesis": _required_text(hypothesis, "hypothesis"),
            "falsification_criterion": _required_text(
                falsification_criterion, "falsification criterion"
            ),
            "status": clean_status,
            "current_version_id": None,
            "current_experiment_id": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        with self._transaction(write=True) as connection:
            if (
                connection.execute("SELECT 1 FROM projects WHERE project_id = ?", (pid,)).fetchone()
                is not None
            ):
                raise DataError(f"strategy project {pid!r} already exists")
            connection.execute(
                """INSERT INTO projects (
                    project_id, name, hypothesis, falsification_criterion, status,
                    current_version_id, current_experiment_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(row.values()),
            )
            connection.execute(
                """INSERT INTO project_research_governance (
                    project_id, research_required, origin, recorded_at
                ) VALUES (?, ?, ?, ?)""",
                (pid, 1, clean_origin, timestamp),
            )
            self._append_project_scope_event(
                connection,
                project_id=pid,
                version_id=None,
                experiment_id=None,
                at=timestamp,
                reason="project created",
            )
        return row

    @staticmethod
    def _capture_fault_checkpoint(_label: str) -> None:
        """No-op seam used by transactional fault-injection tests."""

    def _bootstrap_research_case_authority(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        contract_id: str,
        actor: str,
        boundary_hash: str,
        at: str,
    ) -> None:
        """Create the captured-phase / idle-execution / sealed-D2 authority triplet.

        Shared by ``capture_research_case`` and ``create_research_contract`` so the two
        bootstrap paths cannot drift apart; the fault checkpoints are production no-ops.
        """

        self._append_research_phase_event(
            connection,
            project_id=project_id,
            contract_id=contract_id,
            phase="captured",
            actor=actor,
            reason="research contract draft captured",
            next_action="Triage the captured research idea.",
            responsibility="codex",
            blocker=None,
            recovery=None,
            at=at,
        )
        self._capture_fault_checkpoint("captured")
        connection.execute(
            """INSERT INTO research_execution_events (
                project_id, sequence, contract_id, state, occurred_at, actor, reason,
                next_action, responsibility, active_job_id, checkpoint, blocker, recovery
            ) VALUES (?, 1, ?, 'idle', ?, ?, ?, ?, 'codex', NULL, NULL, NULL, NULL)""",
            (
                project_id,
                contract_id,
                at,
                actor,
                "research case captured",
                "Triage the captured research idea.",
            ),
        )
        self._capture_fault_checkpoint("execution")
        self._append_research_d2_event(
            connection,
            project_id=project_id,
            contract_id=contract_id,
            state="sealed",
            boundary_hash=boundary_hash,
            actor="system",
            reason="confirmation data remains sealed before D2 authorization",
            at=at,
        )
        self._capture_fault_checkpoint("d2")

    def capture_research_case(
        self,
        *,
        name: str,
        hypothesis: str,
        falsification_criterion: str,
        draft_payload: Mapping[str, object],
        created_by: str,
        next_action: str,
        responsibility: ResearchResponsibility,
        blocker: str | None = None,
        recovery: str | None = None,
        project_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Atomically and idempotently create one project plus its captured/triaged case."""

        clean_name = _required_text(name, "project name", max_length=200)
        clean_hypothesis = _required_text(hypothesis, "hypothesis")
        clean_falsifier = _required_text(falsification_criterion, "falsification criterion")
        clean_payload = _json_object(draft_payload, "research contract payload")
        clean_actor = _required_text(created_by, "research contract creator", max_length=200)
        clean_action = _required_text(next_action, "research next_action")
        clean_responsibility = _enum_value(
            responsibility, "research responsibility", RESEARCH_RESPONSIBILITIES
        )
        clean_blocker = _optional_text(blocker, "research blocker")
        clean_recovery = _optional_text(recovery, "research recovery")
        if (clean_blocker is None) != (clean_recovery is None):
            raise DataError("research blocker and recovery must be recorded together")
        capture_identity = {
            "schema_version": 1,
            "name": clean_name,
            "hypothesis": clean_hypothesis,
            "falsification_criterion": clean_falsifier,
        }
        pid = (
            str(
                uuid.uuid5(
                    _RESEARCH_CAPTURE_NAMESPACE,
                    _canonical_json(capture_identity, "research capture identity"),
                )
            )
            if project_id is None
            else _canonical_uuid(project_id, "project_id")
        )
        contract_identity = {
            "schema_version": 1,
            "project_id": pid,
            "scope": "exploration",
            "parent_contract_id": None,
            "payload": clean_payload,
        }
        contract_id = _content_id("rc", contract_identity)
        try:
            _, draft_d2_boundary = _research_d2_topology(clean_payload)
        except DataError:
            draft_d2_boundary = contract_id
        timestamp = _at(at)
        project_row: dict[str, object] = {
            "project_id": pid,
            "name": clean_name,
            "hypothesis": clean_hypothesis,
            "falsification_criterion": clean_falsifier,
            "status": "active",
            "current_version_id": None,
            "current_experiment_id": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        with self._transaction(write=True) as connection:
            existing_project = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?", (pid,)
            ).fetchone()
            if existing_project is None:
                connection.execute(
                    """INSERT INTO projects (
                        project_id, name, hypothesis, falsification_criterion, status,
                        current_version_id, current_experiment_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    tuple(project_row.values()),
                )
                self._capture_fault_checkpoint("project")
                connection.execute(
                    """INSERT INTO project_research_governance (
                        project_id, research_required, origin, recorded_at
                    ) VALUES (?, 1, 'research_capture', ?)""",
                    (pid, timestamp),
                )
                self._capture_fault_checkpoint("governance")
                self._append_project_scope_event(
                    connection,
                    project_id=pid,
                    version_id=None,
                    experiment_id=None,
                    at=timestamp,
                    reason="project created",
                )
                self._capture_fault_checkpoint("scope")
            else:
                project_row = dict(existing_project)
                expected_project = {
                    "name": clean_name,
                    "hypothesis": clean_hypothesis,
                    "falsification_criterion": clean_falsifier,
                    "status": "active",
                    "current_version_id": None,
                    "current_experiment_id": None,
                }
                mismatches = [
                    field
                    for field, expected in expected_project.items()
                    if existing_project[field] != expected
                ]
                governance = connection.execute(
                    """SELECT research_required, origin FROM project_research_governance
                    WHERE project_id = ?""",
                    (pid,),
                ).fetchone()
                if mismatches or governance is None or tuple(governance) != (1, "research_capture"):
                    raise DataError("research capture id conflicts with an existing project")

            contract = connection.execute(
                "SELECT * FROM research_contracts WHERE contract_id = ?", (contract_id,)
            ).fetchone()
            if contract is None:
                other = connection.execute(
                    "SELECT 1 FROM research_contracts WHERE project_id = ? LIMIT 1", (pid,)
                ).fetchone()
                if other is not None:
                    raise DataError("research capture project already has a different contract")
                connection.execute(
                    """INSERT INTO research_contracts (
                        contract_id, project_id, scope, parent_contract_id, payload_json,
                        created_by, author_kind, created_at
                    ) VALUES (?, ?, 'exploration', NULL, ?, ?, 'agent', ?)""",
                    (
                        contract_id,
                        pid,
                        _canonical_json(clean_payload, "research contract payload"),
                        clean_actor,
                        timestamp,
                    ),
                )
                self._capture_fault_checkpoint("contract")

            phase = self._latest_research_phase(connection, pid)
            execution = self._latest_research_execution(connection, pid)
            d2 = self._latest_research_d2(connection, pid)
            if phase is None:
                if execution is not None or d2 is not None:
                    raise DataError("research capture has partial authority state")
                self._bootstrap_research_case_authority(
                    connection,
                    project_id=pid,
                    contract_id=contract_id,
                    actor=clean_actor,
                    boundary_hash=draft_d2_boundary,
                    at=timestamp,
                )
                phase = self._latest_research_phase(connection, pid)
            if execution is None:
                execution = self._latest_research_execution(connection, pid)
            if d2 is None:
                d2 = self._latest_research_d2(connection, pid)
            if (
                phase is None
                or execution is None
                or d2 is None
                or phase["contract_id"] != contract_id
                or execution["contract_id"] != contract_id
                or d2["contract_id"] != contract_id
            ):
                raise DataError("research capture authority state is incomplete or mismatched")
            if phase["phase"] == "captured":
                self._append_research_phase_event(
                    connection,
                    project_id=pid,
                    contract_id=contract_id,
                    phase="triage",
                    actor=clean_actor,
                    reason="bounded triage recorded material ambiguities without a parameter sweep",
                    next_action=clean_action,
                    responsibility=clean_responsibility,
                    blocker=clean_blocker,
                    recovery=clean_recovery,
                    at=timestamp,
                )
                self._capture_fault_checkpoint("triage")
            elif phase["phase"] == "triage":
                if (
                    phase["next_action"] != clean_action
                    or phase["responsibility"] != clean_responsibility
                    or phase["blocker"] != clean_blocker
                    or phase["recovery"] != clean_recovery
                ):
                    raise DataError("research capture retry conflicts with persisted triage state")
            # A repeated capture after later progress resolves to the existing case without
            # manufacturing a duplicate project or resetting its phase.
            project_row["research_gate_state"] = self._research_gate_state(connection, pid)

        contract_view = self.get_research_contract(contract_id)
        return {
            "project": project_row,
            "contract": contract_view,
            "case": self.research_case_summary(pid),
        }

    def list_projects(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, object]]:
        """Return bounded project summaries, newest first."""
        limit, offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC, project_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            views = []
            for row in rows:
                view = dict(row)
                view["research_gate_state"] = self._research_gate_state(
                    connection, str(row["project_id"])
                )
                views.append(view)
        return views

    def _research_gate_state(self, connection: sqlite3.Connection, project_id: str) -> str:
        """Derive the spec-§15 anti-premature-backtesting gate state for one project.

        `passed` deliberately supersedes `overridden`: once an owner advance_to_strategy
        decision exists, earlier overrides are historical ledger entries, not live authority.
        """
        governance = connection.execute(
            """SELECT research_required FROM project_research_governance
            WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        if governance is None:
            raise DataError("strategy project has no research-governance record")
        governed = int(governance["research_required"]) == 1 or (
            self._latest_research_phase(connection, project_id) is not None
        )
        if not governed:
            return "not_required"
        advanced = connection.execute(
            """SELECT 1 FROM research_decision_events
            WHERE project_id = ? AND disposition = 'advance_to_strategy' LIMIT 1""",
            (project_id,),
        ).fetchone()
        if advanced is not None:
            return "passed"
        override = connection.execute(
            "SELECT 1 FROM research_gate_override_events WHERE project_id = ? LIMIT 1",
            (project_id,),
        ).fetchone()
        if override is not None:
            return "overridden"
        return "open"

    def research_gate_state(self, project_id: str) -> str:
        """Return {not_required, open, passed, overridden} for one project (spec §15)."""
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            return self._research_gate_state(connection, project_id)

    def record_research_gate_override(
        self,
        project_id: str,
        *,
        actor: str,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append one owner research-gate override event (never a mutable boolean)."""
        clean_actor = _required_text(actor, "research gate override actor", max_length=100)
        clean_reason = _required_text(reason, "research gate override reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            state = self._research_gate_state(connection, project_id)
            if state == "not_required":
                raise DataError("grandfathered project has no research gate to override")
            if state == "passed":
                raise DataError("research gate already passed; an override cannot apply")
            latest = connection.execute(
                """SELECT COALESCE(MAX(sequence), 0) AS sequence
                FROM research_gate_override_events WHERE project_id = ?""",
                (project_id,),
            ).fetchone()
            sequence = int(latest["sequence"]) + 1
            connection.execute(
                """INSERT INTO research_gate_override_events (
                    project_id, sequence, actor, reason, recorded_at
                ) VALUES (?, ?, ?, ?, ?)""",
                (project_id, sequence, clean_actor, clean_reason, timestamp),
            )
        return {
            "project_id": project_id,
            "sequence": sequence,
            "actor": clean_actor,
            "reason": clean_reason,
            "recorded_at": timestamp,
        }

    def list_active_research_gate_overrides(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, object]]:
        """Return override events for projects whose gate is currently overridden.

        Overrides on projects that later pass research drop out of this projection but
        remain in the per-project append-only ledger.
        """
        limit, offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            rows = connection.execute(
                """SELECT o.project_id, o.sequence, o.actor, o.reason, o.recorded_at,
                    p.name AS project_name
                FROM research_gate_override_events o
                JOIN projects p ON p.project_id = o.project_id
                ORDER BY o.recorded_at DESC, o.project_id, o.sequence DESC""",
            ).fetchall()
            states: dict[str, str] = {}
            active = []
            for row in rows:
                pid = str(row["project_id"])
                if pid not in states:
                    states[pid] = self._research_gate_state(connection, pid)
                if states[pid] == "overridden":
                    active.append(dict(row))
        return active[offset : offset + limit]

    def get_project(self, project_id: str) -> dict[str, object]:
        """Return a complete bounded projection of one project's control-plane lineage."""
        with self._transaction(write=False) as connection:
            project = dict(self._require_project(connection, project_id))
            versions = connection.execute(
                """SELECT v.* FROM strategy_versions v
                JOIN project_versions pv ON pv.version_id = v.version_id
                WHERE pv.project_id = ? ORDER BY pv.linked_at, v.version_id""",
                (project_id,),
            ).fetchall()
            experiments = connection.execute(
                """SELECT e.* FROM experiment_specs e
                JOIN project_experiments pe ON pe.experiment_id = e.experiment_id
                WHERE pe.project_id = ? ORDER BY pe.linked_at, e.experiment_id""",
                (project_id,),
            ).fetchall()
            links = connection.execute(
                """SELECT * FROM stage_run_links
                WHERE project_id = ? ORDER BY linked_at, link_id""",
                (project_id,),
            ).fetchall()
            attempts = connection.execute(
                """SELECT * FROM attempt_records
                WHERE project_id = ? ORDER BY recorded_at, attempt_id""",
                (project_id,),
            ).fetchall()
            holdouts = connection.execute(
                """SELECT h.*, s.spec_hash AS holdout_spec_hash,
                    CASE WHEN h.revealed_at IS NOT NULL THEN s.start_date END AS start_date,
                    CASE WHEN h.revealed_at IS NOT NULL THEN s.end_date END AS end_date
                FROM holdout_state h
                LEFT JOIN holdout_specs s
                    ON s.project_id = h.project_id AND s.experiment_id = h.experiment_id
                WHERE h.project_id = ? ORDER BY h.revealed_at""",
                (project_id,),
            ).fetchall()
            audit = connection.execute(
                "SELECT * FROM holdout_audit WHERE project_id = ? ORDER BY audit_id",
                (project_id,),
            ).fetchall()
            decisions = connection.execute(
                """SELECT * FROM decision_packets
                WHERE project_id = ? ORDER BY created_at, packet_id""",
                (project_id,),
            ).fetchall()
            monte_carlo_reviews = connection.execute(
                """SELECT * FROM monte_carlo_reviews
                WHERE project_id = ? ORDER BY recorded_at, review_id""",
                (project_id,),
            ).fetchall()
            gate_state = self._research_gate_state(connection, project_id)
            gate_overrides = connection.execute(
                """SELECT * FROM research_gate_override_events
                WHERE project_id = ? ORDER BY sequence""",
                (project_id,),
            ).fetchall()
            version_views = []
            for row in versions:
                view = self._version_view(row)
                research_link = connection.execute(
                    """SELECT contract_id FROM research_contract_strategy_links
                    WHERE project_id = ? AND version_id = ?""",
                    (project_id, row["version_id"]),
                ).fetchone()
                if research_link is not None:
                    view["research_contract_id"] = research_link["contract_id"]
                version_views.append(view)
            experiment_views = []
            for row in experiments:
                view = self._experiment_view(row)
                research_link = connection.execute(
                    """SELECT contract_id FROM research_contract_experiment_links
                    WHERE project_id = ? AND experiment_id = ?""",
                    (project_id, row["experiment_id"]),
                ).fetchone()
                if research_link is not None:
                    view["research_contract_id"] = research_link["contract_id"]
                experiment_views.append(view)
            link_views = [self._stage_link_view(connection, row) for row in links]
            stage_views = [
                self._experiment_stage_view(
                    connection,
                    project_id=project_id,
                    experiment_id=str(experiment["experiment_id"]),
                    stage=stage,
                )
                for experiment in experiments
                for stage in DEVELOPMENT_STAGE_ORDER
            ]
        project["versions"] = version_views
        project["experiments"] = experiment_views
        project["stage_run_links"] = link_views
        project["stage_states"] = stage_views
        project["attempts"] = [self._attempt_view(row) for row in attempts]
        project["holdouts"] = [dict(row) for row in holdouts]
        project["holdout_audit"] = [dict(row) for row in audit]
        project["decision_packets"] = [self._decision_packet_view(row) for row in decisions]
        project["monte_carlo_reviews"] = [
            {
                **dict(row),
                "schema_version": 1,
                "evidence_hashes": _decode_json(
                    row["evidence_hashes_json"], "Monte Carlo review evidence hashes"
                ),
            }
            for row in monte_carlo_reviews
        ]
        project["research_gate_state"] = gate_state
        project["research_gate_overrides"] = [dict(row) for row in gate_overrides]
        return project

    def _monte_carlo_evidence_hashes(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
    ) -> tuple[tuple[str, str], ...]:
        rows = connection.execute(
            """SELECT * FROM stage_run_links
            WHERE project_id = ? AND experiment_id = ? AND stage = 'monte_carlo'
            ORDER BY linked_at, link_id""",
            (project_id, experiment_id),
        ).fetchall()
        evidence: list[tuple[str, str, str, str]] = []
        for row in rows:
            view = self._stage_link_view(connection, row)
            if view["state"] not in {"pass", "warning"}:
                continue
            run_id = str(row["run_id"])
            rdir, manifest = self._verified_run(run_id)
            command = str(manifest.get("command"))
            if command not in _MONTE_CARLO_COMMANDS:
                continue
            evidence.append(
                (
                    command,
                    run_id,
                    sha256_file(rdir / "manifest.json"),
                    str(manifest.get("source_run_id")),
                )
            )
        commands = {command for command, _, _, _ in evidence}
        if commands != _MONTE_CARLO_COMMANDS:
            raise DataError(
                "Monte Carlo review requires verified classical and Kronos run evidence"
            )
        source_runs = {source_run_id for _, _, _, source_run_id in evidence}
        if len(source_runs) != 1:
            raise DataError("Monte Carlo family evidence does not share one source validation run")
        return tuple((run_id, digest) for _, run_id, digest, _ in sorted(evidence))

    def _encoded_monte_carlo_evidence_hashes(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
    ) -> str:
        evidence_hashes = self._monte_carlo_evidence_hashes(
            connection,
            project_id=project_id,
            experiment_id=experiment_id,
        )
        return _canonical_json(
            [[run_id, digest] for run_id, digest in evidence_hashes],
            "Monte Carlo review evidence hashes",
        )

    def review_monte_carlo(
        self,
        project_id: str,
        experiment_id: str,
        *,
        decision: MonteCarloReviewDecision,
        actor: str,
        rationale: str,
        review_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append the CLI-only owner disposition for one exact warning evidence set."""
        if decision not in {"continue", "revise", "reject"}:
            raise DataError("Monte Carlo decision must be continue, revise, or reject")
        clean_actor = _required_text(actor, "Monte Carlo review actor", max_length=200)
        clean_rationale = _required_text(rationale, "Monte Carlo review rationale")
        rid = _new_uuid(review_id, "review_id")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            stage_state = self._latest_experiment_stage_state(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage="monte_carlo",
            )
            if stage_state != "warning":
                raise DataError("owner Monte Carlo review is allowed only for a warning stage")
            encoded = self._encoded_monte_carlo_evidence_hashes(
                connection, project_id=project_id, experiment_id=experiment_id
            )
            existing = connection.execute(
                """SELECT * FROM monte_carlo_reviews
                WHERE project_id = ? AND experiment_id = ?""",
                (project_id, experiment_id),
            ).fetchone()
            if existing is not None:
                if (
                    existing["decision"] == decision
                    and existing["actor"] == clean_actor
                    and existing["rationale"] == clean_rationale
                    and existing["evidence_hashes_json"] == encoded
                ):
                    row = existing
                else:
                    raise DataError("Monte Carlo evidence already has an append-only owner review")
            else:
                connection.execute(
                    """INSERT INTO monte_carlo_reviews (
                    review_id, project_id, experiment_id, decision, actor, rationale,
                    evidence_hashes_json, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rid,
                        project_id,
                        experiment_id,
                        decision,
                        clean_actor,
                        clean_rationale,
                        encoded,
                        timestamp,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM monte_carlo_reviews WHERE review_id = ?", (rid,)
                ).fetchone()
            if row is None:  # pragma: no cover - insert/select invariant.
                raise DataError("control store failed to persist Monte Carlo review")
            return {
                **dict(row),
                "schema_version": 1,
                "evidence_hashes": _decode_json(
                    row["evidence_hashes_json"], "Monte Carlo review evidence hashes"
                ),
            }

    def monte_carlo_review_allows_progression(self, project_id: str, experiment_id: str) -> bool:
        """Return true for a clear stage or an untampered warning explicitly continued by owner."""
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            state = self._latest_experiment_stage_state(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage="monte_carlo",
            )
            if state == "pass":
                return True
            if state != "warning":
                return False
            review = connection.execute(
                """SELECT * FROM monte_carlo_reviews
                WHERE project_id = ? AND experiment_id = ?""",
                (project_id, experiment_id),
            ).fetchone()
            if review is None or review["decision"] != "continue":
                return False
            expected = self._encoded_monte_carlo_evidence_hashes(
                connection, project_id=project_id, experiment_id=experiment_id
            )
            return bool(review["evidence_hashes_json"] == expected)

    def create_research_source(
        self,
        project_id: str,
        *,
        title: str,
        locator: str,
        provider: str,
        access_mode: str,
        metadata: Mapping[str, object] | None = None,
        content_hash: str | None = None,
        doi: str | None = None,
        year: int | None = None,
        authors: Sequence[str] | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Create or reuse one immutable, content-addressed literature/source record."""
        clean_access = _enum_value(
            access_mode, "research source access_mode", RESEARCH_SOURCE_ACCESS_MODES
        )
        clean_hash = (
            None
            if content_hash is None
            else _required_text(content_hash, "research source content_hash", max_length=64)
        )
        if clean_hash is not None and _SHA256_RE.fullmatch(clean_hash) is None:
            raise DataError("research source content_hash must be a lowercase SHA-256 digest")
        clean_metadata = _json_object(metadata or {}, "research source metadata")
        clean_doi = (
            None
            if doi is None
            else _required_text(doi, "research source doi", max_length=200).lower()
        )
        if year is not None and (
            isinstance(year, bool) or not isinstance(year, int) or not 1800 <= year <= 2100
        ):
            raise DataError("research source year must be a plausible integer year")
        clean_authors: list[str] | None = None
        if authors is not None:
            clean_authors = [
                _required_text(author, "research source authors entry", max_length=200)
                for author in authors
            ]
        identity = {
            "schema_version": 1,
            "project_id": _canonical_uuid(project_id, "project_id"),
            "title": _required_text(title, "research source title", max_length=500),
            "locator": _required_text(locator, "research source locator", max_length=2_000),
            "provider": _required_text(provider, "research source provider", max_length=100),
            "access_mode": clean_access,
            "content_hash": clean_hash,
            "metadata": clean_metadata,
        }
        # Typed descriptors join the identity only when supplied so pre-R4 ids stay stable.
        if clean_doi is not None:
            identity["doi"] = clean_doi
        if year is not None:
            identity["year"] = year
        if clean_authors is not None:
            identity["authors"] = clean_authors
        source_id = _content_id("rs", identity)
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            existing = connection.execute(
                "SELECT * FROM research_source_records WHERE source_id = ?", (source_id,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """INSERT INTO research_source_records (
                        source_id, project_id, title, locator, provider, access_mode,
                        content_hash, metadata_json, created_at, doi, year, authors_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        source_id,
                        project_id,
                        identity["title"],
                        identity["locator"],
                        identity["provider"],
                        clean_access,
                        clean_hash,
                        _canonical_json(clean_metadata, "research source metadata"),
                        timestamp,
                        clean_doi,
                        year,
                        (
                            None
                            if clean_authors is None
                            else _canonical_json(clean_authors, "research source authors")
                        ),
                    ),
                )
                existing = connection.execute(
                    "SELECT * FROM research_source_records WHERE source_id = ?", (source_id,)
                ).fetchone()
        if existing is None:  # pragma: no cover
            raise DataError("control store failed to persist research source")
        return self._research_source_view(existing)

    def get_research_source(self, source_id: str) -> dict[str, object]:
        """Read one immutable research source."""
        sid = _require_content_id(source_id, "research source_id", prefix="rs")
        with self._transaction(write=False) as connection:
            row = connection.execute(
                "SELECT * FROM research_source_records WHERE source_id = ?", (sid,)
            ).fetchone()
        if row is None:
            raise DataError(f"unknown research source {sid!r}")
        return self._research_source_view(row)

    def get_research_source_context(
        self, source_id: str, *, excerpt_limit: int = 4_000
    ) -> dict[str, object]:
        """Return one source plus bounded untrusted extracted-page previews for review/Codex."""
        if isinstance(excerpt_limit, bool) or not 1 <= excerpt_limit <= 8_000:
            raise DataError("research source excerpt limit must be in 1..8000")
        source = self.get_research_source(source_id)
        with self._transaction(write=False) as connection:
            document = connection.execute(
                "SELECT extraction_id FROM research_document_texts WHERE source_id = ?",
                (source["source_id"],),
            ).fetchone()
        if document is None:
            return {**source, "document": None, "page_previews": []}
        record = self.get_research_document_text(str(document["extraction_id"]))
        artifact = record.pop("artifact")
        pages = artifact.get("pages") if isinstance(artifact, dict) else None
        previews: list[dict[str, object]] = []
        remaining = excerpt_limit
        for page in pages if isinstance(pages, list) else []:
            if remaining <= 0 or not isinstance(page, dict):
                break
            text = page.get("text")
            page_number = page.get("page")
            if not isinstance(text, str) or not isinstance(page_number, int):
                continue
            excerpt = text[:remaining]
            remaining -= len(excerpt)
            previews.append(
                {
                    "page": page_number,
                    "excerpt": excerpt,
                    "excerpt_truncated": len(excerpt) < len(text),
                    "text_sha256": page.get("text_sha256"),
                    "trust_label": "UNTRUSTED_SOURCE",
                }
            )
        return {**source, "document": record, "page_previews": previews}

    def _store_literature_artifact(
        self, *, category: str, artifact_id: str, payload: Mapping[str, object]
    ) -> tuple[str, str]:
        """Write one immutable JSON artifact below the fixed literature root."""
        if category not in {"discoveries", "extractions"}:
            raise DataError("unsupported literature artifact category")
        encoded = (
            json.dumps(
                _json_object(payload, "literature artifact"),
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        relative = Path("research") / "literature" / category / f"{artifact_id}.json"
        target = self._data_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise DataError("literature artifact path must not be a symlink")
        if target.exists():
            if not target.is_file() or target.read_bytes() != encoded:
                raise DataError("literature artifact identifier collision")
        else:
            descriptor, raw_temporary = tempfile.mkstemp(
                prefix=f".{artifact_id}.", suffix=".tmp", dir=target.parent
            )
            temporary = Path(raw_temporary)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
        return relative.as_posix(), digest

    def record_literature_discovery(
        self,
        project_id: str,
        *,
        artifact: Mapping[str, object],
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Record one bounded worker discovery without granting evidence authority."""
        payload = _json_object(artifact, "literature discovery")
        if payload.get("schema") != "LiteratureDiscoveryV1":
            raise DataError("literature discovery has an unsupported schema")
        raw_discovery_id = payload.get("discovery_id")
        if not isinstance(raw_discovery_id, str):
            raise DataError("literature discovery identifier is missing")
        discovery_id = _require_content_id(raw_discovery_id, "literature discovery_id", prefix="ld")
        query = _required_text(payload.get("query"), "literature discovery query", max_length=500)
        receipt = payload.get("receipt")
        if not isinstance(receipt, Mapping) or receipt.get("receipt_id") != discovery_id:
            raise DataError("literature discovery receipt does not match its identifier")
        raw_budget = receipt.get("budget")
        if not isinstance(raw_budget, Mapping):
            raise DataError("literature discovery budget is missing")
        budget = _json_object(raw_budget, "literature discovery budget")
        relative, artifact_sha256 = self._store_literature_artifact(
            category="discoveries", artifact_id=discovery_id, payload=payload
        )
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            connection.execute(
                """INSERT OR IGNORE INTO literature_discoveries
                (discovery_id, project_id, query, artifact_sha256, artifact_relpath,
                    budget_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    discovery_id,
                    project_id,
                    query,
                    artifact_sha256,
                    relative,
                    _canonical_json(budget, "literature discovery budget"),
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM literature_discoveries WHERE discovery_id = ?", (discovery_id,)
            ).fetchone()
        if row is None or row["project_id"] != project_id:
            raise DataError("literature discovery belongs to another project")
        return {**dict(row), "budget": budget, "artifact": payload}

    def get_literature_discovery(self, project_id: str, discovery_id: str) -> dict[str, object]:
        did = _require_content_id(discovery_id, "literature discovery_id", prefix="ld")
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            row = connection.execute(
                "SELECT * FROM literature_discoveries WHERE discovery_id = ? AND project_id = ?",
                (did, project_id),
            ).fetchone()
        if row is None:
            raise DataError(f"unknown literature discovery {did!r}")
        path = self._data_dir / str(row["artifact_relpath"])
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["artifact_sha256"]:
            raise DataError("literature discovery artifact failed integrity verification")
        payload = _decode_json(raw.decode(), "literature discovery artifact")
        if not isinstance(payload, dict) or payload.get("discovery_id") != did:
            raise DataError("literature discovery artifact identity is corrupt")
        result = dict(row)
        result["budget"] = _decode_json(result.pop("budget_json"), "literature discovery budget")
        result.pop("artifact_relpath", None)
        result["artifact"] = payload
        return result

    def record_research_document_text(
        self,
        source_id: str,
        *,
        artifact: Mapping[str, object],
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Bind an immutable ResearchDocumentTextV1 artifact to its acquired source."""
        payload = _json_object(artifact, "research document text")
        if payload.get("schema") != "ResearchDocumentTextV1":
            raise DataError("research document text has an unsupported schema")
        raw_extraction_id = payload.get("extraction_id")
        if not isinstance(raw_extraction_id, str):
            raise DataError("research extraction identifier is missing")
        extraction_id = _require_content_id(
            raw_extraction_id, "research extraction_id", prefix="rx"
        )
        source_sha = _required_text(
            payload.get("source_sha256"), "research document source_sha256", max_length=64
        )
        config_hash = _required_text(
            payload.get("config_hash"), "research document config_hash", max_length=64
        )
        if _SHA256_RE.fullmatch(source_sha) is None or _SHA256_RE.fullmatch(config_hash) is None:
            raise DataError("research document hashes must be lowercase SHA-256 digests")
        status = _enum_value(
            payload.get("status"),
            "research document status",
            frozenset({"extracted", "encrypted", "image_only", "truncated", "parser_failed"}),
        )
        pages = payload.get("pages")
        warnings = payload.get("warnings")
        if (
            not isinstance(pages, list)
            or not isinstance(warnings, list)
            or any(not isinstance(warning, str) for warning in warnings)
        ):
            raise DataError("research document pages or warnings are invalid")
        page_count = payload.get("page_count")
        character_count = payload.get("character_count")
        if (
            isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or page_count != len(pages)
            or isinstance(character_count, bool)
            or not isinstance(character_count, int)
            or character_count < 0
        ):
            raise DataError("research document counts are inconsistent")
        relative, artifact_sha256 = self._store_literature_artifact(
            category="extractions", artifact_id=extraction_id, payload=payload
        )
        sid = _require_content_id(source_id, "research source_id", prefix="rs")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            source = connection.execute(
                "SELECT content_hash FROM research_source_records WHERE source_id = ?", (sid,)
            ).fetchone()
            if source is None:
                raise DataError(f"unknown research source {sid!r}")
            if source["content_hash"] != source_sha:
                raise DataError("research document source digest does not match source receipt")
            connection.execute(
                """INSERT OR IGNORE INTO research_document_texts
                (extraction_id, source_id, source_sha256, artifact_sha256, artifact_relpath,
                    status, page_count, character_count, parser_version, config_hash,
                    warnings_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    extraction_id,
                    sid,
                    source_sha,
                    artifact_sha256,
                    relative,
                    status,
                    page_count,
                    character_count,
                    _required_text(
                        payload.get("parser_version"),
                        "research document parser_version",
                        max_length=64,
                    ),
                    config_hash,
                    _canonical_json(warnings, "research document warnings"),
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM research_document_texts WHERE extraction_id = ?", (extraction_id,)
            ).fetchone()
        if row is None or row["source_id"] != sid:
            raise DataError("research document extraction belongs to another source")
        return self.get_research_document_text(extraction_id)

    def get_research_document_text(self, extraction_id: str) -> dict[str, object]:
        eid = _require_content_id(extraction_id, "research extraction_id", prefix="rx")
        with self._transaction(write=False) as connection:
            row = connection.execute(
                "SELECT * FROM research_document_texts WHERE extraction_id = ?", (eid,)
            ).fetchone()
        if row is None:
            raise DataError(f"unknown research extraction {eid!r}")
        raw = (self._data_dir / str(row["artifact_relpath"])).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["artifact_sha256"]:
            raise DataError("research document text failed integrity verification")
        artifact = _decode_json(raw.decode(), "research document text artifact")
        if not isinstance(artifact, dict) or artifact.get("extraction_id") != eid:
            raise DataError("research document text identity is corrupt")
        result = dict(row)
        result.pop("artifact_relpath", None)
        result["warnings"] = _decode_json(result.pop("warnings_json"), "document warnings")
        result["artifact"] = artifact
        return result

    def _verified_source_anchor(
        self,
        connection: sqlite3.Connection,
        *,
        source_id: str,
        anchor: Mapping[str, object],
    ) -> dict[str, object]:
        raw_extraction_id = anchor.get("extraction_id")
        if not isinstance(raw_extraction_id, str):
            raise DataError("source anchor extraction identifier is missing")
        extraction_id = _require_content_id(
            raw_extraction_id, "source anchor extraction_id", prefix="rx"
        )
        page = anchor.get("page")
        char_start = anchor.get("char_start")
        char_end = anchor.get("char_end")
        exact_hash = _required_text(
            anchor.get("exact_text_sha256"), "source anchor exact_text_sha256", max_length=64
        )
        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or page < 1
            or isinstance(char_start, bool)
            or not isinstance(char_start, int)
            or char_start < 0
            or isinstance(char_end, bool)
            or not isinstance(char_end, int)
            or char_end <= char_start
            or char_end - char_start > 2_000
            or _SHA256_RE.fullmatch(exact_hash) is None
        ):
            raise DataError("source anchor coordinates or hash are invalid")
        document = connection.execute(
            "SELECT * FROM research_document_texts WHERE extraction_id = ? AND source_id = ?",
            (extraction_id, source_id),
        ).fetchone()
        if document is None or document["status"] != "extracted":
            raise DataError("source anchor requires an extracted document for this source")
        raw = (self._data_dir / str(document["artifact_relpath"])).read_bytes()
        if hashlib.sha256(raw).hexdigest() != document["artifact_sha256"]:
            raise DataError("source anchor document failed integrity verification")
        artifact = _decode_json(raw.decode(), "source anchor document")
        if not isinstance(artifact, dict) or not isinstance(artifact.get("pages"), list):
            raise DataError("source anchor document is corrupt")
        pages = artifact["pages"]
        if page > len(pages) or not isinstance(pages[page - 1], dict):
            raise DataError("source anchor page is outside the extracted document")
        text = pages[page - 1].get("text")
        if not isinstance(text, str) or char_end > len(text):
            raise DataError("source anchor span is outside the extracted page")
        excerpt = text[char_start:char_end]
        if not excerpt or hashlib.sha256(excerpt.encode()).hexdigest() != exact_hash:
            raise DataError("source anchor exact text hash does not match the extracted page")
        return {
            "schema": "SourceAnchorV1",
            "extraction_id": extraction_id,
            "page": page,
            "char_start": char_start,
            "char_end": char_end,
            "exact_text_sha256": exact_hash,
            "excerpt": excerpt,
            "trust_label": "UNTRUSTED_SOURCE",
        }

    @staticmethod
    def _source_claim_view(row: sqlite3.Row | dict[str, object]) -> dict[str, object]:
        result = dict(row)
        markets = _decode_json(result.pop("markets_json"), "research claim markets")
        if not isinstance(markets, list) or any(not isinstance(item, str) for item in markets):
            raise DataError("corrupt research claim markets")
        result["markets"] = markets
        return result

    def _source_claim_with_anchor(
        self, connection: sqlite3.Connection, row: sqlite3.Row | dict[str, object]
    ) -> dict[str, object]:
        result = self._source_claim_view(row)
        anchor = connection.execute(
            """SELECT extraction_id, page, char_start, char_end, exact_text_sha256
            FROM research_source_claim_anchors WHERE claim_id = ? AND revision = ?""",
            (result["claim_id"], result["revision"]),
        ).fetchone()
        if anchor is not None:
            verified = self._verified_source_anchor(
                connection, source_id=str(result["source_id"]), anchor=dict(anchor)
            )
            result["source_anchor"] = verified
            result["anchor_state"] = "verified"
            return result
        source = connection.execute(
            "SELECT content_hash FROM research_source_records WHERE source_id = ?",
            (result["source_id"],),
        ).fetchone()
        result["source_anchor"] = None
        result["anchor_state"] = (
            "LEGACY — NO TEXT ANCHOR"
            if source is not None and source["content_hash"] is not None
            else "metadata_only"
        )
        return result

    def draft_source_claim(
        self,
        project_id: str,
        *,
        source_id: str,
        contract_id: str,
        claim_text: str,
        direction: str,
        strength: str,
        method_summary: str,
        sample_summary: str,
        markets: Sequence[str],
        limitations: str,
        author: str,
        author_kind: str,
        source_anchor: Mapping[str, object] | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Draft one claim-level literature statement (spec §7.2, ADR-0024).

        A published paper is never auto-trusted: drafts carry their author kind, and only
        the owner's screening appends a ``screened`` revision. Rows are append-only.
        """
        clean_source = _require_content_id(source_id, "research source_id", prefix="rs")
        clean_contract = _require_content_id(contract_id, "research contract_id", prefix="rc")
        clean_direction = _enum_value(
            direction, "research claim direction", _SOURCE_CLAIM_DIRECTIONS
        )
        clean_strength = _enum_value(strength, "research claim strength", _SOURCE_CLAIM_STRENGTHS)
        clean_text = _required_text(claim_text, "research claim text", max_length=4_000)
        clean_method = _required_text(method_summary, "research claim method", max_length=4_000)
        clean_sample = _required_text(sample_summary, "research claim sample", max_length=4_000)
        clean_limits = _required_text(limitations, "research claim limitations", max_length=4_000)
        clean_markets = [
            _required_text(market, "research claim markets entry", max_length=64)
            for market in markets
        ]
        clean_author = _required_text(author, "research claim author", max_length=200)
        clean_author_kind = _enum_value(
            author_kind, "research claim author kind", _RESEARCH_NOTE_AUTHOR_KINDS
        )
        timestamp = _at(at)
        identity = {
            "schema_version": 1,
            "project_id": _canonical_uuid(project_id, "project_id"),
            "source_id": clean_source,
            "contract_id": clean_contract,
            "claim_text": clean_text,
            "direction": clean_direction,
        }
        claim_id = _content_id("sc", identity)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            source = connection.execute(
                "SELECT project_id, content_hash FROM research_source_records WHERE source_id = ?",
                (clean_source,),
            ).fetchone()
            if source is None or source["project_id"] != identity["project_id"]:
                raise DataError(f"unknown research source {clean_source!r} for this project")
            self._require_research_contract(connection, project_id, clean_contract)
            verified_anchor = (
                None
                if source_anchor is None
                else self._verified_source_anchor(
                    connection, source_id=clean_source, anchor=source_anchor
                )
            )
            if source["content_hash"] is not None and verified_anchor is None:
                raise DataError("new full-text claims require a verified SourceAnchorV1")
            existing = connection.execute(
                "SELECT * FROM research_source_claims WHERE claim_id = ? ORDER BY revision DESC "
                "LIMIT 1",
                (claim_id,),
            ).fetchone()
            if existing is not None:
                return self._source_claim_with_anchor(connection, existing)
            connection.execute(
                """INSERT INTO research_source_claims (
                    claim_id, revision, project_id, source_id, contract_id, claim_text,
                    direction, strength, method_summary, sample_summary, markets_json,
                    limitations, status, author, author_kind, screened_by, created_at
                ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, NULL, ?)""",
                (
                    claim_id,
                    identity["project_id"],
                    clean_source,
                    clean_contract,
                    clean_text,
                    clean_direction,
                    clean_strength,
                    clean_method,
                    clean_sample,
                    _canonical_json(clean_markets, "research claim markets"),
                    clean_limits,
                    clean_author,
                    clean_author_kind,
                    timestamp,
                ),
            )
            if verified_anchor is not None:
                connection.execute(
                    """INSERT INTO research_source_claim_anchors
                    (claim_id, revision, extraction_id, page, char_start, char_end,
                        exact_text_sha256)
                    VALUES (?, 1, ?, ?, ?, ?, ?)""",
                    (
                        claim_id,
                        verified_anchor["extraction_id"],
                        verified_anchor["page"],
                        verified_anchor["char_start"],
                        verified_anchor["char_end"],
                        verified_anchor["exact_text_sha256"],
                    ),
                )
        return {
            "claim_id": claim_id,
            "revision": 1,
            "project_id": identity["project_id"],
            "source_id": clean_source,
            "contract_id": clean_contract,
            "claim_text": clean_text,
            "direction": clean_direction,
            "strength": clean_strength,
            "method_summary": clean_method,
            "sample_summary": clean_sample,
            "markets": clean_markets,
            "limitations": clean_limits,
            "status": "draft",
            "author": clean_author,
            "author_kind": clean_author_kind,
            "screened_by": None,
            "created_at": timestamp,
            "source_anchor": verified_anchor,
            "anchor_state": "verified" if verified_anchor is not None else "metadata_only",
        }

    def screen_source_claim(
        self,
        project_id: str,
        *,
        claim_id: str,
        actor: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append the owner's ``screened`` revision; the draft row survives unchanged."""
        clean_claim = _require_content_id(claim_id, "research claim_id", prefix="sc")
        clean_actor = _required_text(actor, "research claim screener", max_length=200)
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            latest = connection.execute(
                "SELECT * FROM research_source_claims WHERE claim_id = ? AND project_id = ? "
                "ORDER BY revision DESC LIMIT 1",
                (clean_claim, project_id),
            ).fetchone()
            if latest is None:
                raise DataError(f"unknown research claim {clean_claim!r}")
            if latest["status"] == "screened":
                raise DataError(f"research claim {clean_claim!r} is already screened")
            source = connection.execute(
                "SELECT content_hash FROM research_source_records WHERE source_id = ?",
                (latest["source_id"],),
            ).fetchone()
            anchor_row = connection.execute(
                """SELECT extraction_id, page, char_start, char_end, exact_text_sha256
                FROM research_source_claim_anchors WHERE claim_id = ? AND revision = ?""",
                (clean_claim, latest["revision"]),
            ).fetchone()
            verified_anchor = None
            if anchor_row is not None:
                verified_anchor = self._verified_source_anchor(
                    connection, source_id=str(latest["source_id"]), anchor=dict(anchor_row)
                )
            if (
                source is not None
                and source["content_hash"] is not None
                and verified_anchor is None
            ):
                raise DataError("full-text claim screening requires a verified SourceAnchorV1")
            revision = int(latest["revision"]) + 1
            connection.execute(
                """INSERT INTO research_source_claims (
                    claim_id, revision, project_id, source_id, contract_id, claim_text,
                    direction, strength, method_summary, sample_summary, markets_json,
                    limitations, status, author, author_kind, screened_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'screened', ?, ?, ?, ?)""",
                (
                    clean_claim,
                    revision,
                    latest["project_id"],
                    latest["source_id"],
                    latest["contract_id"],
                    latest["claim_text"],
                    latest["direction"],
                    latest["strength"],
                    latest["method_summary"],
                    latest["sample_summary"],
                    latest["markets_json"],
                    latest["limitations"],
                    latest["author"],
                    latest["author_kind"],
                    clean_actor,
                    timestamp,
                ),
            )
            if verified_anchor is not None:
                connection.execute(
                    """INSERT INTO research_source_claim_anchors
                    (claim_id, revision, extraction_id, page, char_start, char_end,
                        exact_text_sha256)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        clean_claim,
                        revision,
                        verified_anchor["extraction_id"],
                        verified_anchor["page"],
                        verified_anchor["char_start"],
                        verified_anchor["char_end"],
                        verified_anchor["exact_text_sha256"],
                    ),
                )
            row = connection.execute(
                "SELECT * FROM research_source_claims WHERE claim_id = ? AND revision = ?",
                (clean_claim, revision),
            ).fetchone()
        if row is None:  # pragma: no cover - written in this transaction.
            raise DataError("control store failed to persist research claim screening")
        result = self._source_claim_view(row)
        result["source_anchor"] = verified_anchor
        result["anchor_state"] = (
            "verified"
            if verified_anchor is not None
            else "LEGACY — NO TEXT ANCHOR"
            if source is not None and source["content_hash"] is not None
            else "metadata_only"
        )
        return result

    def record_source_claim_owner_direction(
        self,
        project_id: str,
        *,
        claim_id: str,
        decision: Literal["reject", "revise"],
        actor: str,
        reason: str,
        payload: Mapping[str, object] | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append an owner rejection/revision direction without rewriting claim history."""
        clean_claim = _require_content_id(claim_id, "research claim_id", prefix="sc")
        clean_decision = _enum_value(
            decision, "research claim owner decision", frozenset({"reject", "revise"})
        )
        clean_actor = _required_text(actor, "research claim owner actor", max_length=200)
        clean_reason = _required_text(reason, "research claim owner reason")
        clean_payload = _json_object(payload or {}, "research claim owner payload")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            claim = connection.execute(
                """SELECT status FROM research_source_claims
                WHERE claim_id = ? AND project_id = ? ORDER BY revision DESC LIMIT 1""",
                (clean_claim, project_id),
            ).fetchone()
            if claim is None:
                raise DataError(f"unknown research claim {clean_claim!r}")
            if claim["status"] == "screened":
                raise DataError("a screened claim cannot be rejected or revised in place")
            sequence = int(
                connection.execute(
                    """SELECT COALESCE(MAX(sequence), 0) + 1
                    FROM research_source_claim_owner_events WHERE claim_id = ?""",
                    (clean_claim,),
                ).fetchone()[0]
            )
            connection.execute(
                """INSERT INTO research_source_claim_owner_events
                (claim_id, sequence, project_id, decision, actor, reason, payload_json, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    clean_claim,
                    sequence,
                    project_id,
                    clean_decision,
                    clean_actor,
                    clean_reason,
                    _canonical_json(clean_payload, "research claim owner payload"),
                    timestamp,
                ),
            )
        return {
            "claim_id": clean_claim,
            "sequence": sequence,
            "project_id": project_id,
            "decision": clean_decision,
            "actor": clean_actor,
            "reason": clean_reason,
            "payload": clean_payload,
            "occurred_at": timestamp,
        }

    def list_source_claims(
        self,
        project_id: str,
        *,
        include_history: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        """Return claims (latest revision per claim unless history is requested)."""
        limit, offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            if include_history:
                rows = connection.execute(
                    """SELECT * FROM research_source_claims WHERE project_id = ?
                    ORDER BY created_at DESC, claim_id, revision DESC LIMIT ? OFFSET ?""",
                    (project_id, limit, offset),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT claims.* FROM research_source_claims AS claims
                    JOIN (
                        SELECT claim_id, MAX(revision) AS revision
                        FROM research_source_claims WHERE project_id = ? GROUP BY claim_id
                    ) AS latest
                        ON latest.claim_id = claims.claim_id
                        AND latest.revision = claims.revision
                    ORDER BY claims.created_at DESC, claims.claim_id LIMIT ? OFFSET ?""",
                    (project_id, limit, offset),
                ).fetchall()
            return [self._source_claim_with_anchor(connection, row) for row in rows]

    def list_research_decisions(self, project_id: str) -> list[dict[str, object]]:
        """Return the append-only owner decision history for one case, oldest first."""
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            rows = connection.execute(
                """SELECT sequence, contract_id, outcome, disposition, actor, actor_kind,
                    occurred_at, reason
                FROM research_decision_events WHERE project_id = ? ORDER BY sequence""",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def search_research_sources(
        self, query: str, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, object]]:
        """Local-records-only search over titles, locators, and DOIs (never the network)."""
        clean_query = _required_text(query, "research source search query", max_length=200)
        limit, offset = _page(limit, offset)
        tokens = clean_query.casefold().split()
        if not tokens or len(tokens) > 8:
            raise DataError("research source search query must contain 1..8 terms")
        # Every token must appear in the concatenated title/locator/DOI text (AND search).
        clause = " AND ".join(
            "(lower(title) || ' ' || lower(locator) || ' ' || lower(COALESCE(doi, ''))) LIKE ?"
            for _ in tokens
        )
        params: list[object] = [f"%{token}%" for token in tokens]
        with self._transaction(write=False) as connection:
            rows = connection.execute(
                f"""SELECT * FROM research_source_records
                WHERE {clause}
                ORDER BY created_at, source_id LIMIT ? OFFSET ?""",  # noqa: S608
                [*params, limit, offset],
            ).fetchall()
        return [self._research_source_view(row) for row in rows]

    def list_research_sources(
        self, project_id: str, *, limit: int = 200, offset: int = 0
    ) -> list[dict[str, object]]:
        """List project sources with honest acquisition/extraction state."""
        limit, offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            rows = connection.execute(
                """SELECT sources.*, documents.extraction_id, documents.status AS extraction_status,
                    documents.page_count, documents.character_count, documents.warnings_json
                FROM research_source_records AS sources
                LEFT JOIN research_document_texts AS documents
                    ON documents.source_id = sources.source_id
                WHERE sources.project_id = ?
                ORDER BY sources.created_at DESC, sources.source_id LIMIT ? OFFSET ?""",
                (project_id, limit, offset),
            ).fetchall()
        results: list[dict[str, object]] = []
        for row in rows:
            source = self._research_source_view(row)
            source["extraction_id"] = source.pop("extraction_id", None)
            source["extraction_status"] = source.pop("extraction_status", None)
            source["page_count"] = source.pop("page_count", None)
            source["character_count"] = source.pop("character_count", None)
            warnings_raw = source.pop("warnings_json", None)
            source["extraction_warnings"] = (
                []
                if warnings_raw is None
                else _decode_json(warnings_raw, "research source extraction warnings")
            )
            results.append(source)
        return results

    def create_research_source_pack(
        self,
        project_id: str,
        *,
        source_ids: Sequence[str],
        definition: Mapping[str, object] | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Freeze and reuse an ordered-independent pack of project-owned sources."""
        if not source_ids or len(source_ids) > 256:
            raise DataError("research source pack requires 1..256 sources")
        clean_ids = sorted(
            {_require_content_id(value, "research source_id", prefix="rs") for value in source_ids}
        )
        clean_definition = _json_object(definition or {}, "research source pack definition")
        identity = {
            "schema_version": 1,
            "project_id": _canonical_uuid(project_id, "project_id"),
            "source_ids": clean_ids,
            "definition": clean_definition,
        }
        pack_id = _content_id("sp", identity)
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            placeholders = ",".join("?" for _ in clean_ids)
            rows = connection.execute(
                f"""SELECT source_id FROM research_source_records
                WHERE project_id = ? AND source_id IN ({placeholders})""",  # noqa: S608
                [project_id, *clean_ids],
            ).fetchall()
            if {str(row["source_id"]) for row in rows} != set(clean_ids):
                raise DataError("research source pack contains unknown or cross-project sources")
            existing = connection.execute(
                "SELECT * FROM research_source_packs WHERE pack_id = ?", (pack_id,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """INSERT INTO research_source_packs
                    (pack_id, project_id, source_ids_json, definition_json, created_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (
                        pack_id,
                        project_id,
                        _canonical_json(clean_ids, "research source pack ids"),
                        _canonical_json(clean_definition, "research source pack definition"),
                        timestamp,
                    ),
                )
                existing = connection.execute(
                    "SELECT * FROM research_source_packs WHERE pack_id = ?", (pack_id,)
                ).fetchone()
        if existing is None:  # pragma: no cover
            raise DataError("control store failed to persist research source pack")
        return self._research_source_pack_view(existing)

    def get_research_source_pack(self, pack_id: str) -> dict[str, object]:
        """Read one immutable research source pack."""
        pid = _require_content_id(pack_id, "research source pack_id", prefix="sp")
        with self._transaction(write=False) as connection:
            row = connection.execute(
                "SELECT * FROM research_source_packs WHERE pack_id = ?", (pid,)
            ).fetchone()
        if row is None:
            raise DataError(f"unknown research source pack {pid!r}")
        return self._research_source_pack_view(row)

    def list_research_source_packs(
        self, project_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, object]]:
        """Return immutable source packs owned by one research case."""

        clean_limit, clean_offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            rows = connection.execute(
                """SELECT * FROM research_source_packs WHERE project_id = ?
                ORDER BY created_at DESC, pack_id LIMIT ? OFFSET ?""",
                (project_id, clean_limit, clean_offset),
            ).fetchall()
        return [self._research_source_pack_view(row) for row in rows]

    def create_research_contract(
        self,
        project_id: str,
        *,
        scope: ResearchContractScope,
        payload: Mapping[str, object],
        created_by: str,
        author_kind: AuthorKind,
        parent_contract_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Persist an immutable draft; approval separately validates the complete contract."""
        clean_scope = _enum_value(scope, "research contract scope", RESEARCH_CONTRACT_SCOPES)
        clean_author = _required_text(created_by, "research contract creator", max_length=200)
        clean_kind = _enum_value(author_kind, "research contract author_kind", AUTHOR_KINDS)
        clean_payload = _json_object(payload, "research contract payload")
        parent_id = (
            None
            if parent_contract_id is None
            else _require_content_id(parent_contract_id, "parent research contract_id", prefix="rc")
        )
        if clean_scope == "confirmation" and parent_id is None:
            raise DataError("confirmation contract requires an approved exploration parent")
        identity = {
            "schema_version": 1,
            "project_id": _canonical_uuid(project_id, "project_id"),
            "scope": clean_scope,
            "parent_contract_id": parent_id,
            "payload": clean_payload,
        }
        contract_id = _content_id("rc", identity)
        try:
            _, draft_d2_boundary = _research_d2_topology(clean_payload)
        except DataError:
            # Draft capture deliberately accepts an incomplete raw idea.  Until the immutable
            # contract clears review, its content id is the conservative provisional seal.
            draft_d2_boundary = contract_id
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            if parent_id is not None:
                parent = self._require_research_contract(connection, project_id, parent_id)
                if clean_scope == "confirmation":
                    review = self._latest_research_review(connection, parent_id)
                    if (
                        parent["scope"] != "exploration"
                        or _research_review_state(review) != "approved"
                    ):
                        raise DataError(
                            "confirmation contract requires an approved exploration parent"
                        )
                elif parent["scope"] != "exploration":
                    raise DataError("exploration revisions require an exploration parent")
            existing = connection.execute(
                "SELECT * FROM research_contracts WHERE contract_id = ?", (contract_id,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """INSERT INTO research_contracts (
                        contract_id, project_id, scope, parent_contract_id, payload_json,
                        created_by, author_kind, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        contract_id,
                        project_id,
                        clean_scope,
                        parent_id,
                        _canonical_json(clean_payload, "research contract payload"),
                        clean_author,
                        clean_kind,
                        timestamp,
                    ),
                )
                existing = connection.execute(
                    "SELECT * FROM research_contracts WHERE contract_id = ?", (contract_id,)
                ).fetchone()
                phase = self._latest_research_phase(connection, project_id)
                if phase is None:
                    if clean_scope != "exploration":  # pragma: no cover
                        raise DataError("a research case must begin with an exploration contract")
                    self._bootstrap_research_case_authority(
                        connection,
                        project_id=project_id,
                        contract_id=contract_id,
                        actor=clean_author,
                        boundary_hash=draft_d2_boundary,
                        at=timestamp,
                    )
                elif clean_scope == "exploration" and phase["phase"] in {
                    "captured",
                    "triage",
                    "exploration_review",
                }:
                    replacing_rejected_contract = phase["phase"] == "exploration_review"
                    self._append_research_phase_event(
                        connection,
                        project_id=project_id,
                        contract_id=contract_id,
                        phase=str(phase["phase"]),
                        actor=clean_author,
                        reason="research contract draft revision selected",
                        next_action=(
                            "Owner approves or rejects the replacement exploration contract."
                            if replacing_rejected_contract
                            else str(phase["next_action"])
                        ),
                        responsibility=(
                            "owner" if replacing_rejected_contract else str(phase["responsibility"])
                        ),
                        blocker=None if replacing_rejected_contract else phase["blocker"],
                        recovery=None if replacing_rejected_contract else phase["recovery"],
                        at=timestamp,
                    )
        if existing is None:  # pragma: no cover
            raise DataError("control store failed to persist research contract")
        with self._transaction(write=False) as connection:
            row = self._require_research_contract(connection, project_id, contract_id)
            return self._research_contract_view(connection, row)

    def get_research_contract(self, contract_id: str) -> dict[str, object]:
        """Read one immutable contract plus its derived owner-review state."""
        cid = _require_content_id(contract_id, "research contract_id", prefix="rc")
        with self._transaction(write=False) as connection:
            row = connection.execute(
                "SELECT * FROM research_contracts WHERE contract_id = ?", (cid,)
            ).fetchone()
            if row is None:
                raise DataError(f"unknown research contract {cid!r}")
            return self._research_contract_view(connection, row)

    def reopen_research_revision(
        self,
        project_id: str,
        contract_id: str,
        *,
        actor: str,
        reason: str,
        next_action: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Select one post-decision exploration revision without recycling prior D2 data."""
        clean_actor = _required_text(actor, "research revision actor", max_length=200)
        clean_reason = _required_text(reason, "research revision reason")
        clean_action = _required_text(next_action, "research revision next_action")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            revision = self._require_research_contract(connection, project_id, contract_id)
            parent_id = revision["parent_contract_id"]
            if revision["scope"] != "exploration" or not isinstance(parent_id, str):
                raise DataError("research reopen requires an exploration revision")

            phase = self._latest_research_phase(connection, project_id)
            if phase is None or phase["phase"] not in {"research_decision", "closed"}:
                raise DataError("research reopen requires a terminal research decision")
            decided = self._require_research_contract(
                connection, project_id, str(phase["contract_id"])
            )
            prior_exploration_id = (
                str(decided["parent_contract_id"])
                if decided["scope"] == "confirmation"
                else str(decided["contract_id"])
            )
            if parent_id != prior_exploration_id:
                raise DataError(
                    "research revision must descend from the decided exploration contract"
                )
            decision = connection.execute(
                """SELECT * FROM research_decision_events
                WHERE project_id = ? AND contract_id = ?
                ORDER BY sequence DESC LIMIT 1""",
                (project_id, decided["contract_id"]),
            ).fetchone()
            if decision is None or decision["disposition"] != "revise":
                raise DataError("research reopen requires owner disposition 'revise'")
            if str(revision["created_at"]) < str(decision["occurred_at"]):
                raise DataError("research revision must be frozen after the revise decision")
            if self._latest_research_review(connection, contract_id) is not None:
                raise DataError("research reopen requires an unreviewed exploration revision")

            payload = self._validate_research_contract_for_approval(connection, revision)
            d2, boundary_hash = _research_d2_topology(payload)
            self._require_revision_d2_reuse(
                connection,
                project_id=project_id,
                d2=d2,
                boundary_hash=boundary_hash,
                exclude_contract_id=None,
                subject="research revision",
            )

            reopened = self._append_research_phase_event(
                connection,
                project_id=project_id,
                contract_id=contract_id,
                phase="exploration_review",
                actor=clean_actor,
                reason=clean_reason,
                next_action=clean_action,
                responsibility="owner",
                blocker=None,
                recovery=None,
                at=timestamp,
            )
            execution = self._latest_research_execution(connection, project_id)
            if execution is None:
                raise DataError("research case has no execution state")
            if timestamp < str(execution["occurred_at"]):
                raise DataError("research revision timestamp precedes prior execution")
            connection.execute(
                """INSERT INTO research_execution_events (
                    project_id, sequence, contract_id, state, occurred_at, actor, reason,
                    next_action, responsibility, active_job_id, checkpoint, blocker, recovery
                ) VALUES (?, ?, ?, 'idle', ?, ?, ?, ?, 'owner', NULL, NULL, NULL, NULL)""",
                (
                    project_id,
                    int(execution["sequence"]) + 1,
                    contract_id,
                    timestamp,
                    clean_actor,
                    clean_reason,
                    clean_action,
                ),
            )
            self._append_research_d2_event(
                connection,
                project_id=project_id,
                contract_id=contract_id,
                state="sealed",
                boundary_hash=boundary_hash,
                actor=clean_actor,
                reason="owner-directed revision sealed a distinct D2 boundary",
                at=timestamp,
            )
        return dict(reopened)

    def review_research_contract(
        self,
        project_id: str,
        contract_id: str,
        *,
        scope: ResearchContractScope,
        decision: ResearchReviewDecision,
        actor: str,
        actor_kind: AuthorKind,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append one owner-only terminal review for the exact immutable contract."""
        clean_scope = _enum_value(scope, "research review scope", RESEARCH_CONTRACT_SCOPES)
        clean_decision = _enum_value(
            decision, "research review decision", RESEARCH_REVIEW_DECISIONS
        )
        clean_kind = _enum_value(actor_kind, "research review actor_kind", AUTHOR_KINDS)
        if clean_kind != "human":
            raise DataError("owner review requires a human actor")
        clean_actor = _required_text(actor, "research review actor", max_length=200)
        clean_reason = _required_text(reason, "research review reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            row = self._require_research_contract(connection, project_id, contract_id)
            if row["scope"] != clean_scope:
                raise DataError("research review scope does not match the immutable contract")
            phase = self._latest_research_phase(connection, project_id)
            expected_phase = f"{clean_scope}_review"
            if (
                phase is None
                or phase["phase"] != expected_phase
                or phase["contract_id"] != contract_id
            ):
                raise DataError(f"{clean_scope} review requires the {expected_phase} phase")
            prior = self._latest_research_review(connection, contract_id)
            if prior is not None:
                if prior["decision"] == clean_decision:
                    return dict(prior)
                raise DataError("research contract already has a conflicting owner review")
            approved_payload: dict[str, object] | None = None
            if clean_decision == "approve":
                approved_payload = self._validate_research_contract_for_approval(connection, row)
                if clean_scope == "confirmation":
                    parent_id = row["parent_contract_id"]
                    if not isinstance(parent_id, str):
                        raise DataError(
                            "confirmation approval requires an approved exploration parent"
                        )
                    parent_review = self._latest_research_review(connection, parent_id)
                    if _research_review_state(parent_review) != "approved":
                        raise DataError(
                            "confirmation approval requires an approved exploration parent"
                        )
            connection.execute(
                """INSERT INTO research_contract_review_events (
                    contract_id, sequence, project_id, scope, decision, actor, actor_kind,
                    occurred_at, reason
                ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    contract_id,
                    project_id,
                    clean_scope,
                    clean_decision,
                    clean_actor,
                    clean_kind,
                    timestamp,
                    clean_reason,
                ),
            )
            if clean_decision == "approve":
                if approved_payload is None:  # pragma: no cover - branch invariant.
                    raise DataError("approved research contract payload is unavailable")
                _, boundary_hash = _research_d2_topology(approved_payload)
                d2 = self._latest_research_d2(connection, project_id)
                if d2 is None or d2["state"] != "sealed":
                    raise DataError("research approval requires D2 to remain sealed")
                if clean_scope == "exploration":
                    if d2["contract_id"] != contract_id or d2["boundary_hash"] != boundary_hash:
                        self._append_research_d2_event(
                            connection,
                            project_id=project_id,
                            contract_id=contract_id,
                            state="sealed",
                            boundary_hash=boundary_hash,
                            actor=clean_actor,
                            reason="owner exploration approval froze the exact D2 boundary",
                            at=timestamp,
                        )
                else:
                    if d2["boundary_hash"] != boundary_hash:
                        raise DataError(
                            "confirmation approval requires its exploration D2 boundary"
                        )
                    self._append_research_d2_event(
                        connection,
                        project_id=project_id,
                        contract_id=contract_id,
                        state="authorized",
                        boundary_hash=boundary_hash,
                        actor=clean_actor,
                        reason="owner confirmation approval authorized one D2 consumption",
                        at=timestamp,
                    )
            else:
                self._append_research_phase_event(
                    connection,
                    project_id=project_id,
                    contract_id=contract_id,
                    phase=f"{clean_scope}_review",
                    actor=clean_actor,
                    reason=f"owner rejected the exact {clean_scope} contract: {clean_reason}",
                    next_action=(
                        "Owner closes the rejected exploration contract or requests one bounded "
                        "replacement draft."
                        if clean_scope == "exploration"
                        else (
                            "Owner closes the rejected confirmation contract or requests one "
                            "bounded corrected child."
                        )
                    ),
                    responsibility="owner",
                    blocker=None,
                    recovery=None,
                    at=timestamp,
                )
            stored = self._latest_research_review(connection, contract_id)
        if stored is None:  # pragma: no cover
            raise DataError("control store failed to persist research review")
        return dict(stored)

    def transition_research_phase(
        self,
        project_id: str,
        *,
        to_phase: ResearchPhase,
        contract_id: str,
        actor: str,
        reason: str,
        next_action: str,
        responsibility: ResearchResponsibility,
        blocker: str | None = None,
        recovery: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Advance the exact research lifecycle by one governed phase."""
        clean_phase = _enum_value(to_phase, "research phase", RESEARCH_PHASES)
        clean_actor = _required_text(actor, "research phase actor", max_length=200)
        clean_reason = _required_text(reason, "research phase reason")
        clean_action = _required_text(next_action, "research next_action")
        clean_responsibility = _enum_value(
            responsibility, "research responsibility", RESEARCH_RESPONSIBILITIES
        )
        clean_blocker = _optional_text(blocker, "research blocker")
        clean_recovery = _optional_text(recovery, "research recovery")
        if (clean_blocker is None) != (clean_recovery is None):
            raise DataError("research blocker and recovery must be recorded together")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            contract = self._require_research_contract(connection, project_id, contract_id)
            prior = self._latest_research_phase(connection, project_id)
            if prior is None:
                raise DataError("research case has no captured phase")
            current = str(prior["phase"])
            early_terminal = clean_phase == "research_decision" and current in {
                "pilot",
                "deep_research",
                "confirmation_review",
            }
            expected_index = RESEARCH_PHASE_ORDER.index(current) + 1
            if not early_terminal and (
                expected_index >= len(RESEARCH_PHASE_ORDER)
                or clean_phase != RESEARCH_PHASE_ORDER[expected_index]
            ):
                raise DataError(f"invalid research phase transition {current!r} -> {clean_phase!r}")

            prior_contract = self._require_research_contract(
                connection, project_id, str(prior["contract_id"])
            )
            if early_terminal:
                exploration = contract
                if current == "confirmation_review":
                    if prior_contract["scope"] != "confirmation":
                        raise DataError("early terminal review has no confirmation child")
                    expected_parent = prior_contract["parent_contract_id"]
                    if contract_id != expected_parent:
                        raise DataError(
                            "early terminal decision must bind the approved exploration parent"
                        )
                    confirmation_review = self._latest_research_review(
                        connection, str(prior_contract["contract_id"])
                    )
                    if _research_review_state(confirmation_review) == "approved":
                        raise DataError(
                            "approved confirmation must follow the sealed D2 decision path"
                        )
                elif contract_id != prior["contract_id"]:
                    raise DataError(
                        "early terminal decision must bind the active exploration contract"
                    )
                exploration_review = self._latest_research_review(
                    connection, str(exploration["contract_id"])
                )
                d2 = self._latest_research_d2(connection, project_id)
                if (
                    exploration["scope"] != "exploration"
                    or _research_review_state(exploration_review) != "approved"
                    or d2 is None
                    or d2["state"] != "sealed"
                ):
                    raise DataError(
                        "early terminal decision requires approved exploration with D2 sealed"
                    )
            elif clean_phase == "confirmation_review":
                if (
                    contract["scope"] != "confirmation"
                    or contract["parent_contract_id"] != prior_contract["contract_id"]
                    or prior_contract["scope"] != "exploration"
                ):
                    raise DataError(
                        "confirmation review requires a child of the active exploration contract"
                    )
            elif contract_id != prior["contract_id"]:
                raise DataError(
                    "research phase transition changed the active contract unexpectedly"
                )

            if clean_phase == "pilot":
                review = self._latest_research_review(connection, contract_id)
                if (
                    contract["scope"] != "exploration"
                    or _research_review_state(review) != "approved"
                ):
                    raise DataError("pilot requires exact exploration approval")
            elif clean_phase == "deep_research":
                execution = self._latest_research_execution(connection, project_id)
                if execution is None or execution["state"] != "idle":
                    raise DataError("pilot advancement requires idle execution")
                payload = self._validate_research_contract_for_approval(connection, contract)
                self._require_completed_d0_attempt(
                    connection,
                    project_id=project_id,
                    contract_id=contract_id,
                    contract_payload=payload,
                )
            elif clean_phase == "sealed_confirmation":
                review = self._latest_research_review(connection, contract_id)
                d2 = self._latest_research_d2(connection, project_id)
                if (
                    contract["scope"] != "confirmation"
                    or _research_review_state(review) != "approved"
                ):
                    raise DataError("sealed confirmation requires exact confirmation approval")
                if d2 is None or d2["state"] != "authorized" or d2["contract_id"] != contract_id:
                    raise DataError(
                        "sealed confirmation requires D2 authorization for this contract"
                    )
            elif clean_phase == "research_decision" and not early_terminal:
                d2 = self._latest_research_d2(connection, project_id)
                if (
                    d2 is None
                    or d2["state"] not in {"consumed", "contaminated"}
                    or d2["contract_id"] != contract_id
                ):
                    raise DataError(
                        "D2 must be consumed or contaminated by the exact confirmation contract"
                    )
                if d2["state"] == "consumed":
                    confirmation_payload = _decode_json(
                        contract["payload_json"], "research confirmation contract payload"
                    )
                    if not isinstance(
                        confirmation_payload, dict
                    ):  # pragma: no cover - stored JSON invariant.
                        raise DataError("corrupt research confirmation contract payload")
                    self._mechanical_confirmation_outcome(
                        connection,
                        project_id=project_id,
                        contract_id=contract_id,
                        contract_payload=confirmation_payload,
                    )
            closing_decision: sqlite3.Row | None = None
            if clean_phase == "closed":
                closing_decision = connection.execute(
                    """SELECT * FROM research_decision_events
                    WHERE project_id = ? AND contract_id = ?""",
                    (project_id, contract_id),
                ).fetchone()
                if closing_decision is None:
                    raise DataError("research case cannot close without an owner research decision")

            row = self._append_research_phase_event(
                connection,
                project_id=project_id,
                contract_id=contract_id,
                phase=clean_phase,
                actor=clean_actor,
                reason=clean_reason,
                next_action=clean_action,
                responsibility=clean_responsibility,
                blocker=clean_blocker,
                recovery=clean_recovery,
                at=timestamp,
            )
            if (
                closing_decision is not None
                and closing_decision["disposition"] == "advance_to_strategy"
            ):
                # The terminal gate packet exists only once the case closes, so the lossless
                # spec-§11 promotion dossier commits atomically with the closing phase event —
                # an advance_to_strategy case cannot close without its research inheritance.
                self._record_strategy_promotion_packet(
                    connection,
                    project_id=project_id,
                    contract_id=contract_id,
                    decision=dict(closing_decision),
                    actor=str(closing_decision["actor"]),
                    timestamp=timestamp,
                )
        return dict(row)

    def transition_research_execution(
        self,
        project_id: str,
        *,
        to_state: ResearchExecutionState,
        contract_id: str,
        actor: str,
        reason: str,
        next_action: str,
        responsibility: ResearchResponsibility,
        active_job_id: str | None = None,
        checkpoint: str | None = None,
        blocker: str | None = None,
        recovery: str | None = None,
        reconcile_running: bool = False,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append execution state without conflating it with the research lifecycle phase."""
        clean_state = _enum_value(to_state, "research execution state", RESEARCH_EXECUTION_STATES)
        clean_actor = _required_text(actor, "research execution actor", max_length=200)
        clean_reason = _required_text(reason, "research execution reason")
        clean_action = _required_text(next_action, "research next_action")
        clean_responsibility = _enum_value(
            responsibility, "research responsibility", RESEARCH_RESPONSIBILITIES
        )
        clean_job = (
            None
            if active_job_id is None
            else _canonical_uuid(active_job_id, "research active_job_id")
        )
        clean_checkpoint = _optional_text(checkpoint, "research checkpoint")
        clean_blocker = _optional_text(blocker, "research blocker")
        clean_recovery = _optional_text(recovery, "research recovery")
        if (clean_blocker is None) != (clean_recovery is None):
            raise DataError("research blocker and recovery must be recorded together")
        if not isinstance(reconcile_running, bool):
            raise DataError("research running reconciliation flag must be boolean")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_research_contract(connection, project_id, contract_id)
            phase = self._latest_research_phase(connection, project_id)
            if phase is None or phase["contract_id"] != contract_id:
                raise DataError("research execution must bind the active phase contract")
            prior = self._latest_research_execution(connection, project_id)
            if prior is None:
                raise DataError("research case has no execution state")
            prior_state = str(prior["state"])
            if clean_state not in _RESEARCH_EXECUTION_TRANSITIONS[prior_state]:
                raise DataError(
                    f"invalid research execution transition {prior_state!r} -> {clean_state!r}"
                )
            if prior_state == "running" and clean_state == "queued":
                if not reconcile_running:
                    raise DataError(
                        "running research requires explicit orphan reconciliation acknowledgement"
                    )
                if prior["active_job_id"] is not None:
                    raise DataError(
                        "running research with an active durable job must be reconciled through "
                        "the job lease"
                    )
            elif reconcile_running:
                raise DataError(
                    "running reconciliation acknowledgement is valid only for running -> queued"
                )
            if not isinstance(prior["occurred_at"], str) or timestamp < prior["occurred_at"]:
                raise DataError("research execution timestamp precedes prior event")
            if clean_job is not None:
                job = connection.execute(
                    "SELECT kind, project_id FROM jobs WHERE job_id = ?", (clean_job,)
                ).fetchone()
                if (
                    job is None
                    or not str(job["kind"]).startswith("research:")
                    or job["project_id"] != project_id
                ):
                    raise DataError("active research job is not safely bound to this project")
            sequence = int(prior["sequence"]) + 1
            connection.execute(
                """INSERT INTO research_execution_events (
                    project_id, sequence, contract_id, state, occurred_at, actor, reason,
                    next_action, responsibility, active_job_id, checkpoint, blocker, recovery
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    sequence,
                    contract_id,
                    clean_state,
                    timestamp,
                    clean_actor,
                    clean_reason,
                    clean_action,
                    clean_responsibility,
                    clean_job,
                    clean_checkpoint,
                    clean_blocker,
                    clean_recovery,
                ),
            )
            row = self._latest_research_execution(connection, project_id)
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist research execution event")
        return dict(row)

    def transition_research_d2_state(
        self,
        project_id: str,
        contract_id: str,
        *,
        to_state: Literal["consumed", "contaminated"],
        actor: str,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Consume or contaminate D2; authorization remains owner-review-only."""
        clean_state = _enum_value(to_state, "research D2 state", RESEARCH_D2_STATES)
        if clean_state not in {"consumed", "contaminated"}:
            raise DataError("research APIs may only consume or contaminate D2")
        clean_actor = _required_text(actor, "research D2 actor", max_length=200)
        clean_reason = _required_text(reason, "research D2 reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            contract = self._require_research_contract(connection, project_id, contract_id)
            if contract["scope"] != "confirmation":
                raise DataError("D2 can only bind an approved confirmation contract")
            prior = self._latest_research_d2(connection, project_id)
            if prior is None:
                raise DataError("research case has no sealed D2 state")
            if clean_state == "consumed":
                phase = self._latest_research_phase(connection, project_id)
                if (
                    prior["state"] != "authorized"
                    or prior["contract_id"] != contract_id
                    or phase is None
                    or phase["phase"] != "sealed_confirmation"
                    or phase["contract_id"] != contract_id
                ):
                    raise DataError(
                        "D2 consumption requires the authorized sealed_confirmation contract"
                    )
            elif prior["state"] == "contaminated":
                return dict(prior)
            row = self._append_research_d2_event(
                connection,
                project_id=project_id,
                contract_id=contract_id,
                state=clean_state,
                boundary_hash=str(prior["boundary_hash"]),
                actor=clean_actor,
                reason=clean_reason,
                at=timestamp,
            )
        return dict(row)

    @staticmethod
    def _research_attempt_view(
        row: sqlite3.Row, *, launch_reservation_id: str | None = None
    ) -> dict[str, object]:
        result = dict(row)
        result["budget_used"] = _decode_json(
            result.pop("budget_used_json"), "research attempt budget"
        )
        result["details"] = _decode_json(result.pop("details_json"), "research attempt details")
        if launch_reservation_id is not None:
            result["launch_reservation_id"] = launch_reservation_id
        return result

    @staticmethod
    def _research_reservation_view(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["budget_reserved"] = _decode_json(
            result.pop("budget_reserved_json"), "research launch reservation budget"
        )
        return result

    @staticmethod
    def _research_lineage_accounting(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        contract_ids: Sequence[str],
    ) -> tuple[dict[str, int | float], int]:
        """Count reservations once and retain compatibility for unreserved attempts."""

        if not contract_ids:  # pragma: no cover - every research lineage has one contract.
            return {}, 0
        placeholders = ",".join("?" for _ in contract_ids)
        reservation_rows = connection.execute(
            f"""SELECT budget_reserved_json FROM research_launch_reservations
            WHERE project_id = ? AND contract_id IN ({placeholders})""",  # noqa: S608
            [project_id, *contract_ids],
        ).fetchall()
        unlinked_attempt_rows = connection.execute(
            f"""SELECT a.budget_used_json FROM research_attempt_records AS a
            LEFT JOIN research_launch_attempt_links AS l ON l.attempt_id = a.attempt_id
            WHERE a.project_id = ? AND a.contract_id IN ({placeholders})
                AND l.attempt_id IS NULL""",  # noqa: S608
            [project_id, *contract_ids],
        ).fetchall()
        elapsed: dict[str, int | float] = {}
        for row in reservation_rows:
            used = _budget_values(
                _decode_json(row["budget_reserved_json"], "research launch reservation budget"),
                require_minimum=False,
            )
            for key, value in used.items():
                elapsed[key] = elapsed.get(key, 0) + value
        for row in unlinked_attempt_rows:
            used = _budget_values(
                _decode_json(row["budget_used_json"], "research attempt budget"),
                require_minimum=False,
            )
            for key, value in used.items():
                elapsed[key] = elapsed.get(key, 0) + value
        return elapsed, len(reservation_rows) + len(unlinked_attempt_rows)

    def reserve_d0_research_launch(
        self,
        project_id: str,
        contract_id: str,
        *,
        config_fingerprint: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Atomically consume one fixed D0 retry slot and its budget before computation."""

        from alpha_cli.research_runtime import validate_d0_pilot_contract

        clean_fingerprint = _required_text(
            config_fingerprint, "research launch config_fingerprint", max_length=512
        )
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            contract = self._require_research_contract(connection, project_id, contract_id)
            review = self._latest_research_review(connection, contract_id)
            phase = self._latest_research_phase(connection, project_id)
            execution = self._latest_research_execution(connection, project_id)
            if (
                contract["scope"] != "exploration"
                or _research_review_state(review) != "approved"
                or phase is None
                or phase["phase"] != "pilot"
                or phase["contract_id"] != contract_id
            ):
                raise DataError("D0 launch reservation requires the active approved pilot contract")
            if (
                execution is None
                or execution["state"] != "queued"
                or execution["contract_id"] != contract_id
            ):
                raise DataError("D0 launch reservation requires explicitly queued execution")
            if (
                not isinstance(execution["occurred_at"], str)
                or timestamp < execution["occurred_at"]
            ):
                raise DataError("research launch timestamp precedes queued execution")
            payload = self._validate_research_contract_for_approval(connection, contract)
            validate_d0_pilot_contract(payload)

            reservation_count_row = connection.execute(
                """SELECT COUNT(*) AS count FROM research_launch_reservations
                WHERE project_id = ? AND contract_id = ? AND kind = ?""",
                (project_id, contract_id, _D0_RESEARCH_KIND),
            ).fetchone()
            unlinked_count_row = connection.execute(
                """SELECT COUNT(*) AS count FROM research_attempt_records AS a
                LEFT JOIN research_launch_attempt_links AS l ON l.attempt_id = a.attempt_id
                WHERE a.project_id = ? AND a.contract_id = ? AND a.kind = ?
                    AND l.attempt_id IS NULL""",
                (project_id, contract_id, _D0_RESEARCH_KIND),
            ).fetchone()
            launch_number = (
                int(cast(sqlite3.Row, reservation_count_row)["count"])
                + int(cast(sqlite3.Row, unlinked_count_row)["count"])
                + 1
            )
            if launch_number > _D0_MAX_LAUNCHES:
                raise DataError(
                    "synthetic pilot stopped after the initial attempt and two safe retries"
                )

            budget_limit = _budget_values(payload["budget"], require_minimum=True)
            elapsed, _ = self._research_lineage_accounting(
                connection,
                project_id=project_id,
                contract_ids=[contract_id],
            )
            for key, value in _D0_LAUNCH_BUDGET.items():
                if key not in budget_limit:
                    raise DataError(f"research launch uses undeclared budget dimension {key!r}")
                if elapsed.get(key, 0) + value > budget_limit[key]:
                    raise DataError(f"research launch exceeds approved {key!r} budget")

            identity: dict[str, object] = {
                "schema_version": 1,
                "project_id": project_id,
                "contract_id": contract_id,
                "phase": "pilot",
                "kind": _D0_RESEARCH_KIND,
                "launch_number": launch_number,
                "config_fingerprint": clean_fingerprint,
                "budget_reserved": _D0_LAUNCH_BUDGET,
                "execution_sequence": int(execution["sequence"]) + 1,
            }
            reservation_id = _content_id("rl", identity)
            execution_sequence = int(execution["sequence"]) + 1
            connection.execute(
                """INSERT INTO research_execution_events (
                    project_id, sequence, contract_id, state, occurred_at, actor, reason,
                    next_action, responsibility, active_job_id, checkpoint, blocker, recovery
                ) VALUES (?, ?, ?, 'running', ?, 'system', ?, ?, 'codex', NULL, ?, NULL, NULL)""",
                (
                    project_id,
                    execution_sequence,
                    contract_id,
                    timestamp,
                    "the deterministic D0 pilot started after durable launch reservation",
                    "Evaluate planted and null detector fixtures.",
                    f"d0:running:{launch_number}",
                ),
            )
            connection.execute(
                """INSERT INTO research_launch_reservations (
                    reservation_id, project_id, contract_id, phase, kind, launch_number,
                    config_fingerprint, budget_reserved_json, execution_sequence, reserved_at
                ) VALUES (?, ?, ?, 'pilot', ?, ?, ?, ?, ?, ?)""",
                (
                    reservation_id,
                    project_id,
                    contract_id,
                    _D0_RESEARCH_KIND,
                    launch_number,
                    clean_fingerprint,
                    _canonical_json(_D0_LAUNCH_BUDGET, "research launch reservation budget"),
                    execution_sequence,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM research_launch_reservations WHERE reservation_id = ?",
                (reservation_id,),
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist research launch reservation")
        return self._research_reservation_view(cast(sqlite3.Row, row))

    def count_research_attempts(self, project_id: str, contract_id: str, *, kind: str) -> int:
        """Count recorded attempts of one registered kind for a contract (retry ceilings)."""
        clean_kind = _required_text(kind, "research attempt kind", max_length=100)
        with self._transaction(write=False) as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS count FROM research_attempt_records
                WHERE project_id = ? AND contract_id = ? AND kind = ?""",
                (project_id, contract_id, clean_kind),
            ).fetchone()
        return int(cast(sqlite3.Row, row)["count"])

    def verified_research_attempt(
        self,
        project_id: str,
        attempt_id: str,
    ) -> dict[str, object]:
        """Return one attempt and its exact immutable manifest after full lineage verification."""
        clean_attempt_id = _require_content_id(attempt_id, "research attempt_id", prefix="ra")
        with self._transaction(write=False) as connection:
            row = connection.execute(
                """SELECT a.*, l.reservation_id AS launch_reservation_id
                FROM research_attempt_records AS a
                LEFT JOIN research_launch_attempt_links AS l ON l.attempt_id = a.attempt_id
                WHERE a.project_id = ? AND a.attempt_id = ?""",
                (project_id, clean_attempt_id),
            ).fetchone()
            if row is None:
                raise DataError(f"unknown research attempt {clean_attempt_id!r}")
            attempt = self._research_attempt_view(cast(sqlite3.Row, row))
            run_id = attempt.get("run_id")
            if not isinstance(run_id, str):
                raise DataError("research attempt has no immutable run to verify")
            contract_id = str(attempt["contract_id"])
            contract = self._require_research_contract(connection, project_id, contract_id)
            payload = _decode_json(contract["payload_json"], "research attempt contract payload")
            if not isinstance(payload, dict):  # pragma: no cover - stored JSON invariant.
                raise DataError("corrupt research attempt contract payload")
            manifest = self._verify_research_attempt_run(
                project_id=project_id,
                attempt=attempt,
                contract_payload=payload,
            )
        return {"attempt": attempt, "manifest": manifest}

    def record_research_attempt(
        self,
        project_id: str,
        contract_id: str,
        *,
        kind: str,
        status: AttemptStatus,
        config_fingerprint: str,
        budget_used: Mapping[str, object],
        details: Mapping[str, object] | None = None,
        run_id: str | None = None,
        error: str | None = None,
        launch_reservation_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Record or reuse one immutable, budget-accounted research attempt."""
        clean_kind = _required_text(kind, "research attempt kind", max_length=100)
        clean_status = _enum_value(status, "research attempt status", ATTEMPT_STATUSES)
        clean_fingerprint = _required_text(
            config_fingerprint, "research attempt config_fingerprint", max_length=512
        )
        clean_budget = _budget_values(budget_used, require_minimum=False)
        clean_details = _json_object(details or {}, "research attempt details")
        if "gate_packet_evidence" in clean_details:
            raise DataError(
                "inline gate_packet_evidence is forbidden; store only an immutable artifact "
                "selector"
            )
        clean_error = _optional_text(error, "research attempt error")
        if clean_status == "failed" and clean_error is None:
            raise DataError("failed research attempt requires an error")
        if clean_error is not None and clean_status != "failed":
            raise DataError("research attempt error is only valid for failed status")
        clean_run = (
            None
            if run_id is None
            else _required_text(run_id, "research attempt run_id", max_length=64)
        )
        clean_reservation_id = (
            None
            if launch_reservation_id is None
            else _require_content_id(
                launch_reservation_id,
                "research launch_reservation_id",
                prefix="rl",
            )
        )
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            contract = self._require_research_contract(connection, project_id, contract_id)
            review = self._latest_research_review(connection, contract_id)
            if _research_review_state(review) != "approved":
                raise DataError("research attempts require the exact approved contract")
            phase = self._latest_research_phase(connection, project_id)
            if phase is None or phase["contract_id"] != contract_id:
                raise DataError("research attempt must bind the active phase contract")
            allowed_phases = (
                {"pilot", "deep_research"}
                if contract["scope"] == "exploration"
                else {"sealed_confirmation"}
            )
            if phase["phase"] not in allowed_phases:
                raise DataError("research attempt is not allowed in the current phase")
            payload = self._validate_research_contract_for_approval(connection, contract)
            phase_name = str(phase["phase"])
            expected_zone = {
                "pilot": "D0",
                "deep_research": "D1",
                "sealed_confirmation": "D2",
            }[phase_name]
            declared_zone = clean_details.get("evidence_zone")
            if declared_zone != expected_zone:
                raise DataError("research attempt evidence_zone does not match its active phase")
            if phase_name == "pilot":
                if clean_kind != "d0-synthetic-pilot":
                    raise DataError("pilot accepts only the registered d0-synthetic-pilot kind")
                if clean_status not in {"completed", "failed"}:
                    raise DataError("D0 pilot attempts must be completed or failed")
                if clean_status == "completed" and clean_run is None:
                    raise DataError("completed D0 pilot requires an immutable run_id")
            if phase_name == "deep_research":
                if clean_kind != _D1_RESEARCH_KIND:
                    raise DataError(
                        "deep research accepts only the registered d1-deep-research kind"
                    )
                if clean_status not in {"completed", "failed"}:
                    raise DataError("D1 deep-research attempts must be completed or failed")
                if clean_status == "completed" and clean_run is None:
                    raise DataError("completed D1 deep research requires an immutable run_id")
            if phase_name == "sealed_confirmation":
                if clean_kind != _D2_RESEARCH_KIND:
                    raise DataError(
                        "sealed confirmation accepts only the registered sealed-confirmation kind"
                    )
                if clean_status not in {"completed", "failed"}:
                    raise DataError("D2 sealed-confirmation attempts must be completed or failed")
                if clean_status == "completed" and clean_run is None:
                    raise DataError("completed sealed confirmation requires an immutable run_id")
            reservation: sqlite3.Row | None = None
            reservation_link: sqlite3.Row | None = None
            if clean_reservation_id is not None:
                reservation = connection.execute(
                    "SELECT * FROM research_launch_reservations WHERE reservation_id = ?",
                    (clean_reservation_id,),
                ).fetchone()
                if reservation is None:
                    raise DataError("research attempt launch reservation does not exist")
                if (
                    reservation["project_id"] != project_id
                    or reservation["contract_id"] != contract_id
                    or reservation["phase"] != phase_name
                    or reservation["kind"] != clean_kind
                    or reservation["config_fingerprint"] != clean_fingerprint
                ):
                    raise DataError("research attempt does not match its launch reservation")
                if clean_status not in {"completed", "failed"}:
                    raise DataError("reserved research launch accepts only a terminal attempt")
                if clean_budget:
                    raise DataError("reserved research attempt must not debit budget a second time")
                attempt_number = clean_details.get("attempt_number")
                if (
                    isinstance(attempt_number, bool)
                    or not isinstance(attempt_number, int)
                    or attempt_number != reservation["launch_number"]
                ):
                    raise DataError("research attempt number does not match its launch reservation")
                reservation_link = connection.execute(
                    """SELECT attempt_id FROM research_launch_attempt_links
                    WHERE reservation_id = ?""",
                    (clean_reservation_id,),
                ).fetchone()
                if reservation_link is None:
                    launch_execution = self._latest_research_execution(connection, project_id)
                    if (
                        launch_execution is None
                        or launch_execution["state"] != "running"
                        or launch_execution["contract_id"] != contract_id
                        or launch_execution["sequence"] != reservation["execution_sequence"]
                    ):
                        raise DataError(
                            "research attempt is not terminalizing its active reserved launch"
                        )
            if clean_run is not None:
                self._require_research_run(
                    clean_run,
                    project_id=project_id,
                    contract_id=contract_id,
                    contract_payload=payload,
                    phase=str(phase["phase"]),
                    config_fingerprint=clean_fingerprint,
                )
            evidence_ref_present = "gate_packet_evidence_ref" in clean_details
            if phase_name == "pilot" and evidence_ref_present:
                raise DataError("D0 pilot cannot carry typed D1 or D2 gate evidence")
            if (
                phase_name == "deep_research"
                and clean_status == "completed"
                and not evidence_ref_present
            ):
                raise DataError(
                    "completed D1 deep research requires its typed gate evidence artifact"
                )
            if evidence_ref_present:
                if clean_run is None:
                    raise DataError("research gate evidence selector requires an immutable run_id")
                if clean_status != "completed":
                    raise DataError("research gate evidence is valid only on a completed attempt")
                evidence = self._read_research_gate_evidence(clean_run, clean_details)
                if evidence.get("schema") != "ResearchGateEvidenceV1":
                    raise DataError("research gate evidence artifact has an unsupported schema")
                if evidence.get("evidence_zone") != expected_zone:
                    raise DataError("research gate evidence zone does not match its contract phase")
                if clean_details.get("evidence_zone") != expected_zone:
                    raise DataError("research attempt evidence_zone does not match its artifact")
                if expected_zone == "D1":
                    self._require_d1_verified_evidence(
                        run_id=clean_run,
                        project_id=project_id,
                        contract_id=contract_id,
                        contract_payload=payload,
                    )
                if expected_zone == "D2":
                    _confirmation_classification(evidence)
                    self._require_d2_verified_evidence(
                        run_id=clean_run,
                        project_id=project_id,
                        contract_id=contract_id,
                        contract_payload=payload,
                    )
            elif contract["scope"] == "confirmation" and clean_status == "completed":
                raise DataError(
                    "completed confirmation requires a declared immutable artifact for typed D2 "
                    "evidence"
                )
            if phase_name == "pilot" and clean_status == "completed":
                if clean_run is None:  # pragma: no cover - checked above.
                    raise DataError("completed D0 pilot requires an immutable run_id")
                d0_manifest = self._require_passing_d0_run(
                    run_id=clean_run,
                    project_id=project_id,
                    contract_id=contract_id,
                    contract_payload=payload,
                    config_fingerprint=clean_fingerprint,
                )
                self._require_d0_acceptance_reference(clean_details, d0_manifest)
                if any(isinstance(value, bool) for value in clean_details.values()):
                    raise DataError(
                        "completed D0 attempt details may not inline acceptance booleans"
                    )
            identity = {
                "schema_version": 1,
                "project_id": project_id,
                "contract_id": contract_id,
                "phase": phase["phase"],
                "kind": clean_kind,
                "status": clean_status,
                "config_fingerprint": clean_fingerprint,
                "budget_used": clean_budget,
                "run_id": clean_run,
                "error": clean_error,
                "details": clean_details,
            }
            if clean_reservation_id is not None:
                identity["launch_reservation_id"] = clean_reservation_id
            attempt_id = _content_id("ra", identity)
            if reservation_link is not None and reservation_link["attempt_id"] != attempt_id:
                raise DataError("research launch reservation already has a terminal attempt")
            existing = connection.execute(
                "SELECT * FROM research_attempt_records WHERE attempt_id = ?", (attempt_id,)
            ).fetchone()
            if existing is not None:
                if clean_reservation_id is not None and reservation_link is None:
                    raise DataError("research launch reservation terminal link is missing")
                return self._research_attempt_view(
                    existing, launch_reservation_id=clean_reservation_id
                )
            if phase_name == "pilot" and clean_reservation_id is None:
                reservation_count = connection.execute(
                    """SELECT COUNT(*) AS count FROM research_launch_reservations
                    WHERE project_id = ? AND contract_id = ? AND kind = ?""",
                    (project_id, contract_id, _D0_RESEARCH_KIND),
                ).fetchone()
                if int(cast(sqlite3.Row, reservation_count)["count"]) > 0:
                    raise DataError("D0 terminalization requires its durable launch reservation")
                direct_count = connection.execute(
                    """SELECT COUNT(*) AS count FROM research_attempt_records
                    WHERE project_id = ? AND contract_id = ? AND kind = ?""",
                    (project_id, contract_id, _D0_RESEARCH_KIND),
                ).fetchone()
                if int(cast(sqlite3.Row, direct_count)["count"]) >= _D0_MAX_LAUNCHES:
                    raise DataError(
                        "synthetic pilot stopped after the initial attempt and two safe retries"
                    )
            budget_limit = _budget_values(payload["budget"], require_minimum=True)
            lineage_ids = [contract_id]
            if isinstance(contract["parent_contract_id"], str):
                lineage_ids.append(str(contract["parent_contract_id"]))
            elapsed, _ = self._research_lineage_accounting(
                connection,
                project_id=project_id,
                contract_ids=lineage_ids,
            )
            for key, value in clean_budget.items():
                if key not in budget_limit:
                    raise DataError(f"research attempt uses undeclared budget dimension {key!r}")
                if elapsed.get(key, 0) + value > budget_limit[key]:
                    raise DataError(f"research attempt exceeds approved {key!r} budget")
            connection.execute(
                """INSERT INTO research_attempt_records (
                    attempt_id, project_id, contract_id, phase, kind, status,
                    config_fingerprint, budget_used_json, run_id, error, details_json,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    attempt_id,
                    project_id,
                    contract_id,
                    phase["phase"],
                    clean_kind,
                    clean_status,
                    clean_fingerprint,
                    _canonical_json(clean_budget, "research attempt budget"),
                    clean_run,
                    clean_error,
                    _canonical_json(clean_details, "research attempt details"),
                    timestamp,
                ),
            )
            if clean_reservation_id is not None:
                connection.execute(
                    """INSERT INTO research_launch_attempt_links (
                        reservation_id, attempt_id, linked_at
                    ) VALUES (?, ?, ?)""",
                    (clean_reservation_id, attempt_id, timestamp),
                )
            existing = connection.execute(
                "SELECT * FROM research_attempt_records WHERE attempt_id = ?", (attempt_id,)
            ).fetchone()
        if existing is None:  # pragma: no cover
            raise DataError("control store failed to persist research attempt")
        return self._research_attempt_view(existing, launch_reservation_id=clean_reservation_id)

    def record_research_decision(
        self,
        project_id: str,
        contract_id: str,
        *,
        outcome: ResearchOutcome,
        disposition: ResearchDisposition,
        actor: str,
        actor_kind: AuthorKind,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append the owner-only terminal research outcome and explicit disposition."""
        clean_outcome = _enum_value(outcome, "research outcome", RESEARCH_OUTCOMES)
        clean_disposition = _enum_value(disposition, "research disposition", RESEARCH_DISPOSITIONS)
        clean_actor_kind = _enum_value(actor_kind, "research decision actor_kind", AUTHOR_KINDS)
        if clean_actor_kind != "human":
            raise DataError("research decision requires a human owner")
        if clean_disposition == "advance_to_strategy" and clean_outcome != "SUPPORTED":
            raise DataError("only a SUPPORTED research outcome may advance to strategy")
        clean_actor = _required_text(actor, "research decision actor", max_length=200)
        clean_reason = _required_text(reason, "research decision reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            contract = self._require_research_contract(connection, project_id, contract_id)
            review = self._latest_research_review(connection, contract_id)
            phase = self._latest_research_phase(connection, project_id)
            d2 = self._latest_research_d2(connection, project_id)
            confirmation_path = contract["scope"] == "confirmation" and (
                _research_review_state(review) == "approved"
                and phase is not None
                and phase["phase"] == "research_decision"
                and phase["contract_id"] == contract_id
                and d2 is not None
                and d2["state"] in {"consumed", "contaminated"}
                and d2["contract_id"] == contract_id
            )
            early_path = (
                contract["scope"] == "exploration"
                and _research_review_state(review) == "approved"
                and phase is not None
                and phase["phase"] == "research_decision"
                and phase["contract_id"] == contract_id
                and d2 is not None
                and d2["state"] == "sealed"
                and clean_outcome in {"INCONCLUSIVE", "INVALID"}
                and clean_disposition in {"revise", "park", "reject"}
            )
            if (
                contract["scope"] == "exploration"
                and _research_review_state(review) == "approved"
                and phase is not None
                and phase["phase"] == "research_decision"
                and phase["contract_id"] == contract_id
                and d2 is not None
                and d2["state"] == "sealed"
                and clean_outcome == "CONTRADICTED"
            ):
                raise DataError("CONTRADICTED requires lineage-bound typed non-synthetic evidence")
            if not confirmation_path and not early_path:
                raise DataError(
                    "research decision requires either sealed early termination or the consumed/"
                    "contaminated approved confirmation contract"
                )
            if confirmation_path:
                if d2 is None:  # pragma: no cover - confirmation_path invariant.
                    raise DataError("research confirmation D2 state is unavailable")
                if d2["state"] == "contaminated":
                    if clean_outcome != "INVALID" or clean_disposition not in {
                        "revise",
                        "park",
                        "reject",
                    }:
                        raise DataError(
                            "contaminated confirmation must be recorded as INVALID without advance"
                        )
                else:
                    payload = _decode_json(
                        contract["payload_json"], "research confirmation contract payload"
                    )
                    if not isinstance(payload, dict):  # pragma: no cover - stored JSON invariant.
                        raise DataError("corrupt research confirmation contract payload")
                    mechanical_evidence = self._mechanical_confirmation_evidence(
                        connection,
                        project_id=project_id,
                        contract_id=contract_id,
                        contract_payload=payload,
                    )
                    mechanical_outcome = _confirmation_classification(mechanical_evidence)
                    if mechanical_outcome != clean_outcome:
                        raise DataError(
                            "owner outcome does not match the mechanical D2 classification"
                        )
                    promotion_readiness = derive_research_readiness(mechanical_evidence)[
                        "promotion_readiness"
                    ]
                    if (
                        clean_disposition == "advance_to_strategy"
                        and promotion_readiness["state"] != "ready"
                    ):
                        blockers = promotion_readiness["blockers"]
                        codes = (
                            [
                                str(blocker.get("code"))
                                for blocker in blockers
                                if isinstance(blocker, Mapping)
                            ]
                            if isinstance(blockers, list)
                            else []
                        )
                        raise DataError(
                            "strategy promotion is blocked by mechanical readiness: "
                            + ", ".join(codes)
                        )
            existing = connection.execute(
                """SELECT * FROM research_decision_events
                WHERE project_id = ? AND contract_id = ?""",
                (project_id, contract_id),
            ).fetchone()
            if existing is not None:
                if (
                    existing["outcome"] == clean_outcome
                    and existing["disposition"] == clean_disposition
                ):
                    return dict(existing)
                raise DataError("research contract already has a conflicting owner decision")
            sequence_row = connection.execute(
                """SELECT MAX(sequence) AS sequence FROM research_decision_events
                WHERE project_id = ?""",
                (project_id,),
            ).fetchone()
            prior_sequence = (
                0
                if sequence_row is None or sequence_row["sequence"] is None
                else int(sequence_row["sequence"])
            )
            connection.execute(
                """INSERT INTO research_decision_events (
                    project_id, sequence, contract_id, outcome, disposition, actor, actor_kind,
                    occurred_at, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    prior_sequence + 1,
                    contract_id,
                    clean_outcome,
                    clean_disposition,
                    clean_actor,
                    clean_actor_kind,
                    timestamp,
                    clean_reason,
                ),
            )
            stored = connection.execute(
                """SELECT * FROM research_decision_events
                WHERE project_id = ? AND contract_id = ?""",
                (project_id, contract_id),
            ).fetchone()
        if stored is None:  # pragma: no cover
            raise DataError("control store failed to persist research decision")
        return dict(stored)

    def close_early_research_case(
        self,
        project_id: str,
        *,
        outcome: ResearchOutcome,
        disposition: ResearchDisposition,
        actor: str,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Atomically close a pre-D2 case without manufacturing empirical support."""

        clean_outcome = _enum_value(outcome, "research outcome", RESEARCH_OUTCOMES)
        clean_disposition = _enum_value(disposition, "research disposition", RESEARCH_DISPOSITIONS)
        if clean_outcome not in {"INCONCLUSIVE", "INVALID"}:
            raise DataError(
                "evidence-free or D0-only research can close only as INCONCLUSIVE or INVALID"
            )
        if clean_disposition not in {"revise", "park", "reject"}:
            raise DataError("pre-D2 research cannot advance to strategy")
        clean_actor = _required_text(actor, "research decision actor", max_length=200)
        clean_reason = _required_text(reason, "research decision reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            phase = self._latest_research_phase(connection, project_id)
            execution = self._latest_research_execution(connection, project_id)
            d2 = self._latest_research_d2(connection, project_id)
            if phase is None or phase["phase"] not in {
                "exploration_review",
                "pilot",
                "deep_research",
                "confirmation_review",
            }:
                raise DataError("early research close requires a pre-D2 decision phase")
            if execution is None or execution["state"] != "idle":
                raise DataError("early research close requires idle execution")
            active = self._require_research_contract(
                connection, project_id, str(phase["contract_id"])
            )
            exploration = active
            rejected_exploration = False
            if phase["phase"] == "exploration_review":
                review = self._latest_research_review(connection, str(active["contract_id"]))
                if active["scope"] != "exploration" or _research_review_state(review) != "rejected":
                    raise DataError(
                        "early exploration close requires an owner-rejected exploration contract"
                    )
                if clean_outcome != "INVALID":
                    raise DataError("a rejected exploration protocol can close only as INVALID")
                rejected_exploration = True
            if active["scope"] == "confirmation":
                review = self._latest_research_review(connection, str(active["contract_id"]))
                if (
                    phase["phase"] != "confirmation_review"
                    or _research_review_state(review) != "rejected"
                ):
                    raise DataError(
                        "early confirmation close requires an owner-rejected confirmation child"
                    )
                parent_id = active["parent_contract_id"]
                if not isinstance(parent_id, str):  # pragma: no cover - schema invariant.
                    raise DataError("rejected confirmation child has no exploration parent")
                exploration = self._require_research_contract(connection, project_id, parent_id)
            exploration_id = str(exploration["contract_id"])
            exploration_review = self._latest_research_review(connection, exploration_id)
            if (
                exploration["scope"] != "exploration"
                or (
                    not rejected_exploration
                    and _research_review_state(exploration_review) != "approved"
                )
                or d2 is None
                or d2["state"] != "sealed"
            ):
                raise DataError("early research close requires approved exploration with D2 sealed")
            self._append_research_phase_event(
                connection,
                project_id=project_id,
                contract_id=exploration_id,
                phase="research_decision",
                actor=clean_actor,
                reason=clean_reason,
                next_action="Record and close the non-supporting pre-D2 research outcome.",
                responsibility="owner",
                blocker=None,
                recovery=None,
                at=timestamp,
            )
            prior_sequence_row = connection.execute(
                """SELECT MAX(sequence) AS sequence FROM research_decision_events
                WHERE project_id = ?""",
                (project_id,),
            ).fetchone()
            prior_sequence = (
                0
                if prior_sequence_row is None or prior_sequence_row["sequence"] is None
                else int(prior_sequence_row["sequence"])
            )
            connection.execute(
                """INSERT INTO research_decision_events (
                    project_id, sequence, contract_id, outcome, disposition, actor, actor_kind,
                    occurred_at, reason
                ) VALUES (?, ?, ?, ?, ?, ?, 'human', ?, ?)""",
                (
                    project_id,
                    prior_sequence + 1,
                    exploration_id,
                    clean_outcome,
                    clean_disposition,
                    clean_actor,
                    timestamp,
                    clean_reason,
                ),
            )
            self._append_research_phase_event(
                connection,
                project_id=project_id,
                contract_id=exploration_id,
                phase="closed",
                actor=clean_actor,
                reason="owner recorded the terminal pre-D2 research disposition",
                next_action=(
                    "Research case is closed; revise only through a new immutable child lineage."
                ),
                responsibility="owner",
                blocker=None,
                recovery=None,
                at=timestamp,
            )
            stored = connection.execute(
                """SELECT * FROM research_decision_events
                WHERE project_id = ? AND contract_id = ?""",
                (project_id, exploration_id),
            ).fetchone()
        if stored is None:  # pragma: no cover
            raise DataError("control store failed to persist early research decision")
        return dict(stored)

    def research_case_summary(self, project_id: str) -> dict[str, object]:
        """Project one bounded, decision-oriented research case summary."""
        with self._transaction(write=False) as connection:
            project = self._require_project(connection, project_id)
            phase = self._latest_research_phase(connection, project_id)
            execution = self._latest_research_execution(connection, project_id)
            d2 = self._latest_research_d2(connection, project_id)
            if phase is None or execution is None or d2 is None:
                raise DataError(f"strategy project {project_id!r} has no research case")
            contract = self._require_research_contract(
                connection, project_id, str(phase["contract_id"])
            )
            contract_view = self._research_contract_view(connection, contract)
            confirmation_id = (
                str(contract["contract_id"]) if contract["scope"] == "confirmation" else None
            )
            exploration_id = (
                str(contract["parent_contract_id"])
                if confirmation_id is not None
                else str(contract["contract_id"])
            )
            exploration_review = self._latest_research_review(connection, exploration_id)
            confirmation_review = (
                None
                if confirmation_id is None
                else self._latest_research_review(connection, confirmation_id)
            )
            lineage_ids = [exploration_id]
            if confirmation_id is not None:
                lineage_ids.append(confirmation_id)
            placeholders = ",".join("?" for _ in lineage_ids)
            attempt_rows = connection.execute(
                f"""SELECT a.*, l.reservation_id AS launch_reservation_id
                FROM research_attempt_records AS a
                LEFT JOIN research_launch_attempt_links AS l ON l.attempt_id = a.attempt_id
                WHERE a.project_id = ? AND a.contract_id IN ({placeholders})
                ORDER BY a.recorded_at, a.attempt_id""",  # noqa: S608
                [project_id, *lineage_ids],
            ).fetchall()
            reservation_rows = connection.execute(
                f"""SELECT r.*, l.attempt_id AS terminal_attempt_id
                FROM research_launch_reservations AS r
                LEFT JOIN research_launch_attempt_links AS l
                    ON l.reservation_id = r.reservation_id
                WHERE r.project_id = ? AND r.contract_id IN ({placeholders})
                ORDER BY r.reserved_at, r.reservation_id""",  # noqa: S608
                [project_id, *lineage_ids],
            ).fetchall()
            elapsed, logical_attempt_count = self._research_lineage_accounting(
                connection,
                project_id=project_id,
                contract_ids=lineage_ids,
            )
            payload = contract_view["payload"]
            if not isinstance(payload, dict):  # pragma: no cover - decoded contract invariant.
                raise DataError("corrupt research contract payload")
            budget = _budget_values(payload.get("budget", {}), require_minimum=False)
            remaining = {
                key: max(0, value - elapsed.get(key, 0)) for key, value in sorted(budget.items())
            }
            phase_rows = connection.execute(
                """SELECT phase, contract_id, occurred_at, reason
                FROM research_phase_events WHERE project_id = ? ORDER BY sequence""",
                (project_id,),
            ).fetchall()
            milestones = [
                {
                    "phase": row["phase"],
                    "contract_id": row["contract_id"],
                    "occurred_at": row["occurred_at"],
                    "reason": row["reason"],
                }
                for row in phase_rows
            ]
            latest_attempt = (
                None if not attempt_rows else self._research_attempt_view(attempt_rows[-1])
            )
            if (
                latest_attempt is not None
                and latest_attempt.get("phase") == "pilot"
                and latest_attempt.get("status") == "completed"
            ):
                latest_contract_id = latest_attempt.get("contract_id")
                if not isinstance(latest_contract_id, str):
                    raise DataError("latest completed D0 attempt has corrupt contract lineage")
                latest_contract = self._require_research_contract(
                    connection, project_id, latest_contract_id
                )
                latest_payload = _decode_json(
                    latest_contract["payload_json"], "latest completed D0 contract payload"
                )
                if not isinstance(latest_payload, dict):
                    raise DataError("latest completed D0 contract payload is corrupt")
                self._verify_research_attempt_run(
                    project_id=project_id,
                    attempt=latest_attempt,
                    contract_payload=latest_payload,
                )
            latest_finding = None
            if latest_attempt is not None:
                details = latest_attempt.get("details")
                if isinstance(details, dict) and isinstance(details.get("finding"), str):
                    latest_finding = details["finding"]
                elif latest_attempt.get("status") == "failed" and isinstance(
                    latest_attempt.get("error"), str
                ):
                    latest_finding = f"Attempt failed: {latest_attempt['error']}"
            durable_times = [
                str(row["occurred_at"]) for row in phase_rows if isinstance(row["occurred_at"], str)
            ]
            if isinstance(execution["occurred_at"], str):
                durable_times.append(str(execution["occurred_at"]))
            durable_times.extend(
                str(row["recorded_at"])
                for row in attempt_rows
                if isinstance(row["recorded_at"], str)
            )
            durable_times.extend(
                str(row["reserved_at"])
                for row in reservation_rows
                if isinstance(row["reserved_at"], str)
            )
            elapsed_time_seconds = 0.0
            if durable_times:
                elapsed_time_seconds = max(
                    0.0,
                    (
                        parse_timestamp(max(durable_times), "research latest durable timestamp")
                        - parse_timestamp(min(durable_times), "research first durable timestamp")
                    ).total_seconds(),
                )
            phase_index = RESEARCH_PHASE_ORDER.index(str(phase["phase"]))
            remaining_milestones = list(RESEARCH_PHASE_ORDER[phase_index + 1 :])
            d2_history = [
                dict(row)
                for row in connection.execute(
                    """SELECT contract_id, state, boundary_hash, actor, occurred_at, reason
                    FROM research_d2_events WHERE project_id = ? ORDER BY sequence""",
                    (project_id,),
                ).fetchall()
            ]
            decision = connection.execute(
                f"""SELECT * FROM research_decision_events
                WHERE project_id = ? AND contract_id IN ({placeholders})
                ORDER BY sequence DESC LIMIT 1""",  # noqa: S608
                [project_id, *lineage_ids],
            ).fetchone()
            use_execution = str(execution["occurred_at"]) > str(phase["occurred_at"])
            action_source = execution if use_execution else phase
            current_experiment_id = project["current_experiment_id"]
            holdout = (
                None
                if current_experiment_id is None
                else connection.execute(
                    """SELECT revealed_at, contaminated_at FROM holdout_state
                    WHERE project_id = ? AND experiment_id = ?""",
                    (project_id, current_experiment_id),
                ).fetchone()
            )
            if holdout is None:
                d3_state = "not_sealed"
            elif holdout["contaminated_at"] is not None:
                d3_state = "contaminated"
            elif holdout["revealed_at"] is not None:
                d3_state = "consumed"
            else:
                d3_state = "sealed"
        return {
            "schema_version": 1,
            "project_id": project_id,
            "project_name": project["name"],
            "phase": phase["phase"],
            "execution_state": execution["state"],
            "active_contract_id": contract["contract_id"],
            "active_contract": contract_view,
            "exploration_contract_id": exploration_id,
            "confirmation_contract_id": confirmation_id,
            "exploration_review": {
                "state": _research_review_state(exploration_review),
                "event": None if exploration_review is None else dict(exploration_review),
            },
            "confirmation_review": {
                "state": _research_review_state(confirmation_review),
                "event": None if confirmation_review is None else dict(confirmation_review),
            },
            "research_decision": None if decision is None else dict(decision),
            "next_action": action_source["next_action"],
            "responsibility": action_source["responsibility"],
            "blocker": action_source["blocker"],
            "recovery": action_source["recovery"],
            "latest_finding": latest_finding,
            "milestones": milestones,
            "completed_milestones": milestones,
            "remaining_milestones": remaining_milestones,
            "elapsed_time_seconds": elapsed_time_seconds,
            "elapsed_budget": dict(sorted(elapsed.items())),
            "remaining_budget": remaining,
            "active_job_id": execution["active_job_id"],
            "checkpoint": execution["checkpoint"],
            "hashes": payload.get("hashes", {}),
            "source_pack_id": payload.get("source_pack_id"),
            "attempt_count": logical_attempt_count,
            "terminal_attempt_count": len(attempt_rows),
            "unfinalized_launch_count": sum(
                row["terminal_attempt_id"] is None for row in reservation_rows
            ),
            "remaining_launches": max(0, _D0_MAX_LAUNCHES - logical_attempt_count),
            "latest_launch_reservation_id": (
                None if not reservation_rows else reservation_rows[-1]["reservation_id"]
            ),
            "latest_launch_number": (
                None if not reservation_rows else reservation_rows[-1]["launch_number"]
            ),
            "latest_attempt_id": (None if latest_attempt is None else latest_attempt["attempt_id"]),
            "latest_run_id": None if latest_attempt is None else latest_attempt["run_id"],
            "latest_run_fingerprint": (
                None if latest_attempt is None else latest_attempt["config_fingerprint"]
            ),
            "d2_state": d2["state"],
            "d2_boundary_hash": d2["boundary_hash"],
            "d2_history": d2_history,
            "d3_state": d3_state,
        }

    def list_research_cases(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, object]]:
        """Return bounded research-case rows ordered by latest research activity.

        Each row is ``{"case": <research_case_summary>, "updated_at": <ISO timestamp>}``.
        The nested summary is byte-identical to :meth:`research_case_summary` so the
        dossier's embedded-summary hash never drifts; ``updated_at`` rides alongside it
        because the summary itself is hash-pinned and cannot gain keys.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise DataError("research case list limit must be in 1..200")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise DataError("research case list offset must be non-negative")
        with self._transaction(write=False) as connection:
            ordered = connection.execute(
                """SELECT project_id, MAX(ts) AS updated_at FROM (
                    SELECT project_id, occurred_at AS ts FROM research_phase_events
                    UNION ALL
                    SELECT project_id, occurred_at AS ts FROM research_execution_events
                    UNION ALL
                    SELECT project_id, recorded_at AS ts FROM research_attempt_records
                    UNION ALL
                    SELECT project_id, reserved_at AS ts FROM research_launch_reservations
                ) GROUP BY project_id ORDER BY updated_at DESC, project_id
                LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [
            {
                "case": self.research_case_summary(str(row["project_id"])),
                "updated_at": str(row["updated_at"]),
            }
            for row in ordered
        ]

    def _bounded_project_rows(
        self,
        connection: sqlite3.Connection,
        query: str,
        params: Sequence[object],
        *,
        limit: int = _RESEARCH_PACKET_COLLECTION_LIMIT,
    ) -> tuple[list[dict[str, object]], bool]:
        rows = connection.execute(f"{query} LIMIT ?", [*params, limit + 1]).fetchall()  # noqa: S608
        truncated = len(rows) > limit
        return [dict(row) for row in rows[:limit]], truncated

    def _packet_row_view(self, row: sqlite3.Row | dict[str, object]) -> dict[str, object]:
        record = dict(row)
        payload = _decode_json(record.pop("payload_json"), "research context packet payload")
        if not isinstance(payload, dict):
            raise DataError("corrupt research context packet payload")
        return {**record, "payload": payload}

    def build_research_context_packet(
        self,
        project_id: str,
        *,
        kind: str,
        created_by: str,
        symbol: str | None = None,
        protocol_id: str | None = None,
        protocol_content_hash: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Assemble and append-only-record one content-addressed Codex context packet.

        The payload is built from authoritative records inside one write transaction with
        bounded collections and explicit truncation flags; ``cp_<sha256>`` is derived from
        the canonical payload bytes, so identical inputs re-record idempotently and the UI
        can display byte-identical context. Recording is visibility (spec §3.2).
        """
        clean_kind = _enum_value(kind, "research context packet kind", _RESEARCH_PACKET_KINDS)
        clean_actor = _required_text(created_by, "research packet creator", max_length=200)
        clean_protocol = _optional_text(protocol_id, "research packet protocol_id")
        clean_protocol_hash = _optional_text(
            protocol_content_hash, "research packet protocol_content_hash"
        )
        if clean_protocol_hash is not None and _SHA256_RE.fullmatch(clean_protocol_hash) is None:
            raise DataError("research packet protocol_content_hash must be a sha256 hex digest")
        if (clean_protocol is None) != (clean_protocol_hash is None):
            raise DataError("research packet protocol id and content hash travel together")
        clean_symbol = None
        if clean_kind == "asset":
            if symbol is None:
                raise DataError("asset research packets require a symbol")
            clean_symbol = _symbols([symbol])[0]
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            project = dict(self._require_project(connection, project_id))
            pid = str(project["project_id"])
            phase = self._latest_research_phase(connection, pid)
            execution = self._latest_research_execution(connection, pid)
            if phase is None or execution is None:
                raise DataError(f"strategy project {pid!r} has no research case")
            contract = self._require_research_contract(connection, pid, str(phase["contract_id"]))
            contract_view = self._research_contract_view(connection, contract)
            decision = connection.execute(
                """SELECT * FROM research_decision_events WHERE project_id = ?
                ORDER BY sequence DESC LIMIT 1""",
                (pid,),
            ).fetchone()
            attempts, attempts_truncated = self._bounded_project_rows(
                connection,
                """SELECT attempt_id, contract_id, phase, kind, status, config_fingerprint,
                    run_id, recorded_at
                FROM research_attempt_records WHERE project_id = ?
                ORDER BY recorded_at, attempt_id""",
                (pid,),
            )
            sources, sources_truncated = self._bounded_project_rows(
                connection,
                """SELECT source_id, title, locator, provider, access_mode, created_at
                FROM research_source_records WHERE project_id = ?
                ORDER BY created_at, source_id""",
                (pid,),
            )
            notes, notes_truncated = self._bounded_project_rows(
                connection,
                """SELECT note_id, note_kind, body, author, author_kind, context_packet_id,
                    created_at
                FROM research_case_notes WHERE project_id = ? ORDER BY sequence""",
                (pid,),
            )
            screened_claims, screened_claims_truncated = self._screened_claims(connection, pid)
            payload_contract = contract_view["payload"]
            if not isinstance(payload_contract, dict):
                raise DataError("corrupt research contract payload")
            kind_specific = self._packet_kind_specific(
                connection,
                kind=clean_kind,
                symbol=clean_symbol,
                contract_payload=payload_contract,
                decision=None if decision is None else dict(decision),
                attempts=attempts,
            )
            cursor_rows = connection.execute(
                """SELECT
                    (SELECT COALESCE(MAX(sequence), 0) FROM research_phase_events
                        WHERE project_id = ?) AS phase,
                    (SELECT COALESCE(MAX(sequence), 0) FROM research_execution_events
                        WHERE project_id = ?) AS execution,
                    (SELECT COUNT(*) FROM research_attempt_records
                        WHERE project_id = ?) AS attempts,
                    (SELECT COALESCE(MAX(sequence), 0) FROM research_decision_events
                        WHERE project_id = ?) AS decisions""",
                (pid, pid, pid, pid),
            ).fetchone()
            payload: dict[str, object] = {
                "packet_schema": "ResearchContextPacketV1",
                "packet_kind": clean_kind,
                "project_id": pid,
                "project_name": project["name"],
                "hypothesis": project["hypothesis"],
                "falsification_criterion": project["falsification_criterion"],
                "phase": phase["phase"],
                "execution_state": execution["state"],
                "next_action": (
                    execution["next_action"]
                    if str(execution["occurred_at"]) > str(phase["occurred_at"])
                    else phase["next_action"]
                ),
                "responsibility": (
                    execution["responsibility"]
                    if str(execution["occurred_at"]) > str(phase["occurred_at"])
                    else phase["responsibility"]
                ),
                "active_contract_id": contract_view["contract_id"],
                "contract_review_state": contract_view["review_state"],
                "contract_payload": payload_contract,
                "decision": None if decision is None else dict(decision),
                "attempts": attempts,
                "attempts_truncated": attempts_truncated,
                "sources": sources,
                "sources_truncated": sources_truncated,
                "screened_source_claims": screened_claims,
                "screened_source_claims_truncated": screened_claims_truncated,
                "notes": notes,
                "notes_truncated": notes_truncated,
                "kind_specific": kind_specific,
                "history_cursors": {
                    "phase": int(cursor_rows["phase"]),
                    "execution": int(cursor_rows["execution"]),
                    "attempts": int(cursor_rows["attempts"]),
                    "decisions": int(cursor_rows["decisions"]),
                },
                # Honest availability: planes that have not shipped are named, not faked.
                "unavailable_context": {
                    "dataset_refs": "registered research datasets arrive with the data plane",
                },
            }
            packet_id = _content_id("cp", payload)
            existing = connection.execute(
                "SELECT * FROM research_context_packets WHERE packet_id = ?",
                (packet_id,),
            ).fetchone()
            if existing is not None:
                return self._packet_row_view(existing)
            connection.execute(
                """INSERT INTO research_context_packets (
                    packet_id, project_id, packet_kind, protocol_id, protocol_content_hash,
                    payload_json, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    packet_id,
                    pid,
                    clean_kind,
                    clean_protocol,
                    clean_protocol_hash,
                    _canonical_json(payload, "research context packet payload"),
                    clean_actor,
                    timestamp,
                ),
            )
        return {
            "packet_id": packet_id,
            "project_id": pid,
            "packet_kind": clean_kind,
            "protocol_id": clean_protocol,
            "protocol_content_hash": clean_protocol_hash,
            "payload": payload,
            "created_by": clean_actor,
            "created_at": timestamp,
        }

    def _packet_kind_specific(
        self,
        connection: sqlite3.Connection,
        *,
        kind: str,
        symbol: str | None,
        contract_payload: Mapping[str, object],
        decision: Mapping[str, object] | None,
        attempts: list[dict[str, object]],
    ) -> dict[str, object]:
        if kind == "asset":
            rows = connection.execute(
                """SELECT evidence_id, revision, status, claim, timeframe, method,
                    metric_name, metric_value, metric_unit, market_data_cutoff, knowledge_at,
                    author_kind
                FROM evidence_revisions WHERE assets_json LIKE ?
                ORDER BY created_at DESC, evidence_id, revision DESC LIMIT ?""",
                (f'%"{symbol}"%', _RESEARCH_PACKET_COLLECTION_LIMIT + 1),
            ).fetchall()
            return {
                "symbol": symbol,
                "asset_evidence": [dict(row) for row in rows[:_RESEARCH_PACKET_COLLECTION_LIMIT]],
                "asset_evidence_truncated": len(rows) > _RESEARCH_PACKET_COLLECTION_LIMIT,
            }
        if kind == "experiment":
            return {"attempts": attempts}
        if kind == "chart":
            report_plan = contract_payload.get("report_plan")
            return {"report_plan": report_plan if isinstance(report_plan, dict) else None}
        if kind == "validation":
            return {
                "required_falsifiers": contract_payload.get("required_falsifiers", []),
                "confounders": contract_payload.get("confounders", []),
                "stop_rules": contract_payload.get("stop_rules", []),
            }
        if kind == "strategy_promotion":
            promotion_packet_id: str | None = None
            if decision is not None:
                decision_project = decision.get("project_id")
                decision_contract = decision.get("contract_id")
                if isinstance(decision_project, str) and isinstance(decision_contract, str):
                    reference = self._promotion_reference(
                        connection,
                        project_id=decision_project,
                        contract_id=decision_contract,
                        cutoff=None,
                    )
                    if reference is not None:
                        promotion_packet_id = cast(str, reference["packet_id"])
            return {"decision": decision, "promotion_packet_id": promotion_packet_id}
        # research_case: the open material questions are the packet's task surface.
        return {"blocking_questions": contract_payload.get("blocking_questions", [])}

    def get_research_context_packet(self, packet_id: str) -> dict[str, object]:
        """Return one recorded packet byte-identically (recording is visibility)."""
        clean = _require_content_id(packet_id, "research context packet_id", prefix="cp")
        with self._transaction(write=False) as connection:
            row = connection.execute(
                "SELECT * FROM research_context_packets WHERE packet_id = ?", (clean,)
            ).fetchone()
        if row is None:
            raise DataError(f"unknown research context packet {clean!r}")
        return self._packet_row_view(row)

    def list_research_context_packets(
        self, project_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, object]]:
        """Return this case's recorded packets, newest first."""
        limit, offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            rows = connection.execute(
                """SELECT * FROM research_context_packets WHERE project_id = ?
                ORDER BY created_at DESC, packet_id LIMIT ? OFFSET ?""",
                (project_id, limit, offset),
            ).fetchall()
        return [self._packet_row_view(row) for row in rows]

    def add_research_note(
        self,
        project_id: str,
        *,
        note_kind: str,
        body: str,
        author: str,
        author_kind: str,
        context_packet_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append one Codex/owner commentary note — structurally outside the evidence model."""
        clean_kind = _enum_value(note_kind, "research note kind", _RESEARCH_NOTE_KINDS)
        clean_body = _required_text(body, "research note body", max_length=20_000)
        clean_author = _required_text(author, "research note author", max_length=200)
        clean_author_kind = _enum_value(
            author_kind, "research note author kind", _RESEARCH_NOTE_AUTHOR_KINDS
        )
        clean_packet = (
            None
            if context_packet_id is None
            else _require_content_id(
                context_packet_id, "research note context_packet_id", prefix="cp"
            )
        )
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            if clean_packet is not None:
                packet = connection.execute(
                    "SELECT project_id FROM research_context_packets WHERE packet_id = ?",
                    (clean_packet,),
                ).fetchone()
                if packet is None or packet["project_id"] != project_id:
                    raise DataError(f"unknown research context packet {clean_packet!r}")
            sequence_row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM research_case_notes "
                "WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            sequence = int(sequence_row[0])
            note_identity = {
                "schema_version": 1,
                "project_id": project_id,
                "sequence": sequence,
                "note_kind": clean_kind,
                "body": clean_body,
                "author": clean_author,
                "author_kind": clean_author_kind,
                "context_packet_id": clean_packet,
                "created_at": timestamp,
            }
            note_id = _content_id("rn", note_identity)
            connection.execute(
                """INSERT INTO research_case_notes (
                    note_id, project_id, sequence, note_kind, body, author, author_kind,
                    context_packet_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    note_id,
                    project_id,
                    sequence,
                    clean_kind,
                    clean_body,
                    clean_author,
                    clean_author_kind,
                    clean_packet,
                    timestamp,
                ),
            )
        return {
            "note_id": note_id,
            "project_id": project_id,
            "sequence": sequence,
            "note_kind": clean_kind,
            "body": clean_body,
            "author": clean_author,
            "author_kind": clean_author_kind,
            "context_packet_id": clean_packet,
            "created_at": timestamp,
        }

    def list_research_notes(
        self, project_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, object]]:
        """Return this case's commentary notes, newest first (never evidence)."""
        limit, offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            rows = connection.execute(
                """SELECT * FROM research_case_notes WHERE project_id = ?
                ORDER BY sequence DESC LIMIT ? OFFSET ?""",
                (project_id, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def _dataset_ref_view(self, row: sqlite3.Row | dict[str, object]) -> dict[str, object]:
        record = dict(row)
        origin = _decode_json(record.pop("origin_json"), "research dataset origin")
        if not isinstance(origin, dict):
            raise DataError("corrupt research dataset origin")
        record["origin"] = origin
        record["research_only"] = bool(record.get("research_only"))
        return record

    def register_research_dataset(
        self,
        *,
        dataset_kind: str,
        instrument: str,
        provider: str,
        start_ts: str,
        end_ts: str,
        bar_duration_minutes: int | None,
        origin: Mapping[str, object],
        registered_by: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Fail-closed research dataset registration: no receipt/provenance → no ref.

        The ref is content-addressed (``rd_<sha256>``) over its complete identity, so an
        identical registration is idempotent and a changed origin is a different dataset.
        Every ref is ``research_only`` forever (ADR-0023): registration grants research
        readability, never canonical authority.
        """
        clean_kind = _enum_value(dataset_kind, "research dataset kind", _RESEARCH_DATASET_KINDS)
        clean_instrument = _symbols([instrument])[0]
        clean_provider = _required_text(provider, "research dataset provider", max_length=100)
        clean_start = _required_text(start_ts, "research dataset start_ts", max_length=64)
        clean_end = _required_text(end_ts, "research dataset end_ts", max_length=64)
        if bar_duration_minutes is not None and (
            isinstance(bar_duration_minutes, bool)
            or not isinstance(bar_duration_minutes, int)
            or bar_duration_minutes < 1
        ):
            raise DataError("research dataset bar_duration_minutes must be a positive integer")
        clean_origin = _json_object(origin, "research dataset origin")
        for field in _RESEARCH_DATASET_ORIGIN_FIELDS[clean_kind]:
            value = clean_origin.get(field)
            if not isinstance(value, str) or not value:
                raise DataError(
                    f"research dataset origin for {clean_kind!r} requires {field} "
                    "(fail-closed: unreceipted data cannot be registered)"
                )
            if field.endswith("sha256") and _SHA256_RE.fullmatch(value) is None:
                raise DataError(f"research dataset origin {field} must be a sha256 hex digest")
        clean_actor = _required_text(registered_by, "research dataset registrar", max_length=200)
        identity = {
            "schema_version": 1,
            "dataset_kind": clean_kind,
            "instrument": clean_instrument,
            "provider": clean_provider,
            "start_ts": clean_start,
            "end_ts": clean_end,
            "bar_duration_minutes": bar_duration_minutes,
            "origin": clean_origin,
        }
        ref_id = _content_id("rd", identity)
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM research_dataset_refs WHERE ref_id = ?", (ref_id,)
            ).fetchone()
            if existing is not None:
                return self._dataset_ref_view(existing)
            connection.execute(
                """INSERT INTO research_dataset_refs (
                    ref_id, dataset_kind, instrument, provider, start_ts, end_ts,
                    bar_duration_minutes, origin_json, research_only, registered_by,
                    registered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    ref_id,
                    clean_kind,
                    clean_instrument,
                    clean_provider,
                    clean_start,
                    clean_end,
                    bar_duration_minutes,
                    _canonical_json(clean_origin, "research dataset origin"),
                    clean_actor,
                    timestamp,
                ),
            )
        return {
            "ref_id": ref_id,
            "dataset_kind": clean_kind,
            "instrument": clean_instrument,
            "provider": clean_provider,
            "start_ts": clean_start,
            "end_ts": clean_end,
            "bar_duration_minutes": bar_duration_minutes,
            "origin": clean_origin,
            "research_only": True,
            "registered_by": clean_actor,
            "registered_at": timestamp,
        }

    def get_research_dataset(self, ref_id: str) -> dict[str, object]:
        """Return one registered research dataset ref."""
        clean = _require_content_id(ref_id, "research dataset ref_id", prefix="rd")
        with self._transaction(write=False) as connection:
            row = connection.execute(
                "SELECT * FROM research_dataset_refs WHERE ref_id = ?", (clean,)
            ).fetchone()
        if row is None:
            raise DataError(f"unknown research dataset {clean!r}")
        return self._dataset_ref_view(row)

    def list_research_datasets(
        self, *, instrument: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, object]]:
        """Return registered refs (optionally per instrument) with their latest audit."""
        limit, offset = _page(limit, offset)
        clean_instrument = None if instrument is None else _symbols([instrument])[0]
        with self._transaction(write=False) as connection:
            if clean_instrument is None:
                rows = connection.execute(
                    """SELECT * FROM research_dataset_refs
                    ORDER BY registered_at DESC, ref_id LIMIT ? OFFSET ?""",
                    (limit, offset),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM research_dataset_refs WHERE instrument = ?
                    ORDER BY registered_at DESC, ref_id LIMIT ? OFFSET ?""",
                    (clean_instrument, limit, offset),
                ).fetchall()
            views: list[dict[str, object]] = []
            for row in rows:
                view = self._dataset_ref_view(row)
                audit = connection.execute(
                    """SELECT * FROM research_dataset_audits WHERE ref_id = ?
                    ORDER BY sequence DESC LIMIT 1""",
                    (row["ref_id"],),
                ).fetchone()
                view["latest_audit"] = None if audit is None else self._dataset_audit_view(audit)
                views.append(view)
        return views

    def _dataset_audit_view(self, row: sqlite3.Row | dict[str, object]) -> dict[str, object]:
        record = dict(row)
        summary = _decode_json(record.pop("summary_json"), "research dataset audit summary")
        if not isinstance(summary, dict):
            raise DataError("corrupt research dataset audit summary")
        record["summary"] = summary
        return record

    def record_research_dataset_audit(
        self,
        ref_id: str,
        *,
        project_id: str,
        run_id: str,
        summary: Mapping[str, object],
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append one immutable data-audit result for a registered dataset."""
        clean_ref = _require_content_id(ref_id, "research dataset ref_id", prefix="rd")
        clean_run = _required_text(run_id, "research dataset audit run_id", max_length=64)
        clean_summary = _json_object(summary, "research dataset audit summary")
        if clean_summary.get("audit_schema") != "ResearchDataAuditV1":
            raise DataError(
                "research dataset audit summary must declare audit_schema ResearchDataAuditV1"
            )
        for field in ("blocking_count", "limiting_count"):
            value = clean_summary.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DataError(f"research dataset audit summary requires integer {field}")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            ref = connection.execute(
                "SELECT ref_id FROM research_dataset_refs WHERE ref_id = ?", (clean_ref,)
            ).fetchone()
            if ref is None:
                raise DataError(f"unknown research dataset {clean_ref!r}")
            sequence_row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM research_dataset_audits "
                "WHERE ref_id = ?",
                (clean_ref,),
            ).fetchone()
            sequence = int(sequence_row[0])
            connection.execute(
                """INSERT INTO research_dataset_audits (
                    ref_id, sequence, project_id, run_id, summary_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    clean_ref,
                    sequence,
                    project_id,
                    clean_run,
                    _canonical_json(clean_summary, "research dataset audit summary"),
                    timestamp,
                ),
            )
        return {
            "ref_id": clean_ref,
            "sequence": sequence,
            "project_id": project_id,
            "run_id": clean_run,
            "summary": clean_summary,
            "recorded_at": timestamp,
        }

    def list_research_dataset_audits(
        self, ref_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, object]]:
        """Return one dataset's audit history, newest first."""
        clean = _require_content_id(ref_id, "research dataset ref_id", prefix="rd")
        limit, offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            rows = connection.execute(
                """SELECT * FROM research_dataset_audits WHERE ref_id = ?
                ORDER BY sequence DESC LIMIT ? OFFSET ?""",
                (clean, limit, offset),
            ).fetchall()
        return [self._dataset_audit_view(row) for row in rows]

    def research_brief(
        self,
        project_id: str,
        *,
        created_by: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Build the "Resume with Codex" delta brief and record it as a packet.

        The delta covers phase/execution/attempt/decision history appended since the
        previous ``research_case`` packet for this project (the whole history on the
        first brief), so an external Codex session resumes without re-reading everything.
        """
        clean_actor = _required_text(created_by, "research brief creator", max_length=200)
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            previous = connection.execute(
                """SELECT payload_json FROM research_context_packets
                WHERE project_id = ? AND packet_kind = 'research_case'
                ORDER BY created_at DESC, packet_id LIMIT 1""",
                (project_id,),
            ).fetchone()
            cursors = {"phase": 0, "execution": 0, "attempts": 0, "decisions": 0}
            if previous is not None:
                payload = _decode_json(previous["payload_json"], "previous research packet")
                if isinstance(payload, dict):
                    recorded = payload.get("history_cursors")
                    if isinstance(recorded, dict):
                        for key in cursors:
                            value = recorded.get(key)
                            if isinstance(value, int) and not isinstance(value, bool):
                                cursors[key] = value
            phase_events = [
                dict(row)
                for row in connection.execute(
                    """SELECT sequence, phase, contract_id, occurred_at, reason
                    FROM research_phase_events WHERE project_id = ? AND sequence > ?
                    ORDER BY sequence""",
                    (project_id, cursors["phase"]),
                ).fetchall()
            ]
            execution_events = [
                dict(row)
                for row in connection.execute(
                    """SELECT sequence, state, occurred_at, reason, next_action
                    FROM research_execution_events WHERE project_id = ? AND sequence > ?
                    ORDER BY sequence""",
                    (project_id, cursors["execution"]),
                ).fetchall()
            ]
            attempt_rows = connection.execute(
                """SELECT attempt_id, phase, kind, status, run_id, recorded_at
                FROM research_attempt_records WHERE project_id = ?
                ORDER BY recorded_at, attempt_id""",
                (project_id,),
            ).fetchall()
            attempts = [dict(row) for row in attempt_rows[cursors["attempts"] :]]
            decision_events = [
                dict(row)
                for row in connection.execute(
                    """SELECT sequence, contract_id, outcome, disposition, occurred_at, reason
                    FROM research_decision_events WHERE project_id = ? AND sequence > ?
                    ORDER BY sequence""",
                    (project_id, cursors["decisions"]),
                ).fetchall()
            ]
        case = self.research_case_summary(project_id)
        changes = {
            "phase_events": phase_events,
            "execution_events": execution_events,
            "attempts": attempts,
            "decisions": decision_events,
        }
        packet = self.build_research_context_packet(
            project_id, kind="research_case", created_by=clean_actor, at=at
        )
        return {
            "brief_schema": "ResearchBriefV1",
            "case": case,
            "changes": changes,
            "next_action": case["next_action"],
            "packet_id": packet["packet_id"],
        }

    def research_gate_packet_inputs(
        self, project_id: str, *, ledger_limit: int = 10_000
    ) -> dict[str, object]:
        """Return canonical public inputs for a deterministic ResearchGatePacket renderer."""
        with self._transaction(write=False) as connection:
            return self._gate_packet_inputs(connection, project_id, ledger_limit=ledger_limit)

    def _gate_packet_inputs(
        self, connection: sqlite3.Connection, project_id: str, *, ledger_limit: int
    ) -> dict[str, object]:
        """Assemble the packet inputs on an existing connection (decision-transaction safe)."""
        if (
            isinstance(ledger_limit, bool)
            or not isinstance(ledger_limit, int)
            or not 1 <= ledger_limit <= 100_000
        ):
            raise DataError("research gate packet ledger_limit must be in 1..100000")
        project_row = self._require_project(connection, project_id)
        # Only the immutable research identity feeds packet content: mutable strategy-plane
        # fields (status, current version/experiment, updated_at) would silently change the
        # terminal packet identity after promotion, breaking recorded id/hash references.
        project: dict[str, object] = {
            "project_id": project_row["project_id"],
            "name": project_row["name"],
            "hypothesis": project_row["hypothesis"],
            "falsification_criterion": project_row["falsification_criterion"],
            "created_at": project_row["created_at"],
        }
        phase = self._latest_research_phase(connection, project_id)
        if phase is None:
            raise DataError(f"strategy project {project_id!r} has no research case")
        active = self._require_research_contract(connection, project_id, str(phase["contract_id"]))
        exploration_id = (
            str(active["parent_contract_id"])
            if active["scope"] == "confirmation"
            else str(active["contract_id"])
        )
        lineage_ids = [exploration_id]
        if active["scope"] == "confirmation":
            lineage_ids.append(str(active["contract_id"]))
        placeholders = ",".join("?" for _ in lineage_ids)

        contract_rows = [
            self._require_research_contract(connection, project_id, contract_id)
            for contract_id in lineage_ids
        ]
        contracts = [self._research_contract_view(connection, row) for row in contract_rows]
        pack_ids: set[str] = set()
        for contract in contracts:
            payload = contract["payload"]
            if isinstance(payload, dict) and isinstance(payload.get("source_pack_id"), str):
                pack_ids.add(str(payload["source_pack_id"]))
        pack_rows: list[sqlite3.Row] = []
        source_ids: set[str] = set()
        for pack_id in sorted(pack_ids):
            pack = connection.execute(
                """SELECT * FROM research_source_packs
                WHERE project_id = ? AND pack_id = ?""",
                (project_id, pack_id),
            ).fetchone()
            if pack is None:
                raise DataError("active research contract references a missing source pack")
            pack_rows.append(cast(sqlite3.Row, pack))
            ids = _decode_json(pack["source_ids_json"], "research source pack ids")
            if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
                raise DataError("corrupt research source pack ids")
            source_ids.update(cast(list[str], ids))
        source_rows: list[sqlite3.Row] = []
        for source_id in sorted(source_ids):
            source = connection.execute(
                """SELECT * FROM research_source_records
                WHERE project_id = ? AND source_id = ?""",
                (project_id, source_id),
            ).fetchone()
            if source is None:
                raise DataError("active research source pack references a missing source")
            source_rows.append(cast(sqlite3.Row, source))

        def bounded_rows(query: str, parameters: Sequence[object], label: str) -> list[sqlite3.Row]:
            rows = connection.execute(
                f"{query} LIMIT ?",  # noqa: S608 - static queries plus a bound limit.
                [*parameters, ledger_limit + 1],
            ).fetchall()
            if len(rows) > ledger_limit:
                raise DataError(f"research gate packet {label} exceeds ledger_limit={ledger_limit}")
            return [cast(sqlite3.Row, row) for row in rows]

        attempts = bounded_rows(
            f"""SELECT a.*, l.reservation_id AS launch_reservation_id
            FROM research_attempt_records AS a
            LEFT JOIN research_launch_attempt_links AS l ON l.attempt_id = a.attempt_id
            WHERE a.project_id = ? AND a.contract_id IN ({placeholders})
            ORDER BY a.recorded_at, a.attempt_id""",  # noqa: S608
            [project_id, *lineage_ids],
            "attempt ledger",
        )
        launch_reservations = bounded_rows(
            f"""SELECT * FROM research_launch_reservations
            WHERE project_id = ? AND contract_id IN ({placeholders})
            ORDER BY reserved_at, reservation_id""",  # noqa: S608
            [project_id, *lineage_ids],
            "launch reservation ledger",
        )
        launch_attempt_links = bounded_rows(
            f"""SELECT l.* FROM research_launch_attempt_links AS l
            JOIN research_launch_reservations AS r
                ON r.reservation_id = l.reservation_id
            WHERE r.project_id = ? AND r.contract_id IN ({placeholders})
            ORDER BY l.linked_at, l.reservation_id""",  # noqa: S608
            [project_id, *lineage_ids],
            "launch terminal-link ledger",
        )
        phase_events = bounded_rows(
            """SELECT * FROM research_phase_events
            WHERE project_id = ? ORDER BY sequence""",
            [project_id],
            "phase ledger",
        )
        review_events = bounded_rows(
            """SELECT * FROM research_contract_review_events
            WHERE project_id = ? ORDER BY occurred_at, contract_id, sequence""",
            [project_id],
            "review ledger",
        )
        execution_events = bounded_rows(
            """SELECT * FROM research_execution_events
            WHERE project_id = ? ORDER BY sequence""",
            [project_id],
            "execution ledger",
        )
        d2_events = bounded_rows(
            """SELECT * FROM research_d2_events
            WHERE project_id = ? ORDER BY sequence""",
            [project_id],
            "D2 ledger",
        )
        decision_events = bounded_rows(
            """SELECT * FROM research_decision_events
            WHERE project_id = ? ORDER BY sequence""",
            [project_id],
            "decision ledger",
        )

        contract_payloads: dict[str, dict[str, object]] = {}
        for contract in contracts:
            contract_id = contract.get("contract_id")
            payload = contract.get("payload")
            if not isinstance(contract_id, str) or not isinstance(payload, dict):
                raise DataError("corrupt research contract packet projection")
            contract_payloads[contract_id] = payload
        attempt_views: list[dict[str, object]] = []
        for attempt_row in attempts:
            attempt = self._research_attempt_view(attempt_row)
            attempt_contract_id = attempt.get("contract_id")
            payload = contract_payloads.get(str(attempt_contract_id))
            if payload is None:
                raise DataError("research attempt is outside the packet contract lineage")
            run_id = attempt.get("run_id")
            if isinstance(run_id, str):
                self._verify_research_attempt_run(
                    project_id=project_id,
                    attempt=attempt,
                    contract_payload=payload,
                )
            details = attempt.get("details")
            if not isinstance(details, dict):  # pragma: no cover - stored JSON invariant.
                raise DataError("corrupt research attempt details")
            if "gate_packet_evidence_ref" in details:
                if not isinstance(run_id, str):
                    raise DataError("research gate evidence selector has no immutable run")
                projected_details = dict(details)
                projected_details["gate_packet_evidence"] = self._read_research_gate_evidence(
                    run_id, details
                )
                attempt["details"] = projected_details
            attempt_views.append(attempt)

        return {
            "schema_version": 1,
            "project": project,
            "phase": phase["phase"],
            "active_contract_id": active["contract_id"],
            "lineage_contract_ids": lineage_ids,
            "contracts": contracts,
            "source_packs": [self._research_source_pack_view(row) for row in pack_rows],
            "sources": [self._research_source_view(row) for row in source_rows],
            "attempts": attempt_views,
            "launch_reservations": [
                self._research_reservation_view(row) for row in launch_reservations
            ],
            "launch_attempt_links": [dict(row) for row in launch_attempt_links],
            "phase_events": [dict(row) for row in phase_events],
            "review_events": [dict(row) for row in review_events],
            "execution_events": [dict(row) for row in execution_events],
            "d2_events": [dict(row) for row in d2_events],
            "decision_events": [dict(row) for row in decision_events],
        }

    def _contract_datasets(
        self, connection: sqlite3.Connection, contract_payload: Mapping[str, object]
    ) -> tuple[list[dict[str, object]], bool]:
        """Registered dataset refs for the contract's instrument, on this connection."""
        fingerprint = contract_payload.get("chart_fingerprint")
        instrument = fingerprint.get("instrument") if isinstance(fingerprint, Mapping) else None
        if not isinstance(instrument, str) or not instrument:
            return [], False
        try:
            clean_instrument = _symbols([instrument])[0]
        except DataError:
            # Synthetic fixture instruments are not registrable symbols; no datasets exist.
            return [], False
        rows = connection.execute(
            """SELECT * FROM research_dataset_refs WHERE instrument = ?
            ORDER BY registered_at DESC, ref_id LIMIT ?""",
            (clean_instrument, _RESEARCH_PACKET_COLLECTION_LIMIT + 1),
        ).fetchall()
        views: list[dict[str, object]] = []
        for row in rows[:_RESEARCH_PACKET_COLLECTION_LIMIT]:
            view = self._dataset_ref_view(row)
            audit = connection.execute(
                """SELECT * FROM research_dataset_audits WHERE ref_id = ?
                ORDER BY sequence DESC LIMIT 1""",
                (row["ref_id"],),
            ).fetchone()
            view["latest_audit"] = None if audit is None else self._dataset_audit_view(audit)
            views.append(view)
        return views, len(rows) > _RESEARCH_PACKET_COLLECTION_LIMIT

    def _screened_claims(
        self, connection: sqlite3.Connection, project_id: str
    ) -> tuple[list[dict[str, object]], bool]:
        """Latest-revision screened literature claims for one case, on this connection."""
        rows = connection.execute(
            """SELECT claims.* FROM research_source_claims AS claims
            JOIN (
                SELECT claim_id, MAX(revision) AS revision
                FROM research_source_claims WHERE project_id = ? GROUP BY claim_id
            ) AS latest
                ON latest.claim_id = claims.claim_id
                AND latest.revision = claims.revision
            WHERE claims.status = 'screened'
            ORDER BY claims.created_at, claims.claim_id LIMIT ?""",
            (project_id, _RESEARCH_PACKET_COLLECTION_LIMIT + 1),
        ).fetchall()
        views = [
            self._source_claim_with_anchor(connection, row)
            for row in rows[:_RESEARCH_PACKET_COLLECTION_LIMIT]
        ]
        return views, len(rows) > _RESEARCH_PACKET_COLLECTION_LIMIT

    def _verified_chart_references(
        self, attempts: Sequence[Mapping[str, object]]
    ) -> list[dict[str, object]]:
        """Exact content-addressed chart-data references from verified immutable runs."""
        references: list[dict[str, object]] = []
        seen: set[str] = set()
        for attempt in attempts:
            run_id = attempt.get("run_id")
            if not isinstance(run_id, str) or run_id in seen:
                continue
            seen.add(run_id)
            _, manifest = self._verified_run(run_id)
            artifacts = manifest.get("artifacts")
            metadata = artifacts.get("chart-data.json") if isinstance(artifacts, Mapping) else None
            sha256 = metadata.get("sha256") if isinstance(metadata, Mapping) else None
            if not isinstance(sha256, str):
                continue
            details = attempt.get("details")
            zone = details.get("evidence_zone") if isinstance(details, Mapping) else None
            references.append(
                {
                    "run_id": run_id,
                    "artifact": "chart-data.json",
                    "content_sha256": sha256,
                    "evidence_zone": zone if isinstance(zone, str) else None,
                }
            )
        return references

    def _record_strategy_promotion_packet(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        contract_id: str,
        decision: Mapping[str, object],
        actor: str,
        timestamp: str,
    ) -> str:
        """Record the lossless spec-§11 promotion dossier inside the decision transaction.

        The dossier binds the deterministic terminal gate packet (id + hash) computed from
        the exact post-decision ledgers on this connection, so an ``advance_to_strategy``
        decision and its complete research inheritance commit or roll back together.
        """
        from alpha_cli.research_gate_packet import build_strategy_promotion_payload
        from alpha_research import build_research_gate_packet

        inputs = self._gate_packet_inputs(connection, project_id, ledger_limit=10_000)
        gate_packet = build_research_gate_packet(inputs).to_dict()
        contracts = inputs.get("contracts")
        contract_payload: dict[str, object] | None = None
        for contract in contracts if isinstance(contracts, list) else []:
            if isinstance(contract, dict) and contract.get("contract_id") == contract_id:
                payload = contract.get("payload")
                if isinstance(payload, dict):
                    contract_payload = payload
        if contract_payload is None:
            raise DataError("strategy promotion requires the decided contract payload")
        datasets, datasets_truncated = self._contract_datasets(connection, contract_payload)
        claims, claims_truncated = self._screened_claims(connection, project_id)
        attempts = inputs.get("attempts")
        chart_references = self._verified_chart_references(
            [attempt for attempt in attempts if isinstance(attempt, Mapping)]
            if isinstance(attempts, list)
            else []
        )
        project = inputs.get("project")
        payload_out = build_strategy_promotion_payload(
            project=project if isinstance(project, Mapping) else {},
            decision=decision,
            contract_payload=contract_payload,
            gate_packet=gate_packet,
            datasets=datasets,
            datasets_truncated=datasets_truncated,
            claims=claims,
            claims_truncated=claims_truncated,
            chart_references=chart_references,
        )
        packet_id = _content_id("cp", payload_out)
        existing = connection.execute(
            "SELECT packet_id FROM research_context_packets WHERE packet_id = ?",
            (packet_id,),
        ).fetchone()
        if existing is None:
            connection.execute(
                """INSERT INTO research_context_packets (
                    packet_id, project_id, packet_kind, protocol_id, protocol_content_hash,
                    payload_json, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    packet_id,
                    project_id,
                    "strategy_promotion",
                    None,
                    None,
                    _canonical_json(payload_out, "strategy promotion packet payload"),
                    actor,
                    timestamp,
                ),
            )
        return packet_id

    def _promotion_reference(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        contract_id: str,
        cutoff: str | None,
    ) -> dict[str, object] | None:
        """Resolve the recorded promotion dossier for one linked contract at the cutoff."""
        params: list[object] = [project_id]
        time_filter = ""
        if cutoff is not None:
            time_filter = " AND created_at <= ?"
            params.append(cutoff)
        rows = connection.execute(
            """SELECT packet_id, payload_json, created_at FROM research_context_packets
            WHERE project_id = ? AND packet_kind = 'strategy_promotion'"""
            + time_filter
            + " ORDER BY created_at, packet_id",
            params,
        ).fetchall()
        for row in rows:
            payload = _decode_json(row["payload_json"], "strategy promotion packet payload")
            if not isinstance(payload, dict):
                raise DataError("corrupt strategy promotion packet payload")
            if payload.get("packet_schema") != "StrategyPromotionPacketV1":
                # Codex-built review packets share the kind but are not the dossier.
                continue
            decision = payload.get("decision")
            if not isinstance(decision, Mapping) or decision.get("contract_id") != contract_id:
                continue
            reference = payload.get("gate_packet_reference")
            gate = reference if isinstance(reference, Mapping) else {}
            return {
                "packet_id": str(row["packet_id"]),
                "contract_id": contract_id,
                "gate_packet_id": gate.get("packet_id"),
                "gate_packet_hash": gate.get("packet_hash"),
                "recorded_at": str(row["created_at"]),
            }
        return None

    def get_agent_brief_context(
        self,
        project_id: str,
        *,
        as_of: datetime | None = None,
        evidence_limit: int | None = None,
    ) -> dict[str, object]:
        """Return the project scope and stage lineage that existed at ``as_of``.

        The mutable current pointers are not trusted for historical reads.  Selection events and
        stage/link event timestamps are filtered inside one SQLite snapshot so a later holdout run,
        reveal, contamination, or strategy selection cannot enter an earlier AgentBrief.
        """
        cutoff = None if as_of is None else _format_timestamp(as_of)
        if evidence_limit is not None:
            evidence_limit, _ = _page(evidence_limit, 0)
        with self._transaction(write=False) as connection:
            project = dict(self._require_project(connection, project_id))
            created_at = project.get("created_at")
            if cutoff is not None and (not isinstance(created_at, str) or created_at > cutoff):
                raise DataError(f"strategy project {project_id!r} did not exist at the cutoff")

            scope_history_complete = True
            if cutoff is None:
                version_id = cast(str | None, project["current_version_id"])
                experiment_id = cast(str | None, project["current_experiment_id"])
            else:
                scope_event = connection.execute(
                    """SELECT current_version_id, current_experiment_id
                    FROM project_scope_events
                    WHERE project_id = ? AND occurred_at <= ?
                    ORDER BY occurred_at DESC, sequence DESC LIMIT 1""",
                    (project_id, cutoff),
                ).fetchone()
                if scope_event is None:
                    # Fail closed for a database created before scope events existed.  Current
                    # pointers are safe only when the cutoff is at/after their last mutation.
                    updated_at = project.get("updated_at")
                    if isinstance(updated_at, str) and updated_at <= cutoff:
                        version_id = cast(str | None, project["current_version_id"])
                        experiment_id = cast(str | None, project["current_experiment_id"])
                    else:
                        version_id = None
                        experiment_id = None
                    scope_history_complete = False
                else:
                    version_id = cast(str | None, scope_event["current_version_id"])
                    experiment_id = cast(str | None, scope_event["current_experiment_id"])

            version_row = (
                None
                if version_id is None
                else connection.execute(
                    "SELECT * FROM strategy_versions WHERE version_id = ?",
                    (version_id,),
                ).fetchone()
            )
            experiment_row = (
                None
                if experiment_id is None
                else connection.execute(
                    "SELECT * FROM experiment_specs WHERE experiment_id = ?",
                    (experiment_id,),
                ).fetchone()
            )
            if version_id is not None and version_row is None:
                raise DataError("corrupt control store: selected strategy version is missing")
            if experiment_id is not None and experiment_row is None:
                raise DataError("corrupt control store: selected experiment is missing")
            version_view = None if version_row is None else self._version_view(version_row)
            research_promotion: dict[str, object] | None = None
            if version_view is not None and version_id is not None:
                version_link_params: list[object] = [project_id, version_id]
                time_filter = ""
                if cutoff is not None:
                    time_filter = " AND linked_at <= ?"
                    version_link_params.append(cutoff)
                research_link = connection.execute(
                    """SELECT contract_id FROM research_contract_strategy_links
                    WHERE project_id = ? AND version_id = ?"""
                    + time_filter,
                    version_link_params,
                ).fetchone()
                if research_link is not None:
                    version_view["research_contract_id"] = research_link["contract_id"]
                    research_promotion = self._promotion_reference(
                        connection,
                        project_id=project_id,
                        contract_id=str(research_link["contract_id"]),
                        cutoff=cutoff,
                    )
            experiment_view = (
                None if experiment_row is None else self._experiment_view(experiment_row)
            )
            if experiment_view is not None and experiment_id is not None:
                experiment_link_params: list[object] = [project_id, experiment_id]
                time_filter = ""
                if cutoff is not None:
                    time_filter = " AND linked_at <= ?"
                    experiment_link_params.append(cutoff)
                research_link = connection.execute(
                    """SELECT contract_id FROM research_contract_experiment_links
                    WHERE project_id = ? AND experiment_id = ?"""
                    + time_filter,
                    experiment_link_params,
                ).fetchone()
                if research_link is not None:
                    experiment_view["research_contract_id"] = research_link["contract_id"]

            stages: dict[str, dict[str, object]] = {}
            holdout_events: list[dict[str, object]] = []
            if experiment_id is not None:
                for stage in DEVELOPMENT_STAGE_ORDER:
                    params: list[object] = [project_id, experiment_id, stage]
                    timestamp_filter = ""
                    if cutoff is not None:
                        timestamp_filter = " AND occurred_at <= ?"
                        params.append(cutoff)
                    event = connection.execute(
                        """SELECT sequence, state, occurred_at FROM experiment_stage_events
                        WHERE project_id = ? AND experiment_id = ? AND stage = ?"""
                        + timestamp_filter
                        + " ORDER BY sequence DESC LIMIT 1",
                        params,
                    ).fetchone()
                    if event is not None:
                        stages[stage] = {
                            "stage": stage,
                            "state": event["state"],
                            "run_id": None,
                        }

                link_params: list[object] = [project_id, experiment_id]
                link_filter = ""
                if cutoff is not None:
                    link_filter = " AND linked_at <= ?"
                    link_params.append(cutoff)
                links = connection.execute(
                    """SELECT * FROM stage_run_links
                    WHERE project_id = ? AND experiment_id = ?"""
                    + link_filter
                    + " ORDER BY linked_at, link_id",
                    link_params,
                ).fetchall()
                for link in links:
                    state_params: list[object] = [link["link_id"]]
                    state_filter = ""
                    if cutoff is not None:
                        state_filter = " AND occurred_at <= ?"
                        state_params.append(cutoff)
                    state = connection.execute(
                        """SELECT sequence, state, occurred_at FROM stage_state_events
                        WHERE link_id = ?"""
                        + state_filter
                        + " ORDER BY sequence DESC LIMIT 1",
                        state_params,
                    ).fetchone()
                    if state is None:
                        continue
                    stage = str(link["stage"])
                    authoritative = stages.get(stage)
                    # Experiment-stage events are the lifecycle authority.  A run link may
                    # identify the run that produced that state, but an older link must never
                    # overwrite a newer transition from another link or from the suite.
                    if authoritative is not None and state["state"] == authoritative["state"]:
                        linked_at = str(state["occurred_at"])
                        selected_at = authoritative.get("_run_state_at")
                        selected_id = authoritative.get("_run_link_id")
                        if selected_at is None or (linked_at, str(link["link_id"])) > (
                            str(selected_at),
                            str(selected_id),
                        ):
                            authoritative["run_id"] = link["run_id"]
                            authoritative["_run_state_at"] = linked_at
                            authoritative["_run_link_id"] = link["link_id"]

                audit_params: list[object] = [project_id, experiment_id]
                audit_filter = ""
                if cutoff is not None:
                    audit_filter = " AND occurred_at <= ?"
                    audit_params.append(cutoff)
                holdout_events = [
                    dict(row)
                    for row in connection.execute(
                        """SELECT event, occurred_at FROM holdout_audit
                        WHERE project_id = ? AND experiment_id = ?"""
                        + audit_filter
                        + " ORDER BY audit_id",
                        audit_params,
                    ).fetchall()
                ]

            evidence: list[dict[str, object]] | None = None
            if evidence_limit is not None:
                evidence_where = "WHERE project_id = ?"
                evidence_params: list[object] = [project_id]
                if cutoff is not None:
                    evidence_where += " AND knowledge_at <= ? AND created_at <= ?"
                    evidence_params.extend([cutoff, cutoff])
                evidence_params.append(evidence_limit)
                evidence_rows = connection.execute(
                    f"""WITH ranked AS (
                        SELECT *, ROW_NUMBER() OVER (
                            PARTITION BY evidence_id ORDER BY revision DESC
                        ) AS rank FROM evidence_revisions {evidence_where}
                    ) SELECT * FROM ranked WHERE rank = 1
                    ORDER BY created_at DESC, evidence_id LIMIT ?""",  # noqa: S608
                    evidence_params,
                ).fetchall()
                evidence = []
                for row in evidence_rows:
                    view = self._evidence_view(row)
                    view.pop("rank", None)
                    evidence.append(view)

            for stage_view in stages.values():
                stage_view.pop("_run_state_at", None)
                stage_view.pop("_run_link_id", None)

        return {
            "project_id": project["project_id"],
            "project_name": project["name"],
            "hypothesis": project["hypothesis"],
            "falsification_criterion": project["falsification_criterion"],
            "version_id": version_id,
            "experiment_id": experiment_id,
            "strategy_version": version_view,
            "experiment": experiment_view,
            "stage_statuses": [stages[name] for name in sorted(stages)],
            "holdout_events": holdout_events,
            "scope_history_complete": scope_history_complete,
            "evidence": evidence,
            "research_promotion": research_promotion,
        }

    @staticmethod
    def _version_view(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["definition"] = _decode_json(result.pop("definition_json"), "strategy definition")
        result["parameter_space"] = _decode_json(
            result.pop("parameter_space_json"), "parameter space"
        )
        return result

    @staticmethod
    def _experiment_view(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        for stored, public in (
            ("universe_json", "universe"),
            ("split_policy_json", "split_policy"),
            ("costs_json", "costs"),
            ("seeds_json", "seeds"),
            ("stage_config_json", "stage_config"),
        ):
            result[public] = _decode_json(result.pop(stored), public)
        return result

    @staticmethod
    def _attempt_view(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["details"] = _decode_json(result.pop("details_json"), "attempt details")
        return result

    @staticmethod
    def _stage_link_view(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        events = connection.execute(
            """SELECT sequence, state, occurred_at, reason FROM stage_state_events
            WHERE link_id = ? ORDER BY sequence""",
            (row["link_id"],),
        ).fetchall()
        if not events:
            raise DataError(f"corrupt control store: stage link {row['link_id']!r} has no events")
        result["state"] = events[-1]["state"]
        result["state_history"] = [dict(event) for event in events]
        return result

    @staticmethod
    def _experiment_stage_view(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
        stage: str,
    ) -> dict[str, object]:
        events = connection.execute(
            """SELECT sequence, state, occurred_at, reason FROM experiment_stage_events
            WHERE project_id = ? AND experiment_id = ? AND stage = ? ORDER BY sequence""",
            (project_id, experiment_id, stage),
        ).fetchall()
        if not events:
            raise DataError(
                f"corrupt control store: experiment {experiment_id!r} stage {stage!r} has no events"
            )
        return {
            "project_id": project_id,
            "experiment_id": experiment_id,
            "stage": stage,
            "state": events[-1]["state"],
            "state_history": [dict(event) for event in events],
        }

    @staticmethod
    def _latest_experiment_stage_state(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
        stage: str,
    ) -> str:
        row = connection.execute(
            """SELECT state FROM experiment_stage_events
            WHERE project_id = ? AND experiment_id = ? AND stage = ?
            ORDER BY sequence DESC LIMIT 1""",
            (project_id, experiment_id, stage),
        ).fetchone()
        if row is None:
            raise DataError(f"unknown experiment stage {experiment_id!r}/{stage!r}")
        return str(row["state"])

    @staticmethod
    def _initialize_experiment_stages(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
        at: str,
    ) -> None:
        for stage in DEVELOPMENT_STAGE_ORDER:
            if stage in {"hypothesis", "data", "strategy"}:
                state = "pass"
                reason = "immutable experiment specification created"
            elif stage == "baseline":
                state = "ready"
                reason = "immutable experiment specification is ready for baseline"
            else:
                state = "not_started"
                reason = "awaiting prerequisite stages"
            connection.execute(
                """INSERT OR IGNORE INTO experiment_stage_events
                (project_id, experiment_id, stage, sequence, state, occurred_at, reason)
                VALUES (?, ?, ?, 1, ?, ?, ?)""",
                (project_id, experiment_id, stage, state, at, reason),
            )

    @staticmethod
    def _append_experiment_stage_event(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
        stage: str,
        state: str,
        reason: str,
        at: str,
        enforce_transition: bool,
    ) -> None:
        prior = connection.execute(
            """SELECT sequence, state, occurred_at FROM experiment_stage_events
            WHERE project_id = ? AND experiment_id = ? AND stage = ?
            ORDER BY sequence DESC LIMIT 1""",
            (project_id, experiment_id, stage),
        ).fetchone()
        if prior is None:
            raise DataError(f"unknown experiment stage {experiment_id!r}/{stage!r}")
        prior_state = str(prior["state"])
        if state == prior_state:
            return
        if enforce_transition and state not in _STAGE_TRANSITIONS[prior_state]:
            raise DataError(f"invalid stage transition {prior_state!r} -> {state!r}")
        if not isinstance(prior["occurred_at"], str) or at < prior["occurred_at"]:
            raise DataError("stage state timestamp precedes prior event")
        connection.execute(
            """INSERT INTO experiment_stage_events
            (project_id, experiment_id, stage, sequence, state, occurred_at, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                experiment_id,
                stage,
                int(prior["sequence"]) + 1,
                state,
                at,
                reason,
            ),
        )

    @staticmethod
    def _mark_stage_links_stale(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        reason: str,
        at: str,
        except_experiment_id: str | None = None,
    ) -> None:
        query = """SELECT l.link_id FROM stage_run_links l
            WHERE l.project_id = ? AND NOT EXISTS (
                SELECT 1 FROM stage_state_events e
                WHERE e.link_id = l.link_id AND e.state = 'stale'
            )"""
        params: list[object] = [project_id]
        if except_experiment_id is not None:
            query += " AND l.experiment_id != ?"
            params.append(except_experiment_id)
        for row in connection.execute(query, params).fetchall():
            state_row = connection.execute(
                """SELECT sequence, occurred_at FROM stage_state_events
                WHERE link_id = ? ORDER BY sequence DESC LIMIT 1""",
                (row["link_id"],),
            ).fetchone()
            if state_row is None:
                raise DataError("corrupt control store: stage link has no initial state")
            if not isinstance(state_row["occurred_at"], str) or at < state_row["occurred_at"]:
                raise DataError("stage stale timestamp precedes prior state event")
            connection.execute(
                "INSERT INTO stage_state_events VALUES (?, ?, 'stale', ?, ?)",
                (row["link_id"], int(state_row["sequence"]) + 1, at, reason),
            )
        stage_query = """SELECT project_id, experiment_id, stage, state FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY project_id, experiment_id, stage ORDER BY sequence DESC
            ) AS rank
            FROM experiment_stage_events WHERE project_id = ?
        ) WHERE rank = 1 AND state != 'stale'"""
        stage_params: list[object] = [project_id]
        if except_experiment_id is not None:
            stage_query += " AND experiment_id != ?"
            stage_params.append(except_experiment_id)
        for row in connection.execute(stage_query, stage_params).fetchall():
            ControlStore._append_experiment_stage_event(
                connection,
                project_id=str(row["project_id"]),
                experiment_id=str(row["experiment_id"]),
                stage=str(row["stage"]),
                state="stale",
                reason=reason,
                at=at,
                enforce_transition=True,
            )

    def _contaminate_revealed_holdouts(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        version_id: str,
        experiment_id: str | None,
        reason: str,
        at: str,
    ) -> None:
        rows = connection.execute(
            """SELECT * FROM holdout_state
            WHERE project_id = ? AND revealed_at IS NOT NULL AND contaminated_at IS NULL""",
            (project_id,),
        ).fetchall()
        for row in rows:
            changed = row["revealed_version_id"] != version_id
            if experiment_id is not None:
                changed = changed or row["experiment_id"] != experiment_id
            if not changed:
                continue
            revealed_at = row["revealed_at"]
            if not isinstance(revealed_at, str) or at < revealed_at:
                raise DataError("holdout contamination timestamp precedes reveal")
            connection.execute(
                """UPDATE holdout_state
                SET contaminated_at = ?, contamination_reason = ?
                WHERE project_id = ? AND experiment_id = ? AND contaminated_at IS NULL""",
                (at, reason, project_id, row["experiment_id"]),
            )
            connection.execute(
                """INSERT INTO holdout_audit (
                    project_id, experiment_id, event, actor, occurred_at, reason, version_id
                ) VALUES (?, ?, 'contaminated', 'system', ?, ?, ?)""",
                (project_id, row["experiment_id"], at, reason, version_id),
            )

    def create_strategy_version(
        self,
        project_id: str,
        *,
        strategy_name: str,
        source_fingerprint: str,
        definition: Mapping[str, object],
        parameter_space: Mapping[str, object],
        research_contract_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Link an immutable, content-addressed strategy version to a project."""
        clean_definition = _json_object(definition, "strategy definition")
        clean_space = _json_object(parameter_space, "parameter space")
        clean_contract_id = (
            None
            if research_contract_id is None
            else _require_content_id(
                research_contract_id, "strategy research_contract_id", prefix="rc"
            )
        )
        identity: dict[str, object] = {
            "schema_version": 1 if clean_contract_id is None else 2,
            "strategy_name": _required_text(strategy_name, "strategy name", max_length=100),
            "source_fingerprint": _required_text(
                source_fingerprint, "source fingerprint", max_length=512
            ),
            "definition": clean_definition,
            "parameter_space": clean_space,
        }
        if clean_contract_id is not None:
            identity["research_contract_id"] = clean_contract_id
        version_id = _content_id("sv", identity)
        timestamp = _at(at)
        definition_json = _canonical_json(clean_definition, "strategy definition")
        parameter_space_json = _canonical_json(clean_space, "parameter space")
        with self._transaction(write=True) as connection:
            project = self._require_project(connection, project_id)
            gate_state = self._research_gate_state(connection, project_id)
            # An explicit owner override (spec §15) is the only unlinked path through a
            # governed gate; runs under it stay watermarked EXPLORATORY, and a later pass
            # re-locks the gate so promoted work must carry its research linkage.
            if clean_contract_id is None and gate_state not in ("not_required", "overridden"):
                raise DataError(
                    "research-governed project strategy versions require research_contract_id"
                )
            if clean_contract_id is not None:
                contract = self._require_research_contract(
                    connection, project_id, clean_contract_id
                )
                review = self._latest_research_review(connection, clean_contract_id)
                decision = connection.execute(
                    """SELECT disposition FROM research_decision_events
                    WHERE project_id = ? AND contract_id = ?""",
                    (project_id, clean_contract_id),
                ).fetchone()
                if (
                    contract["scope"] != "confirmation"
                    or _research_review_state(review) != "approved"
                    or decision is None
                    or decision["disposition"] != "advance_to_strategy"
                ):
                    raise DataError(
                        "strategy linkage requires the approved confirmation contract and "
                        "owner advance_to_strategy decision"
                    )
            existing = connection.execute(
                "SELECT * FROM strategy_versions WHERE version_id = ?", (version_id,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """INSERT INTO strategy_versions (
                        version_id, strategy_name, source_fingerprint, definition_json,
                        parameter_space_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        version_id,
                        identity["strategy_name"],
                        identity["source_fingerprint"],
                        definition_json,
                        parameter_space_json,
                        timestamp,
                    ),
                )
            connection.execute(
                "INSERT OR IGNORE INTO project_versions VALUES (?, ?, ?)",
                (project_id, version_id, timestamp),
            )
            if clean_contract_id is not None:
                connection.execute(
                    """INSERT OR IGNORE INTO research_contract_strategy_links
                    (project_id, version_id, contract_id, linked_at) VALUES (?, ?, ?, ?)""",
                    (project_id, version_id, clean_contract_id, timestamp),
                )
            if project["current_version_id"] != version_id:
                self._mark_stage_links_stale(
                    connection,
                    project_id=project_id,
                    reason="strategy version changed",
                    at=timestamp,
                )
                self._contaminate_revealed_holdouts(
                    connection,
                    project_id=project_id,
                    version_id=version_id,
                    experiment_id=None,
                    reason="strategy version changed after holdout reveal",
                    at=timestamp,
                )
                connection.execute(
                    """UPDATE projects SET current_version_id = ?, updated_at = ?
                    WHERE project_id = ?""",
                    (version_id, timestamp, project_id),
                )
                self._append_project_scope_event(
                    connection,
                    project_id=project_id,
                    version_id=version_id,
                    experiment_id=cast(str | None, project["current_experiment_id"]),
                    at=timestamp,
                    reason="strategy version selected",
                )
            row = connection.execute(
                "SELECT * FROM strategy_versions WHERE version_id = ?", (version_id,)
            ).fetchone()
        if row is None:  # pragma: no cover - guarded by the insert/select transaction.
            raise DataError("control store failed to persist strategy version")
        view = self._version_view(row)
        if clean_contract_id is not None:
            view["research_contract_id"] = clean_contract_id
        return view

    def create_experiment_spec(
        self,
        project_id: str,
        *,
        strategy_version_id: str,
        snapshot_id: str,
        universe: Sequence[str],
        split_policy: Mapping[str, object],
        costs: Mapping[str, object],
        seeds: Mapping[str, object],
        stage_config: Mapping[str, object] | None = None,
        research_contract_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Link an immutable, content-addressed experiment specification to a project."""
        version_id = _require_content_id(strategy_version_id, "strategy_version_id", prefix="sv")
        clean_universe = _symbols(universe)
        clean_split = _json_object(split_policy, "split policy")
        clean_costs = _json_object(costs, "costs")
        clean_seeds = _json_object(seeds, "seeds")
        clean_stage = _json_object(stage_config or {}, "stage config")
        market_state_value = clean_stage.get("market_state")
        if market_state_value is not None:
            from alpha_research import MarketStateContractV1

            if not isinstance(market_state_value, Mapping):
                raise DataError("invalid experiment market-state contract: expected an object")
            try:
                market_state = MarketStateContractV1.from_dict(market_state_value)
            except DataError as exc:
                raise DataError(f"invalid experiment market-state contract: {exc}") from exc
            if list(market_state.universe) != clean_universe:
                raise DataError(
                    "invalid experiment market-state universe: must equal the experiment universe"
                )
            clean_stage["market_state"] = market_state.to_dict()
        calibration_value = clean_stage.get("kronos_calibration")
        if calibration_value is not None:
            from alpha_validation import ForecastCalibrationContractV1

            if market_state_value is None:
                raise DataError("kronos_calibration requires a frozen market_state contract")
            if not isinstance(calibration_value, Mapping):
                raise DataError(
                    "invalid experiment kronos_calibration contract: expected an object"
                )
            try:
                calibration = ForecastCalibrationContractV1.from_dict(calibration_value)
            except DataError as exc:
                raise DataError(f"invalid experiment kronos_calibration contract: {exc}") from exc
            clean_stage["kronos_calibration"] = calibration.to_dict()
        clean_contract_id = (
            None
            if research_contract_id is None
            else _require_content_id(
                research_contract_id, "experiment research_contract_id", prefix="rc"
            )
        )
        identity: dict[str, object] = {
            "schema_version": 1 if clean_contract_id is None else 2,
            "strategy_version_id": version_id,
            "snapshot_id": _required_text(snapshot_id, "snapshot_id", max_length=200),
            "universe": clean_universe,
            "split_policy": clean_split,
            "costs": clean_costs,
            "seeds": clean_seeds,
            "stage_config": clean_stage,
        }
        if clean_contract_id is not None:
            identity["research_contract_id"] = clean_contract_id
        experiment_id = _content_id("ex", identity)
        timestamp = _at(at)
        stored = (
            experiment_id,
            version_id,
            identity["snapshot_id"],
            _canonical_json(clean_universe, "universe"),
            _canonical_json(clean_split, "split policy"),
            _canonical_json(clean_costs, "costs"),
            _canonical_json(clean_seeds, "seeds"),
            _canonical_json(clean_stage, "stage config"),
            timestamp,
        )
        with self._transaction(write=True) as connection:
            project = self._require_project(connection, project_id)
            linked = connection.execute(
                "SELECT 1 FROM project_versions WHERE project_id = ? AND version_id = ?",
                (project_id, version_id),
            ).fetchone()
            if linked is None:
                raise DataError(
                    f"strategy version {version_id!r} is not linked to project {project_id!r}"
                )
            strategy_contract = connection.execute(
                """SELECT contract_id FROM research_contract_strategy_links
                WHERE project_id = ? AND version_id = ?""",
                (project_id, version_id),
            ).fetchone()
            linked_contract_id = (
                None if strategy_contract is None else str(strategy_contract["contract_id"])
            )
            if linked_contract_id != clean_contract_id:
                raise DataError(
                    "research-governed experiment requires the matching research_contract_id"
                )
            connection.execute(
                """INSERT OR IGNORE INTO experiment_specs (
                    experiment_id, strategy_version_id, snapshot_id, universe_json,
                    split_policy_json, costs_json, seeds_json, stage_config_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                stored,
            )
            connection.execute(
                "INSERT OR IGNORE INTO project_experiments VALUES (?, ?, ?)",
                (project_id, experiment_id, timestamp),
            )
            if clean_contract_id is not None:
                connection.execute(
                    """INSERT OR IGNORE INTO research_contract_experiment_links
                    (project_id, experiment_id, contract_id, linked_at) VALUES (?, ?, ?, ?)""",
                    (project_id, experiment_id, clean_contract_id, timestamp),
                )
            self._initialize_experiment_stages(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                at=timestamp,
            )
            if project["current_experiment_id"] != experiment_id:
                self._mark_stage_links_stale(
                    connection,
                    project_id=project_id,
                    reason="experiment specification changed",
                    at=timestamp,
                    except_experiment_id=experiment_id,
                )
                self._contaminate_revealed_holdouts(
                    connection,
                    project_id=project_id,
                    version_id=version_id,
                    experiment_id=experiment_id,
                    reason="experiment specification changed after holdout reveal",
                    at=timestamp,
                )
                connection.execute(
                    """UPDATE projects SET current_version_id = ?, current_experiment_id = ?,
                    updated_at = ? WHERE project_id = ?""",
                    (version_id, experiment_id, timestamp, project_id),
                )
                self._append_project_scope_event(
                    connection,
                    project_id=project_id,
                    version_id=version_id,
                    experiment_id=experiment_id,
                    at=timestamp,
                    reason="experiment specification selected",
                )
            row = connection.execute(
                "SELECT * FROM experiment_specs WHERE experiment_id = ?", (experiment_id,)
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist experiment specification")
        view = self._experiment_view(row)
        if clean_contract_id is not None:
            view["research_contract_id"] = clean_contract_id
        return view

    def link_stage_run(
        self,
        project_id: str,
        experiment_id: str,
        *,
        stage: str,
        state: StageState,
        run_id: str,
        link_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Link a run without granting a terminal gate outcome.

        Terminal pass/warning/fail links are reserved for :meth:`link_suite_stage_run`, which
        verifies the immutable suite result before recording it.
        """
        return self._link_stage_run(
            project_id,
            experiment_id,
            stage=stage,
            state=state,
            run_id=run_id,
            suite_action=None,
            link_id=link_id,
            at=at,
        )

    def link_suite_stage_run(
        self,
        project_id: str,
        experiment_id: str,
        *,
        suite_action: str,
        stage: str,
        state: StageState,
        run_id: str,
        link_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Link one terminal run result produced by an allowlisted canonical suite action."""
        return self._link_stage_run(
            project_id,
            experiment_id,
            stage=stage,
            state=state,
            run_id=run_id,
            suite_action=suite_action,
            link_id=link_id,
            at=at,
        )

    def _link_stage_run(
        self,
        project_id: str,
        experiment_id: str,
        *,
        stage: str,
        state: StageState,
        run_id: str,
        suite_action: str | None,
        link_id: str | None,
        at: datetime | None,
    ) -> dict[str, object]:
        clean_stage = _required_text(stage, "development stage", max_length=32)
        if clean_stage not in DEVELOPMENT_STAGES:
            raise DataError(f"unsupported development stage {stage!r}")
        clean_state = _required_text(state, "stage state", max_length=16)
        if clean_state not in STAGE_STATES:
            raise DataError(f"unsupported stage state {state!r}")
        if suite_action is None and clean_state in _TERMINAL_STAGE_STATES:
            raise DataError(
                "terminal stage links are suite-owned; launch the resolved development suite"
            )
        if suite_action is not None and clean_state not in _TERMINAL_STAGE_STATES:
            raise DataError("suite stage links require pass, warning, or fail")
        _, manifest = self._verified_run(run_id)
        if suite_action is not None:
            expected = _SUITE_ACTION_STAGE_COMMANDS.get(suite_action)
            if expected is None:
                raise DataError(f"suite action {suite_action!r} does not publish canonical runs")
            expected_stage, commands = expected
            if clean_stage != expected_stage:
                raise DataError(
                    f"suite action {suite_action!r} belongs to stage {expected_stage!r}, "
                    f"not {clean_stage!r}"
                )
            if manifest.get("schema_version") != 3:
                raise DataError("terminal suite evidence requires a verified v3 run")
            if manifest.get("command") not in commands:
                raise DataError(
                    f"suite action {suite_action!r} cannot cite command {manifest.get('command')!r}"
                )
        lid = _new_uuid(link_id, "link_id")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            if suite_action is not None:
                experiment = connection.execute(
                    "SELECT snapshot_id FROM experiment_specs WHERE experiment_id = ?",
                    (experiment_id,),
                ).fetchone()
                if experiment is None:  # pragma: no cover - project link proves it exists.
                    raise DataError(f"unknown experiment {experiment_id!r}")
                expected_snapshot = str(experiment["snapshot_id"])
                run_snapshot = manifest.get("snapshot_id")
                if run_snapshot is not None and run_snapshot != expected_snapshot:
                    raise DataError(
                        f"suite result uses snapshot {run_snapshot!r}, "
                        f"expected {expected_snapshot!r}"
                    )
                from alpha_cli._runner import verified_snapshot_hash

                expected_hash = verified_snapshot_hash(self._data_dir, expected_snapshot)
                if manifest.get("snapshot_hash") != expected_hash:
                    raise DataError("suite result snapshot hash does not match the experiment")
                candidate = connection.execute(
                    """SELECT v.strategy_name, l.contract_id
                    FROM experiment_specs e
                    JOIN strategy_versions v ON v.version_id = e.strategy_version_id
                    LEFT JOIN research_contract_strategy_links l
                      ON l.project_id = ? AND l.version_id = v.version_id
                    WHERE e.experiment_id = ?""",
                    (project_id, experiment_id),
                ).fetchone()
                candidate_strategy = (
                    candidate is not None
                    and candidate["strategy_name"] == "hedged_basis_crowding_v1"
                )
                candidate_command = manifest.get("command") in _CANDIDATE_EVIDENCE_COMMANDS
                if candidate_strategy != candidate_command:
                    raise DataError(
                        "suite evidence command family does not match the registered strategy"
                    )
                if candidate_command:
                    inheritance = manifest.get("research_inheritance")
                    if (
                        candidate is None  # static narrowing; query is required above.
                        or candidate["contract_id"] is None
                        or not isinstance(inheritance, Mapping)
                        or inheritance.get("contract_id") != candidate["contract_id"]
                        or manifest.get("deployment_scope") != "sandbox_only"
                        or manifest.get("places_orders") is not False
                        or manifest.get("paper_eligible") is not False
                    ):
                        raise DataError(
                            "candidate suite evidence does not preserve its promoted research "
                            "inheritance and sandbox boundary"
                        )
                if suite_action in {
                    "baseline",
                    "inner_oos",
                    "three_null_families",
                    "monte_carlo",
                    "optimize_grid",
                    "portfolio_cross_asset",
                    "qlib",
                    "kronos",
                }:
                    holdout = self._require_pre_reveal_holdout(
                        connection, project_id, experiment_id
                    )
                    expected_cutoff = self._manifest_research_cutoff(holdout)
                    if manifest.get("research_cutoff") != expected_cutoff:
                        raise DataError(
                            "suite result does not match the sealed pre-holdout research cutoff"
                        )
                if suite_action in {"optimize_grid", "holdout_reveal"}:
                    verdict = manifest.get("passed")
                    if clean_state == "pass" and verdict is not True:
                        raise DataError("suite pass state does not match the canonical run verdict")
                    if clean_state == "fail" and verdict is not False:
                        raise DataError("suite fail state does not match the canonical run verdict")
                if suite_action == "holdout_reveal":
                    holdout = connection.execute(
                        """SELECT revealed_at, contaminated_at FROM holdout_state
                        WHERE project_id = ? AND experiment_id = ?""",
                        (project_id, experiment_id),
                    ).fetchone()
                    if holdout is None or holdout["revealed_at"] is None:
                        raise DataError("holdout run evidence requires the audited one-shot reveal")
                    if holdout["contaminated_at"] is not None:
                        raise DataError("contaminated holdout evidence cannot complete the gate")
                    sealed = connection.execute(
                        """SELECT spec_hash FROM holdout_specs
                        WHERE project_id = ? AND experiment_id = ?""",
                        (project_id, experiment_id),
                    ).fetchone()
                    if sealed is None or manifest.get("holdout_spec_hash") != sealed["spec_hash"]:
                        raise DataError("holdout run does not match the dated sealed window")
                if suite_action == "three_null_families":
                    metadata = manifest.get("metadata")
                    null_model = (
                        metadata.get("null_model") if isinstance(metadata, Mapping) else None
                    )
                    if clean_state == "pass" and (
                        null_model != "bootstrap" or manifest.get("passed") is not True
                    ):
                        raise DataError(
                            "robustness pass requires the passing stationary-bootstrap headline run"
                        )
                    if clean_state == "warning" and null_model not in {"student_t", "garch"}:
                        raise DataError(
                            "robustness warning links are reserved for Student-t/GARCH sensitivity"
                        )
                if suite_action == "monte_carlo":
                    run_status = manifest.get("status")
                    if clean_state == "pass" and run_status != "clear":
                        raise DataError("Monte Carlo pass link requires a clear family run")
                    if clean_state == "warning" and run_status != "warning":
                        raise DataError("Monte Carlo warning link requires warning family evidence")
                    if clean_state == "fail" and run_status != "fail":
                        raise DataError("Monte Carlo fail link requires failed family evidence")
            existing = connection.execute(
                """SELECT * FROM stage_run_links
                WHERE project_id = ? AND experiment_id = ? AND stage = ? AND run_id = ?""",
                (project_id, experiment_id, clean_stage, run_id),
            ).fetchone()
            if existing is not None:
                view = self._stage_link_view(connection, existing)
                if view["state"] != clean_state:
                    raise DataError("stage/run link already exists with a different state")
                return view
            connection.execute(
                "INSERT INTO stage_run_links VALUES (?, ?, ?, ?, ?, ?)",
                (lid, project_id, experiment_id, clean_stage, run_id, timestamp),
            )
            connection.execute(
                "INSERT INTO stage_state_events VALUES (?, 1, ?, ?, 'stage/run link created')",
                (lid, clean_state, timestamp),
            )
            if suite_action is None:
                self._append_experiment_stage_event(
                    connection,
                    project_id=project_id,
                    experiment_id=experiment_id,
                    stage=clean_stage,
                    state=clean_state,
                    reason="completed run linked to stage",
                    at=timestamp,
                    enforce_transition=False,
                )
            row = connection.execute(
                "SELECT * FROM stage_run_links WHERE link_id = ?", (lid,)
            ).fetchone()
            if row is None:  # pragma: no cover
                raise DataError("control store failed to persist stage/run link")
            view = self._stage_link_view(connection, row)
        return view

    def append_stage_state(
        self,
        link_id: str,
        state: StageState,
        *,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append one legal lifecycle transition to a stage/run link."""
        lid = _canonical_uuid(link_id, "link_id")
        clean_state = _required_text(state, "stage state", max_length=16)
        if clean_state not in STAGE_STATES:
            raise DataError(f"unsupported stage state {state!r}")
        if clean_state in _TERMINAL_STAGE_STATES:
            raise DataError(
                "terminal stage links are suite-owned; launch the resolved development suite"
            )
        clean_reason = _required_text(reason, "stage state reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            link = connection.execute(
                "SELECT * FROM stage_run_links WHERE link_id = ?", (lid,)
            ).fetchone()
            if link is None:
                raise DataError(f"unknown stage/run link {lid!r}")
            prior = connection.execute(
                """SELECT * FROM stage_state_events WHERE link_id = ?
                ORDER BY sequence DESC LIMIT 1""",
                (lid,),
            ).fetchone()
            if prior is None:
                raise DataError(f"corrupt control store: stage link {lid!r} has no events")
            prior_state = str(prior["state"])
            if clean_state not in _STAGE_TRANSITIONS[prior_state]:
                raise DataError(f"invalid stage transition {prior_state!r} -> {clean_state!r}")
            if not isinstance(prior["occurred_at"], str) or timestamp < prior["occurred_at"]:
                raise DataError("stage state timestamp precedes prior event")
            connection.execute(
                "INSERT INTO stage_state_events VALUES (?, ?, ?, ?, ?)",
                (lid, int(prior["sequence"]) + 1, clean_state, timestamp, clean_reason),
            )
            self._append_experiment_stage_event(
                connection,
                project_id=str(link["project_id"]),
                experiment_id=str(link["experiment_id"]),
                stage=str(link["stage"]),
                state=clean_state,
                reason=clean_reason,
                at=timestamp,
                enforce_transition=False,
            )
            view = self._stage_link_view(connection, link)
        return view

    def _terminal_stage_runs(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
        stage: str,
    ) -> list[tuple[dict[str, object], dict[str, object]]]:
        rows = connection.execute(
            """SELECT * FROM stage_run_links
            WHERE project_id = ? AND experiment_id = ? AND stage = ?
            ORDER BY linked_at, link_id""",
            (project_id, experiment_id, stage),
        ).fetchall()
        result: list[tuple[dict[str, object], dict[str, object]]] = []
        for row in rows:
            view = self._stage_link_view(connection, row)
            if view["state"] not in {"pass", "warning"}:
                continue
            _, manifest = self._verified_run(str(row["run_id"]))
            result.append((view, manifest))
        return result

    def _require_suite_action_evidence(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
        suite_action: str,
        stage: str,
    ) -> None:
        expected = _SUITE_ACTION_STAGE_COMMANDS.get(suite_action)
        if expected is None or expected[0] != stage:
            raise DataError(f"suite action {suite_action!r} cannot complete stage {stage!r}")
        evidence = self._terminal_stage_runs(
            connection,
            project_id=project_id,
            experiment_id=experiment_id,
            stage=stage,
        )
        commands = {str(manifest.get("command")) for _, manifest in evidence}
        if suite_action == "three_null_families":
            candidate_family = not commands.isdisjoint(_CANDIDATE_NULL_COMMANDS)
            if candidate_family and commands != _CANDIDATE_NULL_COMMANDS:
                raise DataError(
                    "candidate robustness completion requires exactly its three null runs"
                )
            if not candidate_family and commands != {"validate"}:
                raise DataError(
                    "single-instrument robustness completion requires validate runs only"
                )
            families = {
                metadata.get("null_model")
                for _, manifest in evidence
                if isinstance((metadata := manifest.get("metadata")), Mapping)
            }
            headline = any(
                view["state"] == "pass"
                and manifest.get("passed") is True
                and manifest.get("command")
                == ("candidate_null_bootstrap" if candidate_family else "validate")
                and isinstance(manifest.get("metadata"), Mapping)
                and cast(Mapping[str, object], manifest["metadata"]).get("null_model")
                == "bootstrap"
                for view, manifest in evidence
            )
            if families != {"bootstrap", "student_t", "garch"} or not headline:
                raise DataError(
                    "robustness completion requires one passing bootstrap headline plus "
                    "Student-t and GARCH sensitivity runs"
                )
            return
        if suite_action == "monte_carlo":
            family = (
                _CANDIDATE_MONTE_CARLO_COMMANDS
                if not commands.isdisjoint(_CANDIDATE_MONTE_CARLO_COMMANDS)
                else _MONTE_CARLO_COMMANDS
            )
            if commands != family:
                raise DataError(
                    "Monte Carlo completion requires classical and Kronos canonical runs"
                )
            source_runs = {str(manifest.get("source_run_id")) for _, manifest in evidence}
            if len(source_runs) != 1:
                raise DataError("Monte Carlo families must cite one source validation run")
            return
        if suite_action == "portfolio_cross_asset":
            if not commands.isdisjoint(_CANDIDATE_PORTFOLIO_COMMANDS):
                if commands != _CANDIDATE_PORTFOLIO_COMMANDS:
                    raise DataError(
                        "candidate portfolio completion requires concentration and scope checks"
                    )
                return
            required = (
                {"backtest_portfolio"},
                {"cross_sectional", "backtest_cross_sectional"},
            )
            if any(commands.isdisjoint(group) for group in required):
                raise DataError(
                    "portfolio completion requires canonical portfolio and cross-sectional runs"
                )
            return
        if suite_action == "kronos":
            if not {"forecast_run", "forecast_eval"}.issubset(commands):
                raise DataError(
                    "Kronos completion requires canonical forecast and rolling-evaluation runs"
                )
            return
        required_commands = expected[1]
        if commands.isdisjoint(required_commands):
            raise DataError(
                f"suite action {suite_action!r} has no verified canonical result "
                f"for stage {stage!r}"
            )

    def _pre_holdout_stage_evidence(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
    ) -> dict[str, list[dict[str, object]]]:
        """Rebuild the pre-holdout gate from verified canonical runs, never cached labels."""
        experiment = connection.execute(
            "SELECT snapshot_id FROM experiment_specs WHERE experiment_id = ?", (experiment_id,)
        ).fetchone()
        if experiment is None:  # pragma: no cover - caller validates the project link.
            raise DataError(f"unknown experiment {experiment_id!r}")
        sealed = connection.execute(
            """SELECT spec_hash, start_date FROM holdout_specs
            WHERE project_id = ? AND experiment_id = ?""",
            (project_id, experiment_id),
        ).fetchone()
        if sealed is None:
            raise DataError(
                "candidate freeze requires a dated holdout sealed before research began"
            )
        expected_cutoff = self._manifest_research_cutoff(sealed)
        snapshot_id = str(experiment["snapshot_id"])
        from alpha_cli._runner import verified_snapshot_hash

        try:
            snapshot_hash = verified_snapshot_hash(self._data_dir, snapshot_id)
        except DataError as exc:
            raise DataError(
                "candidate freeze requires verified canonical suite evidence: "
                "the frozen experiment snapshot is unavailable"
            ) from exc
        by_stage: dict[str, list[dict[str, object]]] = {}
        for stage in (
            "baseline",
            "oos",
            "robustness",
            "monte_carlo",
            "optimization",
            "portfolio",
        ):
            for view, manifest in self._terminal_stage_runs(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage=stage,
            ):
                if manifest.get("schema_version") != 3:
                    continue
                run_snapshot = manifest.get("snapshot_id")
                if run_snapshot is not None and run_snapshot != snapshot_id:
                    continue
                if manifest.get("snapshot_hash") != snapshot_hash:
                    continue
                if manifest.get("research_cutoff") != expected_cutoff:
                    continue
                by_stage.setdefault(stage, []).append(
                    {
                        "run_id": view["run_id"],
                        "state": view["state"],
                        "command": manifest.get("command"),
                        "passed": manifest.get("passed"),
                        "metadata": manifest.get("metadata"),
                        "status": manifest.get("status"),
                    }
                )

        problems: list[str] = []
        if not any(row["command"] == "backtest_run" for row in by_stage.get("baseline", [])):
            problems.append("baseline backtest")
        if not any(row["command"] == "backtest_oos" for row in by_stage.get("oos", [])):
            problems.append("inner OOS evaluation")
        robustness = by_stage.get("robustness", [])
        families = {
            metadata.get("null_model")
            for row in robustness
            if isinstance((metadata := row.get("metadata")), Mapping)
        }
        headline = any(
            row["command"] == "validate"
            and row["state"] == "pass"
            and row["passed"] is True
            and isinstance(row.get("metadata"), Mapping)
            and cast(Mapping[str, object], row["metadata"]).get("null_model") == "bootstrap"
            for row in robustness
        )
        if families != {"bootstrap", "student_t", "garch"} or not headline:
            problems.append("three-family robustness evidence with a passing bootstrap headline")
        monte_carlo = by_stage.get("monte_carlo", [])
        monte_carlo_commands = {str(row["command"]) for row in monte_carlo}
        monte_carlo_clear = monte_carlo_commands == _MONTE_CARLO_COMMANDS and all(
            row["status"] == "clear" for row in monte_carlo
        )
        if not monte_carlo_clear:
            review = connection.execute(
                """SELECT decision, evidence_hashes_json FROM monte_carlo_reviews
                WHERE project_id = ? AND experiment_id = ?""",
                (project_id, experiment_id),
            ).fetchone()
            expected_review_hashes: str | None = None
            if monte_carlo_commands == _MONTE_CARLO_COMMANDS:
                try:
                    expected_review_hashes = self._encoded_monte_carlo_evidence_hashes(
                        connection,
                        project_id=project_id,
                        experiment_id=experiment_id,
                    )
                except DataError:
                    expected_review_hashes = None
            if (
                monte_carlo_commands != _MONTE_CARLO_COMMANDS
                or review is None
                or review["decision"] != "continue"
                or review["evidence_hashes_json"] != expected_review_hashes
            ):
                problems.append("four-family Monte Carlo evidence and owner warning disposition")
        if not any(
            row["command"] == "optim_grid" and row["passed"] is True
            for row in by_stage.get("optimization", [])
        ):
            problems.append("passing deterministic optimization")
        portfolio_commands = {str(row["command"]) for row in by_stage.get("portfolio", [])}
        if "backtest_portfolio" not in portfolio_commands:
            problems.append("portfolio analysis")
        if portfolio_commands.isdisjoint({"cross_sectional", "backtest_cross_sectional"}):
            problems.append("cross-sectional analysis")
        if problems:
            raise DataError(
                "candidate freeze requires verified canonical suite evidence for: "
                + ", ".join(problems)
            )
        return by_stage

    def complete_suite_stage(
        self,
        project_id: str,
        experiment_id: str,
        *,
        suite_action: str,
        stage: str,
        state: StageState,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Complete a suite-owned stage after independently validating its canonical evidence."""
        clean_state = _required_text(state, "stage state", max_length=16)
        if clean_state not in _TERMINAL_STAGE_STATES:
            raise DataError("suite completion requires pass, warning, or fail")
        clean_reason = _required_text(reason, "stage state reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            expected = _SUITE_ACTION_STAGE_COMMANDS.get(suite_action)
            if expected is None or expected[0] != stage:
                raise DataError(f"suite action {suite_action!r} cannot complete stage {stage!r}")
            if clean_state in {"pass", "warning"}:
                self._require_suite_action_evidence(
                    connection,
                    project_id=project_id,
                    experiment_id=experiment_id,
                    suite_action=suite_action,
                    stage=stage,
                )
            self._append_experiment_stage_event(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage=stage,
                state=clean_state,
                reason=clean_reason,
                at=timestamp,
                enforce_transition=True,
            )
            return self._experiment_stage_view(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage=stage,
            )

    def complete_suite_journal_stage(
        self,
        project_id: str,
        experiment_id: str,
        *,
        suite_action: str,
        stage: str,
        state: StageState,
        job_id: str,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Complete the runless paper gate from its reserved job and exact step attempts."""
        if suite_action != "paper_preflight" or stage != "paper":
            raise DataError("only paper_preflight has a runless suite completion contract")
        clean_state = _required_text(state, "stage state", max_length=16)
        if clean_state not in {"pass", "fail"}:
            raise DataError("paper preflight completion requires pass or fail")
        clean_reason = _required_text(reason, "stage state reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            job = self._require_job(connection, job_id)
            if (
                job["kind"] != "suite:paper_preflight"
                or job["project_id"] != project_id
                or job["experiment_id"] != experiment_id
                or job["status"] != "running"
            ):
                raise DataError("paper completion requires its active reserved suite job")
            request = _decode_json(job["request_json"], "paper suite request")
            if not isinstance(request, dict) or (
                request.get("action") != "paper_preflight" or request.get("stage") != "paper"
            ):
                raise DataError("paper suite job does not match the paper preflight action")
            if clean_state == "pass":
                steps = request.get("steps")
                if not isinstance(steps, list) or not steps:
                    raise DataError("paper suite job has no resolved preflight steps")
                terminal_attempts = connection.execute(
                    """SELECT status, details_json FROM attempt_records
                    WHERE project_id = ? AND experiment_id = ? AND stage = ?
                    AND status IN ('passed', 'failed', 'cancelled', 'pruned', 'rejected')""",
                    (project_id, experiment_id, stage),
                ).fetchall()
                passed_steps: set[int] = set()
                for attempt in terminal_attempts:
                    details = _decode_json(attempt["details_json"], "paper attempt details")
                    if not isinstance(details, dict) or details.get("job_id") != job_id:
                        continue
                    if details.get("action") != suite_action:
                        raise DataError(
                            "paper attempt action does not match its reserved suite job"
                        )
                    step = details.get("step")
                    if (
                        attempt["status"] != "passed"
                        or isinstance(step, bool)
                        or not isinstance(step, int)
                    ):
                        raise DataError("paper preflight has a non-passing terminal attempt")
                    passed_steps.add(step)
                if passed_steps != set(range(1, len(steps) + 1)):
                    raise DataError("paper preflight requires one passing attempt for every step")
            self._append_experiment_stage_event(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage=stage,
                state=clean_state,
                reason=clean_reason,
                at=timestamp,
                enforce_transition=True,
            )
            return self._experiment_stage_view(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage=stage,
            )

    def append_experiment_stage_state(
        self,
        project_id: str,
        experiment_id: str,
        stage: str,
        state: StageState,
        *,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append a legal project/experiment lifecycle transition before a run exists."""
        clean_stage = _required_text(stage, "development stage", max_length=32)
        if clean_stage not in DEVELOPMENT_STAGES:
            raise DataError(f"unsupported development stage {stage!r}")
        clean_state = _required_text(state, "stage state", max_length=16)
        if clean_state not in STAGE_STATES:
            raise DataError(f"unsupported stage state {state!r}")
        owner_validated_pass = clean_stage in {"hypothesis", "data", "strategy"} and (
            clean_state == "pass"
        )
        candidate_pass = clean_stage == "candidate" and clean_state == "pass"
        if clean_state in _TERMINAL_STAGE_STATES and not (owner_validated_pass or candidate_pass):
            raise DataError(
                "terminal experiment stage states are suite-owned; launch the resolved suite"
            )
        clean_reason = _required_text(reason, "stage state reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            project = self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            if owner_validated_pass:
                experiment = connection.execute(
                    "SELECT * FROM experiment_specs WHERE experiment_id = ?", (experiment_id,)
                ).fetchone()
                if experiment is None:  # pragma: no cover - project link proves it exists.
                    raise DataError(f"unknown experiment {experiment_id!r}")
                if clean_stage == "hypothesis" and (
                    not project["hypothesis"] or not project["falsification_criterion"]
                ):
                    raise DataError("hypothesis completion requires a falsifiable project claim")
                if clean_stage == "data" and (
                    not experiment["snapshot_id"] or not experiment["universe_json"]
                ):
                    raise DataError("data completion requires a frozen experiment specification")
                if clean_stage == "strategy":
                    linked = connection.execute(
                        """SELECT 1 FROM project_versions
                        WHERE project_id = ? AND version_id = ?""",
                        (project_id, experiment["strategy_version_id"]),
                    ).fetchone()
                    if linked is None:
                        raise DataError("strategy completion requires a linked immutable version")
            if clean_stage == "candidate" and clean_state != "stale":
                self._pre_holdout_stage_evidence(
                    connection,
                    project_id=project_id,
                    experiment_id=experiment_id,
                )
            self._append_experiment_stage_event(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage=clean_stage,
                state=clean_state,
                reason=clean_reason,
                at=timestamp,
                enforce_transition=True,
            )
            return self._experiment_stage_view(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage=clean_stage,
            )

    def record_attempt(
        self,
        project_id: str,
        experiment_id: str,
        *,
        stage: str,
        status: AttemptStatus,
        config_fingerprint: str,
        run_id: str | None = None,
        error: str | None = None,
        details: Mapping[str, object] | None = None,
        attempt_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append one immutable attempted/pruned/failed/successful configuration record."""
        clean_stage = _required_text(stage, "development stage", max_length=32)
        if clean_stage not in DEVELOPMENT_STAGES:
            raise DataError(f"unsupported development stage {stage!r}")
        clean_status = _required_text(status, "attempt status", max_length=16)
        if clean_status not in ATTEMPT_STATUSES:
            raise DataError(f"unsupported attempt status {status!r}")
        if clean_status == "failed" and error is None:
            raise DataError("failed attempt requires an error")
        if error is not None and clean_status != "failed":
            raise DataError("attempt error is only valid for failed status")
        clean_run = None if run_id is None else self._require_run(run_id)
        clean_details = _json_object(details or {}, "attempt details")
        aid = _new_uuid(attempt_id, "attempt_id")
        timestamp = _at(at)
        values = (
            aid,
            project_id,
            experiment_id,
            clean_stage,
            clean_status,
            _required_text(config_fingerprint, "config fingerprint", max_length=512),
            clean_run,
            _optional_text(error, "attempt error"),
            _canonical_json(clean_details, "attempt details"),
            timestamp,
        )
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            if (
                connection.execute(
                    "SELECT 1 FROM attempt_records WHERE attempt_id = ?", (aid,)
                ).fetchone()
                is not None
            ):
                raise DataError(f"attempt {aid!r} already exists")
            connection.execute(
                "INSERT INTO attempt_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values
            )
            row = connection.execute(
                "SELECT * FROM attempt_records WHERE attempt_id = ?", (aid,)
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist attempt")
        return self._attempt_view(row)

    def seal_holdout(
        self,
        project_id: str,
        experiment_id: str,
        *,
        actor: str,
        reason: str,
        start_date: str,
        end_date: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Seal one immutable experiment as the final holdout before any reveal."""
        timestamp = _at(at)
        clean_actor = _required_text(actor, "holdout actor", max_length=200)
        clean_reason = _required_text(reason, "holdout seal reason")
        clean_start = _iso_date(start_date, "holdout start_date")
        clean_end = _iso_date(end_date, "holdout end_date")
        if clean_start > clean_end:
            raise DataError("holdout start_date must not follow end_date")
        holdout_spec: dict[str, object] = {
            "schema_version": 1,
            "project_id": project_id,
            "experiment_id": experiment_id,
            "start_date": clean_start,
            "end_date": clean_end,
        }
        encoded = _canonical_json(holdout_spec, "holdout specification")
        holdout_spec_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            if (
                connection.execute(
                    "SELECT 1 FROM holdout_state WHERE project_id = ? AND experiment_id = ?",
                    (project_id, experiment_id),
                ).fetchone()
                is not None
            ):
                raise DataError(f"holdout for experiment {experiment_id!r} was already sealed")
            experiment = connection.execute(
                "SELECT strategy_version_id FROM experiment_specs WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
            if experiment is None:  # pragma: no cover - project link proves it exists.
                raise DataError(f"unknown experiment {experiment_id!r}")
            version_id = str(experiment["strategy_version_id"])
            attempted = connection.execute(
                f"""SELECT 1 FROM attempt_records
                WHERE project_id = ? AND experiment_id = ?
                    AND stage IN ({",".join("?" for _ in _PRE_REVEAL_RESEARCH_STAGES)})
                LIMIT 1""",  # noqa: S608 - placeholders come from a closed constant.
                (project_id, experiment_id, *sorted(_PRE_REVEAL_RESEARCH_STAGES)),
            ).fetchone()
            linked = connection.execute(
                """SELECT 1 FROM stage_run_links
                WHERE project_id = ? AND experiment_id = ? LIMIT 1""",
                (project_id, experiment_id),
            ).fetchone()
            launched = connection.execute(
                f"""SELECT 1 FROM jobs WHERE project_id = ? AND experiment_id = ?
                    AND kind IN ({",".join("?" for _ in _PRE_REVEAL_RESEARCH_JOB_KINDS)})
                    LIMIT 1""",  # noqa: S608 - placeholders come from a closed constant.
                (project_id, experiment_id, *sorted(_PRE_REVEAL_RESEARCH_JOB_KINDS)),
            ).fetchone()
            progressed = connection.execute(
                f"""SELECT 1 FROM experiment_stage_events
                WHERE project_id = ? AND experiment_id = ?
                    AND stage IN ({",".join("?" for _ in _PRE_REVEAL_RESEARCH_STAGES)})
                    AND state IN ('queued', 'running', 'pass', 'warning', 'fail')
                LIMIT 1""",  # noqa: S608 - placeholders come from a closed constant.
                (project_id, experiment_id, *sorted(_PRE_REVEAL_RESEARCH_STAGES)),
            ).fetchone()
            if any(value is not None for value in (attempted, linked, launched, progressed)):
                raise DataError("final holdout must be sealed before any research attempt or run")
            overlap = connection.execute(
                """SELECT s.start_date, s.end_date FROM holdout_specs s
                JOIN holdout_state h
                    ON h.project_id = s.project_id AND h.experiment_id = s.experiment_id
                WHERE s.project_id = ? AND h.revealed_at IS NOT NULL
                    AND NOT (? < s.start_date OR ? > s.end_date)
                LIMIT 1""",
                (project_id, clean_end, clean_start),
            ).fetchone()
            if overlap is not None:
                raise DataError(
                    "holdout window overlaps a previously revealed window in this project lineage"
                )
            connection.execute(
                """INSERT INTO holdout_state (
                    project_id, experiment_id, sealed_at, sealed_by, sealed_version_id,
                    seal_reason, revealed_at, revealed_by, revealed_version_id, reveal_reason,
                    contaminated_at, contamination_reason
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL)""",
                (
                    project_id,
                    experiment_id,
                    timestamp,
                    clean_actor,
                    version_id,
                    clean_reason,
                ),
            )
            connection.execute(
                """INSERT INTO holdout_specs (
                    project_id, experiment_id, spec_hash, start_date, end_date
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    project_id,
                    experiment_id,
                    holdout_spec_hash,
                    holdout_spec["start_date"],
                    holdout_spec["end_date"],
                ),
            )
            connection.execute(
                """INSERT INTO holdout_audit (
                    project_id, experiment_id, event, actor, occurred_at, reason, version_id
                ) VALUES (?, ?, 'sealed', ?, ?, ?, ?)""",
                (project_id, experiment_id, clean_actor, timestamp, clean_reason, version_id),
            )
            row = connection.execute(
                """SELECT h.*, s.spec_hash AS holdout_spec_hash,
                    NULL AS start_date, NULL AS end_date
                FROM holdout_state h LEFT JOIN holdout_specs s
                    ON s.project_id = h.project_id AND s.experiment_id = h.experiment_id
                WHERE h.project_id = ? AND h.experiment_id = ?""",
                (project_id, experiment_id),
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist holdout seal")
        return dict(row)

    def get_holdout_spec(self, project_id: str, experiment_id: str) -> dict[str, object] | None:
        """Resolve the sealed window for CLI-owned execution; no REST/MCP route exposes this."""
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            row = connection.execute(
                """SELECT spec_hash, start_date, end_date FROM holdout_specs
                WHERE project_id = ? AND experiment_id = ?""",
                (project_id, experiment_id),
            ).fetchone()
        return None if row is None else dict(row)

    def holdout_reveal_resume_authorized(
        self,
        project_id: str,
        experiment_id: str,
        job_id: str,
        *,
        require_terminal: bool = False,
    ) -> bool:
        """Allow only the interrupted journal that audited the reveal to finish evaluation."""
        with self._transaction(write=False) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            jid = _canonical_uuid(job_id, "job_id")
            job = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (jid,)).fetchone()
            if job is None:
                return False
            if (
                job["kind"] != "suite:holdout_reveal"
                or job["project_id"] != project_id
                or job["experiment_id"] != experiment_id
                or (require_terminal and job["status"] not in {"failed", "cancelled"})
            ):
                return False
            holdout = connection.execute(
                """SELECT revealed_at, contaminated_at FROM holdout_state
                WHERE project_id = ? AND experiment_id = ?""",
                (project_id, experiment_id),
            ).fetchone()
            return bool(
                holdout is not None
                and holdout["revealed_at"] is not None
                and holdout["contaminated_at"] is None
                and self._reveal_attempt_matches_job(connection, project_id, experiment_id, job_id)
            )

    def reveal_holdout(
        self,
        project_id: str,
        experiment_id: str,
        *,
        actor: str,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Permanently audit the one-shot reveal of a previously sealed final holdout."""
        timestamp = _at(at)
        clean_actor = _required_text(actor, "holdout actor", max_length=200)
        clean_reason = _required_text(reason, "holdout reveal reason")
        with self._transaction(write=True) as connection:
            self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            state = connection.execute(
                "SELECT * FROM holdout_state WHERE project_id = ? AND experiment_id = ?",
                (project_id, experiment_id),
            ).fetchone()
            if state is None:
                raise DataError(
                    f"holdout for experiment {experiment_id!r} must be sealed before reveal"
                )
            if state["revealed_at"] is not None:
                raise DataError(f"holdout for experiment {experiment_id!r} was already revealed")
            if not isinstance(state["sealed_at"], str) or timestamp < state["sealed_at"]:
                raise DataError("holdout reveal timestamp precedes seal")
            self._pre_holdout_stage_evidence(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
            )
            candidate_state = self._latest_experiment_stage_state(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage="candidate",
            )
            if candidate_state != "pass":
                raise DataError(
                    "final holdout reveal requires a candidate freeze backed by verified "
                    "canonical suite evidence"
                )
            sealed_spec = connection.execute(
                """SELECT 1 FROM holdout_specs
                WHERE project_id = ? AND experiment_id = ?""",
                (project_id, experiment_id),
            ).fetchone()
            if sealed_spec is None:
                raise DataError(
                    "final holdout reveal requires a dated sealed holdout specification"
                )
            experiment = connection.execute(
                "SELECT strategy_version_id FROM experiment_specs WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
            if experiment is None:  # pragma: no cover - project link proves it exists.
                raise DataError(f"unknown experiment {experiment_id!r}")
            version_id = str(experiment["strategy_version_id"])
            if state["sealed_version_id"] != version_id:
                raise DataError("sealed holdout strategy version no longer matches the experiment")
            connection.execute(
                """UPDATE holdout_state SET revealed_at = ?, revealed_by = ?,
                revealed_version_id = ?, reveal_reason = ?
                WHERE project_id = ? AND experiment_id = ?""",
                (timestamp, clean_actor, version_id, clean_reason, project_id, experiment_id),
            )
            connection.execute(
                """INSERT INTO holdout_audit (
                    project_id, experiment_id, event, actor, occurred_at, reason, version_id
                ) VALUES (?, ?, 'revealed', ?, ?, ?, ?)""",
                (project_id, experiment_id, clean_actor, timestamp, clean_reason, version_id),
            )
            row = connection.execute(
                """SELECT h.*, s.spec_hash AS holdout_spec_hash,
                    s.start_date, s.end_date
                FROM holdout_state h LEFT JOIN holdout_specs s
                    ON s.project_id = h.project_id AND s.experiment_id = h.experiment_id
                WHERE h.project_id = ? AND h.experiment_id = ?""",
                (project_id, experiment_id),
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist holdout reveal")
        return dict(row)

    @staticmethod
    def _decision_packet_view(row: sqlite3.Row) -> dict[str, object]:
        content = _decode_json(row["packet_json"], "decision packet")
        if not isinstance(content, dict):
            raise DataError("corrupt control store: decision packet is not an object")
        return {
            "packet_id": row["packet_id"],
            "packet_hash": row["packet_hash"],
            **cast(dict[str, object], content),
            "created_at": row["created_at"],
        }

    def _promotion_stage_evidence(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        experiment_id: str,
        snapshot_id: str,
    ) -> dict[str, object]:
        """Resolve exact immutable run citations for every run-backed promotion gate."""
        self._pre_holdout_stage_evidence(
            connection,
            project_id=project_id,
            experiment_id=experiment_id,
        )
        rows = connection.execute(
            """SELECT * FROM stage_run_links
            WHERE project_id = ? AND experiment_id = ? ORDER BY linked_at, link_id""",
            (project_id, experiment_id),
        ).fetchall()
        by_stage: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            view = self._stage_link_view(connection, row)
            if view["state"] not in {"pass", "warning"}:
                continue
            run_id = str(row["run_id"])
            rdir, manifest = self._verified_run(run_id)
            manifest_path = rdir / "manifest.json"
            command = manifest.get("command")
            run_snapshot_id = manifest.get("snapshot_id")
            snapshot_hash = manifest.get("snapshot_hash")
            if run_snapshot_id != snapshot_id:
                raise DataError(
                    f"promotion evidence run {run_id!r} uses snapshot {run_snapshot_id!r}, "
                    f"expected {snapshot_id!r}"
                )
            if (
                not isinstance(snapshot_hash, str)
                or re.fullmatch(r"[0-9a-f]{64}", snapshot_hash) is None
            ):
                raise DataError(f"promotion evidence run {run_id!r} has no valid snapshot hash")
            by_stage.setdefault(str(row["stage"]), []).append(
                {
                    "run_id": run_id,
                    "command": command,
                    "state": view["state"],
                    "snapshot_hash": snapshot_hash,
                    "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                    "passed": manifest.get("passed"),
                }
            )

        command_requirements: dict[str, tuple[frozenset[str], ...]] = {
            "baseline": (frozenset({"backtest_run"}),),
            "oos": (frozenset({"backtest_oos"}),),
            "robustness": (frozenset({"validate"}),),
            "monte_carlo": (
                frozenset({"monte_carlo_classical"}),
                frozenset({"monte_carlo_kronos"}),
            ),
            "optimization": (frozenset({"optim_grid"}),),
            "portfolio": (
                frozenset({"backtest_portfolio"}),
                frozenset({"cross_sectional", "backtest_cross_sectional"}),
            ),
            "holdout": (frozenset({"backtest_holdout"}),),
        }
        problems: list[str] = []
        for stage, alternatives in command_requirements.items():
            evidence = by_stage.get(stage, [])
            commands = {str(row["command"]) for row in evidence}
            for allowed in alternatives:
                if commands.isdisjoint(allowed):
                    problems.append(f"{stage} ({'/'.join(sorted(allowed))})")
        for stage in ("robustness", "optimization", "holdout"):
            if not any(row.get("passed") is True for row in by_stage.get(stage, [])):
                problems.append(f"{stage} passed verdict")
        sealed_spec = connection.execute(
            """SELECT spec_hash FROM holdout_specs
            WHERE project_id = ? AND experiment_id = ?""",
            (project_id, experiment_id),
        ).fetchone()
        if sealed_spec is None:
            problems.append("sealed holdout specification")
        else:
            expected_hash = str(sealed_spec["spec_hash"])
            matching_holdout = False
            for row in by_stage.get("holdout", []):
                _, manifest = self._verified_run(str(row["run_id"]))
                if manifest.get("holdout_spec_hash") == expected_hash:
                    matching_holdout = True
                    row["holdout_spec_hash"] = expected_hash
            if not matching_holdout:
                problems.append("holdout run matching the sealed window hash")
        snapshot_hashes = {
            str(row["snapshot_hash"]) for evidence in by_stage.values() for row in evidence
        }
        if len(snapshot_hashes) != 1:
            problems.append("one consistent snapshot hash")
        if problems:
            raise DataError(
                "promotion requires exact canonical evidence for: " + ", ".join(problems)
            )
        result: dict[str, object] = {
            stage: evidence for stage, evidence in sorted(by_stage.items())
        }
        result["paper"] = {
            "state": self._latest_experiment_stage_state(
                connection,
                project_id=project_id,
                experiment_id=experiment_id,
                stage="paper",
            )
        }
        return result

    def freeze_decision_packet(
        self,
        project_id: str,
        experiment_id: str,
        *,
        verdict: DecisionVerdict,
        actor: str,
        reason: str,
        negative_results_acknowledged: bool,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Freeze one append-only accept/reject/revise packet; never place or route an order."""
        clean_verdict = _required_text(verdict, "decision verdict", max_length=16)
        if clean_verdict not in DECISION_VERDICTS:
            raise DataError(f"unsupported decision verdict {verdict!r}")
        if not isinstance(negative_results_acknowledged, bool):
            raise DataError("negative_results_acknowledged must be a boolean")
        if not negative_results_acknowledged:
            raise DataError("negative results must be explicitly acknowledged")
        clean_actor = _required_text(actor, "decision actor", max_length=200)
        clean_reason = _required_text(reason, "decision reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            project = self._require_project(connection, project_id)
            self._require_project_experiment(connection, project_id, experiment_id)
            if (
                connection.execute(
                    "SELECT 1 FROM decision_packets WHERE project_id = ? AND experiment_id = ?",
                    (project_id, experiment_id),
                ).fetchone()
                is not None
            ):
                raise DataError("experiment already has a frozen decision packet")
            experiment = connection.execute(
                "SELECT * FROM experiment_specs WHERE experiment_id = ?", (experiment_id,)
            ).fetchone()
            if experiment is None:  # pragma: no cover - project link proves existence.
                raise DataError(f"unknown experiment {experiment_id!r}")
            version_id = str(experiment["strategy_version_id"])
            version = connection.execute(
                "SELECT * FROM strategy_versions WHERE version_id = ?", (version_id,)
            ).fetchone()
            if version is None:  # pragma: no cover
                raise DataError(f"unknown strategy version {version_id!r}")

            stage_evidence: dict[str, object] = {}
            if clean_verdict == "accept":
                if (
                    project["current_version_id"] != version_id
                    or project["current_experiment_id"] != experiment_id
                ):
                    raise DataError(
                        "promotion requires the current immutable version and experiment"
                    )
                source = str(version["source_fingerprint"])
                if not source.startswith("git:") or any(
                    marker in source.lower() for marker in ("dirty", "uncommitted", "unknown")
                ):
                    raise DataError("promotion requires clean git source provenance")
                required_states = (
                    "baseline",
                    "oos",
                    "robustness",
                    "monte_carlo",
                    "optimization",
                    "portfolio",
                    "candidate",
                    "holdout",
                    "paper",
                )
                incomplete = [
                    stage
                    for stage in required_states
                    if self._latest_experiment_stage_state(
                        connection,
                        project_id=project_id,
                        experiment_id=experiment_id,
                        stage=stage,
                    )
                    not in {"pass", "warning"}
                ]
                if incomplete:
                    raise DataError(
                        "promotion requires passed lifecycle stages: " + ", ".join(incomplete)
                    )
                holdout = connection.execute(
                    "SELECT * FROM holdout_state WHERE project_id = ? AND experiment_id = ?",
                    (project_id, experiment_id),
                ).fetchone()
                if (
                    holdout is None
                    or holdout["revealed_at"] is None
                    or holdout["contaminated_at"] is not None
                    or holdout["revealed_version_id"] != version_id
                ):
                    raise DataError("promotion requires an uncontaminated one-shot holdout reveal")
                stage_evidence = self._promotion_stage_evidence(
                    connection,
                    project_id=project_id,
                    experiment_id=experiment_id,
                    snapshot_id=str(experiment["snapshot_id"]),
                )

            negative_rows = connection.execute(
                """SELECT attempt_id FROM attempt_records
                WHERE project_id = ? AND experiment_id = ?
                AND status IN ('failed', 'pruned', 'rejected', 'cancelled')
                ORDER BY recorded_at, attempt_id""",
                (project_id, experiment_id),
            ).fetchall()
            packet = {
                "schema_version": 1,
                "project_id": project_id,
                "experiment_id": experiment_id,
                "strategy_version_id": version_id,
                "verdict": clean_verdict,
                "actor": clean_actor,
                "reason": clean_reason,
                "negative_results_acknowledged": True,
                "negative_result_attempt_ids": [str(row["attempt_id"]) for row in negative_rows],
                "stage_evidence": stage_evidence,
                "deployment_scope": "sandbox_only",
                "places_real_orders": False,
            }
            packet_json = _canonical_json(packet, "decision packet")
            packet_hash = hashlib.sha256(packet_json.encode("utf-8")).hexdigest()
            packet_id = f"dp_{packet_hash}"
            connection.execute(
                """INSERT INTO decision_packets (
                    packet_id, packet_hash, project_id, experiment_id, strategy_version_id,
                    verdict, packet_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    packet_id,
                    packet_hash,
                    project_id,
                    experiment_id,
                    version_id,
                    clean_verdict,
                    packet_json,
                    timestamp,
                ),
            )
            for state in ("ready", "queued", "running", "pass"):
                self._append_experiment_stage_event(
                    connection,
                    project_id=project_id,
                    experiment_id=experiment_id,
                    stage="decision",
                    state=state,
                    reason="owner decision packet frozen",
                    at=timestamp,
                    enforce_transition=True,
                )
            project_status = (
                "accepted"
                if clean_verdict == "accept"
                else ("rejected" if clean_verdict == "reject" else "active")
            )
            connection.execute(
                "UPDATE projects SET status = ?, updated_at = ? WHERE project_id = ?",
                (project_status, timestamp, project_id),
            )
            row = connection.execute(
                "SELECT * FROM decision_packets WHERE packet_id = ?", (packet_id,)
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist decision packet")
        return self._decision_packet_view(row)

    @staticmethod
    def _job_view(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["request"] = _decode_json(result.pop("request_json"), "job request")
        return result

    @staticmethod
    def _job_event_view(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["payload"] = _decode_json(result.pop("payload_json"), "job event payload")
        return result

    def create_job(
        self,
        *,
        kind: str,
        request: Mapping[str, object],
        project_id: str | None = None,
        experiment_id: str | None = None,
        job_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Create a generic queued job without access to reserved executable suite kinds."""
        return self._create_job(
            kind=kind,
            request=request,
            project_id=project_id,
            experiment_id=experiment_id,
            job_id=job_id,
            at=at,
            allow_reserved=False,
        )

    def create_research_job(
        self,
        project_id: str,
        *,
        contract_id: str,
        request: Mapping[str, object],
        job_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Create the governed ``research:event-study`` durable job for active D1/D2 work.

        The phase pre-check runs in its own read transaction; a lost race can only leave a
        stray queued job that the execution-event binding check refuses to activate.
        """
        with self._transaction(write=False) as connection:
            contract = self._require_research_contract(connection, project_id, contract_id)
            review = self._latest_research_review(connection, contract_id)
            phase = self._latest_research_phase(connection, project_id)
            expected_phase = (
                "deep_research" if contract["scope"] == "exploration" else "sealed_confirmation"
            )
            if (
                contract["scope"] not in {"exploration", "confirmation"}
                or _research_review_state(review) != "approved"
                or phase is None
                or phase["phase"] != expected_phase
                or phase["contract_id"] != contract_id
            ):
                raise DataError(
                    "research job creation requires the approved active deep_research or "
                    "sealed_confirmation contract"
                )
        return self._create_job(
            kind="research:event-study",
            request=request,
            project_id=project_id,
            experiment_id=None,
            job_id=job_id,
            at=at,
            allow_reserved=True,
        )

    def create_suite_job(
        self,
        *,
        kind: str,
        request: Mapping[str, object],
        project_id: str,
        experiment_id: str,
        job_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Create an allowlisted executable suite job for the internal suite orchestrator."""
        if kind not in _SUITE_JOB_KINDS:
            raise DataError(f"unsupported executable suite job kind {kind!r}")
        return self._create_job(
            kind=kind,
            request=request,
            project_id=project_id,
            experiment_id=experiment_id,
            job_id=job_id,
            at=at,
            allow_reserved=True,
        )

    def _create_job(
        self,
        *,
        kind: str,
        request: Mapping[str, object],
        project_id: str | None,
        experiment_id: str | None,
        job_id: str | None,
        at: datetime | None,
        allow_reserved: bool,
    ) -> dict[str, object]:
        """Persist one job after enforcing the caller's job-kind authority."""
        jid = _new_uuid(job_id, "job_id")
        timestamp = _at(at)
        clean_request = _json_object(request, "job request")
        clean_kind = _required_text(kind, "job kind", max_length=100)
        request_json = _canonical_json(clean_request, "job request")
        if not allow_reserved and clean_kind.startswith(_RESERVED_JOB_PREFIXES):
            raise DataError("reserved job kinds require their governed internal executor")
        if experiment_id is not None and project_id is None:
            raise DataError("job experiment_id requires project_id")
        with self._transaction(write=True) as connection:
            if project_id is not None:
                self._require_project(connection, project_id)
            if experiment_id is not None and project_id is not None:
                self._require_project_experiment(connection, project_id, experiment_id)
                if allow_reserved and clean_kind in _PRE_REVEAL_RESEARCH_JOB_KINDS:
                    self._require_pre_reveal_holdout(connection, project_id, experiment_id)
            existing = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (jid,)).fetchone()
            if existing is not None:
                reusable = (
                    allow_reserved
                    and str(existing["kind"]) == clean_kind
                    and existing["project_id"] == project_id
                    and existing["experiment_id"] == experiment_id
                    and str(existing["request_json"]) == request_json
                    and str(existing["status"]) == "queued"
                )
                if reusable:
                    return self._job_view(existing)
                resumable_holdout = (
                    allow_reserved
                    and clean_kind == "suite:holdout_reveal"
                    and str(existing["kind"]) == clean_kind
                    and existing["project_id"] == project_id
                    and existing["experiment_id"] == experiment_id
                    and existing["status"] in {"failed", "cancelled"}
                    and project_id is not None
                    and experiment_id is not None
                    and self._reveal_attempt_matches_job(connection, project_id, experiment_id, jid)
                )
                if resumable_holdout:
                    holdout = connection.execute(
                        """SELECT revealed_at, contaminated_at FROM holdout_state
                        WHERE project_id = ? AND experiment_id = ?""",
                        (project_id, experiment_id),
                    ).fetchone()
                    if (
                        holdout is None
                        or holdout["revealed_at"] is None
                        or holdout["contaminated_at"] is not None
                    ):
                        raise DataError("interrupted holdout evaluation is not resumable")
                    self._require_monotonic(existing["updated_at"], timestamp, "resume timestamp")
                    sequence = int(existing["last_sequence"]) + 1
                    payload = {
                        "from": str(existing["status"]),
                        "to": "queued",
                        "resume": True,
                    }
                    connection.execute(
                        "INSERT INTO job_events VALUES (?, ?, 'status', ?, ?)",
                        (jid, sequence, timestamp, _canonical_json(payload, "job resume event")),
                    )
                    connection.execute(
                        """UPDATE jobs SET status = 'queued', updated_at = ?, heartbeat_at = ?,
                        result_run_id = NULL, terminal_error = NULL, last_sequence = ?
                        WHERE job_id = ?""",
                        (timestamp, timestamp, sequence, jid),
                    )
                    resumed = connection.execute(
                        "SELECT * FROM jobs WHERE job_id = ?", (jid,)
                    ).fetchone()
                    if resumed is None:  # pragma: no cover
                        raise DataError("control store failed to resume holdout job")
                    return self._job_view(resumed)
                raise DataError(f"job {jid!r} already exists")
            if clean_kind in HEAVYWEIGHT_JOB_KINDS:
                heavyweight_kinds = sorted(HEAVYWEIGHT_JOB_KINDS)
                placeholders = ",".join("?" for _ in heavyweight_kinds)
                active_rows = connection.execute(
                    f"""SELECT job_id, kind FROM jobs
                    WHERE status IN ('queued', 'running') AND kind IN ({placeholders})
                    ORDER BY created_at LIMIT ?""",  # noqa: S608 - placeholders are generated only.
                    [*heavyweight_kinds, HEAVYWEIGHT_JOB_CAPACITY],
                ).fetchall()
                if len(active_rows) >= HEAVYWEIGHT_JOB_CAPACITY:
                    active = active_rows[0]
                    raise DataError(
                        "heavyweight job capacity is occupied by "
                        f"{active['kind']} job {active['job_id']}"
                    )
            connection.execute(
                """INSERT INTO jobs VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, NULL, NULL, 1)""",
                (
                    jid,
                    clean_kind,
                    project_id,
                    experiment_id,
                    request_json,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                "INSERT INTO job_events VALUES (?, 1, 'created', ?, ?)",
                (jid, timestamp, _canonical_json({"status": "queued"}, "job event")),
            )
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (jid,)).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist job")
        return self._job_view(row)

    def heavyweight_job_capacity(self) -> dict[str, object]:
        """Return exact shared heavyweight occupancy without a paginated job scan."""
        heavyweight_kinds = sorted(HEAVYWEIGHT_JOB_KINDS)
        placeholders = ",".join("?" for _ in heavyweight_kinds)
        with self._transaction(write=False) as connection:
            rows = connection.execute(
                f"""SELECT job_id, kind, status, created_at FROM jobs
                WHERE status IN ('queued', 'running') AND kind IN ({placeholders})
                ORDER BY created_at, job_id""",  # noqa: S608 - placeholders are generated only.
                heavyweight_kinds,
            ).fetchall()
        active = [dict(row) for row in rows]
        return {
            "capacity_class": "heavyweight",
            "limit": HEAVYWEIGHT_JOB_CAPACITY,
            "active_count": len(active),
            "busy": len(active) >= HEAVYWEIGHT_JOB_CAPACITY,
            "active_jobs": active,
        }

    @staticmethod
    def _require_job(connection: sqlite3.Connection, job_id: str) -> sqlite3.Row:
        jid = _canonical_uuid(job_id, "job_id")
        row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (jid,)).fetchone()
        if row is None:
            raise DataError(f"unknown control job {jid!r}")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _require_monotonic(prior: object, current: str, field: str) -> None:
        if not isinstance(prior, str) or current < prior:
            raise DataError(f"control {field} precedes prior job update")

    def request_job_cancellation(
        self,
        job_id: str,
        *,
        actor: str,
        reason: str,
        at: datetime | None = None,
    ) -> dict[str, str]:
        """Persist an idempotent cancellation request without signalling an unresolved PID."""
        clean_actor = _required_text(actor, "job cancellation actor", max_length=200)
        clean_reason = _required_text(reason, "job cancellation reason")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            job = self._require_job(connection, job_id)
            if str(job["status"]) in _TERMINAL_JOB_STATUSES:
                return {"job_id": str(job["job_id"]), "status": "already_terminal"}
            if self._active_job_cancellation(connection, job_id):
                return {"job_id": str(job["job_id"]), "status": "cancellation_requested"}
            self._require_monotonic(job["updated_at"], timestamp, "cancellation timestamp")
            sequence = int(job["last_sequence"]) + 1
            payload = {"actor": clean_actor, "reason": clean_reason}
            connection.execute(
                "INSERT INTO job_events VALUES (?, ?, 'cancel_requested', ?, ?)",
                (
                    job_id,
                    sequence,
                    timestamp,
                    _canonical_json(payload, "job cancellation event"),
                ),
            )
            connection.execute(
                "UPDATE jobs SET updated_at = ?, last_sequence = ? WHERE job_id = ?",
                (timestamp, sequence, job_id),
            )
        return {"job_id": job_id, "status": "cancellation_requested"}

    @staticmethod
    def _active_job_cancellation(connection: sqlite3.Connection, job_id: str) -> bool:
        """Return whether the latest cancellation has not been superseded by a resume."""
        rows = connection.execute(
            """SELECT sequence, event_type, payload_json FROM job_events
            WHERE job_id = ? AND event_type IN ('cancel_requested', 'status')
            ORDER BY sequence""",
            (job_id,),
        ).fetchall()
        last_cancel = 0
        last_resume = 0
        for row in rows:
            if row["event_type"] == "cancel_requested":
                last_cancel = int(row["sequence"])
                continue
            payload = _decode_json(row["payload_json"], "job status event")
            if isinstance(payload, dict) and payload.get("resume") is True:
                last_resume = int(row["sequence"])
        return last_cancel > last_resume

    def job_cancellation_requested(self, job_id: str) -> bool:
        """Return whether a durable cancellation request exists for a nonterminal job."""
        with self._transaction(write=False) as connection:
            job = self._require_job(connection, job_id)
            if str(job["status"]) in _TERMINAL_JOB_STATUSES:
                return False
            return self._active_job_cancellation(connection, job_id)

    def append_job_event(
        self,
        job_id: str,
        *,
        event_type: str,
        payload: Mapping[str, object],
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append a bounded non-status job event and advance the durable cursor."""
        clean_type = _required_text(event_type, "job event type", max_length=20)
        if clean_type not in JOB_EVENT_TYPES - {
            "created",
            "status",
            "result",
            "cancel_requested",
        }:
            raise DataError(f"unsupported append-only job event type {event_type!r}")
        clean_payload = _json_object(payload, "job event payload")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            job = self._require_job(connection, job_id)
            if job["status"] in _TERMINAL_JOB_STATUSES:
                raise DataError(f"cannot append to terminal job {job_id!r}")
            self._require_monotonic(job["updated_at"], timestamp, "event timestamp")
            sequence = int(job["last_sequence"]) + 1
            connection.execute(
                "INSERT INTO job_events VALUES (?, ?, ?, ?, ?)",
                (
                    job_id,
                    sequence,
                    clean_type,
                    timestamp,
                    _canonical_json(clean_payload, "job event payload"),
                ),
            )
            heartbeat = timestamp if clean_type == "heartbeat" else job["heartbeat_at"]
            connection.execute(
                """UPDATE jobs SET updated_at = ?, heartbeat_at = ?, last_sequence = ?
                WHERE job_id = ?""",
                (timestamp, heartbeat, sequence, job_id),
            )
            row = connection.execute(
                "SELECT * FROM job_events WHERE job_id = ? AND sequence = ?",
                (job_id, sequence),
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist job event")
        return self._job_event_view(row)

    def append_job_result(
        self,
        job_id: str,
        payload: Mapping[str, object],
        *,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append the typed result payload before a job enters its terminal state."""
        clean_payload = _json_object(payload, "job result")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            job = self._require_job(connection, job_id)
            if job["status"] in _TERMINAL_JOB_STATUSES:
                raise DataError(f"cannot append to terminal job {job_id!r}")
            self._require_monotonic(job["updated_at"], timestamp, "result timestamp")
            sequence = int(job["last_sequence"]) + 1
            connection.execute(
                "INSERT INTO job_events VALUES (?, ?, 'result', ?, ?)",
                (job_id, sequence, timestamp, _canonical_json(clean_payload, "job result")),
            )
            connection.execute(
                "UPDATE jobs SET updated_at = ?, last_sequence = ? WHERE job_id = ?",
                (timestamp, sequence, job_id),
            )
            row = connection.execute(
                "SELECT * FROM job_events WHERE job_id = ? AND sequence = ?",
                (job_id, sequence),
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist job result")
        return self._job_event_view(row)

    def set_job_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        result_run_id: str | None = None,
        terminal_error: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Transition a job and append the transition to its event journal atomically."""
        clean_status = _required_text(status, "job status", max_length=16)
        if clean_status not in JOB_STATUSES:
            raise DataError(f"unsupported job status {status!r}")
        clean_result = None if result_run_id is None else self._require_run(result_run_id)
        clean_error = _optional_text(terminal_error, "job terminal error")
        if clean_status == "failed" and clean_error is None:
            raise DataError("failed job requires terminal_error")
        if clean_status != "failed" and clean_error is not None:
            raise DataError("terminal_error is only valid for failed jobs")
        if clean_status != "succeeded" and clean_result is not None:
            raise DataError("result_run_id is only valid for succeeded jobs")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            job = self._require_job(connection, job_id)
            prior_status = str(job["status"])
            if prior_status in _TERMINAL_JOB_STATUSES:
                raise DataError(f"cannot transition terminal job {job_id!r}")
            if clean_status not in _JOB_TRANSITIONS[prior_status]:
                raise DataError(f"invalid job transition {prior_status!r} -> {clean_status!r}")
            self._require_monotonic(job["updated_at"], timestamp, "status timestamp")
            sequence = int(job["last_sequence"]) + 1
            payload = {"from": prior_status, "to": clean_status}
            connection.execute(
                "INSERT INTO job_events VALUES (?, ?, 'status', ?, ?)",
                (job_id, sequence, timestamp, _canonical_json(payload, "job status event")),
            )
            connection.execute(
                """UPDATE jobs SET status = ?, updated_at = ?, heartbeat_at = ?,
                result_run_id = ?, terminal_error = ?, last_sequence = ? WHERE job_id = ?""",
                (
                    clean_status,
                    timestamp,
                    timestamp,
                    clean_result,
                    clean_error,
                    sequence,
                    job_id,
                ),
            )
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist job status")
        return self._job_view(row)

    def get_job(
        self,
        job_id: str,
        *,
        event_limit: int = 200,
        event_offset: int = 0,
        event_tail: bool = False,
    ) -> dict[str, object]:
        """Read one job and a SQL-bounded chronological window of its event journal."""
        event_limit, event_offset = _page(event_limit, event_offset)
        if not isinstance(event_tail, bool):
            raise DataError("control event_tail must be a boolean")
        query = (
            """SELECT * FROM job_events WHERE job_id = ?
            ORDER BY sequence DESC LIMIT ? OFFSET ?"""
            if event_tail
            else """SELECT * FROM job_events WHERE job_id = ?
            ORDER BY sequence ASC LIMIT ? OFFSET ?"""
        )
        with self._transaction(write=False) as connection:
            job = self._job_view(self._require_job(connection, job_id))
            events = connection.execute(
                query,
                (job["job_id"], event_limit, event_offset),
            ).fetchall()
        if event_tail:
            events.reverse()
        event_total = job["last_sequence"]
        if isinstance(event_total, bool) or not isinstance(event_total, int) or event_total < 0:
            raise DataError("control job has an invalid last_sequence invariant")
        events_has_more = event_offset + len(events) < event_total
        job["events"] = [self._job_event_view(row) for row in events]
        job["event_total"] = event_total
        job["event_limit"] = event_limit
        job["event_offset"] = event_offset
        job["event_tail"] = event_tail
        job["events_has_more"] = events_has_more
        job["events_truncated"] = events_has_more
        return job

    def list_jobs(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, object]]:
        """Return bounded durable job summaries, newest first."""
        limit, offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY updated_at DESC, job_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._job_view(row) for row in rows]

    def reconcile_interrupted_jobs(
        self,
        *,
        reason: str = "process restarted before terminal job status",
        stale_after_seconds: int = 60,
        at: datetime | None = None,
    ) -> list[dict[str, object]]:
        """Fail only nonterminal journals whose durable heartbeat lease is stale."""
        clean_reason = _required_text(reason, "job reconciliation reason")
        if isinstance(stale_after_seconds, bool) or not 30 <= stale_after_seconds <= 86_400:
            raise DataError("job stale_after_seconds must be in 30..86400")
        current = datetime.now(UTC) if at is None else at
        timestamp = _at(current)
        stale_before = _format_timestamp(current - timedelta(seconds=stale_after_seconds))
        reconciled: list[dict[str, object]] = []
        with self._transaction(write=True) as connection:
            rows = connection.execute(
                """SELECT * FROM jobs
                WHERE status IN ('queued', 'running') AND heartbeat_at <= ?
                ORDER BY created_at""",
                (stale_before,),
            ).fetchall()
            for job in rows:
                self._require_monotonic(job["updated_at"], timestamp, "reconciliation timestamp")
                sequence = int(job["last_sequence"]) + 1
                payload = {"from": job["status"], "to": "failed", "reason": clean_reason}
                connection.execute(
                    "INSERT INTO job_events VALUES (?, ?, 'status', ?, ?)",
                    (
                        job["job_id"],
                        sequence,
                        timestamp,
                        _canonical_json(payload, "job reconciliation event"),
                    ),
                )
                connection.execute(
                    """UPDATE jobs SET status = 'failed', updated_at = ?, heartbeat_at = ?,
                    terminal_error = ?, last_sequence = ? WHERE job_id = ?""",
                    (timestamp, timestamp, clean_reason, sequence, job["job_id"]),
                )
                current = connection.execute(
                    "SELECT * FROM jobs WHERE job_id = ?", (job["job_id"],)
                ).fetchone()
                if current is None:  # pragma: no cover
                    raise DataError("control store lost a job during reconciliation")
                reconciled.append(self._job_view(current))
        return reconciled

    def _validate_evidence_links(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str | None,
        strategy_version_id: str | None,
        experiment_id: str | None,
    ) -> None:
        if project_id is None:
            if strategy_version_id is not None or experiment_id is not None:
                raise DataError("evidence version/experiment links require project_id")
            return
        self._require_project(connection, project_id)
        if strategy_version_id is not None:
            _require_content_id(strategy_version_id, "strategy_version_id", prefix="sv")
            if (
                connection.execute(
                    "SELECT 1 FROM project_versions WHERE project_id = ? AND version_id = ?",
                    (project_id, strategy_version_id),
                ).fetchone()
                is None
            ):
                raise DataError("evidence strategy version is not linked to the project")
        if experiment_id is not None:
            self._require_project_experiment(connection, project_id, experiment_id)
            if strategy_version_id is not None:
                experiment = connection.execute(
                    "SELECT strategy_version_id FROM experiment_specs WHERE experiment_id = ?",
                    (experiment_id,),
                ).fetchone()
                if experiment is None:  # pragma: no cover - guarded by project link above
                    raise DataError("corrupt control store: linked evidence experiment is missing")
                if experiment["strategy_version_id"] != strategy_version_id:
                    raise DataError(
                        "evidence strategy version does not match the experiment lineage"
                    )

    @staticmethod
    def _validate_contradictions(
        connection: sqlite3.Connection,
        *,
        evidence_id: str,
        contradiction_ids: Sequence[str],
    ) -> None:
        for contradiction_id in contradiction_ids:
            if contradiction_id == evidence_id:
                raise DataError("evidence cannot contradict itself")
            if (
                connection.execute(
                    "SELECT 1 FROM evidence_items WHERE evidence_id = ?", (contradiction_id,)
                ).fetchone()
                is None
            ):
                raise DataError(f"unknown contradiction evidence {contradiction_id!r}")

    def _validate_evidence_citation(
        self,
        *,
        run_id: str,
        artifact: str,
        field: str,
        row_selector: Mapping[str, object],
        metric_name: str | None = None,
        metric_value: float | None = None,
        metric_unit: str | None = None,
    ) -> None:
        """Resolve an exact immutable artifact/field/row citation before it enters the ledger."""
        rdir, manifest = self._verified_run(run_id)
        path = rdir / artifact
        if path.parent != rdir or not path.is_file() or path.is_symlink():
            raise DataError(f"evidence source artifact {artifact!r} does not exist in run {run_id}")

        if artifact == "manifest.json":
            current: object = manifest
            parent: Mapping[str, object] | None = None
            for segment in field.split("."):
                if not segment or not isinstance(current, Mapping) or segment not in current:
                    raise DataError(
                        f"evidence source field {field!r} does not resolve in {artifact!r}"
                    )
                parent = current
                current = current[segment]
            if row_selector:
                raise DataError("manifest evidence citations do not accept a row selector")
            if parent is None:  # pragma: no cover - an empty field cannot pass the loop above
                raise DataError("evidence source field must not be empty")
            self._validate_cited_metric(
                value=current,
                metadata=parent,
                field=field.rsplit(".", 1)[-1],
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
            )
            return

        if path.suffix != ".parquet":
            raise DataError("evidence source artifact must be manifest.json or Parquet")
        try:
            schema = pl.read_parquet_schema(path)
            if field not in schema:
                raise DataError(f"evidence source field {field!r} does not exist in {artifact!r}")
            frame = pl.read_parquet(path)
            row_index = row_selector.get("row_index")
            predicates = {key: value for key, value in row_selector.items() if key != "row_index"}
            if row_index is not None:
                if (
                    isinstance(row_index, bool)
                    or not isinstance(row_index, int)
                    or row_index < 0
                    or row_index >= frame.height
                ):
                    raise DataError("evidence row_selector.row_index is outside the artifact")
                frame = frame.slice(row_index, 1)
            for key, value in predicates.items():
                if key not in schema:
                    raise DataError(f"evidence row selector field {key!r} does not exist")
                if value is None or isinstance(value, (str, bool, int, float)):
                    frame = frame.filter(pl.col(key) == value)
                else:
                    raise DataError("evidence row selector values must be scalar")
        except DataError:
            raise
        except (OSError, pl.exceptions.PolarsError, TypeError) as exc:
            raise DataError(f"cannot resolve evidence source artifact {artifact!r}") from exc
        if frame.height != 1:
            raise DataError(
                f"evidence row selector must resolve exactly one row, resolved {frame.height}"
            )
        row = frame.row(0, named=True)
        self._validate_cited_metric(
            value=row[field],
            metadata=row,
            field=field,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
        )

    @staticmethod
    def _cited_text_metadata(
        metadata: Mapping[str, object],
        *,
        keys: Sequence[str],
        label: str,
    ) -> str | None:
        values = {
            _required_text(metadata[key], f"cited artifact {label}")
            for key in keys
            if key in metadata
        }
        if len(values) > 1:
            raise DataError(f"cited artifact carries conflicting {label} metadata")
        return next(iter(values), None)

    @classmethod
    def _validate_cited_metric(
        cls,
        *,
        value: object,
        metadata: Mapping[str, object],
        field: str,
        metric_name: str | None,
        metric_value: float | None,
        metric_unit: str | None,
    ) -> None:
        supplied = (metric_name is not None, metric_value is not None, metric_unit is not None)
        if not any(supplied):
            return
        if not all(supplied):
            raise DataError("evidence metric name, value, and unit must be supplied together")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DataError("evidence cited metric field must be a numeric scalar")
        cited_value = float(value)
        if not math.isfinite(cited_value):
            raise DataError("evidence cited metric field must be finite")
        if cited_value != metric_value:
            raise DataError("evidence metric_value does not match the cited artifact scalar")

        name_keys = tuple(key for key in (f"{field}_name", "metric_name", "metric") if key != field)
        cited_name = cls._cited_text_metadata(
            metadata,
            keys=name_keys,
            label="metric name",
        )
        if cited_name is None:
            cited_name = field
        if cited_name != metric_name:
            raise DataError("evidence metric_name does not match the cited artifact metric")

        cited_unit = cls._cited_text_metadata(
            metadata,
            keys=(f"{field}_unit", "metric_unit", "unit"),
            label="metric unit",
        )
        if cited_unit is None:
            raise DataError("evidence cited artifact does not carry an explicit metric unit")
        if cited_unit != metric_unit:
            raise DataError("evidence metric_unit does not match the cited artifact unit")

    def _validate_correlation_evidence(
        self,
        *,
        assets: Sequence[str],
        timeframe: str,
        metric_name: str | None,
        metric_value: float | None,
        metric_unit: str | None,
        run_id: str,
        artifact: str,
        row_selector: Mapping[str, object],
    ) -> None:
        """Fail closed on association claims without aligned, snapshot-compatible OOS evidence."""
        if len(assets) < 2:
            raise DataError("correlation evidence requires at least two assets")
        if not artifact.endswith(".parquet"):
            raise DataError("correlation evidence requires a cited Parquet report row")
        if metric_name is None or metric_value is None or metric_unit is None:
            raise DataError(
                "correlation evidence requires an explicit metric name, value, and unit"
            )
        sample_count = row_selector.get("sample_count")
        if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count <= 0:
            raise DataError("correlation evidence requires a positive integer sample_count")
        if row_selector.get("aligned_oos") is not True:
            raise DataError("correlation evidence requires aligned_oos=true")
        if row_selector.get("frequency") != timeframe:
            raise DataError("correlation evidence frequency must match its timeframe")
        if row_selector.get("association_not_causation") is not True:
            raise DataError("correlation evidence must be labeled association, not causation")
        oos_start = row_selector.get("oos_start")
        oos_end = row_selector.get("oos_end")
        if not isinstance(oos_start, str) or not isinstance(oos_end, str) or oos_start >= oos_end:
            raise DataError("correlation evidence requires an ordered aligned OOS period")
        snapshot_hash = row_selector.get("snapshot_hash")
        if (
            not isinstance(snapshot_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", snapshot_hash) is None
        ):
            raise DataError("correlation evidence requires a 64-hex snapshot_hash")
        _, manifest = self._verified_run(run_id)
        if manifest.get("snapshot_hash") != snapshot_hash:
            raise DataError("correlation evidence snapshot_hash does not match its source run")

    def _evidence_values(
        self,
        *,
        claim: str,
        assets: Sequence[str],
        frozen_universe: Sequence[str],
        timeframe: str,
        method: str,
        knowledge_at: datetime,
        market_data_cutoff: datetime | None,
        project_id: str | None,
        strategy_version_id: str | None,
        experiment_id: str | None,
        metric_name: str | None,
        metric_value: float | None,
        metric_unit: str | None,
        source_run_id: str | None,
        source_artifact: str | None,
        source_field: str | None,
        row_selector: Mapping[str, object],
        counterevidence: Sequence[str],
        contradiction_ids: Sequence[str],
        author: str,
        author_kind: AuthorKind,
    ) -> dict[str, object]:
        knowledge = _format_timestamp(knowledge_at)
        cutoff = None if market_data_cutoff is None else _format_timestamp(market_data_cutoff)
        if cutoff is not None and cutoff > knowledge:
            raise DataError("evidence market_data_cutoff must not follow knowledge_at")
        clean_kind = _required_text(author_kind, "evidence author kind", max_length=16)
        if clean_kind not in AUTHOR_KINDS:
            raise DataError(f"unsupported evidence author kind {author_kind!r}")
        if metric_value is not None and (
            isinstance(metric_value, bool)
            or not isinstance(metric_value, int | float)
            or not math.isfinite(metric_value)
        ):
            raise DataError("evidence metric_value must be finite and numeric")
        clean_metric_name = _optional_text(metric_name, "evidence metric name")
        clean_metric_unit = _optional_text(metric_unit, "evidence metric unit")
        metric_parts = (
            clean_metric_name is not None,
            metric_value is not None,
            clean_metric_unit is not None,
        )
        if any(metric_parts) and not all(metric_parts):
            raise DataError("evidence metric name, value, and unit must be supplied together")
        clean_run = (
            None if source_run_id is None else self._require_generic_evidence_run(source_run_id)
        )
        clean_artifact = _optional_text(source_artifact, "evidence source artifact")
        clean_field = _optional_text(source_field, "evidence source field")
        if clean_artifact is not None and _ARTIFACT_RE.fullmatch(clean_artifact) is None:
            raise DataError("evidence source_artifact must be a filename, not a path")
        source_parts = (clean_run, clean_artifact, clean_field)
        if not all(part is not None for part in source_parts):
            raise DataError("evidence source requires run_id, artifact, and field together")
        clean_assets = _symbols(assets)
        clean_universe = _symbols(frozen_universe)
        if not set(clean_assets).issubset(clean_universe):
            raise DataError("evidence assets must be contained in the frozen universe")
        clean_contradictions = _evidence_ids(contradiction_ids)
        clean_selector = _json_object(row_selector, "evidence row selector")
        clean_timeframe = _required_text(timeframe, "evidence timeframe", max_length=32)
        clean_method = _required_text(method, "evidence method", max_length=200)
        if clean_method in ASSOCIATION_METHODS:
            self._validate_correlation_evidence(
                assets=clean_assets,
                timeframe=clean_timeframe,
                metric_name=clean_metric_name,
                metric_value=metric_value,
                metric_unit=clean_metric_unit,
                run_id=cast(str, clean_run),
                artifact=cast(str, clean_artifact),
                row_selector=clean_selector,
            )
        elif _is_association_like(clean_method):
            raise DataError(
                "unsupported association method identifier; use one of "
                + ", ".join(sorted(ASSOCIATION_METHODS))
            )
        elif clean_metric_name is not None and _is_association_like(clean_metric_name):
            raise DataError("association-like metrics require an allowed association method")
        self._validate_evidence_citation(
            run_id=cast(str, clean_run),
            artifact=cast(str, clean_artifact),
            field=cast(str, clean_field),
            row_selector=clean_selector,
            metric_name=clean_metric_name,
            metric_value=metric_value,
            metric_unit=clean_metric_unit,
        )
        return {
            "claim": _required_text(claim, "evidence claim"),
            "assets_json": _canonical_json(clean_assets, "evidence assets"),
            "frozen_universe_json": _canonical_json(clean_universe, "evidence frozen universe"),
            "timeframe": clean_timeframe,
            "method": clean_method,
            "market_data_cutoff": cutoff,
            "knowledge_at": knowledge,
            "project_id": project_id,
            "strategy_version_id": strategy_version_id,
            "experiment_id": experiment_id,
            "metric_name": clean_metric_name,
            "metric_value": metric_value,
            "metric_unit": clean_metric_unit,
            "source_run_id": clean_run,
            "source_artifact": clean_artifact,
            "source_field": clean_field,
            "row_selector_json": _canonical_json(clean_selector, "evidence row selector"),
            "counterevidence_json": _canonical_json(
                _strings(counterevidence, "counterevidence"), "counterevidence"
            ),
            "contradiction_ids_json": _canonical_json(clean_contradictions, "contradiction ids"),
            "contradiction_ids": clean_contradictions,
            "author": _required_text(author, "evidence author", max_length=200),
            "author_kind": clean_kind,
        }

    @staticmethod
    def _evidence_view(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["assets"] = _decode_json(result.pop("assets_json"), "evidence assets")
        result["frozen_universe"] = _decode_json(
            result.pop("frozen_universe_json"), "evidence frozen universe"
        )
        result["row_selector"] = _decode_json(
            result.pop("row_selector_json"), "evidence row selector"
        )
        result["counterevidence"] = _decode_json(
            result.pop("counterevidence_json"), "counterevidence"
        )
        result["contradiction_ids"] = _decode_json(
            result.pop("contradiction_ids_json"), "contradiction ids"
        )
        result["interpretation_label"] = (
            "association, not causation" if _is_association_like(str(result["method"])) else None
        )
        return result

    def create_evidence(
        self,
        *,
        claim: str,
        assets: Sequence[str],
        frozen_universe: Sequence[str],
        timeframe: str,
        method: str,
        knowledge_at: datetime,
        author: str,
        author_kind: AuthorKind,
        market_data_cutoff: datetime | None = None,
        project_id: str | None = None,
        strategy_version_id: str | None = None,
        experiment_id: str | None = None,
        metric_name: str | None = None,
        metric_value: float | None = None,
        metric_unit: str | None = None,
        source_run_id: str | None = None,
        source_artifact: str | None = None,
        source_field: str | None = None,
        row_selector: Mapping[str, object] | None = None,
        counterevidence: Sequence[str] = (),
        contradiction_ids: Sequence[str] = (),
        evidence_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Create revision one. New human and agent records always begin as draft."""
        eid = _new_uuid(evidence_id, "evidence_id")
        timestamp = _at(at)
        values = self._evidence_values(
            claim=claim,
            assets=assets,
            frozen_universe=frozen_universe,
            timeframe=timeframe,
            method=method,
            knowledge_at=knowledge_at,
            market_data_cutoff=market_data_cutoff,
            project_id=project_id,
            strategy_version_id=strategy_version_id,
            experiment_id=experiment_id,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
            source_run_id=source_run_id,
            source_artifact=source_artifact,
            source_field=source_field,
            row_selector=row_selector or {},
            counterevidence=counterevidence,
            contradiction_ids=contradiction_ids,
            author=author,
            author_kind=author_kind,
        )
        if timestamp < str(values["knowledge_at"]):
            raise DataError("evidence revision timestamp precedes knowledge_at")
        with self._transaction(write=True) as connection:
            self._validate_evidence_links(
                connection,
                project_id=project_id,
                strategy_version_id=strategy_version_id,
                experiment_id=experiment_id,
            )
            self._validate_contradictions(
                connection,
                evidence_id=eid,
                contradiction_ids=cast(list[str], values["contradiction_ids"]),
            )
            if (
                connection.execute(
                    "SELECT 1 FROM evidence_items WHERE evidence_id = ?", (eid,)
                ).fetchone()
                is not None
            ):
                raise DataError(f"evidence item {eid!r} already exists")
            connection.execute("INSERT INTO evidence_items VALUES (?, ?)", (eid, timestamp))
            self._insert_evidence_revision(
                connection,
                evidence_id=eid,
                revision=1,
                parent_revision=None,
                status="draft",
                values=values,
                created_at=timestamp,
            )
            row = connection.execute(
                "SELECT * FROM evidence_revisions WHERE evidence_id = ? AND revision = 1",
                (eid,),
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist evidence")
        return self._evidence_view(row)

    @staticmethod
    def _insert_evidence_revision(
        connection: sqlite3.Connection,
        *,
        evidence_id: str,
        revision: int,
        parent_revision: int | None,
        status: str,
        values: Mapping[str, object],
        created_at: str,
    ) -> None:
        connection.execute(
            """INSERT INTO evidence_revisions (
                evidence_id, revision, parent_revision, status, claim, assets_json,
                frozen_universe_json,
                timeframe, method,
                market_data_cutoff, knowledge_at, project_id, strategy_version_id,
                experiment_id, metric_name, metric_value, metric_unit, source_run_id,
                source_artifact, source_field, row_selector_json, counterevidence_json,
                contradiction_ids_json,
                author, author_kind, created_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                evidence_id,
                revision,
                parent_revision,
                status,
                values["claim"],
                values["assets_json"],
                values["frozen_universe_json"],
                values["timeframe"],
                values["method"],
                values["market_data_cutoff"],
                values["knowledge_at"],
                values["project_id"],
                values["strategy_version_id"],
                values["experiment_id"],
                values["metric_name"],
                values["metric_value"],
                values["metric_unit"],
                values["source_run_id"],
                values["source_artifact"],
                values["source_field"],
                values["row_selector_json"],
                values["counterevidence_json"],
                values["contradiction_ids_json"],
                values["author"],
                values["author_kind"],
                created_at,
            ),
        )

    def revise_evidence(
        self,
        evidence_id: str,
        *,
        status: EvidenceStatus,
        author: str,
        author_kind: AuthorKind,
        claim: str | None = None,
        counterevidence: Sequence[str] | None = None,
        contradiction_ids: Sequence[str] | None = None,
        source_run_id: str | None = None,
        source_artifact: str | None = None,
        source_field: str | None = None,
        row_selector: Mapping[str, object] | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Append a validated revision; prior revisions are never updated or deleted."""
        eid = _canonical_uuid(evidence_id, "evidence_id")
        clean_status = _required_text(status, "evidence status", max_length=16)
        if clean_status not in EVIDENCE_STATUSES:
            raise DataError(f"unsupported evidence status {status!r}")
        timestamp = _at(at)
        with self._transaction(write=True) as connection:
            prior = connection.execute(
                """SELECT * FROM evidence_revisions WHERE evidence_id = ?
                ORDER BY revision DESC LIMIT 1""",
                (eid,),
            ).fetchone()
            if prior is None:
                raise DataError(f"unknown evidence item {eid!r}")
            if not isinstance(prior["created_at"], str) or timestamp < prior["created_at"]:
                raise DataError("evidence revision timestamp precedes prior revision")
            prior_status = str(prior["status"])
            if clean_status not in _EVIDENCE_TRANSITIONS[prior_status]:
                raise DataError(f"invalid evidence transition {prior_status!r} -> {clean_status!r}")
            source = (
                source_run_id if source_run_id is not None else prior["source_run_id"],
                source_artifact if source_artifact is not None else prior["source_artifact"],
                source_field if source_field is not None else prior["source_field"],
            )
            prior_assets = _decode_json(prior["assets_json"], "evidence assets")
            prior_universe = _decode_json(prior["frozen_universe_json"], "evidence frozen universe")
            prior_counter = _decode_json(prior["counterevidence_json"], "counterevidence")
            prior_contradictions = _decode_json(
                prior["contradiction_ids_json"], "contradiction ids"
            )
            prior_selector = _decode_json(prior["row_selector_json"], "evidence row selector")
            if not isinstance(prior_assets, list) or not all(
                isinstance(item, str) for item in prior_assets
            ):
                raise DataError("corrupt control store: invalid evidence assets")
            if not isinstance(prior_counter, list) or not all(
                isinstance(item, str) for item in prior_counter
            ):
                raise DataError("corrupt control store: invalid evidence counterevidence")
            if not isinstance(prior_universe, list) or not all(
                isinstance(item, str) for item in prior_universe
            ):
                raise DataError("corrupt control store: invalid evidence frozen universe")
            if not isinstance(prior_contradictions, list) or not all(
                isinstance(item, str) for item in prior_contradictions
            ):
                raise DataError("corrupt control store: invalid evidence contradiction ids")
            if not isinstance(prior_selector, dict):
                raise DataError("corrupt control store: invalid evidence row selector")
            knowledge = parse_timestamp(str(prior["knowledge_at"]), "evidence knowledge_at")
            cutoff_raw = prior["market_data_cutoff"]
            cutoff = (
                None
                if cutoff_raw is None
                else parse_timestamp(str(cutoff_raw), "evidence market_data_cutoff")
            )
            values = self._evidence_values(
                claim=str(prior["claim"]) if claim is None else claim,
                assets=prior_assets,
                frozen_universe=prior_universe,
                timeframe=str(prior["timeframe"]),
                method=str(prior["method"]),
                knowledge_at=knowledge,
                market_data_cutoff=cutoff,
                project_id=None if prior["project_id"] is None else str(prior["project_id"]),
                strategy_version_id=(
                    None
                    if prior["strategy_version_id"] is None
                    else str(prior["strategy_version_id"])
                ),
                experiment_id=(
                    None if prior["experiment_id"] is None else str(prior["experiment_id"])
                ),
                metric_name=None if prior["metric_name"] is None else str(prior["metric_name"]),
                metric_value=(
                    None if prior["metric_value"] is None else float(prior["metric_value"])
                ),
                metric_unit=None if prior["metric_unit"] is None else str(prior["metric_unit"]),
                source_run_id=None if source[0] is None else str(source[0]),
                source_artifact=None if source[1] is None else str(source[1]),
                source_field=None if source[2] is None else str(source[2]),
                row_selector=prior_selector if row_selector is None else row_selector,
                counterevidence=(prior_counter if counterevidence is None else counterevidence),
                contradiction_ids=(
                    prior_contradictions if contradiction_ids is None else contradiction_ids
                ),
                author=author,
                author_kind=author_kind,
            )
            self._validate_evidence_links(
                connection,
                project_id=cast(str | None, values["project_id"]),
                strategy_version_id=cast(str | None, values["strategy_version_id"]),
                experiment_id=cast(str | None, values["experiment_id"]),
            )
            revision = int(prior["revision"]) + 1
            self._validate_contradictions(
                connection,
                evidence_id=eid,
                contradiction_ids=cast(list[str], values["contradiction_ids"]),
            )
            self._insert_evidence_revision(
                connection,
                evidence_id=eid,
                revision=revision,
                parent_revision=int(prior["revision"]),
                status=clean_status,
                values=values,
                created_at=timestamp,
            )
            row = connection.execute(
                "SELECT * FROM evidence_revisions WHERE evidence_id = ? AND revision = ?",
                (eid, revision),
            ).fetchone()
        if row is None:  # pragma: no cover
            raise DataError("control store failed to persist evidence revision")
        return self._evidence_view(row)

    def get_evidence(self, evidence_id: str) -> dict[str, object]:
        """Return the current evidence projection with its complete revision history."""
        eid = _canonical_uuid(evidence_id, "evidence_id")
        with self._transaction(write=False) as connection:
            rows = connection.execute(
                "SELECT * FROM evidence_revisions WHERE evidence_id = ? ORDER BY revision",
                (eid,),
            ).fetchall()
        if not rows:
            raise DataError(f"unknown evidence item {eid!r}")
        current = self._evidence_view(rows[-1])
        current["revisions"] = [self._evidence_view(row) for row in rows]
        return current

    def list_evidence(
        self,
        *,
        asset: str | None = None,
        project_id: str | None = None,
        status: EvidenceStatus | None = None,
        as_of: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        """List latest revisions, with point-in-time knowledge and revision filtering."""
        limit, offset = _page(limit, offset)
        clean_asset = None if asset is None else _symbols([asset])[0]
        clean_status: str | None = status
        if clean_status is not None and clean_status not in EVIDENCE_STATUSES:
            raise DataError(f"unsupported evidence status {status!r}")
        if project_id is not None:
            _canonical_uuid(project_id, "project_id")
        cutoff = None if as_of is None else _format_timestamp(as_of)
        where = ""
        params: list[object] = []
        if cutoff is not None:
            where = "WHERE knowledge_at <= ? AND created_at <= ?"
            params.extend([cutoff, cutoff])
        query = f"""WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY evidence_id ORDER BY revision DESC
            ) AS rank FROM evidence_revisions {where}
        ) SELECT * FROM ranked WHERE rank = 1 ORDER BY created_at DESC, evidence_id"""
        with self._transaction(write=False) as connection:
            rows = connection.execute(query, params).fetchall()
        filtered: list[dict[str, object]] = []
        for row in rows:
            view = self._evidence_view(row)
            view.pop("rank", None)
            assets = view["assets"]
            if clean_asset is not None and (
                not isinstance(assets, list) or clean_asset not in assets
            ):
                continue
            if project_id is not None and view["project_id"] != project_id:
                continue
            if clean_status is not None and view["status"] != clean_status:
                continue
            filtered.append(view)
        return filtered[offset : offset + limit]

    def create_owner_enrollment_request(
        self,
        *,
        token_hash: str,
        reason: str,
        replace_existing: bool,
        now: datetime,
        expires_at: datetime,
        request_id: str | None = None,
    ) -> dict[str, object]:
        """Record the trusted-CLI half of a short-lived owner enrollment ceremony."""
        rid = _new_uuid(request_id, "owner enrollment request_id")
        digest = _required_text(token_hash, "owner enrollment token hash", max_length=64)
        if _SHA256_RE.fullmatch(digest) is None:
            raise DataError("invalid control owner enrollment token hash")
        clean_reason = _required_text(reason, "owner enrollment reason")
        created = _format_timestamp(now)
        expires = _format_timestamp(expires_at)
        if expires_at <= now:
            raise DataError("owner enrollment request expiry must be after creation")
        with self._transaction(write=True) as connection:
            active = int(
                connection.execute(
                    "SELECT COUNT(*) FROM owner_credentials WHERE revoked_at IS NULL"
                ).fetchone()[0]
            )
            if active and not replace_existing:
                raise DataError(
                    "an owner credential is already enrolled; use the trusted replacement ceremony"
                )
            connection.execute(
                """INSERT INTO owner_enrollment_requests
                (request_id, token_hash, replace_existing, reason, created_at, expires_at, used_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL)""",
                (rid, digest, int(replace_existing), clean_reason, created, expires),
            )
            connection.execute(
                """INSERT INTO owner_credential_events
                (event_id, credential_id, event_type, reason, occurred_at)
                VALUES (?, NULL, 'enrollment_requested', ?, ?)""",
                (str(uuid.uuid4()), clean_reason, created),
            )
        return {
            "request_id": rid,
            "replace_existing": replace_existing,
            "created_at": created,
            "expires_at": expires,
        }

    def get_owner_enrollment_request(self, *, token_hash: str, now: datetime) -> dict[str, object]:
        digest = _required_text(token_hash, "owner enrollment token hash", max_length=64)
        timestamp = _format_timestamp(now)
        with self._transaction(write=False) as connection:
            row = connection.execute(
                "SELECT * FROM owner_enrollment_requests WHERE token_hash = ?", (digest,)
            ).fetchone()
        if row is None or row["used_at"] is not None:
            raise DataError("owner enrollment request is invalid or already used")
        if str(row["expires_at"]) <= timestamp:
            raise DataError("owner enrollment request has expired")
        return {
            "request_id": str(row["request_id"]),
            "replace_existing": bool(row["replace_existing"]),
            "reason": str(row["reason"]),
            "expires_at": str(row["expires_at"]),
        }

    def create_owner_auth_challenge(
        self,
        *,
        ceremony: Literal["registration", "action"],
        challenge: bytes,
        binding: Mapping[str, object],
        now: datetime,
        expires_at: datetime,
        enrollment_request_id: str | None = None,
        challenge_id: str | None = None,
    ) -> dict[str, object]:
        cid = _new_uuid(challenge_id, "owner auth challenge_id")
        if not isinstance(challenge, bytes) or len(challenge) != 32:
            raise DataError("owner auth challenge must contain exactly 32 random bytes")
        created = _format_timestamp(now)
        expires = _format_timestamp(expires_at)
        if expires_at <= now or expires_at - now > timedelta(seconds=60):
            raise DataError("owner auth challenge lifetime must be in 1..60 seconds")
        clean_binding = _json_object(binding, "owner auth binding")
        enrollment_id = (
            None
            if enrollment_request_id is None
            else _canonical_uuid(enrollment_request_id, "owner enrollment request_id")
        )
        if ceremony == "registration" and enrollment_id is None:
            raise DataError("registration challenge requires an enrollment request")
        if ceremony == "action" and enrollment_id is not None:
            raise DataError("action challenge cannot carry an enrollment request")
        with self._transaction(write=True) as connection:
            if ceremony == "action":
                active = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM owner_credentials WHERE revoked_at IS NULL"
                    ).fetchone()[0]
                )
                if not active:
                    raise DataError("owner Touch ID credential is not enrolled")
            connection.execute(
                """INSERT INTO owner_auth_challenges
                (challenge_id, ceremony, challenge, enrollment_request_id, binding_json,
                 created_at, expires_at, used_at, verified_credential_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
                (
                    cid,
                    ceremony,
                    challenge,
                    enrollment_id,
                    _canonical_json(clean_binding, "owner auth binding"),
                    created,
                    expires,
                ),
            )
        return {"challenge_id": cid, "expires_at": expires, "binding": clean_binding}

    def get_owner_auth_challenge(
        self,
        challenge_id: str,
        *,
        ceremony: Literal["registration", "action"],
        now: datetime,
    ) -> dict[str, object]:
        cid = _canonical_uuid(challenge_id, "owner auth challenge_id")
        timestamp = _format_timestamp(now)
        with self._transaction(write=False) as connection:
            row = connection.execute(
                "SELECT * FROM owner_auth_challenges WHERE challenge_id = ?", (cid,)
            ).fetchone()
        if row is None or row["ceremony"] != ceremony or row["used_at"] is not None:
            raise DataError("owner auth challenge is invalid or already used")
        if str(row["expires_at"]) <= timestamp:
            raise DataError("owner auth challenge has expired")
        binding = _decode_json(row["binding_json"], "owner auth binding")
        if not isinstance(binding, dict):
            raise DataError("corrupt control store: owner auth binding is not an object")
        return {
            "challenge_id": cid,
            "challenge": bytes(row["challenge"]),
            "enrollment_request_id": row["enrollment_request_id"],
            "binding": binding,
            "expires_at": str(row["expires_at"]),
        }

    def list_active_owner_credentials(self) -> list[dict[str, object]]:
        with self._transaction(write=False) as connection:
            rows = connection.execute(
                """SELECT credential_id, public_key, sign_count, actor, transports_json, created_at
                FROM owner_credentials WHERE revoked_at IS NULL
                ORDER BY created_at, credential_id"""
            ).fetchall()
        return [
            {
                "credential_id": str(row["credential_id"]),
                "public_key": bytes(row["public_key"]),
                "sign_count": int(row["sign_count"]),
                "actor": str(row["actor"]),
                "transports": _decode_json(row["transports_json"], "owner credential transports"),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def complete_owner_registration(
        self,
        *,
        token_hash: str,
        challenge_id: str,
        credential_id: str,
        public_key: bytes,
        sign_count: int,
        transports: Sequence[str],
        now: datetime,
    ) -> dict[str, object]:
        digest = _required_text(token_hash, "owner enrollment token hash", max_length=64)
        cid = _canonical_uuid(challenge_id, "owner auth challenge_id")
        encoded_credential = _required_text(credential_id, "owner credential_id", max_length=2048)
        if not isinstance(public_key, bytes) or not public_key:
            raise DataError("owner credential public key is required")
        if isinstance(sign_count, bool) or sign_count < 0:
            raise DataError("owner credential signature counter must be non-negative")
        clean_transports = _strings(transports, "owner credential transport", limit=16)
        timestamp = _format_timestamp(now)
        actor = f"owner:{hashlib.sha256(encoded_credential.encode()).hexdigest()[:16]}"
        with self._transaction(write=True) as connection:
            enrollment = connection.execute(
                "SELECT * FROM owner_enrollment_requests WHERE token_hash = ?", (digest,)
            ).fetchone()
            challenge = connection.execute(
                "SELECT * FROM owner_auth_challenges WHERE challenge_id = ?", (cid,)
            ).fetchone()
            if (
                enrollment is None
                or enrollment["used_at"] is not None
                or str(enrollment["expires_at"]) <= timestamp
                or challenge is None
                or challenge["ceremony"] != "registration"
                or challenge["used_at"] is not None
                or str(challenge["expires_at"]) <= timestamp
                or challenge["enrollment_request_id"] != enrollment["request_id"]
            ):
                raise DataError("owner registration ceremony is invalid, expired, or already used")
            existing = connection.execute(
                "SELECT credential_id FROM owner_credentials WHERE revoked_at IS NULL"
            ).fetchall()
            replace = bool(enrollment["replace_existing"])
            if existing and not replace:
                raise DataError("owner credential replacement requires a trusted CLI ceremony")
            for row in existing:
                prior = str(row["credential_id"])
                connection.execute(
                    "UPDATE owner_credentials SET revoked_at = ? WHERE credential_id = ?",
                    (timestamp, prior),
                )
                connection.execute(
                    """INSERT INTO owner_credential_events
                    (event_id, credential_id, event_type, reason, occurred_at)
                    VALUES (?, ?, 'replaced', ?, ?)""",
                    (str(uuid.uuid4()), prior, str(enrollment["reason"]), timestamp),
                )
            connection.execute(
                """INSERT INTO owner_credentials
                (credential_id, public_key, sign_count, actor, transports_json, created_at,
                 revoked_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL)""",
                (
                    encoded_credential,
                    public_key,
                    sign_count,
                    actor,
                    _canonical_json(clean_transports, "owner credential transports"),
                    timestamp,
                ),
            )
            connection.execute(
                "UPDATE owner_enrollment_requests SET used_at = ? WHERE request_id = ?",
                (timestamp, enrollment["request_id"]),
            )
            connection.execute(
                """UPDATE owner_auth_challenges
                SET used_at = ?, verified_credential_id = ? WHERE challenge_id = ?""",
                (timestamp, encoded_credential, cid),
            )
            connection.execute(
                """INSERT INTO owner_credential_events
                (event_id, credential_id, event_type, reason, occurred_at)
                VALUES (?, ?, 'enrolled', ?, ?)""",
                (str(uuid.uuid4()), encoded_credential, str(enrollment["reason"]), timestamp),
            )
        return {"credential_id": encoded_credential, "actor": actor, "created_at": timestamp}

    def record_owner_action_authorization(
        self,
        *,
        challenge_id: str,
        credential_id: str,
        previous_sign_count: int,
        new_sign_count: int,
        assertion_hash: str,
        outcome: Mapping[str, object],
        now: datetime,
        receipt_id: str | None = None,
    ) -> dict[str, object]:
        """Consume one verified assertion and append its exact action-bound receipt once."""
        cid = _canonical_uuid(challenge_id, "owner auth challenge_id")
        rid = _new_uuid(receipt_id, "owner action receipt_id")
        assertion_digest = _required_text(assertion_hash, "owner assertion hash", max_length=64)
        if _SHA256_RE.fullmatch(assertion_digest) is None:
            raise DataError("invalid control owner assertion hash")
        if new_sign_count <= previous_sign_count:
            raise DataError("owner credential signature counter regressed")
        timestamp = _format_timestamp(now)
        clean_outcome = _json_object(outcome, "owner action outcome")
        with self._transaction(write=True) as connection:
            challenge = connection.execute(
                "SELECT * FROM owner_auth_challenges WHERE challenge_id = ?", (cid,)
            ).fetchone()
            credential = connection.execute(
                "SELECT * FROM owner_credentials WHERE credential_id = ?", (credential_id,)
            ).fetchone()
            if (
                challenge is None
                or challenge["ceremony"] != "action"
                or challenge["used_at"] is not None
                or str(challenge["expires_at"]) <= timestamp
                or credential is None
                or credential["revoked_at"] is not None
                or int(credential["sign_count"]) != previous_sign_count
            ):
                raise DataError(
                    "owner action assertion is invalid, expired, stale, or already used"
                )
            binding = _decode_json(challenge["binding_json"], "owner action binding")
            if not isinstance(binding, dict):
                raise DataError("corrupt control store: owner action binding is not an object")
            action_type = _enum_value(
                binding.get("action_type"), "owner action type", OWNER_ACTION_TYPES
            )
            project_id = _canonical_uuid(str(binding.get("project_id")), "project_id")
            artifact_hash = _required_text(
                binding.get("artifact_hash"), "owner action artifact_hash", max_length=64
            )
            revision = _required_text(
                binding.get("expected_case_revision"),
                "owner action expected_case_revision",
                max_length=64,
            )
            request_hash = _required_text(
                binding.get("request_hash"), "owner action request_hash", max_length=64
            )
            consequence = _required_text(
                binding.get("consequence_summary"), "owner action consequence summary"
            )
            reason = _required_text(binding.get("reason"), "owner action reason")
            for label, value in (
                ("artifact_hash", artifact_hash),
                ("expected_case_revision", revision),
                ("request_hash", request_hash),
            ):
                if _SHA256_RE.fullmatch(value) is None:
                    raise DataError(f"invalid control owner action {label}")
            actor = str(credential["actor"])
            connection.execute(
                "UPDATE owner_credentials SET sign_count = ? WHERE credential_id = ?",
                (new_sign_count, credential_id),
            )
            connection.execute(
                """UPDATE owner_auth_challenges
                SET used_at = ?, verified_credential_id = ? WHERE challenge_id = ?""",
                (timestamp, credential_id, cid),
            )
            connection.execute(
                """INSERT INTO owner_action_receipts
                (receipt_id, challenge_id, credential_id, actor, action_type, project_id,
                 artifact_hash, expected_case_revision, consequence_summary, reason,
                 request_hash, assertion_hash, outcome_json, performed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rid,
                    cid,
                    credential_id,
                    actor,
                    action_type,
                    project_id,
                    artifact_hash,
                    revision,
                    consequence,
                    reason,
                    request_hash,
                    assertion_digest,
                    _canonical_json(clean_outcome, "owner action outcome"),
                    timestamp,
                ),
            )
        return {
            "receipt_id": rid,
            "action_type": action_type,
            "project_id": project_id,
            "actor": actor,
            "outcome": clean_outcome,
            "performed_at": timestamp,
        }


__all__ = [
    "ASSOCIATION_METHODS",
    "ATTEMPT_STATUSES",
    "AUTHOR_KINDS",
    "DATABASE_NAME",
    "DEVELOPMENT_STAGE_ORDER",
    "DEVELOPMENT_STAGES",
    "EVIDENCE_STATUSES",
    "JOB_EVENT_TYPES",
    "JOB_STATUSES",
    "LEGACY_SCHEMA_VERSION",
    "OWNER_ACTION_TYPES",
    "PREVIOUS_SCHEMA_VERSION",
    "PROJECT_STATUSES",
    "RESEARCH_CONTRACT_SCOPES",
    "RESEARCH_D2_REVISION_RELATIONS",
    "RESEARCH_D2_STATES",
    "RESEARCH_DISPOSITIONS",
    "RESEARCH_EXECUTION_STATES",
    "RESEARCH_OUTCOMES",
    "RESEARCH_PHASE_ORDER",
    "RESEARCH_PHASES",
    "RESEARCH_RESPONSIBILITIES",
    "RESEARCH_REVIEW_DECISIONS",
    "RESEARCH_SOURCE_ACCESS_MODES",
    "SCHEMA_VERSION",
    "STAGE_STATES",
    "AttemptStatus",
    "AuthorKind",
    "ControlStore",
    "EvidenceStatus",
    "JobStatus",
    "MonteCarloReviewDecision",
    "OwnerActionType",
    "ProjectStatus",
    "ResearchContractScope",
    "ResearchD2State",
    "ResearchDisposition",
    "ResearchExecutionState",
    "ResearchOutcome",
    "ResearchPhase",
    "ResearchResponsibility",
    "ResearchReviewDecision",
    "StageState",
    "parse_timestamp",
    "research_case_revision",
]
