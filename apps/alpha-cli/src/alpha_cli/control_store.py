"""Lightweight, CLI-owned Workstation v3 control-plane store.

The control plane is mutable operational/research metadata, so it deliberately lives outside
``RUN_DIRS``. Deterministic run artifacts remain immutable and authoritative; this database only
links projects, attempts, jobs, and evidence to those completed runs.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final, Literal, cast

import polars as pl

from alpha_cli.artifact_contract import verify_manifest_artifacts
from alpha_cli.job_capacity import HEAVYWEIGHT_JOB_CAPACITY, HEAVYWEIGHT_JOB_KINDS
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
type JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
type EvidenceStatus = Literal["draft", "corroborated", "rejected", "superseded"]
type AuthorKind = Literal["human", "agent"]
type DecisionVerdict = Literal["accept", "reject", "revise"]

SCHEMA_VERSION: Final = 1
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

_ASSOCIATION_TOKEN_MARKERS: Final = ("associat", "correlat", "kendall", "pearson", "spearman")

_TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
_TERMINAL_STAGE_STATES = frozenset({"pass", "warning", "fail"})
_RESERVED_JOB_PREFIXES = ("suite:",)
_SUITE_JOB_KINDS: Final = frozenset(
    {
        "suite:baseline",
        "suite:inner_oos",
        "suite:three_null_families",
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
    "baseline": ("baseline", frozenset({"backtest_run"})),
    "inner_oos": ("oos", frozenset({"backtest_oos"})),
    "three_null_families": ("robustness", frozenset({"validate"})),
    "optimize_grid": ("optimization", frozenset({"optim_grid"})),
    "portfolio_cross_asset": (
        "portfolio",
        frozenset({"backtest_portfolio", "cross_sectional", "backtest_cross_sectional"}),
    ),
    "qlib": ("ml", frozenset({"ml_replay"})),
    "kronos": ("kronos", frozenset({"forecast_run", "forecast_eval"})),
    "holdout_reveal": ("holdout", frozenset({"backtest_holdout"})),
}
_PRE_REVEAL_RESEARCH_STAGES: Final = frozenset(
    {"baseline", "oos", "robustness", "optimization", "portfolio", "kronos", "ml"}
)
_PRE_REVEAL_RESEARCH_JOB_KINDS: Final = frozenset(
    {
        "suite:baseline",
        "suite:inner_oos",
        "suite:three_null_families",
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
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_CONTENT_ID_RE = re.compile(r"(?P<prefix>sv|ex)_[0-9a-f]{64}")
_SYMBOL_RE = re.compile(r"[A-Z0-9][A-Z0-9._:/-]{0,31}")
_ARTIFACT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}")
_MAX_JSON_BYTES = 65_536
_MAX_TEXT = 8_192

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
            connection = sqlite3.connect(self._database_path(), timeout=5.0, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            version_row = connection.execute("PRAGMA user_version").fetchone()
            version = 0 if version_row is None else int(version_row[0])
            if version not in {0, SCHEMA_VERSION}:
                raise DataError(f"unsupported control store schema version {version}")
            connection.executescript(_SCHEMA)
            if version == 0:
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
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

    def _require_run(self, run_id: str) -> str:
        self._verified_run(run_id)
        return run_id

    def create_project(
        self,
        *,
        name: str,
        hypothesis: str,
        falsification_criterion: str,
        status: ProjectStatus = "active",
        project_id: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Create one owner-facing strategy project."""
        pid = _new_uuid(project_id, "project_id")
        clean_status = _required_text(status, "project status", max_length=16)
        if clean_status not in PROJECT_STATUSES:
            raise DataError(f"unsupported project status {status!r}")
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
            self._append_project_scope_event(
                connection,
                project_id=pid,
                version_id=None,
                experiment_id=None,
                at=timestamp,
                reason="project created",
            )
        return row

    def list_projects(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, object]]:
        """Return bounded project summaries, newest first."""
        limit, offset = _page(limit, offset)
        with self._transaction(write=False) as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC, project_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

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
        project["versions"] = [self._version_view(row) for row in versions]
        project["experiments"] = [self._experiment_view(row) for row in experiments]
        project["stage_run_links"] = link_views
        project["stage_states"] = stage_views
        project["attempts"] = [self._attempt_view(row) for row in attempts]
        project["holdouts"] = [dict(row) for row in holdouts]
        project["holdout_audit"] = [dict(row) for row in audit]
        project["decision_packets"] = [self._decision_packet_view(row) for row in decisions]
        return project

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
            "strategy_version": None if version_row is None else self._version_view(version_row),
            "experiment": (
                None if experiment_row is None else self._experiment_view(experiment_row)
            ),
            "stage_statuses": [stages[name] for name in sorted(stages)],
            "holdout_events": holdout_events,
            "scope_history_complete": scope_history_complete,
            "evidence": evidence,
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
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Link an immutable, content-addressed strategy version to a project."""
        clean_definition = _json_object(definition, "strategy definition")
        clean_space = _json_object(parameter_space, "parameter space")
        identity = {
            "schema_version": SCHEMA_VERSION,
            "strategy_name": _required_text(strategy_name, "strategy name", max_length=100),
            "source_fingerprint": _required_text(
                source_fingerprint, "source fingerprint", max_length=512
            ),
            "definition": clean_definition,
            "parameter_space": clean_space,
        }
        version_id = _content_id("sv", identity)
        timestamp = _at(at)
        definition_json = _canonical_json(clean_definition, "strategy definition")
        parameter_space_json = _canonical_json(clean_space, "parameter space")
        with self._transaction(write=True) as connection:
            project = self._require_project(connection, project_id)
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
        return self._version_view(row)

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
        at: datetime | None = None,
    ) -> dict[str, object]:
        """Link an immutable, content-addressed experiment specification to a project."""
        version_id = _require_content_id(strategy_version_id, "strategy_version_id", prefix="sv")
        clean_universe = _symbols(universe)
        clean_split = _json_object(split_policy, "split policy")
        clean_costs = _json_object(costs, "costs")
        clean_seeds = _json_object(seeds, "seeds")
        clean_stage = _json_object(stage_config or {}, "stage config")
        identity = {
            "schema_version": SCHEMA_VERSION,
            "strategy_version_id": version_id,
            "snapshot_id": _required_text(snapshot_id, "snapshot_id", max_length=200),
            "universe": clean_universe,
            "split_policy": clean_split,
            "costs": clean_costs,
            "seeds": clean_seeds,
            "stage_config": clean_stage,
        }
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
        return self._experiment_view(row)

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
                if suite_action in {
                    "baseline",
                    "inner_oos",
                    "three_null_families",
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
            families = {
                metadata.get("null_model")
                for _, manifest in evidence
                if isinstance((metadata := manifest.get("metadata")), Mapping)
            }
            headline = any(
                view["state"] == "pass"
                and manifest.get("passed") is True
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
        if suite_action == "portfolio_cross_asset":
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
        for stage in ("baseline", "oos", "robustness", "optimization", "portfolio"):
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
            raise DataError(
                "suite job kinds are reserved for the resolved development suite executor"
            )
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
        clean_run = None if source_run_id is None else self._require_run(source_run_id)
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
    "PROJECT_STATUSES",
    "SCHEMA_VERSION",
    "STAGE_STATES",
    "AttemptStatus",
    "AuthorKind",
    "ControlStore",
    "EvidenceStatus",
    "JobStatus",
    "ProjectStatus",
    "StageState",
    "parse_timestamp",
]
