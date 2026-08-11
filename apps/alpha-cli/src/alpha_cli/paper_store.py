"""Durable, low-volume journal for operational paper sessions.

Paper sessions are deliberately separate from deterministic research run artifacts.  Each session
lives under ``data_dir/paper/<uuid>/`` with an atomically replaced ``session.json`` and immutable,
atomically published event records.  Readers recover an event published immediately before a
process crash even when ``session.json.last_sequence`` was not updated yet.
"""

from __future__ import annotations

import json
import math
import re
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from alpha_cli._atomic import write_text
from alpha_core import DataError

type JsonScalar = str | int | float | bool | None
type SessionStatus = Literal["starting", "running", "stopping", "completed", "cancelled", "failed"]
type TerminalSessionStatus = Literal["completed", "cancelled", "failed"]
type ExecutionMode = Literal["local_sandbox", "ibkr_paper"]
type ReconciliationState = Literal["not_applicable", "pending", "matched", "mismatch", "halted"]

LEGACY_SCHEMA_VERSION: Final = 1
SCHEMA_VERSION: Final = 2
STALE_HEARTBEAT_SECONDS: Final = 30.0
EVENT_TYPES: Final = frozenset(
    {
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
    }
)
_LEGACY_EVENT_TYPES: Final = frozenset(
    {"lifecycle", "order", "fill", "rejection", "position", "reconciliation_warning"}
)

_SESSION_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_EVENT_FILE_RE = re.compile(r"([0-9]{20})\.json")
_SESSION_FIELDS_V1 = frozenset(
    {
        "schema_version",
        "session_id",
        "status",
        "provider",
        "sandbox",
        "symbol",
        "instrument_id",
        "strategy",
        "strategy_params",
        "snapshot_id",
        "pid",
        "heartbeat_at",
        "started_at",
        "ended_at",
        "last_sequence",
        "terminal_error",
    }
)
_SESSION_FIELDS_V2 = frozenset(
    {
        *_SESSION_FIELDS_V1,
        "paper",
        "execution_mode",
        "account_alias",
        "risk_profile_id",
        "decision_artifact_id",
        "reconciliation_state",
    }
)
_EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "session_id",
        "sequence",
        "event_type",
        "recorded_at",
        "ts_event_ns",
        "payload",
    }
)
_TERMINAL_STATUSES = frozenset({"completed", "cancelled", "failed"})
_STATUSES = frozenset({"starting", "running", "stopping", *_TERMINAL_STATUSES})
_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "starting": frozenset({"starting", "running", "cancelled", "failed"}),
    "running": frozenset({"running", "stopping", "completed", "cancelled", "failed"}),
    "stopping": frozenset({"stopping", "completed", "cancelled", "failed"}),
    "completed": frozenset({"completed"}),
    "cancelled": frozenset({"cancelled"}),
    "failed": frozenset({"failed"}),
}
_JOURNAL_LOCK = threading.RLock()


@dataclass(frozen=True, slots=True)
class PaperEventSink:
    """Bind a session journal to the ``alpha_core.ExecutionEventSink`` protocol shape."""

    data_dir: Path
    session_id: str

    def __post_init__(self) -> None:
        _require_session_id(self.session_id)

    def emit(
        self,
        event_type: str,
        payload: Mapping[str, JsonScalar],
        *,
        ts_event_ns: int | None = None,
    ) -> None:
        """Persist one event; storage and validation errors intentionally propagate."""
        append_event(
            self.data_dir,
            self.session_id,
            event_type,
            payload,
            ts_event_ns=ts_event_ns,
        )
        state = payload.get("state")
        if event_type == "reconciliation" and state == "matched":
            set_reconciliation_state(self.data_dir, self.session_id, "matched")
        elif event_type == "reconciliation" and state == "mismatch":
            set_reconciliation_state(self.data_dir, self.session_id, "mismatch")
        elif event_type == "reconciliation" and state == "halted":
            set_reconciliation_state(
                self.data_dir,
                self.session_id,
                "halted",
            )
        elif (event_type == "risk_check" and payload.get("passed") is False) or event_type in {
            "rejection",
            "reconciliation_warning",
        }:
            session = read_session(self.data_dir, self.session_id)
            if session["execution_mode"] == "ibkr_paper":
                set_reconciliation_state(self.data_dir, self.session_id, "halted")


def valid_session_id(session_id: str) -> bool:
    """Whether ``session_id`` is a canonical, lowercase, hyphenated UUID."""
    if _SESSION_ID_RE.fullmatch(session_id) is None:
        return False
    try:
        return str(uuid.UUID(session_id)) == session_id
    except ValueError:
        return False


def _require_session_id(session_id: str) -> None:
    if not valid_session_id(session_id):
        raise DataError(f"invalid paper session id {session_id!r}")


def _paper_root(data_dir: Path, *, create: bool = False) -> Path:
    root = data_dir / "paper"
    if root.is_symlink():
        raise DataError(f"paper store root must not be a symlink: {root}")
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _session_dir(data_dir: Path, session_id: str) -> Path:
    _require_session_id(session_id)
    path = _paper_root(data_dir) / session_id
    if path.is_symlink():
        raise DataError(f"paper session directory must not be a symlink: {path}")
    return path


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataError("paper timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DataError(f"invalid paper {field}: expected canonical UTC timestamp")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as exc:
        raise DataError(f"invalid paper {field}: expected canonical UTC timestamp") from exc
    if _format_timestamp(parsed) != value:
        raise DataError(f"invalid paper {field}: expected canonical UTC timestamp")
    return parsed


def _now(value: datetime | None) -> datetime:
    current = datetime.now(UTC) if value is None else value
    # Normalize and validate once at the public boundary.
    return _parse_timestamp(_format_timestamp(current), "timestamp")


def _require_nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"invalid paper {field}: expected a non-empty string")
    return value


def _scalar(value: object, *, label: str) -> JsonScalar:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise DataError(f"invalid paper {label}: values must be finite JSON scalars")


def _scalar_mapping(value: object, *, label: str) -> dict[str, JsonScalar]:
    if not isinstance(value, Mapping):
        raise DataError(f"invalid paper {label}: expected an object")
    result: dict[str, JsonScalar] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise DataError(f"invalid paper {label}: keys must be non-empty strings")
        result[key] = _scalar(item, label=label)
    return result


def _json_text(value: Mapping[str, object]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _read_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise DataError(f"corrupt {label} at {path}") from exc
    if not isinstance(raw, dict):
        raise DataError(f"invalid {label} at {path}: expected a JSON object")
    if not all(isinstance(key, str) for key in raw):
        raise DataError(f"invalid {label} at {path}: expected string keys")
    return raw


def _positive_int_or_none(value: object, field: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise DataError(f"invalid paper {field}: expected a positive integer or null")
    return value


def _nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DataError(f"invalid paper {field}: expected a non-negative integer")
    return value


def _validate_session(raw: dict[str, object], path: Path) -> dict[str, object]:
    version = _nonnegative_int(raw.get("schema_version"), "session schema_version")
    if version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
        raise DataError(f"invalid paper session at {path}: unsupported schema version {version}")
    expected_fields = _SESSION_FIELDS_V1 if version == LEGACY_SCHEMA_VERSION else _SESSION_FIELDS_V2
    if frozenset(raw) != expected_fields:
        raise DataError(f"invalid paper session at {path}: schema fields do not match v{version}")
    session_id = _require_nonempty_string(raw["session_id"], "session_id")
    _require_session_id(session_id)
    status = _require_nonempty_string(raw["status"], "status")
    if status not in _STATUSES:
        raise DataError(f"invalid paper session at {path}: unsupported status {status!r}")
    execution_mode = (
        "local_sandbox"
        if version == LEGACY_SCHEMA_VERSION
        else _require_nonempty_string(raw["execution_mode"], "execution_mode")
    )
    if execution_mode not in {"local_sandbox", "ibkr_paper"}:
        raise DataError(f"invalid paper session at {path}: unsupported execution_mode")
    expected_sandbox = execution_mode == "local_sandbox"
    if raw["sandbox"] is not expected_sandbox:
        raise DataError(f"invalid paper session at {path}: sandbox does not match execution_mode")
    if version == SCHEMA_VERSION and raw["paper"] is not True:
        raise DataError(f"invalid paper session at {path}: paper must be true")
    started = _parse_timestamp(raw["started_at"], "started_at")
    heartbeat = _parse_timestamp(raw["heartbeat_at"], "heartbeat_at")
    if heartbeat < started:
        raise DataError(f"invalid paper session at {path}: heartbeat precedes start")
    ended_raw = raw["ended_at"]
    ended = None if ended_raw is None else _parse_timestamp(ended_raw, "ended_at")
    terminal_error = raw["terminal_error"]
    if terminal_error is not None:
        _require_nonempty_string(terminal_error, "terminal_error")
    if status in _TERMINAL_STATUSES:
        if ended is None or ended < started:
            raise DataError(f"invalid paper session at {path}: terminal status requires ended_at")
    elif ended is not None or terminal_error is not None:
        raise DataError(f"invalid paper session at {path}: nonterminal session has terminal fields")
    if status != "failed" and terminal_error is not None:
        raise DataError(f"invalid paper session at {path}: only failed sessions have errors")

    account_alias = None if version == LEGACY_SCHEMA_VERSION else raw["account_alias"]
    if account_alias is not None:
        account_alias = _require_nonempty_string(account_alias, "account_alias")
    if execution_mode == "ibkr_paper" and account_alias is None:
        raise DataError(f"invalid paper session at {path}: IBKR paper requires account_alias")
    reconciliation_state = (
        "not_applicable" if version == LEGACY_SCHEMA_VERSION else raw["reconciliation_state"]
    )
    if reconciliation_state not in {"not_applicable", "pending", "matched", "mismatch", "halted"}:
        raise DataError(f"invalid paper session at {path}: unsupported reconciliation_state")
    decision_artifact_id = None if version == LEGACY_SCHEMA_VERSION else raw["decision_artifact_id"]
    if decision_artifact_id is not None:
        decision_artifact_id = _require_nonempty_string(
            decision_artifact_id, "decision_artifact_id"
        )
    return {
        "schema_version": version,
        "session_id": session_id,
        "status": status,
        "provider": _require_nonempty_string(raw["provider"], "provider"),
        "paper": True,
        "sandbox": expected_sandbox,
        "execution_mode": execution_mode,
        "account_alias": account_alias,
        "risk_profile_id": (
            "crypto-sandbox-v1"
            if version == LEGACY_SCHEMA_VERSION
            else _require_nonempty_string(raw["risk_profile_id"], "risk_profile_id")
        ),
        "decision_artifact_id": decision_artifact_id,
        "reconciliation_state": reconciliation_state,
        "symbol": _require_nonempty_string(raw["symbol"], "symbol"),
        "instrument_id": _require_nonempty_string(raw["instrument_id"], "instrument_id"),
        "strategy": _require_nonempty_string(raw["strategy"], "strategy"),
        "strategy_params": _scalar_mapping(raw["strategy_params"], label="strategy_params"),
        "snapshot_id": _require_nonempty_string(raw["snapshot_id"], "snapshot_id"),
        "pid": _positive_int_or_none(raw["pid"], "pid"),
        "heartbeat_at": _format_timestamp(heartbeat),
        "started_at": _format_timestamp(started),
        "ended_at": None if ended is None else _format_timestamp(ended),
        "last_sequence": _nonnegative_int(raw["last_sequence"], "last_sequence"),
        "terminal_error": terminal_error,
    }


def _stored_session(doc: Mapping[str, object]) -> dict[str, object]:
    """Strip normalized v2 view fields before mutating a legacy v1 session."""
    fields = (
        _SESSION_FIELDS_V1
        if doc.get("schema_version") == LEGACY_SCHEMA_VERSION
        else _SESSION_FIELDS_V2
    )
    return {field: doc[field] for field in fields}


def _read_session_doc(data_dir: Path, session_id: str) -> tuple[Path, dict[str, object]]:
    sdir = _session_dir(data_dir, session_id)
    path = sdir / "session.json"
    if not path.is_file():
        raise FileNotFoundError(f"unknown paper session {session_id!r}")
    doc = _validate_session(_read_object(path, label="paper session"), path)
    if doc["session_id"] != session_id:
        raise DataError(f"invalid paper session at {path}: id does not match directory")
    return sdir, doc


def _event_sequences(sdir: Path) -> list[int]:
    events_dir = sdir / "events"
    if not events_dir.exists():
        return []
    if not events_dir.is_dir() or events_dir.is_symlink():
        raise DataError(f"invalid paper events directory at {events_dir}")
    sequences: list[int] = []
    for path in events_dir.iterdir():
        if path.name.startswith("."):
            continue
        match = _EVENT_FILE_RE.fullmatch(path.name)
        if match is None or not path.is_file() or path.is_symlink():
            raise DataError(f"invalid paper event path at {path}")
        sequence = int(match.group(1))
        if sequence <= 0:
            raise DataError(f"invalid paper event sequence at {path}")
        sequences.append(sequence)
    sequences.sort()
    if sequences != list(range(1, len(sequences) + 1)):
        raise DataError(f"paper event sequence gap under {events_dir}")
    return sequences


def _recover_last_sequence(sdir: Path, doc: dict[str, object]) -> dict[str, object]:
    sequences = _event_sequences(sdir)
    actual = sequences[-1] if sequences else 0
    stored = _nonnegative_int(doc["last_sequence"], "last_sequence")
    if stored > actual:
        raise DataError(f"paper session {doc['session_id']!r} references a missing event")
    if actual == stored:
        return doc
    return {**doc, "last_sequence": actual}


def _is_stale(doc: Mapping[str, object], *, now: datetime, stale_after_seconds: float) -> bool:
    if not math.isfinite(stale_after_seconds) or stale_after_seconds <= 0:
        raise DataError("stale_after_seconds must be finite and > 0")
    if doc["status"] in _TERMINAL_STATUSES:
        return False
    heartbeat = _parse_timestamp(doc["heartbeat_at"], "heartbeat_at")
    return (now - heartbeat).total_seconds() > stale_after_seconds


def _view(
    doc: dict[str, object], *, now: datetime, stale_after_seconds: float
) -> dict[str, object]:
    return {**doc, "stale": _is_stale(doc, now=now, stale_after_seconds=stale_after_seconds)}


def create_session(
    data_dir: Path,
    *,
    provider: str,
    symbol: str,
    instrument_id: str,
    strategy: str,
    strategy_params: Mapping[str, object],
    snapshot_id: str,
    pid: int | None = None,
    session_id: str | None = None,
    started_at: datetime | None = None,
    execution_mode: ExecutionMode = "local_sandbox",
    account_alias: str | None = None,
    risk_profile_id: str = "crypto-sandbox-v1",
    decision_artifact_id: str | None = None,
) -> dict[str, object]:
    """Create a paper session and atomically publish its initial status."""
    sid = str(uuid.uuid4()) if session_id is None else session_id
    _require_session_id(sid)
    start = _now(started_at)
    if execution_mode not in {"local_sandbox", "ibkr_paper"}:
        raise DataError(f"unsupported paper execution_mode {execution_mode!r}")
    clean_account = (
        None if account_alias is None else _require_nonempty_string(account_alias, "account_alias")
    )
    if execution_mode == "ibkr_paper" and clean_account is None:
        raise DataError("IBKR paper sessions require account_alias")
    clean_artifact = (
        None
        if decision_artifact_id is None
        else _require_nonempty_string(decision_artifact_id, "decision_artifact_id")
    )
    doc: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "session_id": sid,
        "status": "starting",
        "provider": _require_nonempty_string(provider, "provider"),
        "paper": True,
        "sandbox": execution_mode == "local_sandbox",
        "execution_mode": execution_mode,
        "account_alias": clean_account,
        "risk_profile_id": _require_nonempty_string(risk_profile_id, "risk_profile_id"),
        "decision_artifact_id": clean_artifact,
        "reconciliation_state": (
            "not_applicable" if execution_mode == "local_sandbox" else "pending"
        ),
        "symbol": _require_nonempty_string(symbol, "symbol"),
        "instrument_id": _require_nonempty_string(instrument_id, "instrument_id"),
        "strategy": _require_nonempty_string(strategy, "strategy"),
        "strategy_params": _scalar_mapping(strategy_params, label="strategy_params"),
        "snapshot_id": _require_nonempty_string(snapshot_id, "snapshot_id"),
        "pid": _positive_int_or_none(pid, "pid"),
        "heartbeat_at": _format_timestamp(start),
        "started_at": _format_timestamp(start),
        "ended_at": None,
        "last_sequence": 0,
        "terminal_error": None,
    }
    root = _paper_root(data_dir, create=True)
    sdir = root / sid
    if sdir.is_symlink():
        raise DataError(f"paper session directory must not be a symlink: {sdir}")
    try:
        sdir.mkdir()
    except FileExistsError as exc:
        raise DataError(f"paper session {sid!r} already exists") from exc
    path = sdir / "session.json"
    write_text(path, _json_text(_stored_session(doc)))
    return _view(doc, now=start, stale_after_seconds=STALE_HEARTBEAT_SECONDS)


def read_session(
    data_dir: Path,
    session_id: str,
    *,
    now: datetime | None = None,
    stale_after_seconds: float = STALE_HEARTBEAT_SECONDS,
) -> dict[str, object]:
    """Read and validate a session, reporting crash-recovered sequence and live staleness."""
    current = _now(now)
    sdir, doc = _read_session_doc(data_dir, session_id)
    recovered = _recover_last_sequence(sdir, doc)
    return _view(recovered, now=current, stale_after_seconds=stale_after_seconds)


def list_sessions(
    data_dir: Path,
    *,
    now: datetime | None = None,
    stale_after_seconds: float = STALE_HEARTBEAT_SECONDS,
) -> list[dict[str, object]]:
    """Return complete sessions newest-first; crash-partial directories are ignored."""
    root = _paper_root(data_dir)
    if not root.exists():
        return []
    if not root.is_dir():
        raise DataError(f"invalid paper store root at {root}")
    current = _now(now)
    sessions: list[dict[str, object]] = []
    for path in root.iterdir():
        if not path.is_dir() or path.is_symlink() or not valid_session_id(path.name):
            continue
        if not (path / "session.json").is_file():
            continue
        sessions.append(
            read_session(
                data_dir,
                path.name,
                now=current,
                stale_after_seconds=stale_after_seconds,
            )
        )
    return sorted(sessions, key=lambda row: str(row["started_at"]), reverse=True)


def set_session_status(
    data_dir: Path,
    session_id: str,
    status: SessionStatus,
    *,
    pid: int | None = None,
    terminal_error: str | None = None,
    at: datetime | None = None,
) -> dict[str, object]:
    """Advance lifecycle status. Terminal sessions are idempotent and cannot be revived."""
    if status not in _STATUSES:
        raise DataError(f"unsupported paper session status {status!r}")
    current_time = _now(at)
    with _JOURNAL_LOCK:
        sdir, doc = _read_session_doc(data_dir, session_id)
        doc = _recover_last_sequence(sdir, doc)
        current_status = str(doc["status"])
        if status not in _TRANSITIONS[current_status]:
            raise DataError(f"invalid paper session transition {current_status!r} -> {status!r}")
        if current_status in _TERMINAL_STATUSES:
            return _view(doc, now=current_time, stale_after_seconds=STALE_HEARTBEAT_SECONDS)
        heartbeat = _parse_timestamp(doc["heartbeat_at"], "heartbeat_at")
        if current_time < heartbeat:
            raise DataError("paper session status timestamp precedes prior heartbeat")
        if pid is not None:
            doc["pid"] = _positive_int_or_none(pid, "pid")
        if status == "failed":
            doc["terminal_error"] = (
                None
                if terminal_error is None
                else _require_nonempty_string(terminal_error, "terminal_error")
            )
        elif terminal_error is not None:
            raise DataError("terminal_error is only valid for failed paper sessions")
        doc["status"] = status
        doc["heartbeat_at"] = _format_timestamp(current_time)
        if status in _TERMINAL_STATUSES:
            doc["ended_at"] = _format_timestamp(current_time)
        write_text(sdir / "session.json", _json_text(_stored_session(doc)))
    return _view(doc, now=current_time, stale_after_seconds=STALE_HEARTBEAT_SECONDS)


def heartbeat_session(
    data_dir: Path, session_id: str, *, at: datetime | None = None
) -> dict[str, object]:
    """Atomically refresh a live session heartbeat; this never signals or probes its PID."""
    current_time = _now(at)
    with _JOURNAL_LOCK:
        sdir, doc = _read_session_doc(data_dir, session_id)
        doc = _recover_last_sequence(sdir, doc)
        if doc["status"] in _TERMINAL_STATUSES:
            raise DataError(f"cannot heartbeat terminal paper session {session_id!r}")
        prior = _parse_timestamp(doc["heartbeat_at"], "heartbeat_at")
        if current_time < prior:
            raise DataError("paper heartbeat timestamp precedes prior heartbeat")
        doc["heartbeat_at"] = _format_timestamp(current_time)
        write_text(sdir / "session.json", _json_text(_stored_session(doc)))
    return _view(doc, now=current_time, stale_after_seconds=STALE_HEARTBEAT_SECONDS)


def finish_session(
    data_dir: Path,
    session_id: str,
    *,
    status: TerminalSessionStatus,
    terminal_error: str | None = None,
    at: datetime | None = None,
) -> dict[str, object]:
    """Finish a session as completed, cancelled, or failed."""
    if status not in _TERMINAL_STATUSES:
        raise DataError(f"paper terminal status required, got {status!r}")
    return set_session_status(
        data_dir,
        session_id,
        status,
        terminal_error=terminal_error,
        at=at,
    )


def append_event(
    data_dir: Path,
    session_id: str,
    event_type: str,
    payload: Mapping[str, object],
    *,
    ts_event_ns: int | None = None,
) -> dict[str, object]:
    """Append one allowed operational event and return its durable JSON record."""
    if event_type not in EVENT_TYPES:
        raise DataError(f"unsupported paper event type {event_type!r}")
    clean_payload = _scalar_mapping(payload, label="event payload")
    if ts_event_ns is not None and (
        not isinstance(ts_event_ns, int) or isinstance(ts_event_ns, bool) or ts_event_ns < 0
    ):
        raise DataError("invalid paper event ts_event_ns: expected a non-negative integer or null")
    recorded_at = _now(None)
    with _JOURNAL_LOCK:
        sdir, doc = _read_session_doc(data_dir, session_id)
        doc = _recover_last_sequence(sdir, doc)
        if doc["status"] in _TERMINAL_STATUSES:
            raise DataError(f"cannot append to terminal paper session {session_id!r}")
        sequence = _nonnegative_int(doc["last_sequence"], "last_sequence") + 1
        event: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "session_id": session_id,
            "sequence": sequence,
            "event_type": event_type,
            "recorded_at": _format_timestamp(recorded_at),
            "ts_event_ns": ts_event_ns,
            "payload": clean_payload,
        }
        path = sdir / "events" / f"{sequence:020d}.json"
        write_text(path, _json_text(event))
        # Event first, session pointer second: a crash between them is recoverable by scanning.
        doc["last_sequence"] = sequence
        write_text(sdir / "session.json", _json_text(_stored_session(doc)))
    return event


def _validate_event(
    raw: dict[str, object], path: Path, *, session_id: str, sequence: int
) -> dict[str, object]:
    if frozenset(raw) != _EVENT_FIELDS:
        raise DataError(f"invalid paper event at {path}: schema fields do not match v1")
    version = _nonnegative_int(raw["schema_version"], "event schema_version")
    if version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
        raise DataError(f"invalid paper event at {path}: unsupported schema version {version}")
    stored_session_id = _require_nonempty_string(raw["session_id"], "event session_id")
    stored_sequence = _nonnegative_int(raw["sequence"], "event sequence")
    if stored_session_id != session_id or stored_sequence != sequence:
        raise DataError(f"invalid paper event at {path}: identity does not match path")
    event_type = _require_nonempty_string(raw["event_type"], "event_type")
    allowed_types = _LEGACY_EVENT_TYPES if version == LEGACY_SCHEMA_VERSION else EVENT_TYPES
    if event_type not in allowed_types:
        raise DataError(f"invalid paper event at {path}: unsupported type {event_type!r}")
    recorded = _parse_timestamp(raw["recorded_at"], "event recorded_at")
    ts_event_ns = raw["ts_event_ns"]
    if ts_event_ns is not None:
        ts_event_ns = _nonnegative_int(ts_event_ns, "event ts_event_ns")
    return {
        "schema_version": version,
        "session_id": stored_session_id,
        "sequence": stored_sequence,
        "event_type": event_type,
        "recorded_at": _format_timestamp(recorded),
        "ts_event_ns": ts_event_ns,
        "payload": _scalar_mapping(raw["payload"], label="event payload"),
    }


def read_events(data_dir: Path, session_id: str, *, after: int = 0) -> list[dict[str, object]]:
    """Read validated events with sequence strictly greater than ``after``."""
    if not isinstance(after, int) or isinstance(after, bool) or after < 0:
        raise DataError("paper event cursor must be a non-negative integer")
    sdir, doc = _read_session_doc(data_dir, session_id)
    # Take one stable directory snapshot. An atomically published next event can wait for the
    # caller's next cursor poll; normal concurrent appends are not journal corruption.
    sequences = _event_sequences(sdir)
    actual_last = sequences[-1] if sequences else 0
    stored_last = _nonnegative_int(doc["last_sequence"], "last_sequence")
    if stored_last > actual_last:
        raise DataError(f"paper session {session_id!r} references a missing event")
    rows: list[dict[str, object]] = []
    for sequence in sequences:
        if sequence <= after:
            continue
        path = sdir / "events" / f"{sequence:020d}.json"
        rows.append(
            _validate_event(
                _read_object(path, label="paper event"),
                path,
                session_id=session_id,
                sequence=sequence,
            )
        )
    return rows


def set_reconciliation_state(
    data_dir: Path,
    session_id: str,
    state: ReconciliationState,
    *,
    at: datetime | None = None,
) -> dict[str, object]:
    """Persist the fail-closed account reconciliation state for an IBKR paper session."""
    if state not in {"pending", "matched", "mismatch", "halted"}:
        raise DataError(f"unsupported IBKR reconciliation state {state!r}")
    current_time = _now(at)
    with _JOURNAL_LOCK:
        sdir, doc = _read_session_doc(data_dir, session_id)
        if doc["schema_version"] != SCHEMA_VERSION or doc["execution_mode"] != "ibkr_paper":
            raise DataError("reconciliation state applies only to v2 IBKR paper sessions")
        if doc["status"] in _TERMINAL_STATUSES:
            raise DataError(f"cannot reconcile terminal paper session {session_id!r}")
        doc["reconciliation_state"] = state
        doc["heartbeat_at"] = _format_timestamp(current_time)
        write_text(sdir / "session.json", _json_text(_stored_session(doc)))
    return _view(doc, now=current_time, stale_after_seconds=STALE_HEARTBEAT_SECONDS)


def request_safe_stop(
    data_dir: Path, session_id: str, *, at: datetime | None = None
) -> dict[str, object]:
    """Request cooperative cancellation; the worker cancels orders and never flattens positions."""
    current_time = _now(at)
    with _JOURNAL_LOCK:
        sdir, doc = _read_session_doc(data_dir, session_id)
        if doc["status"] in _TERMINAL_STATUSES:
            return _view(doc, now=current_time, stale_after_seconds=STALE_HEARTBEAT_SECONDS)
        marker = sdir / "safe-stop.request.json"
        if not marker.exists():
            write_text(
                marker,
                _json_text(
                    {
                        "schema_version": 1,
                        "session_id": session_id,
                        "requested_at": _format_timestamp(current_time),
                        "flatten_positions": False,
                    }
                ),
            )
        doc["status"] = "stopping"
        doc["heartbeat_at"] = _format_timestamp(current_time)
        write_text(sdir / "session.json", _json_text(_stored_session(doc)))
    return _view(doc, now=current_time, stale_after_seconds=STALE_HEARTBEAT_SECONDS)


def safe_stop_requested(data_dir: Path, session_id: str) -> bool:
    """Return whether the cooperative safe-stop marker exists for this exact session."""
    sdir, _ = _read_session_doc(data_dir, session_id)
    return (sdir / "safe-stop.request.json").is_file()


__all__ = [
    "EVENT_TYPES",
    "ExecutionMode",
    "LEGACY_SCHEMA_VERSION",
    "PaperEventSink",
    "ReconciliationState",
    "SCHEMA_VERSION",
    "STALE_HEARTBEAT_SECONDS",
    "SessionStatus",
    "TerminalSessionStatus",
    "append_event",
    "create_session",
    "finish_session",
    "heartbeat_session",
    "list_sessions",
    "read_events",
    "read_session",
    "request_safe_stop",
    "safe_stop_requested",
    "set_reconciliation_state",
    "set_session_status",
    "valid_session_id",
]
