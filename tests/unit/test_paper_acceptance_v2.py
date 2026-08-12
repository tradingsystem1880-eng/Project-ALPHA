"""Typed paper acceptance and the separate non-transmitting IBKR preview."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alpha_cli import paper_acceptance
from alpha_core import DataError


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
    assert report["schema_version"] == 2
    assert report["paper_passed"] is False
    assert report["predicates"]["zero_live_port_attempts"] is True
    assert report["predicates"]["zero_secret_leakage"] is True

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

