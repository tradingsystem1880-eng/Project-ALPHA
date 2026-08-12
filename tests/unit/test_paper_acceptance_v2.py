"""Typed paper acceptance and the separate non-transmitting IBKR preview."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from alpha_cli import paper_acceptance
from alpha_core import DataError


def _record_complete_acceptance(data_dir: Path, plan_hash: str) -> None:
    facts: tuple[tuple[str, str, dict[str, object]], ...] = (
        ("connection_guard", "connection", {"paper_port": 4002, "live_port_attempted": False}),
        (
            "adapter_callback",
            "cancellation",
            {"requested_order_id": "order-1", "acknowledged_order_id": "order-1"},
        ),
        ("adapter_callback", "entry", {"order_id": "order-1", "fill_id": "fill-1", "quantity": 1}),
        ("adapter_callback", "exit", {"order_id": "order-2", "fill_id": "fill-2", "quantity": 1}),
        (
            "reconciliation_callback",
            "restart",
            {"reconnected": True, "state_reconciled": True},
        ),
        (
            "risk_guard",
            "risk_observation",
            {
                "duplicate_orders": 0,
                "unexplained_positions": 0,
                "unresolved_fills": 0,
                "secret_sentinels_found": 0,
            },
        ),
        (
            "reconciliation_callback",
            "reconciliation",
            {"duplicate_orders": 0, "unexplained_positions": 0, "unresolved_fills": 0},
        ),
    )
    for sequence, (source, fact_type, evidence) in enumerate(facts, start=1):
        paper_acceptance.record_callback_fact(
            data_dir,
            plan_hash=plan_hash,
            session_id="session-complete",
            source=source,
            fact_type=fact_type,
            correlation_id=f"complete/{sequence}",
            raw_evidence=evidence,
            recorded_at=datetime(2026, 8, 13, sequence, tzinfo=UTC),
        )


def test_typed_fact_chain_recomputes_and_rejects_forgery(tmp_path: Path) -> None:
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session-v2",
        implementation_fingerprint="a" * 64,
        correlation_root="corr-1",
    )
    first = paper_acceptance.record_callback_fact(
        tmp_path,
        plan_hash=str(plan["plan_hash"]),
        session_id="session-v2",
        source="connection_guard",
        fact_type="connection",
        correlation_id="corr-1/connect",
        raw_evidence={"paper_port": 4002, "live_port_attempted": False},
    )
    second = paper_acceptance.record_callback_fact(
        tmp_path,
        plan_hash=str(plan["plan_hash"]),
        session_id="session-v2",
        source="risk_guard",
        fact_type="risk_observation",
        correlation_id="corr-1/risk",
        raw_evidence={
            "duplicate_orders": 0,
            "unexplained_positions": 0,
            "unresolved_fills": 0,
            "secret_sentinels_found": 0,
        },
    )
    assert first["previous_fact_hash"] is None
    assert second["previous_fact_hash"] == first["fact_hash"]
    assert "passed" not in second

    report = paper_acceptance.acceptance_report(tmp_path)
    predicates = cast(dict[str, object], report["predicates"])
    assert report["schema_version"] == 2
    assert report["paper_passed"] is False
    assert predicates["zero_live_port_attempts"] is True
    assert predicates["zero_secret_leakage"] is True

    with pytest.raises(DataError, match="closed typed callback"):
        paper_acceptance.record_callback_fact(
            tmp_path,
            plan_hash=str(plan["plan_hash"]),
            session_id="session-v2",
            source="generic_api",
            fact_type="risk_observation",
            correlation_id="corr-1/forged",
            raw_evidence={"passed": True},
        )


def test_what_if_plan_is_exact_non_transmitting_and_gives_no_acceptance_credit(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 8, 13, tzinfo=UTC)
    plan = paper_acceptance.create_ibkr_what_if_plan(
        tmp_path,
        account_id="DU1234567",
        gateway_image="ghcr.io/example/ibkr@sha256:" + "b" * 64,
        limit_price=640.0,
        collar_low=600.0,
        collar_high=680.0,
        expires_at=now + timedelta(minutes=10),
        now=now,
    )
    assert plan["account_alias"] == "DU…4567"
    assert "DU1234567" not in str(plan)
    assert plan["symbol"] == "SPY"
    assert plan["quantity"] == 1
    assert plan["time_in_force"] == "DAY"
    assert plan["what_if"] is True
    assert plan["transmit"] is False
    assert paper_acceptance.acceptance_report(tmp_path)["paper_passed"] is False

    with pytest.raises(DataError, match="collar"):
        paper_acceptance.create_ibkr_what_if_plan(
            tmp_path,
            account_id="DU1234567",
            gateway_image="ghcr.io/example/ibkr@sha256:" + "b" * 64,
            limit_price=700.0,
            collar_low=600.0,
            collar_high=680.0,
            expires_at=now + timedelta(minutes=10),
            now=now,
        )


def test_complete_typed_callback_set_is_mechanically_accepted(tmp_path: Path) -> None:
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session-complete",
        implementation_fingerprint="c" * 64,
        correlation_root="complete",
    )
    _record_complete_acceptance(tmp_path, str(plan["plan_hash"]))

    report = paper_acceptance.acceptance_report(tmp_path)

    assert report["paper_passed"] is True
    predicates = cast(dict[str, object], report["predicates"])
    assert predicates and all(predicates.values())


@pytest.mark.parametrize(
    ("fact_type", "bad_evidence", "failed_predicate"),
    [
        (
            "cancellation",
            {"requested_order_id": "order-1", "acknowledged_order_id": "different"},
            "acknowledged_cancellation",
        ),
        (
            "entry",
            {"order_id": "order-1", "fill_id": "fill-1", "quantity": 0},
            "entry_exit",
        ),
        (
            "restart",
            {"reconnected": True, "state_reconciled": False},
            "restart_reconciled",
        ),
    ],
)
def test_producer_fact_presence_cannot_replace_mechanical_truth(
    tmp_path: Path,
    fact_type: str,
    bad_evidence: dict[str, object],
    failed_predicate: str,
) -> None:
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session-complete",
        implementation_fingerprint="8" * 64,
        correlation_root="complete",
    )
    plan_hash = str(plan["plan_hash"])
    _record_complete_acceptance(tmp_path, plan_hash)
    source = {
        "cancellation": "adapter_callback",
        "entry": "adapter_callback",
        "restart": "reconciliation_callback",
    }[fact_type]
    paper_acceptance.record_callback_fact(
        tmp_path,
        plan_hash=plan_hash,
        session_id="session-complete",
        source=source,
        fact_type=fact_type,
        correlation_id=f"complete/bad-{fact_type}",
        raw_evidence=bad_evidence,
    )

    report = paper_acceptance.acceptance_report(tmp_path)
    predicates = cast(dict[str, object], report["predicates"])
    assert report["paper_passed"] is False
    assert predicates[failed_predicate] is False


def test_plan_and_fact_tamper_fail_closed(tmp_path: Path) -> None:
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session-complete",
        implementation_fingerprint="d" * 64,
        correlation_root="complete",
    )
    plan_hash = str(plan["plan_hash"])
    _record_complete_acceptance(tmp_path, plan_hash)
    fact = next(
        path
        for path in (tmp_path / "paper-acceptance-v2" / "facts" / plan_hash).glob("*.json")
        if '"paper_port": 4002' in path.read_text(encoding="utf-8")
    )
    fact.write_text(fact.read_text(encoding="utf-8").replace("4002", "4001"), encoding="utf-8")

    report = paper_acceptance.acceptance_report(tmp_path)

    assert report["paper_passed"] is False
    assert report["tamper_detected"] is True


def test_plan_identity_and_content_are_reverified(tmp_path: Path) -> None:
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session",
        implementation_fingerprint="1" * 64,
        correlation_root="root",
    )
    plan_hash = str(plan["plan_hash"])
    path = tmp_path / "paper-acceptance-v2" / "plans" / f"{plan_hash}.json"
    path.write_text(path.read_text(encoding="utf-8").replace(plan_hash, "2" * 64), encoding="utf-8")
    with pytest.raises(DataError, match="identity verification"):
        paper_acceptance.record_callback_fact(
            tmp_path,
            plan_hash=plan_hash,
            session_id="session",
            source="connection_guard",
            fact_type="connection",
            correlation_id="root/1",
            raw_evidence={"paper_port": 4002, "live_port_attempted": False},
        )

    path.write_text(json.dumps({**plan, "session_id": "changed"}), encoding="utf-8")
    with pytest.raises(DataError, match="content verification"):
        paper_acceptance.record_callback_fact(
            tmp_path,
            plan_hash=plan_hash,
            session_id="session",
            source="connection_guard",
            fact_type="connection",
            correlation_id="root/1",
            raw_evidence={"paper_port": 4002, "live_port_attempted": False},
        )


def test_plan_and_what_if_identity_collisions_are_rejected(tmp_path: Path) -> None:
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session",
        implementation_fingerprint="3" * 64,
        correlation_root="root",
    )
    plan_path = tmp_path / "paper-acceptance-v2" / "plans" / f"{plan['plan_hash']}.json"
    plan_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="plan identity collision"):
        paper_acceptance.freeze_acceptance_plan(
            tmp_path,
            session_id="session",
            implementation_fingerprint="3" * 64,
            correlation_root="root",
        )

    now = datetime(2026, 8, 13, tzinfo=UTC)
    what_if = paper_acceptance.create_ibkr_what_if_plan(
        tmp_path,
        account_id="DU1234",
        gateway_image="gateway@sha256:" + "4" * 64,
        limit_price=10,
        collar_low=9,
        collar_high=11,
        expires_at=now + timedelta(minutes=1),
        now=now,
    )
    what_if_path = tmp_path / "ibkr-what-if-v1" / "plans" / f"{what_if['plan_hash']}.json"
    what_if_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="what-if plan identity collision"):
        paper_acceptance.create_ibkr_what_if_plan(
            tmp_path,
            account_id="DU1234",
            gateway_image="gateway@sha256:" + "4" * 64,
            limit_price=10,
            collar_low=9,
            collar_high=11,
            expires_at=now + timedelta(minutes=1),
            now=now,
        )


def test_fact_chain_rejects_unreadable_non_object_and_wrong_previous_hash(tmp_path: Path) -> None:
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session",
        implementation_fingerprint="5" * 64,
        correlation_root="root",
    )
    plan_hash = str(plan["plan_hash"])
    root = tmp_path / "paper-acceptance-v2" / "facts" / plan_hash
    root.mkdir(parents=True)
    path = root / "000001-bad.json"
    for body, message in (
        ("not-json", "unreadable"),
        ("[]", "must be an object"),
        ('{"fact_hash":"bad"}', "content verification"),
    ):
        path.write_text(body, encoding="utf-8")
        with pytest.raises(DataError, match=message):
            paper_acceptance.record_callback_fact(
                tmp_path,
                plan_hash=plan_hash,
                session_id="session",
                source="connection_guard",
                fact_type="connection",
                correlation_id="root/1",
                raw_evidence={"paper_port": 4002, "live_port_attempted": False},
            )


def test_callback_timestamp_must_be_timezone_aware(tmp_path: Path) -> None:
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session",
        implementation_fingerprint="6" * 64,
        correlation_root="root",
    )
    with pytest.raises(DataError, match="timezone-aware"):
        paper_acceptance.record_callback_fact(
            tmp_path,
            plan_hash=str(plan["plan_hash"]),
            session_id="session",
            source="connection_guard",
            fact_type="connection",
            correlation_id="root/1",
            raw_evidence={"paper_port": 4002, "live_port_attempted": False},
            recorded_at=datetime(2026, 8, 13),
        )


def test_fact_chain_rejects_a_validly_hashed_wrong_previous_link(tmp_path: Path) -> None:
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session",
        implementation_fingerprint="7" * 64,
        correlation_root="root",
    )
    plan_hash = str(plan["plan_hash"])
    fact = paper_acceptance.record_callback_fact(
        tmp_path,
        plan_hash=plan_hash,
        session_id="session",
        source="connection_guard",
        fact_type="connection",
        correlation_id="root/1",
        raw_evidence={"paper_port": 4002, "live_port_attempted": False},
    )
    path = next((tmp_path / "paper-acceptance-v2" / "facts" / plan_hash).glob("*.json"))
    changed = {**fact, "previous_fact_hash": "wrong"}
    body = {key: value for key, value in changed.items() if key != "fact_hash"}
    changed["fact_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(DataError, match="chain is broken"):
        paper_acceptance.record_callback_fact(
            tmp_path,
            plan_hash=plan_hash,
            session_id="session",
            source="risk_guard",
            fact_type="risk_observation",
            correlation_id="root/2",
            raw_evidence={
                "duplicate_orders": 0,
                "unexplained_positions": 0,
                "unresolved_fills": 0,
                "secret_sentinels_found": 0,
            },
        )


@pytest.mark.parametrize(
    ("fingerprint", "session", "correlation", "message"),
    [
        ("short", "session", "root", "SHA-256"),
        ("e" * 64, "", "root", "session and correlation"),
        ("e" * 64, "session", "", "session and correlation"),
    ],
)
def test_acceptance_plan_rejects_invalid_identity(
    tmp_path: Path, fingerprint: str, session: str, correlation: str, message: str
) -> None:
    with pytest.raises(DataError, match=message):
        paper_acceptance.freeze_acceptance_plan(
            tmp_path,
            session_id=session,
            implementation_fingerprint=fingerprint,
            correlation_root=correlation,
        )


def test_callback_rejects_missing_plan_session_lineage_and_schema(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="missing or unreadable"):
        paper_acceptance.record_callback_fact(
            tmp_path,
            plan_hash="0" * 64,
            session_id="missing",
            source="connection_guard",
            fact_type="connection",
            correlation_id="missing/1",
            raw_evidence={"paper_port": 4002, "live_port_attempted": False},
        )
    plan = paper_acceptance.freeze_acceptance_plan(
        tmp_path,
        session_id="session",
        implementation_fingerprint="f" * 64,
        correlation_root="root",
    )
    plan_hash = str(plan["plan_hash"])

    def record(session_id: str, correlation_id: str, evidence: dict[str, object]) -> None:
        paper_acceptance.record_callback_fact(
            tmp_path,
            plan_hash=plan_hash,
            source="connection_guard",
            fact_type="connection",
            raw_evidence=evidence,
            session_id=session_id,
            correlation_id=correlation_id,
        )

    with pytest.raises(DataError, match="session"):
        record("wrong", "root/1", {"paper_port": 4002, "live_port_attempted": False})
    with pytest.raises(DataError, match="lineage"):
        record("session", "wrong/1", {"paper_port": 4002, "live_port_attempted": False})
    with pytest.raises(DataError, match="closed typed schema"):
        record("session", "root/1", {"paper_port": 4002})


@pytest.mark.parametrize(
    ("account", "image", "price", "low", "high", "expiry", "message"),
    [
        ("LIVE1", "gateway@sha256:" + "a" * 64, 10.0, 9.0, 11.0, 1, "DU paper"),
        ("DU1", "latest", 10.0, 9.0, 11.0, 1, "digest-pinned"),
        ("DU1", "gateway@sha256:" + "a" * 64, float("nan"), 9.0, 11.0, 1, "finite"),
        ("DU1", "gateway@sha256:" + "a" * 64, 10.0, 9.0, 11.0, -1, "future"),
    ],
)
def test_what_if_plan_rejects_unsafe_inputs(
    tmp_path: Path,
    account: str,
    image: str,
    price: float,
    low: float,
    high: float,
    expiry: int,
    message: str,
) -> None:
    now = datetime(2026, 8, 13, tzinfo=UTC)
    with pytest.raises(DataError, match=message):
        paper_acceptance.create_ibkr_what_if_plan(
            tmp_path,
            account_id=account,
            gateway_image=image,
            limit_price=price,
            collar_low=low,
            collar_high=high,
            expires_at=now + timedelta(minutes=expiry),
            now=now,
        )
