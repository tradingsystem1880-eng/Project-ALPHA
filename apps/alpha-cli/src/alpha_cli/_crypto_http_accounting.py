"""Inactive per-explicit-HTTP-open accounting over a supplied disposable connection.

Shelved (2026-11-14, triage card 2): not wired in, kept for a future download-budget
policy and durable acquisition journal (backlog: controlstore-durable-acquisition).

No opener, schema setup, migration, provider policy or live authority. The caller holds
Ledger exclusion before binding. Transport owns retry decisions; only a known closed
HTTP 429 response permits its next retry ordinal. Interrupted bodies stay unknown.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, ClassVar
from urllib.error import HTTPError

from alpha_cli._crypto_backfill_accounting import (
    FixtureAccountingBlocked,
    FixtureBackfillAccounting,
)
from alpha_cli._market_data_acquisition_accounting import AcquisitionTransactions
from alpha_core import DataError

if TYPE_CHECKING:
    from alpha_cli._crypto_backfill import Ledger
    from alpha_data.crypto.providers._wire import HttpAttemptHook


class FixtureHttpAccounting(FixtureBackfillAccounting):
    """Explicit synthetic request charges, distinct from window dispatch accounting.

    Scope cannot mix window and HTTP attempt namespaces. This is cooperative current
    code exclusion, not fencing of old binaries or arbitrary callbacks. The transport
    operation includes bounded body read and close, not parsing or raw persistence.
    """

    _required_basis: ClassVar[str] = "synthetic_http_send"

    def dispatch(
        self,
        ledger: Ledger,
        acquire: Callable[..., Mapping[str, object]],
        args: tuple[str, str, str],
        parameters: Mapping[str, object],
    ) -> Mapping[str, object]:
        raise FixtureAccountingBlocked("HTTP_HOOK_REQUIRED_NOT_WINDOW_DISPATCH")

    def _scope(self, tx: AcquisitionTransactions) -> None:
        super()._scope(tx)
        if any(
            not row["attempt_id"].startswith("http_") for row in tx.scope_attempts(self.scope_id)
        ):
            raise FixtureAccountingBlocked("HTTP_SCOPE_UNIT_MISMATCH")

    def _attempt(self, request: str, ordinal: int) -> str:
        return (
            "http_"
            + hashlib.sha256(
                json.dumps([self.scope_id, request, self.attempt_label, ordinal]).encode()
            ).hexdigest()
        )

    def bind(self, ledger: Ledger, expected_request_hash: str | None = None) -> HttpAttemptHook:
        self._owned(ledger)
        if expected_request_hash is not None and (
            type(expected_request_hash) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_request_hash) is None
        ):
            raise FixtureAccountingBlocked("HTTP_REQUEST_IDENTITY_INVALID")

        def hook(request: str, ordinal: int, send: Callable[[], bytes]) -> bytes:
            if expected_request_hash is not None and request != expected_request_hash:
                raise FixtureAccountingBlocked("HTTP_REQUEST_IDENTITY_CHANGED")
            return self._send(ledger, request, ordinal, send)

        return hook

    def reconcile_http_uncertain(self, ledger: Ledger, request_hash: str, ordinal: int) -> None:
        """Only block on uncertainty; never infer no-send, refund or sender quiescence."""
        self._owned(ledger)
        if (
            type(request_hash) is not str
            or re.fullmatch(r"[0-9a-f]{64}", request_hash) is None
            or type(ordinal) is not int
            or not 0 <= ordinal <= 3
        ):
            raise FixtureAccountingBlocked("HTTP_RECONCILIATION_IDENTITY_INVALID")
        if not self._unknown(ledger, self._attempt(request_hash, ordinal)):
            raise FixtureAccountingBlocked(
                "HTTP_RECONCILIATION_UNAVAILABLE", reconciliation_persisted=False
            )

    def dispatch_window(
        self,
        ledger: Ledger,
        acquire: Callable[..., Mapping[str, object]],
        args: tuple[str, str, str],
        parameters: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Require real successful hooked HTTP work; never count the window as a send."""
        self._owned(ledger)
        try:
            self._transaction(self._scope)
        except Exception:
            raise FixtureAccountingBlocked("HTTP_SCOPE_OR_HISTORY_UNAVAILABLE") from None
        completed = 0
        bound = self.bind(ledger)

        def hook(request: str, ordinal: int, send: Callable[[], bytes]) -> bytes:
            nonlocal completed
            body = bound(request, ordinal, send)
            completed += 1
            return body

        try:
            result = acquire(*args, **dict(parameters), http_attempt_hook=hook)
        except FixtureAccountingBlocked:
            raise
        except BaseException:
            raise FixtureAccountingBlocked("HTTP_WINDOW_NOT_PUBLISHED") from None
        if completed == 0:
            raise FixtureAccountingBlocked("HTTP_HOOK_NOT_USED")
        self._owned(ledger)
        if self._is_cancelled():
            raise FixtureAccountingBlocked("HTTP_WINDOW_CANCELLED_WITHOUT_REFUND")
        try:
            self._transaction(self._scope)
        except Exception:
            raise FixtureAccountingBlocked("HTTP_WINDOW_HISTORY_UNAVAILABLE") from None
        if (
            not isinstance(result, Mapping)
            or not isinstance(result.get("normalized_manifest_id"), str)
            or re.fullmatch(r"[0-9a-f]{64}", str(result["normalized_manifest_id"])) is None
            or result.get("state") not in {"qualified", "warning", "quarantined", "unavailable"}
        ):
            raise FixtureAccountingBlocked("HTTP_WINDOW_RESULT_INVALID")
        return result

    def completion_fields(self, result: Mapping[str, object]) -> dict[str, object]:
        return {}

    def verify_window(
        self,
        ledger: Ledger,
        args: tuple[str, str, str],
        parameters: Mapping[str, object],
        entry: Mapping[str, object],
    ) -> None:
        raise FixtureAccountingBlocked("HTTP_COMPLETED_RESPONSE_BINDING_UNAVAILABLE")

    def _retry_reason_is_429(self, reason: object) -> bool:
        return reason == "http_429"

    def _send(
        self,
        ledger: Ledger,
        request: str,
        ordinal: int,
        send: Callable[[], bytes],
        *,
        response_reason: Callable[[bytes | None, HTTPError | None], str] | None = None,
        defer_success: bool = False,
        before_reserve: Callable[[AcquisitionTransactions], None] | None = None,
    ) -> bytes:
        self._owned(ledger)
        if type(ordinal) is not int or not 0 <= ordinal <= 3:
            raise FixtureAccountingBlocked("HTTP_RETRY_ORDINAL_INVALID")
        if self._is_cancelled():
            raise FixtureAccountingBlocked("CANCELLED_BEFORE_RESERVATION")
        attempt = self._attempt(request, ordinal)
        at_ms = self.bookkeeping_clock_ms()

        def start(tx: AcquisitionTransactions) -> None:
            self._scope(tx)
            if before_reserve is not None:
                before_reserve(tx)
            rows = tx.scope_attempts(self.scope_id)
            if any(row["state"] in {"reserved", "intent", "unknown"} for row in rows):
                raise FixtureAccountingBlocked("SCOPE_HAS_UNRESOLVED_OWNER")
            if tx.find_attempt(attempt) is not None:
                raise FixtureAccountingBlocked("HTTP_ATTEMPT_ALREADY_RECORDED")
            previous = [row for row in rows if row["request_hash"] == request]
            if ordinal == 0 and previous:
                raise FixtureAccountingBlocked("HTTP_REQUEST_REPLAY_REQUIRES_RETAINED_RESPONSE")
            if ordinal > 0:
                prior = tx.find_attempt(self._attempt(request, ordinal - 1))
                if (
                    len(previous) != ordinal
                    or prior is None
                    or prior["state"] != "failure"
                    or not self._retry_reason_is_429(prior["reason"])
                    or prior["cancel_requested"]
                ):
                    raise FixtureAccountingBlocked("HTTP_RETRY_PREDECESSOR_UNAVAILABLE")
            tx.reserve_attempt(
                attempt,
                self.scope_id,
                self.policy,
                request_hash=request,
                charges=self.charges,
                bookkeeping_time_ms=at_ms,
            )
            tx.record_intent("intent_" + attempt[5:], attempt)

        try:
            self._transaction(start)
        except FixtureAccountingBlocked:
            raise
        except DataError:
            raise FixtureAccountingBlocked("HTTP_ALLOWANCE_OR_HISTORY_REFUSED") from None
        except BaseException:
            persisted = self._unknown(ledger, attempt)
            raise FixtureAccountingBlocked(
                "HTTP_RESERVATION_UNCERTAIN", reconciliation_persisted=persisted
            ) from None

        body: bytes | None = None
        error: HTTPError | None = None
        try:
            self._owned(ledger)
            cancel = self._is_cancelled()

            def before_open(tx: AcquisitionTransactions) -> bool:
                self._scope(tx)
                row = tx.read_attempt(attempt)
                if (
                    row["state"] != "intent"
                    or row["scope"] != self.scope_id
                    or row["request_hash"] != request
                ):
                    raise FixtureAccountingBlocked("HTTP_INTENT_CHANGED")
                self._replay(tx, request, attempt, row)
                return bool(row["cancel_requested"])

            # Advisory recheck, not a fence: a change can still race after commit.
            durable_cancel = self._transaction(before_open)
            cancel = cancel or durable_cancel
            if not cancel:
                try:
                    body = send()  # Supplied wire operation; no SQL transaction held.
                except HTTPError as exc:
                    error = exc  # Wire closed the response before propagating it.
                if error is None and type(body) is not bytes:
                    raise FixtureAccountingBlocked("HTTP_BODY_RESULT_INVALID")
                self._owned(ledger)
                cancel = self._is_cancelled()
            retained_reason = (
                response_reason(body, error) if response_reason is not None and not cancel else None
            )
            if defer_success and error is None and not cancel:
                if self._transaction(before_open):
                    cancel = True
                else:
                    assert body is not None
                    return body

            def settle(tx: AcquisitionTransactions) -> bool:
                self._scope(tx)
                row = tx.read_attempt(attempt)
                if (
                    row["state"] != "intent"
                    or row["scope"] != self.scope_id
                    or row["request_hash"] != request
                ):
                    raise FixtureAccountingBlocked("HTTP_INTENT_CHANGED")
                self._replay(tx, request, attempt, row)
                cancelled = cancel or row["cancel_requested"]
                if cancelled and not row["cancel_requested"]:
                    tx.request_cancel("cancel_" + attempt[5:], attempt)
                outcome = "cancelled" if cancelled else "failure" if error else "success"
                reason = (
                    "cancel_without_refund"
                    if cancelled
                    else retained_reason
                    if retained_reason is not None
                    else f"http_{error.code}"
                    if error
                    else "read_operation_closed"
                )
                tx.record_outcome("settle_" + attempt[5:], attempt, outcome, reason)
                return not cancelled

            accepted = self._transaction(settle)
        except BaseException:
            persisted = self._unknown(ledger, attempt)
            raise FixtureAccountingBlocked(
                "HTTP_SEND_OR_SETTLEMENT_UNCERTAIN", reconciliation_persisted=persisted
            ) from None
        if not accepted:
            raise FixtureAccountingBlocked("CANCELLED_WITHOUT_REFUND")
        if error is not None:
            raise error
        assert body is not None
        return body
