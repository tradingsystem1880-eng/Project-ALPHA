"""Mechanically reverified paper acceptance and separate IBKR what-if plans."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from alpha_cli._atomic import write_text
from alpha_core import DataError

type FactSource = Literal[
    "adapter_callback", "risk_guard", "reconciliation_callback", "connection_guard"
]
type FactType = Literal[
    "connection",
    "cancellation",
    "entry",
    "exit",
    "restart",
    "risk_observation",
    "reconciliation",
]

POLICY_VERSION: Final = "paper-acceptance-v2"
_SOURCES: Final = frozenset(
    {"adapter_callback", "risk_guard", "reconciliation_callback", "connection_guard"}
)
_FACT_TYPES: Final = frozenset(
    {"connection", "cancellation", "entry", "exit", "restart", "risk_observation", "reconciliation"}
)
_SOURCE_TYPES: Final = {
    "adapter_callback": frozenset({"cancellation", "entry", "exit"}),
    "risk_guard": frozenset({"risk_observation"}),
    "reconciliation_callback": frozenset({"reconciliation", "restart"}),
    "connection_guard": frozenset({"connection"}),
}
_EVIDENCE_KEYS: Final = {
    "connection": frozenset({"paper_port", "live_port_attempted"}),
    "cancellation": frozenset({"requested_order_id", "acknowledged_order_id"}),
    "entry": frozenset({"order_id", "fill_id", "quantity"}),
    "exit": frozenset({"order_id", "fill_id", "quantity"}),
    "restart": frozenset({"reconnected", "state_reconciled"}),
    "risk_observation": frozenset(
        {"duplicate_orders", "unexplained_positions", "unresolved_fills", "secret_sentinels_found"}
    ),
    "reconciliation": frozenset({"duplicate_orders", "unexplained_positions", "unresolved_fills"}),
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IMAGE = re.compile(r"^[A-Za-z0-9._/:+-]+@sha256:[0-9a-f]{64}$")
_ACCOUNT = re.compile(r"^DU[A-Z0-9]+$")


def _canonical(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _stamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataError("paper timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@contextmanager
def _lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".writer.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def freeze_acceptance_plan(
    data_dir: Path,
    *,
    session_id: str,
    implementation_fingerprint: str,
    correlation_root: str,
) -> dict[str, object]:
    """Freeze a typed one-shot acceptance contract before any broker callback is recorded."""
    if _SHA256.fullmatch(implementation_fingerprint) is None:
        raise DataError("paper acceptance requires an implementation SHA-256")
    if not session_id.strip() or not correlation_root.strip():
        raise DataError("paper acceptance requires session and correlation identifiers")
    body: dict[str, object] = {
        "schema_version": 2,
        "policy_version": POLICY_VERSION,
        "session_id": session_id,
        "correlation_root": correlation_root,
        "implementation_fingerprint": implementation_fingerprint,
        "required_fact_types": [
            "connection",
            "cancellation",
            "entry",
            "exit",
            "restart",
            "risk_observation",
            "reconciliation",
        ],
        "one_shot": True,
    }
    plan_hash = _digest(body)
    plan = {**body, "plan_hash": plan_hash}
    root = Path(data_dir) / "paper-acceptance-v2" / "plans"
    path = root / f"{plan_hash}.json"
    rendered = json.dumps(plan, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with _lock(root):
        if path.exists() and path.read_text(encoding="utf-8") != rendered:
            raise DataError("paper acceptance plan identity collision")
        if not path.exists():
            write_text(path, rendered)
    return plan


def _read_plan(data_dir: Path, plan_hash: str) -> dict[str, object]:
    path = Path(data_dir) / "paper-acceptance-v2" / "plans" / f"{plan_hash}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("paper acceptance plan is missing or unreadable") from exc
    if not isinstance(raw, dict) or raw.get("plan_hash") != plan_hash:
        raise DataError("paper acceptance plan failed identity verification")
    body = {key: value for key, value in raw.items() if key != "plan_hash"}
    if _digest(body) != plan_hash:
        raise DataError("paper acceptance plan failed content verification")
    return raw


def _fact_files(data_dir: Path, plan_hash: str) -> list[Path]:
    root = Path(data_dir) / "paper-acceptance-v2" / "facts" / plan_hash
    return sorted(root.glob("*.json")) if root.exists() else []


def _read_facts(data_dir: Path, plan_hash: str) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = []
    previous: str | None = None
    for path in _fact_files(data_dir, plan_hash):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DataError("paper acceptance fact is unreadable") from exc
        if not isinstance(raw, dict):
            raise DataError("paper acceptance fact must be an object")
        fact_hash = raw.get("fact_hash")
        body = {key: value for key, value in raw.items() if key != "fact_hash"}
        if not isinstance(fact_hash, str) or _digest(body) != fact_hash:
            raise DataError("paper acceptance fact failed content verification")
        if raw.get("previous_fact_hash") != previous:
            raise DataError("paper acceptance fact chain is broken")
        previous = fact_hash
        facts.append(raw)
    return facts


def record_callback_fact(
    data_dir: Path,
    *,
    plan_hash: str,
    session_id: str,
    source: FactSource | str,
    fact_type: FactType | str,
    correlation_id: str,
    raw_evidence: Mapping[str, object],
    recorded_at: datetime | None = None,
) -> dict[str, object]:
    """Internal callback sink. It is intentionally absent from CLI, REST, and MCP."""
    if (
        source not in _SOURCES
        or fact_type not in _FACT_TYPES
        or fact_type not in _SOURCE_TYPES[source]
    ):
        raise DataError("paper evidence must come from a closed typed callback")
    plan = _read_plan(data_dir, plan_hash)
    if plan["session_id"] != session_id:
        raise DataError("paper fact session does not match its frozen plan")
    correlation_root = str(plan["correlation_root"])
    if not correlation_id.startswith(f"{correlation_root}/"):
        raise DataError("paper fact correlation is outside the frozen lineage")
    allowed = _EVIDENCE_KEYS[fact_type]
    if set(raw_evidence) != set(allowed):
        raise DataError("paper fact raw evidence does not match the closed typed schema")
    root = Path(data_dir) / "paper-acceptance-v2" / "facts" / plan_hash
    with _lock(root):
        facts = _read_facts(data_dir, plan_hash)
        previous = str(facts[-1]["fact_hash"]) if facts else None
        sequence = len(facts) + 1
        body: dict[str, object] = {
            "schema_version": 2,
            "plan_hash": plan_hash,
            "session_id": session_id,
            "policy_version": plan["policy_version"],
            "implementation_fingerprint": plan["implementation_fingerprint"],
            "sequence": sequence,
            "previous_fact_hash": previous,
            "source": source,
            "fact_type": fact_type,
            "correlation_id": correlation_id,
            "recorded_at": _stamp(recorded_at or datetime.now(UTC)),
            "raw_evidence": dict(raw_evidence),
        }
        fact_hash = _digest(body)
        fact = {**body, "fact_hash": fact_hash}
        write_text(
            root / f"{sequence:06d}-{fact_hash}.json",
            json.dumps(fact, sort_keys=True, indent=2, allow_nan=False) + "\n",
        )
    return fact


def _zero(facts: list[dict[str, object]], field: str) -> bool:
    values = [
        evidence[field]
        for fact in facts
        if isinstance((evidence := fact.get("raw_evidence")), dict) and field in evidence
    ]
    return bool(values) and all(value == 0 for value in values)


def _evidence_for(facts: list[dict[str, object]], fact_type: str) -> list[dict[str, object]]:
    return [
        evidence
        for fact in facts
        if fact.get("fact_type") == fact_type
        and isinstance((evidence := fact.get("raw_evidence")), dict)
    ]


def _positive_number(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _plan_report(data_dir: Path, plan_hash: str) -> dict[str, object]:
    plan = _read_plan(data_dir, plan_hash)
    facts = _read_facts(data_dir, plan_hash)
    types = {str(fact["fact_type"]) for fact in facts}
    connection_evidence = _evidence_for(facts, "connection")
    cancellations = _evidence_for(facts, "cancellation")
    entries = _evidence_for(facts, "entry")
    exits = _evidence_for(facts, "exit")
    restarts = _evidence_for(facts, "restart")
    no_live_port = bool(connection_evidence) and all(
        item.get("paper_port") == 4002 and item.get("live_port_attempted") is False
        for item in connection_evidence
    )
    cancellation_acknowledged = bool(cancellations) and all(
        isinstance(item.get("requested_order_id"), str)
        and bool(item["requested_order_id"])
        and item.get("acknowledged_order_id") == item["requested_order_id"]
        for item in cancellations
    )
    entry_exit = (
        bool(entries)
        and bool(exits)
        and all(
            isinstance(item.get("order_id"), str)
            and bool(item["order_id"])
            and isinstance(item.get("fill_id"), str)
            and bool(item["fill_id"])
            and _positive_number(item.get("quantity"))
            for item in [*entries, *exits]
        )
    )
    restart_reconciled = bool(restarts) and all(
        item.get("reconnected") is True and item.get("state_reconciled") is True
        for item in restarts
    )
    predicates = {
        "acknowledged_cancellation": cancellation_acknowledged,
        "entry_exit": entry_exit,
        "restart_reconciled": restart_reconciled,
        "zero_duplicate_orders": _zero(facts, "duplicate_orders"),
        "zero_unexplained_positions": _zero(facts, "unexplained_positions"),
        "zero_unresolved_fills": _zero(facts, "unresolved_fills"),
        "zero_live_port_attempts": no_live_port,
        "zero_secret_leakage": _zero(facts, "secret_sentinels_found"),
        "reconciliation_observed": "reconciliation" in types,
    }
    return {
        "plan_hash": plan_hash,
        "session_id": plan["session_id"],
        "fact_count": len(facts),
        "predicates": predicates,
        "paper_passed": bool(predicates) and all(predicates.values()),
    }


def acceptance_report(data_dir: Path) -> dict[str, object]:
    plans_root = Path(data_dir) / "paper-acceptance-v2" / "plans"
    reports: list[dict[str, object]] = []
    tampered = False
    for path in sorted(plans_root.glob("*.json")) if plans_root.exists() else []:
        try:
            reports.append(_plan_report(data_dir, path.stem))
        except DataError:
            tampered = True
    passed = (
        bool(reports) and all(bool(report["paper_passed"]) for report in reports) and not tampered
    )
    merged_predicates: dict[str, bool] = {}
    for report in reports:
        predicates = report["predicates"]
        if isinstance(predicates, dict):
            for key, value in predicates.items():
                merged_predicates[str(key)] = bool(value)
    return {
        "schema_version": 2,
        "status": "passed" if passed else "pending",
        "paper_passed": passed,
        "plans": reports,
        "predicates": merged_predicates,
        "tamper_detected": tampered,
        "legacy_journals": "monitoring_only",
        "what_if_credit": False,
        "live_capital_routing": "absent",
    }


def create_ibkr_what_if_plan(
    data_dir: Path,
    *,
    account_id: str,
    gateway_image: str,
    limit_price: float,
    collar_low: float,
    collar_high: float,
    expires_at: datetime,
    now: datetime | None = None,
) -> dict[str, object]:
    """Create the exact offline preview contract. This function never contacts IBKR."""
    account = account_id.strip().upper()
    if _ACCOUNT.fullmatch(account) is None:
        raise DataError("IBKR what-if requires a DU paper account")
    if _IMAGE.fullmatch(gateway_image) is None:
        raise DataError("IBKR what-if requires a reviewed digest-pinned gateway image")
    if any(
        isinstance(value, bool) or not math.isfinite(value)
        for value in (limit_price, collar_low, collar_high)
    ):
        raise DataError("IBKR what-if prices must be finite")
    if not collar_low <= limit_price <= collar_high or collar_low <= 0:
        raise DataError("IBKR what-if limit price must be inside the positive fixed collar")
    current = now or datetime.now(UTC)
    if expires_at.tzinfo is None or expires_at.utcoffset() is None or expires_at <= current:
        raise DataError("IBKR what-if expiry must be a future timezone-aware instant")
    body: dict[str, object] = {
        "schema_version": 2,
        "account_alias": f"DU…{account[-4:]}",
        "account_fingerprint": hashlib.sha256(account.encode()).hexdigest(),
        "host": "127.0.0.1",
        "port": 4002,
        "gateway_image_digest": gateway_image.rsplit("@", 1)[1],
        "symbol": "SPY",
        "instrument_id": "SPY.ARCA",
        "side": "BUY",
        "quantity": 1,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": limit_price,
        "collar_low": collar_low,
        "collar_high": collar_high,
        "what_if": True,
        "wire_transmit": True,
        "broker_order_transmitted": False,
        "expires_at": _stamp(expires_at),
        "one_shot": True,
        "paper_acceptance_credit": False,
    }
    plan_hash = _digest(body)
    plan = {**body, "plan_hash": plan_hash}
    root = Path(data_dir) / "ibkr-what-if-v2" / "plans"
    path = root / f"{plan_hash}.json"
    rendered = json.dumps(plan, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with _lock(root):
        if path.exists() and path.read_text(encoding="utf-8") != rendered:
            raise DataError("IBKR what-if plan identity collision")
        if not path.exists():
            write_text(path, rendered)
    return plan


def read_ibkr_what_if_plan(data_dir: Path, plan_hash: str) -> dict[str, object]:
    """Read and content-verify one immutable what-if plan without rewriting it."""
    if _SHA256.fullmatch(plan_hash) is None:
        raise DataError("IBKR what-if plan hash is invalid")
    paths = (
        Path(data_dir) / "ibkr-what-if-v2" / "plans" / f"{plan_hash}.json",
        Path(data_dir) / "ibkr-what-if-v1" / "plans" / f"{plan_hash}.json",
    )
    path = next((candidate for candidate in paths if candidate.exists()), None)
    if path is None:
        raise DataError("IBKR what-if plan is missing or unreadable")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("IBKR what-if plan is missing or unreadable") from exc
    if not isinstance(raw, dict) or raw.get("plan_hash") != plan_hash:
        raise DataError("IBKR what-if plan failed identity verification")
    body = {key: value for key, value in raw.items() if key != "plan_hash"}
    if _digest(body) != plan_hash:
        raise DataError("IBKR what-if plan failed content verification")
    return raw


__all__ = [
    "acceptance_report",
    "create_ibkr_what_if_plan",
    "freeze_acceptance_plan",
    "read_ibkr_what_if_plan",
    "record_callback_fact",
]
