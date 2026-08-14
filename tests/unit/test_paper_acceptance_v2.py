"""Typed paper acceptance and the separate non-transmitting IBKR preview."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from alpha_cli import ibkr_what_if, paper_acceptance
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
    assert plan["account_fingerprint"] == hashlib.sha256(b"DU1234567").hexdigest()
    assert "DU1234567" not in str(plan)
    assert plan["symbol"] == "SPY"
    assert plan["quantity"] == 1
    assert plan["time_in_force"] == "DAY"
    assert plan["what_if"] is True
    assert plan["wire_transmit"] is True
    assert plan["broker_order_transmitted"] is False
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


def test_what_if_execution_is_one_shot_redacted_and_non_transmitting(tmp_path: Path) -> None:
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

    class FakeTransport:
        def preview(
            self,
            *,
            plan: dict[str, object],
            account_id: str,
            timeout_seconds: float,
        ) -> ibkr_what_if.PreviewEvidence:
            assert plan["symbol"] == "SPY"
            assert plan["quantity"] == 1
            assert plan["time_in_force"] == "DAY"
            assert plan["what_if"] is True
            assert plan["wire_transmit"] is True
            assert plan["broker_order_transmitted"] is False
            assert account_id == "DU1234567"
            assert timeout_seconds == 15.0
            return ibkr_what_if.PreviewEvidence(
                broker_status="PreSubmitted",
                commission=1.0,
                commission_currency="USD",
                initial_margin_change="640.00",
                maintenance_margin_change="0.00",
                equity_with_loan_change="-640.00",
                position_before=2.0,
                position_after=2.0,
                order_status_callbacks=0,
                execution_callbacks=0,
            )

    receipt = ibkr_what_if.execute_preview(
        tmp_path,
        plan_hash=str(plan["plan_hash"]),
        account_id="DU1234567",
        transport=FakeTransport(),
        now=now + timedelta(minutes=1),
    )

    assert receipt["status"] == "PREVIEW_VERIFIED"
    assert receipt["account_alias"] == "DU…4567"
    assert receipt["what_if"] is True and receipt["wire_transmit"] is True
    assert receipt["broker_order_transmitted"] is False
    assert receipt["position_unchanged"] is True
    assert receipt["order_status_callbacks"] == 0
    assert receipt["execution_callbacks"] == 0
    assert receipt["paper_acceptance_credit"] is False
    artifact = next((tmp_path / "ibkr-what-if-v2" / "receipts").glob("*.json"))
    assert "DU1234567" not in artifact.read_text(encoding="utf-8")

    with pytest.raises(DataError, match="already executed"):
        ibkr_what_if.execute_preview(
            tmp_path,
            plan_hash=str(plan["plan_hash"]),
            account_id="DU1234567",
            transport=FakeTransport(),
            now=now + timedelta(minutes=2),
        )


def test_ibapi_transport_drives_exact_preview_callback_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ibapi.client  # type: ignore[import-untyped]
    import ibapi.contract  # type: ignore[import-untyped]
    import ibapi.order  # type: ignore[import-untyped]
    import ibapi.wrapper  # type: ignore[import-untyped]

    account = "DU1234567"

    class FakeWrapper:
        pass

    class FakeContract:
        pass

    class FakeOrder:
        pass

    class FakeClient:
        captured_contract: object | None = None
        captured_order: object | None = None

        def __init__(self, wrapper: Any) -> None:
            self.wrapper = wrapper
            self.connected = False

        def connect(self, host: str, port: int, clientId: int) -> None:  # noqa: N803
            assert (host, port, clientId) == ("127.0.0.1", 4002, 29)
            self.connected = True

        def run(self) -> None:
            self.wrapper.nextValidId(101)
            self.wrapper.managedAccounts(account)

        def reqPositions(self) -> None:  # noqa: N802
            self.wrapper.position(account, SimpleNamespace(symbol="SPY"), Decimal("2"), 640.0)
            self.wrapper.positionEnd()

        def cancelPositions(self) -> None:  # noqa: N802
            return None

        def placeOrder(self, order_id: int, contract: object, order: object) -> None:  # noqa: N802
            assert order_id == 101
            FakeClient.captured_contract = contract
            FakeClient.captured_order = order
            state = SimpleNamespace(
                status="PreSubmitted",
                commissionAndFees=1.0,
                commissionAndFeesCurrency="USD",
                initMarginChange="640",
                maintMarginChange="0",
                equityWithLoanChange="-640",
                rejectReason="",
            )
            self.wrapper.openOrder(order_id, contract, order, state)

        def isConnected(self) -> bool:  # noqa: N802
            return self.connected

        def disconnect(self) -> None:
            self.connected = False

    monkeypatch.setattr(ibapi.client, "EClient", FakeClient)
    monkeypatch.setattr(ibapi.contract, "Contract", FakeContract)
    monkeypatch.setattr(ibapi.order, "Order", FakeOrder)
    monkeypatch.setattr(ibapi.wrapper, "EWrapper", FakeWrapper)
    plan: dict[str, object] = {
        "host": "127.0.0.1",
        "port": 4002,
        "limit_price": 640.0,
        "plan_hash": "a" * 64,
    }

    evidence = ibkr_what_if.IBAPITransport().preview(
        plan=plan, account_id=account, timeout_seconds=1.0
    )

    assert evidence.broker_status == "PreSubmitted"
    assert evidence.position_before == evidence.position_after == 2.0
    assert evidence.order_status_callbacks == 0
    assert evidence.execution_callbacks == 0
    contract = cast(Any, FakeClient.captured_contract)
    order = cast(Any, FakeClient.captured_order)
    assert contract.symbol == "SPY"
    assert contract.exchange == "SMART"
    assert order.whatIf is True
    assert order.transmit is True
    assert order.totalQuantity == Decimal("1")


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("API is read-only", "read_only"),
        ("invalid account", "account"),
        ("invalid order id", "order_id"),
        ("contract unavailable", "contract"),
        ("invalid price", "price"),
        ("invalid quantity", "quantity"),
        ("unsupported version", "api_version"),
        ("manual user name required", "manual_order"),
        ("permission denied", "trading_permission"),
        ("invalid tif", "time_in_force"),
        ("other", "unclassified"),
    ],
)
def test_ibkr_error_messages_are_reduced_to_safe_categories(message: str, category: str) -> None:
    assert ibkr_what_if._error_category(message) == category


@pytest.mark.parametrize("value", [None, "not-a-date", "2026-08-13T00:00:00"])
def test_invalid_what_if_expiry_is_rejected(value: object) -> None:
    with pytest.raises(DataError, match="expiry is invalid"):
        ibkr_what_if._parse_expiry(value)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"broker_status": "bad/status"}, "invalid preview status"),
        ({"order_status_callbacks": 1}, "forbidden order"),
        ({"position_after": 2.0}, "position changed"),
        ({"position_before": float("inf"), "position_after": float("inf")}, "invalid position"),
        ({"commission": float("inf")}, "invalid preview commission"),
    ],
)
def test_invalid_preview_evidence_is_rejected(changes: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "broker_status": "PreSubmitted",
        "commission": 1.0,
        "commission_currency": "USD",
        "initial_margin_change": "1",
        "maintenance_margin_change": "0",
        "equity_with_loan_change": "-1",
        "position_before": 1.0,
        "position_after": 1.0,
        "order_status_callbacks": 0,
        "execution_callbacks": 0,
    }
    values.update(changes)
    evidence = ibkr_what_if.PreviewEvidence(**cast(Any, values))
    plan: dict[str, object] = {
        "plan_hash": "a" * 64,
        "account_alias": "DU…4567",
        "account_fingerprint": "b" * 64,
    }
    with pytest.raises(DataError, match=message):
        ibkr_what_if._validated_receipt(plan, evidence, datetime(2026, 8, 13, tzinfo=UTC))


def test_execute_preview_rejects_invalid_context_before_transport(tmp_path: Path) -> None:
    now = datetime(2026, 8, 13, tzinfo=UTC)
    plan = paper_acceptance.create_ibkr_what_if_plan(
        tmp_path,
        account_id="DU1234567",
        gateway_image="gateway@sha256:" + "a" * 64,
        limit_price=640.0,
        collar_low=600.0,
        collar_high=680.0,
        expires_at=now + timedelta(minutes=10),
        now=now,
    )
    plan_hash = str(plan["plan_hash"])
    transport = cast(ibkr_what_if.PreviewTransport, object())

    with pytest.raises(DataError, match="timezone-aware"):
        ibkr_what_if.execute_preview(
            tmp_path,
            plan_hash=plan_hash,
            account_id="DU1234567",
            transport=transport,
            now=datetime(2026, 8, 13),
        )
    with pytest.raises(DataError, match="DU paper account"):
        ibkr_what_if.execute_preview(
            tmp_path, plan_hash=plan_hash, account_id="LIVE123", transport=transport, now=now
        )
    with pytest.raises(DataError, match="timeout"):
        ibkr_what_if.execute_preview(
            tmp_path,
            plan_hash=plan_hash,
            account_id="DU1234567",
            transport=transport,
            timeout_seconds=0,
            now=now,
        )
    with pytest.raises(DataError, match="does not match"):
        ibkr_what_if.execute_preview(
            tmp_path, plan_hash=plan_hash, account_id="DU7654321", transport=transport, now=now
        )
    with pytest.raises(DataError, match="expired"):
        ibkr_what_if.execute_preview(
            tmp_path,
            plan_hash=plan_hash,
            account_id="DU1234567",
            transport=transport,
            now=now + timedelta(minutes=11),
        )

    invalid_body = {key: value for key, value in plan.items() if key != "plan_hash"}
    invalid_body["symbol"] = "QQQ"
    invalid_hash = hashlib.sha256(
        json.dumps(invalid_body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    invalid_plan = {**invalid_body, "plan_hash": invalid_hash}
    invalid_path = tmp_path / "ibkr-what-if-v2" / "plans" / f"{invalid_hash}.json"
    invalid_path.write_text(json.dumps(invalid_plan), encoding="utf-8")
    with pytest.raises(DataError, match="closed preview contract"):
        ibkr_what_if.execute_preview(
            tmp_path,
            plan_hash=invalid_hash,
            account_id="DU1234567",
            transport=transport,
            now=now,
        )


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("bad_endpoint", "endpoint is invalid"),
        ("auth_timeout", "authentication timed out"),
        ("wrong_account", "did not expose"),
        ("position_timeout", "position snapshot timed out"),
        ("bad_limit", "limit price is invalid"),
        ("preview_timeout", "preview timed out"),
        ("broker_error", "error code.*321"),
        ("missing_state", "no preview state"),
        ("rejected", "rejected"),
        ("unexpected", "failed safely"),
    ],
)
def test_ibapi_transport_failures_are_typed_and_redacted(
    monkeypatch: pytest.MonkeyPatch, scenario: str, message: str
) -> None:
    import ibapi.client
    import ibapi.contract
    import ibapi.order
    import ibapi.wrapper

    account = "DU1234567"

    class FakeWrapper:
        pass

    class FakeContract:
        pass

    class FakeOrder:
        pass

    class FakeClient:
        def __init__(self, wrapper: Any) -> None:
            self.wrapper = wrapper
            self.connected = False

        def connect(self, host: str, port: int, clientId: int) -> None:  # noqa: N803
            del host, port, clientId
            if scenario == "unexpected":
                raise ValueError("private vendor detail")
            self.connected = True

        def run(self) -> None:
            if scenario == "auth_timeout":
                return
            self.wrapper.nextValidId(101)
            self.wrapper.managedAccounts("DU9999999" if scenario == "wrong_account" else account)

        def reqPositions(self) -> None:  # noqa: N802
            if scenario == "position_timeout":
                return
            self.wrapper.position(account, SimpleNamespace(symbol="SPY"), Decimal("0"), 0.0)
            self.wrapper.positionEnd()

        def cancelPositions(self) -> None:  # noqa: N802
            return None

        def placeOrder(self, order_id: int, contract: object, order: object) -> None:  # noqa: N802
            if scenario == "preview_timeout":
                return
            if scenario == "broker_error":
                self.wrapper.error(
                    order_id,
                    0,
                    321,
                    "Error validating request.-'v': cause - invalid account",
                )
                return
            if scenario == "missing_state":
                self.wrapper.preview_done.set()
                return
            state = SimpleNamespace(
                status="PreSubmitted",
                commissionAndFees=1.0,
                commissionAndFeesCurrency="USD",
                initMarginChange="0",
                maintMarginChange="0",
                equityWithLoanChange="0",
                rejectReason="rejected" if scenario == "rejected" else "",
            )
            self.wrapper.openOrder(order_id, contract, order, state)

        def isConnected(self) -> bool:  # noqa: N802
            return self.connected

        def disconnect(self) -> None:
            self.connected = False

    monkeypatch.setattr(ibapi.client, "EClient", FakeClient)
    monkeypatch.setattr(ibapi.contract, "Contract", FakeContract)
    monkeypatch.setattr(ibapi.order, "Order", FakeOrder)
    monkeypatch.setattr(ibapi.wrapper, "EWrapper", FakeWrapper)
    plan: dict[str, object] = {
        "host": 123 if scenario == "bad_endpoint" else "127.0.0.1",
        "port": 4002,
        "limit_price": "bad" if scenario == "bad_limit" else 640.0,
        "plan_hash": "a" * 64,
    }

    with pytest.raises(DataError, match=message):
        ibkr_what_if.IBAPITransport().preview(plan=plan, account_id=account, timeout_seconds=0.01)


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
    what_if_path = tmp_path / "ibkr-what-if-v2" / "plans" / f"{what_if['plan_hash']}.json"
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


def test_legacy_what_if_v1_plan_remains_readable_but_cannot_execute(tmp_path: Path) -> None:
    body: dict[str, object] = {
        "schema_version": 1,
        "account_alias": "DU…1234",
        "host": "127.0.0.1",
        "port": 4002,
        "symbol": "SPY",
        "instrument_id": "SPY.ARCA",
        "side": "BUY",
        "quantity": 1,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": 10.0,
        "collar_low": 9.0,
        "collar_high": 11.0,
        "what_if": True,
        "transmit": False,
        "expires_at": "2099-01-01T00:00:00Z",
        "one_shot": True,
        "paper_acceptance_credit": False,
    }
    plan_hash = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    plan = {**body, "plan_hash": plan_hash}
    path = tmp_path / "ibkr-what-if-v1" / "plans" / f"{plan_hash}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(plan), encoding="utf-8")

    assert paper_acceptance.read_ibkr_what_if_plan(tmp_path, plan_hash) == plan
    with pytest.raises(DataError, match="does not match|outside the closed"):
        ibkr_what_if.execute_preview(
            tmp_path,
            plan_hash=plan_hash,
            account_id="DU1234",
            transport=cast(ibkr_what_if.PreviewTransport, object()),
            now=datetime(2026, 8, 13, tzinfo=UTC),
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
