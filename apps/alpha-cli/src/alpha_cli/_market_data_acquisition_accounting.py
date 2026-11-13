"""Inactive acquisition transaction fragment, for explicitly disposable fixtures only.

Shelved (2026-11-14, triage card 2): not wired in, kept for a future download-budget
policy and durable acquisition journal (backlog: controlstore-durable-acquisition).

The caller supplies an active transaction and guarantees BEGIN IMMEDIATE for writes.
This module never opens/commits/closes a connection or grants an effect capability.
FIXTURE_DDL is not registered with ControlStore or any production migration. Local
consistency cannot prove retained-history continuity or detect whole-store rollback.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any, cast

from alpha_core.errors import DataError

_PREFIX = "md_acquisition_"
_TABLES = {
    "meta": """CREATE TABLE md_acquisition_meta (
        version INTEGER PRIMARY KEY CHECK(version=1),
        authority TEXT NOT NULL CHECK(authority='synthetic_only')
    ) STRICT""",
    "scopes": """CREATE TABLE md_acquisition_scopes (
        scope_id TEXT PRIMARY KEY, body TEXT NOT NULL
    ) STRICT""",
    "attempts": """CREATE TABLE md_acquisition_attempts (
        attempt_id TEXT PRIMARY KEY, body TEXT NOT NULL
    ) STRICT""",
    "debits": """CREATE TABLE md_acquisition_debits (
        attempt_id TEXT NOT NULL REFERENCES md_acquisition_attempts(attempt_id),
        dimension TEXT NOT NULL, period TEXT NOT NULL,
        units INTEGER NOT NULL CHECK(units>0),
        PRIMARY KEY(attempt_id,dimension,period)
    ) STRICT""",
    "events": """CREATE TABLE md_acquisition_events (
        sequence INTEGER PRIMARY KEY CHECK(sequence>0),
        event_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL
    ) STRICT""",
}
FIXTURE_DDL = ";\n".join(_TABLES.values()) + (
    ";\nINSERT INTO md_acquisition_meta VALUES (1,'synthetic_only');\n"
)
_MAX_EVENTS = 2048
_MAX_PAYLOAD_BYTES = 8192
_MAX_TIME = 253402300799999
_TERMINAL = {"success", "failure", "cancelled"}


@dataclass(frozen=True)
class Dimension:
    dimension: str
    period: str
    limit: int
    start_ms: int | None
    end_ms: int | None
    weight: int


@dataclass(frozen=True)
class FixturePolicy:
    campaign_id: str
    generation: str
    dimensions: tuple[Dimension, ...]


@dataclass(frozen=True)
class Charge:
    dimension: str
    period: str
    units: int


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identifier(value: object) -> None:
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,96}", value) is None:
        raise DataError("acquisition fixture identifier invalid")


def _integer(value: object, *, maximum: int, minimum: int = 0) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise DataError("acquisition fixture integer invalid")


def _keys(value: Any, keys: set[str]) -> None:
    if type(value) is not dict or set(value) != keys:
        raise DataError("acquisition fixture record shape invalid")


def _policy(body: Any, *, ordered: bool = True) -> None:
    _keys(body, {"campaign_id", "generation", "dimensions"})
    _identifier(body["campaign_id"])
    _identifier(body["generation"])
    dimensions = body["dimensions"]
    if type(dimensions) is not list or not 1 <= len(dimensions) <= 16:
        raise DataError("acquisition fixture dimensions invalid")
    seen: dict[str, list[dict[str, Any]]] = {}
    for dim in dimensions:
        _keys(dim, {"dimension", "period", "limit", "start_ms", "end_ms", "weight"})
        _identifier(dim["dimension"])
        _identifier(dim["period"])
        _integer(dim["limit"], maximum=2**31 - 1, minimum=1)
        _integer(dim["weight"], maximum=dim["limit"], minimum=1)
        start, end = dim["start_ms"], dim["end_ms"]
        if start is not None or end is not None:
            _integer(start, maximum=_MAX_TIME)
            _integer(end, maximum=_MAX_TIME)
            if start >= end:
                raise DataError("acquisition fixture period invalid")
        for previous in seen.setdefault(dim["dimension"], []):
            if (
                previous["period"] == dim["period"]
                or start is None
                or previous["start_ms"] is None
                or max(start, previous["start_ms"]) < min(end, previous["end_ms"])
            ):
                raise DataError("acquisition fixture periods overlap")
        seen[dim["dimension"]].append(dim)
    if ordered and dimensions != sorted(dimensions, key=lambda d: (d["dimension"], d["period"])):
        raise DataError("acquisition fixture policy order invalid")


def _policy_body(policy: FixturePolicy) -> dict[str, Any]:
    if type(policy) is not FixturePolicy or type(policy.dimensions) is not tuple:
        raise DataError("acquisition fixture policy invalid")
    if any(type(d) is not Dimension for d in policy.dimensions):
        raise DataError("acquisition fixture dimension invalid")
    if not 1 <= len(policy.dimensions) <= 16:
        raise DataError("acquisition fixture dimensions invalid")
    body: dict[str, Any] = {
        "campaign_id": policy.campaign_id,
        "generation": policy.generation,
        "dimensions": [asdict(d) for d in policy.dimensions],
    }
    _policy(body, ordered=False)
    body["dimensions"] = sorted(body["dimensions"], key=lambda d: (d["dimension"], d["period"]))
    return body


def _hash(body: object) -> str:
    return hashlib.sha256(_json(body).encode()).hexdigest()


def _empty() -> dict[str, Any]:
    return {"scopes": {}, "attempts": {}, "debits": {}}


def _apply(state: dict[str, Any], event: str, payload: Any) -> None:
    """Closed bounded event reducer; also revalidates retained event history."""
    _identifier(event)
    kind = payload["kind"]
    if kind == "scope":
        _keys(payload, {"kind", "scope", "policy", "history_available"})
        scope_id = payload["scope"]
        _identifier(scope_id)
        _policy(payload["policy"])
        if type(payload["history_available"]) is not bool or scope_id in state["scopes"]:
            raise DataError("acquisition fixture scope already exists or invalid")
        state["scopes"][scope_id] = {
            "policy": payload["policy"],
            "policy_hash": _hash(payload["policy"]),
            "history_available": payload["history_available"],
            "last_ms": 0,
        }
        return
    if kind == "reserve":
        _keys(payload, {"kind", "scope", "policy_hash", "request_hash", "charges", "at_ms"})
        scope = state["scopes"][payload["scope"]]
        if not scope["history_available"]:
            raise DataError("acquisition fixture history unavailable")
        if payload["policy_hash"] != scope["policy_hash"]:
            raise DataError("acquisition fixture policy mismatch")
        request = payload["request_hash"]
        if type(request) is not str or re.fullmatch(r"[0-9a-f]{64}", request) is None:
            raise DataError("acquisition fixture request hash invalid")
        now = payload["at_ms"]
        _integer(now, maximum=_MAX_TIME)
        if now < scope["last_ms"]:
            raise DataError("acquisition fixture clock moved backward")
        previous = [
            a
            for a in state["attempts"].values()
            if a["scope"] == payload["scope"] and a["request_hash"] == request
        ]
        if any(a["state"] not in _TERMINAL for a in previous):
            raise DataError("acquisition fixture unresolved predecessor")
        charges = payload["charges"]
        if type(charges) is not list or not 1 <= len(charges) <= 16:
            raise DataError("acquisition fixture charges invalid")
        definitions = scope["policy"]["dimensions"]
        required = {d["dimension"] for d in definitions}
        selected: set[str] = set()
        for charge in charges:
            _keys(charge, {"dimension", "period", "units"})
            _identifier(charge["dimension"])
            _identifier(charge["period"])
            if charge["dimension"] in selected:
                raise DataError("acquisition fixture duplicate dimension")
            selected.add(charge["dimension"])
            definition = next(
                (
                    d
                    for d in definitions
                    if d["dimension"] == charge["dimension"] and d["period"] == charge["period"]
                ),
                None,
            )
            if definition is None or charge["units"] != definition["weight"]:
                raise DataError("acquisition fixture charge disagrees with policy")
            _integer(charge["units"], maximum=2**31 - 1, minimum=1)
            if definition["start_ms"] is not None and not (
                definition["start_ms"] <= now < definition["end_ms"]
            ):
                raise DataError("acquisition fixture outside explicit period")
            if any(
                state["attempts"][attempt]["scope"] == payload["scope"]
                and dim == charge["dimension"]
                and period != charge["period"]
                and state["attempts"][attempt]["state"] in {"reserved", "intent", "unknown"}
                for attempt, dim, period in state["debits"]
            ):
                raise DataError("acquisition fixture unresolved prior period")
            used = sum(
                units
                for (attempt, dim, period), units in state["debits"].items()
                if state["attempts"][attempt]["scope"] == payload["scope"]
                and dim == charge["dimension"]
                and period == charge["period"]
            )
            if used + charge["units"] > definition["limit"]:
                raise DataError("acquisition fixture allowance exhausted")
        if selected != required or charges != sorted(charges, key=lambda c: c["dimension"]):
            raise DataError("acquisition fixture incomplete or unordered debit vector")
        state["attempts"][event] = {
            "attempt_id": event,
            "scope": payload["scope"],
            "request_hash": request,
            "ordinal": len(previous) + 1,
            "state": "reserved",
            "cancel_requested": False,
            "at_ms": now,
            "reason": None,
        }
        for charge in charges:
            state["debits"][(event, charge["dimension"], charge["period"])] = charge["units"]
        scope["last_ms"] = now
        return
    if kind == "unavailable":
        _keys(payload, {"kind", "scope", "reference"})
        _identifier(payload["reference"])
        state["scopes"][payload["scope"]]["history_available"] = False
        return
    attempt = state["attempts"][payload["attempt"]]
    if kind == "intent":
        _keys(payload, {"kind", "attempt"})
        if attempt["state"] != "reserved" or attempt["cancel_requested"]:
            raise DataError("acquisition fixture intent refused")
        if not state["scopes"][attempt["scope"]]["history_available"]:
            raise DataError("acquisition fixture history unavailable")
        attempt["state"] = "intent"
    elif kind == "cancel":
        _keys(payload, {"kind", "attempt"})
        if attempt["state"] in _TERMINAL | {"unknown"} or attempt["cancel_requested"]:
            raise DataError("acquisition fixture cancellation refused")
        attempt["cancel_requested"] = True
    elif kind == "outcome":
        _keys(payload, {"kind", "attempt", "outcome", "reason"})
        outcome = payload["outcome"]
        _identifier(payload["reason"])
        if not (
            attempt["state"] == "intent"
            and outcome in _TERMINAL | {"unknown"}
            or attempt["state"] == "reserved"
            and outcome == "unknown"
        ):
            raise DataError("acquisition fixture outcome refused")
        attempt["state"] = outcome
        attempt["reason"] = payload["reason"]
        if outcome == "unknown":
            state["scopes"][attempt["scope"]]["history_available"] = False
    else:
        raise DataError("acquisition fixture event kind invalid")


class AcquisitionTransactions:
    """Caller-owned active transaction; writes require caller-guaranteed IMMEDIATE.

    No connection lifecycle/transaction handling or DDL runs here. Merely detecting
    in_transaction cannot establish lock mode. Records are synthetic bookkeeping,
    not authority, send tokens, history reconciliation or old-writer fencing.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._load()

    def _load(self) -> dict[str, Any]:
        connection = self._connection
        if not connection.in_transaction:
            raise DataError("acquisition fixture requires caller-owned active transaction")
        try:
            if connection.execute(
                "SELECT 1 FROM sqlite_temp_master WHERE name GLOB 'md_acquisition_*' "
                "OR tbl_name GLOB 'md_acquisition_*'"
            ).fetchone():
                raise DataError(
                    "acquisition fixture temporary schema shadows or attaches domain objects"
                )
            actual = {
                row[0]: " ".join(row[1].split())
                for row in connection.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='table' "
                    "AND name GLOB 'md_acquisition_*'"
                )
            }
            expected = {_PREFIX + name: " ".join(sql.split()) for name, sql in _TABLES.items()}
            if (
                actual != expected
                or connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE tbl_name GLOB 'md_acquisition_*' "
                    "AND type!='table' AND sql IS NOT NULL"
                ).fetchone()
            ):
                raise DataError("acquisition fixture schema missing or altered; no healing")
            if [tuple(row) for row in connection.execute("SELECT * FROM md_acquisition_meta")] != [
                (1, "synthetic_only")
            ]:
                raise DataError("acquisition fixture version or authority invalid")
            for table in _TABLES:
                if connection.execute(f"SELECT count(*) FROM {_PREFIX}{table}").fetchone()[0] > (
                    _MAX_EVENTS * 16 if table == "debits" else _MAX_EVENTS
                ):
                    raise DataError("acquisition fixture inspection budget exhausted")
            for table, column in (("events", "payload"), ("scopes", "body"), ("attempts", "body")):
                if connection.execute(
                    f"SELECT 1 FROM {_PREFIX}{table} "
                    f"WHERE length(CAST({column} AS BLOB))>? LIMIT 1",
                    (_MAX_PAYLOAD_BYTES,),
                ).fetchone():
                    raise DataError("acquisition fixture retained payload budget exhausted")
            state = _empty()
            for expected_seq, row in enumerate(
                connection.execute(
                    "SELECT sequence,event_id,payload FROM md_acquisition_events ORDER BY sequence"
                ),
                1,
            ):
                seq, event, raw = row
                if seq != expected_seq or len(raw.encode()) > _MAX_PAYLOAD_BYTES:
                    raise DataError("acquisition fixture event history invalid")
                payload = json.loads(raw)
                if _json(payload) != raw:
                    raise DataError("acquisition fixture event encoding invalid")
                _apply(state, event, payload)
            for table, key in (("scopes", "scope_id"), ("attempts", "attempt_id")):
                actual_rows = dict(connection.execute(f"SELECT {key},body FROM {_PREFIX}{table}"))
                if actual_rows != {k: _json(v) for k, v in state[table].items()}:
                    raise DataError("acquisition fixture history/projection mismatch")
            debits = {
                (a, d, p): u
                for a, d, p, u in connection.execute(
                    "SELECT attempt_id,dimension,period,units FROM md_acquisition_debits"
                )
            }
            if debits != state["debits"]:
                raise DataError("acquisition fixture debit history mismatch")
            return state
        except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, RecursionError):
            raise DataError("acquisition fixture schema/history unreadable") from None

    def _append(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        state = self._load()
        _identifier(event)
        raw = _json(payload)
        if len(raw.encode()) > _MAX_PAYLOAD_BYTES:
            raise DataError("acquisition fixture event payload budget exhausted")
        connection = self._connection
        previous = connection.execute(
            "SELECT payload FROM md_acquisition_events WHERE event_id=?", (event,)
        ).fetchone()
        if previous is not None:
            if previous[0] != raw:
                raise DataError("acquisition fixture conflicting replay")
            return state
        count = connection.execute("SELECT count(*) FROM md_acquisition_events").fetchone()[0]
        if count >= _MAX_EVENTS:
            raise DataError("acquisition fixture event budget exhausted")
        try:
            _apply(state, event, payload)
        except (KeyError, TypeError, ValueError, IndexError):
            raise DataError("acquisition fixture identity or event invalid") from None
        # Validation/reducer runs before SQL mutations; the caller must rollback any
        # write exception. An operation savepoint also undoes partial fragment writes;
        # it never commits or rolls back the caller-owned outer transaction.
        connection.execute("SAVEPOINT md_acquisition_append")
        try:
            connection.execute(
                "INSERT INTO md_acquisition_events VALUES (?,?,?)", (count + 1, event, raw)
            )
            for table, key in (("scopes", "scope_id"), ("attempts", "attempt_id")):
                for identity, body in state[table].items():
                    connection.execute(
                        f"INSERT INTO {_PREFIX}{table} VALUES (?,?) ON CONFLICT({key}) "
                        "DO UPDATE SET body=excluded.body",
                        (identity, _json(body)),
                    )
            for (attempt, dimension, period), units in state["debits"].items():
                connection.execute(
                    "INSERT INTO md_acquisition_debits VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                    (attempt, dimension, period, units),
                )
            connection.execute("RELEASE md_acquisition_append")
        except BaseException:
            # The outer transaction still belongs to the caller. If SQLite has
            # already aborted it, the original error remains an uncertain outcome.
            if connection.in_transaction:
                connection.execute("ROLLBACK TO md_acquisition_append")
                connection.execute("RELEASE md_acquisition_append")
            raise
        return state

    def record_fixture_scope(
        self, scope_id: str, policy: FixturePolicy, *, history_available: bool
    ) -> None:
        _identifier(scope_id)
        self._append(
            "scope_" + scope_id,
            {
                "kind": "scope",
                "scope": scope_id,
                "policy": _policy_body(policy),
                "history_available": history_available,
            },
        )

    def reserve_attempt(
        self,
        event_id: str,
        scope_id: str,
        policy: FixturePolicy,
        *,
        request_hash: str,
        charges: tuple[Charge, ...],
        bookkeeping_time_ms: int,
    ) -> dict[str, Any]:
        _identifier(scope_id)
        if type(charges) is not tuple or any(type(c) is not Charge for c in charges):
            raise DataError("acquisition fixture charges invalid")
        if not 1 <= len(charges) <= 16:
            raise DataError("acquisition fixture charges invalid")
        for charge in charges:
            _identifier(charge.dimension)
            _identifier(charge.period)
            _integer(charge.units, maximum=2**31 - 1, minimum=1)
        if type(request_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", request_hash) is None:
            raise DataError("acquisition fixture request hash invalid")
        _integer(bookkeeping_time_ms, maximum=_MAX_TIME)
        state = self._append(
            event_id,
            {
                "kind": "reserve",
                "scope": scope_id,
                "policy_hash": _hash(_policy_body(policy)),
                "request_hash": request_hash,
                "charges": sorted((asdict(c) for c in charges), key=lambda c: c["dimension"]),
                "at_ms": bookkeeping_time_ms,
            },
        )
        return copy.deepcopy(state["attempts"][event_id])

    def record_intent(self, event_id: str, attempt_id: str) -> None:
        _identifier(attempt_id)
        self._append(event_id, {"kind": "intent", "attempt": attempt_id})

    def request_cancel(self, event_id: str, attempt_id: str) -> None:
        _identifier(attempt_id)
        self._append(event_id, {"kind": "cancel", "attempt": attempt_id})

    def record_outcome(self, event_id: str, attempt_id: str, outcome: str, reason: str) -> None:
        _identifier(attempt_id)
        _identifier(reason)
        if type(outcome) is not str or outcome not in _TERMINAL | {"unknown"}:
            raise DataError("acquisition fixture outcome invalid")
        self._append(
            event_id,
            {"kind": "outcome", "attempt": attempt_id, "outcome": outcome, "reason": reason},
        )

    def record_unavailable_history(self, event_id: str, scope_id: str, reference: str) -> None:
        _identifier(scope_id)
        _identifier(reference)
        self._append(event_id, {"kind": "unavailable", "scope": scope_id, "reference": reference})

    def read_scope(self, scope_id: str) -> dict[str, Any]:
        state = self._load()
        if scope_id not in state["scopes"]:
            raise DataError("acquisition fixture scope missing")
        return copy.deepcopy(state["scopes"][scope_id])

    def find_attempt(self, attempt_id: str) -> dict[str, Any] | None:
        """Distinguish genuinely absent identity from invalid/unavailable retained history."""
        _identifier(attempt_id)
        return cast(dict[str, Any] | None, copy.deepcopy(self._load()["attempts"].get(attempt_id)))

    def scope_attempts(self, scope_id: str) -> list[dict[str, Any]]:
        """Bounded validated projection only; these records confer no sender ownership."""
        _identifier(scope_id)
        state = self._load()
        if scope_id not in state["scopes"]:
            raise DataError("acquisition fixture scope missing")
        return copy.deepcopy(
            [
                value
                for key, value in sorted(state["attempts"].items())
                if value["scope"] == scope_id
            ]
        )

    def read_attempt(self, attempt_id: str) -> dict[str, Any]:
        state = self._load()
        if attempt_id not in state["attempts"]:
            raise DataError("acquisition fixture attempt missing")
        return copy.deepcopy(state["attempts"][attempt_id])

    def read_event(self, event_id: str) -> dict[str, Any]:
        self._load()
        row = self._connection.execute(
            "SELECT payload FROM md_acquisition_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if row is None:
            raise DataError("acquisition fixture event missing")
        return dict(json.loads(row[0]))
