"""Closed, one-shot IBKR Paper what-if preview executor."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from alpha_cli import paper_acceptance
from alpha_cli._atomic import write_text
from alpha_core import DataError

_ACCOUNT = re.compile(r"^DU[A-Z0-9]+$")
_SAFE_STATUS = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]{0,31}$")
_VALIDATION_TAG = re.compile(r"request\.?-?'([^']+)'", re.IGNORECASE)
_IGNORED_CODES = frozenset({2104, 2106, 2107, 2158})


def _error_category(message: str) -> str:
    lowered = message.lower()
    categories = {
        "read_only": ("read-only", "read only"),
        "account": ("account",),
        "order_id": ("order id", "orderid"),
        "contract": ("contract", "security definition"),
        "price": ("price",),
        "quantity": ("quantity", "size"),
        "api_version": ("version",),
        "manual_order": ("manual", "user name", "username"),
        "trading_permission": ("permission", "not allowed", "restricted"),
        "time_in_force": ("time in force", "tif"),
    }
    return next(
        (name for name, needles in categories.items() if any(item in lowered for item in needles)),
        "unclassified",
    )


@dataclass(frozen=True, slots=True)
class PreviewEvidence:
    broker_status: str
    commission: float | None
    commission_currency: str
    initial_margin_change: str
    maintenance_margin_change: str
    equity_with_loan_change: str
    position_before: float
    position_after: float
    order_status_callbacks: int
    execution_callbacks: int


class PreviewTransport(Protocol):
    def preview(
        self,
        *,
        plan: dict[str, object],
        account_id: str,
        timeout_seconds: float,
    ) -> PreviewEvidence: ...


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_expiry(value: object) -> datetime:
    if not isinstance(value, str):
        raise DataError("IBKR what-if plan expiry is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError("IBKR what-if plan expiry is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataError("IBKR what-if plan expiry is invalid")
    return parsed.astimezone(UTC)


def _claim_once(data_dir: Path, plan_hash: str, attempted_at: datetime) -> None:
    root = Path(data_dir) / "ibkr-what-if-v2" / "attempts"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{plan_hash}.json"
    body = {
        "schema_version": 2,
        "plan_hash": plan_hash,
        "attempted_at": _stamp(attempted_at),
        "one_shot_claimed": True,
    }
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise DataError("IBKR what-if plan was already executed or attempted") from exc
    try:
        os.write(descriptor, json.dumps(body, sort_keys=True, indent=2).encode() + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validated_receipt(
    plan: dict[str, object], evidence: PreviewEvidence, executed_at: datetime
) -> dict[str, object]:
    if _SAFE_STATUS.fullmatch(evidence.broker_status) is None:
        raise DataError("IBKR returned an invalid preview status")
    if evidence.order_status_callbacks or evidence.execution_callbacks:
        raise DataError("IBKR what-if produced a forbidden order or execution callback")
    if evidence.position_before != evidence.position_after:
        raise DataError("IBKR paper position changed during the what-if preview")
    positions = (evidence.position_before, evidence.position_after)
    if not all(math.isfinite(value) for value in positions):
        raise DataError("IBKR returned an invalid position during the what-if preview")
    if evidence.commission is not None and not math.isfinite(evidence.commission):
        raise DataError("IBKR returned an invalid preview commission")
    if not all(
        (
            evidence.initial_margin_change,
            evidence.maintenance_margin_change,
            evidence.equity_with_loan_change,
        )
    ):
        raise DataError("IBKR what-if returned no margin-impact evidence")
    receipt_body: dict[str, object] = {
        "schema_version": 2,
        "plan_hash": plan["plan_hash"],
        "account_alias": plan["account_alias"],
        "account_fingerprint": plan["account_fingerprint"],
        "executed_at": _stamp(executed_at),
        "status": "PREVIEW_VERIFIED",
        "broker_status": evidence.broker_status,
        "what_if": True,
        "wire_transmit": True,
        "broker_order_transmitted": False,
        "position_before": evidence.position_before,
        "position_after": evidence.position_after,
        "position_unchanged": True,
        "order_status_callbacks": 0,
        "execution_callbacks": 0,
        "commission": evidence.commission,
        "commission_currency": evidence.commission_currency,
        "initial_margin_change": evidence.initial_margin_change,
        "maintenance_margin_change": evidence.maintenance_margin_change,
        "equity_with_loan_change": evidence.equity_with_loan_change,
        "paper_acceptance_credit": False,
    }
    return {**receipt_body, "receipt_hash": paper_acceptance.digest(receipt_body)}


def execute_preview(
    data_dir: Path,
    *,
    plan_hash: str,
    account_id: str,
    transport: PreviewTransport | None = None,
    timeout_seconds: float = 15.0,
    now: datetime | None = None,
) -> dict[str, object]:
    """Execute exactly one non-transmitting preview and persist a redacted receipt."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise DataError("IBKR what-if execution time must be timezone-aware")
    account = account_id.strip().upper()
    if _ACCOUNT.fullmatch(account) is None:
        raise DataError("IBKR what-if requires a DU paper account")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0 or timeout_seconds > 60:
        raise DataError("IBKR what-if timeout must be in (0, 60] seconds")
    plan = paper_acceptance.read_ibkr_what_if_plan(data_dir, plan_hash)
    if plan.get("account_alias") != f"DU…{account[-4:]}":
        raise DataError("IBKR paper account does not match the frozen what-if plan")
    if plan.get("account_fingerprint") != hashlib.sha256(account.encode()).hexdigest():
        raise DataError("IBKR paper account does not match the frozen what-if plan")
    if _parse_expiry(plan.get("expires_at")) <= current.astimezone(UTC):
        raise DataError("IBKR what-if plan has expired")
    required = {
        "host": "127.0.0.1",
        "port": 4002,
        "symbol": "SPY",
        "instrument_id": "SPY.ARCA",
        "side": "BUY",
        "quantity": 1,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "what_if": True,
        "wire_transmit": True,
        "broker_order_transmitted": False,
        "one_shot": True,
        "paper_acceptance_credit": False,
    }
    if any(plan.get(key) != value for key, value in required.items()):
        raise DataError("IBKR what-if plan is outside the closed preview contract")
    _claim_once(data_dir, plan_hash, current)
    evidence = (transport or IBAPITransport()).preview(
        plan=plan, account_id=account, timeout_seconds=timeout_seconds
    )
    receipt = _validated_receipt(plan, evidence, current)
    root = Path(data_dir) / "ibkr-what-if-v2" / "receipts"
    write_text(
        root / f"{receipt['receipt_hash']}.json",
        json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
    )
    return receipt


class IBAPITransport:
    """Narrow IB API adapter; it has no order-submission mode."""

    def preview(
        self,
        *,
        plan: dict[str, object],
        account_id: str,
        timeout_seconds: float,
    ) -> PreviewEvidence:
        from ibapi.client import EClient  # type: ignore[import-untyped]
        from ibapi.contract import Contract  # type: ignore[import-untyped]
        from ibapi.order import Order  # type: ignore[import-untyped]
        from ibapi.wrapper import EWrapper  # type: ignore[import-untyped]

        class Client(EWrapper, EClient):  # type: ignore[misc]
            def __init__(self) -> None:
                EClient.__init__(self, self)
                self.ready = threading.Event()
                self.positions_done = threading.Event()
                self.preview_done = threading.Event()
                self.next_order_id: int | None = None
                self.accounts: list[str] = []
                self.position_value = 0.0
                self.preview_state: object | None = None
                self.order_status_callbacks = 0
                self.execution_callbacks = 0
                self.error_codes: list[int] = []
                self.error_categories: list[str] = []
                self.validation_tags: list[str] = []

            def _ready_if_complete(self) -> None:
                if self.next_order_id is not None and self.accounts:
                    self.ready.set()

            def nextValidId(self, orderId: int) -> None:  # noqa: N802
                self.next_order_id = orderId
                self._ready_if_complete()

            def managedAccounts(self, accountsList: str) -> None:  # noqa: N802
                self.accounts = [item for item in accountsList.split(",") if item]
                self._ready_if_complete()

            def position(
                self, account: str, contract: object, position: object, avgCost: float
            ) -> None:
                del avgCost
                if account == account_id and getattr(contract, "symbol", "") == "SPY":
                    self.position_value = float(str(position))

            def positionEnd(self) -> None:  # noqa: N802
                self.positions_done.set()

            def openOrder(
                self, orderId: int, contract: object, order: object, orderState: object
            ) -> None:  # noqa: N802
                if orderId != self.next_order_id:
                    return
                safe = (
                    getattr(contract, "symbol", "") == "SPY"
                    and getattr(order, "whatIf", False) is True
                    and getattr(order, "transmit", False) is True
                    and getattr(order, "account", "") == account_id
                )
                if not safe:
                    self.error_codes.append(-1)
                self.preview_state = orderState
                self.preview_done.set()

            def orderStatus(self, orderId: int, *args: object) -> None:  # noqa: N802
                if orderId == self.next_order_id:
                    self.order_status_callbacks += 1

            def execDetails(self, reqId: int, contract: object, execution: object) -> None:  # noqa: N802
                del reqId, contract
                if getattr(execution, "orderId", None) == self.next_order_id:
                    self.execution_callbacks += 1

            def error(
                self,
                reqId: int,
                errorTime: int,
                errorCode: int,
                errorString: str,
                advancedOrderRejectJson: str = "",
            ) -> None:
                del reqId, errorTime, advancedOrderRejectJson
                if errorCode not in _IGNORED_CODES:
                    self.error_codes.append(errorCode)
                    self.error_categories.append(_error_category(errorString))
                    match = _VALIDATION_TAG.search(errorString)
                    if match is not None and match.group(1).isalnum():
                        self.validation_tags.append(match.group(1))

        client = Client()
        try:
            host = plan["host"]
            port = plan["port"]
            if not isinstance(host, str) or isinstance(port, bool) or not isinstance(port, int):
                raise DataError("IBKR what-if endpoint is invalid")
            client.connect(host, port, clientId=29)
            thread = threading.Thread(target=client.run, daemon=True)
            thread.start()
            if not client.ready.wait(timeout_seconds):
                raise DataError("IBKR paper API authentication timed out")
            if account_id not in client.accounts:
                raise DataError("IBKR gateway did not expose the frozen paper account")

            def snapshot_position() -> float:
                client.position_value = 0.0
                client.positions_done.clear()
                client.reqPositions()
                if not client.positions_done.wait(timeout_seconds):
                    raise DataError("IBKR paper position snapshot timed out")
                client.cancelPositions()
                return client.position_value

            before = snapshot_position()
            contract = Contract()
            contract.symbol = "SPY"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.primaryExchange = "ARCA"
            contract.currency = "USD"
            order = Order()
            order.action = "BUY"
            order.totalQuantity = Decimal("1")
            order.orderType = "LMT"
            limit_price = plan["limit_price"]
            if isinstance(limit_price, bool) or not isinstance(limit_price, int | float):
                raise DataError("IBKR what-if limit price is invalid")
            order.lmtPrice = float(limit_price)
            order.tif = "DAY"
            order.account = account_id
            order.outsideRth = False
            order.whatIf = True
            order.transmit = True
            order.orderRef = f"alpha-what-if-{plan['plan_hash']!s:.16}"
            assert client.next_order_id is not None
            client.placeOrder(client.next_order_id, contract, order)
            if not client.preview_done.wait(timeout_seconds):
                if client.error_codes:
                    codes = ",".join(str(code) for code in sorted(set(client.error_codes)))
                    categories = ",".join(sorted(set(client.error_categories)))
                    tags = ",".join(sorted(set(client.validation_tags))) or "none"
                    raise DataError(
                        f"IBKR what-if failed with broker error code(s): {codes}; "
                        f"category: {categories}; validation tag: {tags}"
                    )
                raise DataError("IBKR what-if preview timed out")
            time.sleep(0.5)
            after = snapshot_position()
            if client.error_codes:
                codes = ",".join(str(code) for code in sorted(set(client.error_codes)))
                categories = ",".join(sorted(set(client.error_categories)))
                tags = ",".join(sorted(set(client.validation_tags))) or "none"
                raise DataError(
                    f"IBKR what-if failed with broker error code(s): {codes}; "
                    f"category: {categories}; validation tag: {tags}"
                )
            state = client.preview_state
            if state is None:
                raise DataError("IBKR what-if returned no preview state")
            for field in (
                "commissionAndFees",
                "initMarginChange",
                "maintMarginChange",
                "equityWithLoanChange",
                "commissionAndFeesCurrency",
            ):
                if not hasattr(state, field):
                    raise DataError(f"IBKR preview state is missing {field}; ibapi drifted")
            raw_commission = float(getattr(state, "commissionAndFees", float("nan")))
            commission = (
                raw_commission
                if math.isfinite(raw_commission) and raw_commission <= 1e100
                else None
            )
            reject_reason = str(getattr(state, "rejectReason", "")).strip()
            if reject_reason:
                raise DataError("IBKR rejected the non-transmitting what-if preview")
            return PreviewEvidence(
                broker_status=str(getattr(state, "status", "")),
                commission=commission,
                commission_currency=str(getattr(state, "commissionAndFeesCurrency", "")),
                initial_margin_change=str(getattr(state, "initMarginChange", "")),
                maintenance_margin_change=str(getattr(state, "maintMarginChange", "")),
                equity_with_loan_change=str(getattr(state, "equityWithLoanChange", "")),
                position_before=before,
                position_after=after,
                order_status_callbacks=client.order_status_callbacks,
                execution_callbacks=client.execution_callbacks,
            )
        except (DataError, OSError):
            raise
        except Exception as exc:
            raise DataError("IBKR what-if preview failed safely") from exc
        finally:
            if client.isConnected():
                client.disconnect()


__all__ = ["IBAPITransport", "PreviewEvidence", "PreviewTransport", "execute_preview"]
