"""Opt-in synthetic WINDOW dispatch accounting over a supplied disposable connection.

No database opener, DDL, live ControlStore, provider route or send permit exists here.
This adapter is the transaction caller of the existing inactive fragment. Ledger ownership
must precede SQLite; callback/artifact I/O never runs inside a SQLite transaction.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from alpha_cli._market_data_acquisition_accounting import (
    AcquisitionTransactions,
    Charge,
    FixturePolicy,
    _policy_body,
)
from alpha_core.errors import DataError

if TYPE_CHECKING:
    from alpha_cli._crypto_backfill import Ledger

T = TypeVar("T")


class FixtureAccountingBlocked(DataError):
    def __init__(self, code: str, *, reconciliation_persisted: bool | None = None) -> None:
        super().__init__(f"synthetic backfill accounting blocked: {code}")
        self.reason_code = code
        self.reconciliation_persisted = reconciliation_persisted


@dataclass(frozen=True, eq=False)
class FixtureBackfillAccounting:
    """One unresolved synthetic dispatch per scope; no lease expiry, steal or refund.

    Policy/charges/attempt label and clock are explicit caller inputs, not inferred
    provider quota. The supplied connection remains caller-owned and is never closed.
    Configured SQLite busy timeout bounds lock waits, not OS I/O or total elapsed time.
    """

    _required_basis: ClassVar[str] = "synthetic_window_dispatch"

    connection: sqlite3.Connection
    scope_id: str
    policy: FixturePolicy
    charges: tuple[Charge, ...]
    attempt_label: str
    bookkeeping_clock_ms: Callable[[], int]
    cancelled: Callable[[], bool]
    busy_timeout_ms: int
    allowance_basis: str
    _owner: tuple[int, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_owner", (os.getpid(), threading.get_ident()))
        connection = self.connection
        scope_id, attempt_label = self.scope_id, self.attempt_label
        policy, charges = self.policy, self.charges
        bookkeeping_clock_ms, cancelled = self.bookkeeping_clock_ms, self.cancelled
        busy_timeout_ms, allowance_basis = self.busy_timeout_ms, self.allowance_basis
        try:
            if (
                not isinstance(connection, sqlite3.Connection)
                or connection.in_transaction
                or allowance_basis != self._required_basis
                or any(
                    type(v) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,96}", v) is None
                    for v in (scope_id, attempt_label)
                )
                or type(charges) is not tuple
                or not charges
                or any(type(c) is not Charge for c in charges)
                or not callable(bookkeeping_clock_ms)
                or not callable(cancelled)
                or type(busy_timeout_ms) is not int
                or not 0 <= busy_timeout_ms <= 2**31 - 1
            ):
                raise ValueError("invalid fixture inputs")
            _policy_body(policy)
            self._configuration()
        except (DataError, ValueError, sqlite3.Error, AttributeError, TypeError):
            raise FixtureAccountingBlocked("EXPLICIT_FIXTURE_INPUTS_REQUIRED") from None

    def _configuration(self) -> None:
        try:
            if (
                self.connection.execute("PRAGMA journal_mode").fetchone()[0] != "wal"
                or self.connection.execute("PRAGMA synchronous").fetchone()[0] < 2
                or self.connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1
                or self.connection.execute("PRAGMA busy_timeout").fetchone()[0]
                != self.busy_timeout_ms
            ):
                raise ValueError("borrowed fixture connection changed")
        except (sqlite3.Error, ValueError):
            raise FixtureAccountingBlocked("FIXTURE_CONNECTION_CONFIGURATION_CHANGED") from None

    def check_idle_owner(self) -> None:
        """Check before the orchestrator touches a filesystem lock; caller lends exclusively."""
        if self._owner != (os.getpid(), threading.get_ident()) or self.connection.in_transaction:
            raise FixtureAccountingBlocked("IDLE_CONNECTION_OWNER_REQUIRED")
        self._configuration()

    def _owned(self, ledger: Ledger) -> None:
        self.check_idle_owner()
        try:
            ledger._check_owner()
        except DataError:
            raise FixtureAccountingBlocked("LEDGER_OWNER_REQUIRED") from None

    def _transaction(self, action: Callable[[AcquisitionTransactions], T]) -> T:
        if self.connection.in_transaction:
            raise FixtureAccountingBlocked("IDLE_CONNECTION_REQUIRED")
        self._configuration()
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            result = action(AcquisitionTransactions(self.connection))
            self.connection.commit()
            if self.connection.in_transaction:
                raise FixtureAccountingBlocked("COMMIT_NOT_ACKNOWLEDGED")
            return result
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _scope(self, tx: AcquisitionTransactions) -> None:
        scope = tx.read_scope(self.scope_id)
        if not scope["history_available"] or scope["policy"] != _policy_body(self.policy):
            raise FixtureAccountingBlocked("SCOPE_POLICY_OR_HISTORY_UNAVAILABLE")
        if self._required_basis == "synthetic_window_dispatch" and any(
            not row["attempt_id"].startswith("attempt_") for row in tx.scope_attempts(self.scope_id)
        ):
            raise FixtureAccountingBlocked("WINDOW_SCOPE_UNIT_MISMATCH")

    def _identity(
        self, args: tuple[str, str, str], parameters: Mapping[str, object]
    ) -> tuple[str, str]:
        try:
            raw = json.dumps(
                {
                    "schema": "synthetic_backfill_window_v1",
                    "args": args,
                    "parameters": dict(parameters),
                },
                sort_keys=True,
                allow_nan=False,
            ).encode()
            if len(raw) > 8192:
                raise ValueError("identity budget")
        except (ValueError, TypeError):
            raise FixtureAccountingBlocked("REQUEST_IDENTITY_INVALID") from None
        request = hashlib.sha256(raw).hexdigest()
        attempt = hashlib.sha256(
            json.dumps([self.scope_id, request, self.attempt_label]).encode()
        ).hexdigest()
        return request, "attempt_" + attempt

    def _replay(
        self, tx: AcquisitionTransactions, request: str, attempt: str, row: Mapping[str, Any]
    ) -> None:
        # Exact reserve replay checks scope, full immutable policy, request and charge vector.
        tx.reserve_attempt(
            attempt,
            self.scope_id,
            self.policy,
            request_hash=request,
            charges=self.charges,
            bookkeeping_time_ms=row["at_ms"],
        )

    def _is_cancelled(self) -> bool:
        value = self.cancelled()
        if type(value) is not bool:
            raise FixtureAccountingBlocked("CANCELLATION_STATE_INVALID")
        return value

    def _unknown(self, ledger: Ledger, attempt: str) -> bool:
        """One-way conservative reconciliation; never release or assert no send/quiescence."""
        try:
            self._owned(ledger)

            def mark(tx: AcquisitionTransactions) -> None:
                row = tx.find_attempt(attempt)
                if (
                    row is not None
                    and row["scope"] == self.scope_id
                    and row["state"] in {"reserved", "intent"}
                ):
                    tx.record_outcome(
                        "unknown_" + attempt.split("_", 1)[1],
                        attempt,
                        "unknown",
                        "dispatch_uncertain",
                    )
                else:
                    tx.record_unavailable_history(
                        "unavailable_" + attempt.split("_", 1)[1],
                        self.scope_id,
                        "dispatch_reconciliation_required",
                    )

            self._transaction(mark)
            return True
        except Exception:
            # The fatal error exposes that this marker could not be persisted. Any retained
            # unresolved intent still blocks subsequent participating scope dispatches.
            return False

    def verify_done(
        self, ledger: Ledger, args: tuple[str, str, str], parameters: Mapping[str, object]
    ) -> None:
        self._owned(ledger)
        request, attempt = self._identity(args, parameters)

        def check(tx: AcquisitionTransactions) -> None:
            self._scope(tx)
            row = tx.find_attempt(attempt)
            if row is None or row["state"] != "success" or row["cancel_requested"]:
                raise FixtureAccountingBlocked("COMPLETED_ACCOUNTING_EVIDENCE_UNAVAILABLE")
            self._replay(tx, request, attempt, row)

        try:
            self._transaction(check)
        except FixtureAccountingBlocked:
            raise
        except Exception:
            raise FixtureAccountingBlocked("COMPLETED_ACCOUNTING_INVALID") from None

    def reconcile_uncertain(
        self, ledger: Ledger, args: tuple[str, str, str], parameters: Mapping[str, object]
    ) -> None:
        self._owned(ledger)
        _request, attempt = self._identity(args, parameters)
        if not self._unknown(ledger, attempt):
            raise FixtureAccountingBlocked(
                "RECONCILIATION_UNAVAILABLE", reconciliation_persisted=False
            )

    def dispatch(
        self,
        ledger: Ledger,
        acquire: Callable[..., Mapping[str, object]],
        args: tuple[str, str, str],
        parameters: Mapping[str, object],
    ) -> Mapping[str, object]:
        self._owned(ledger)
        request, attempt = self._identity(args, parameters)
        if self._is_cancelled():
            raise FixtureAccountingBlocked("CANCELLED_BEFORE_RESERVATION")
        at_ms = self.bookkeeping_clock_ms()  # Caller clock executes outside SQL.

        def start(tx: AcquisitionTransactions) -> None:
            self._scope(tx)
            existing = tx.find_attempt(attempt)
            if existing is not None:
                self._replay(tx, request, attempt, existing)
                raise FixtureAccountingBlocked("EXISTING_ATTEMPT_REQUIRES_EVIDENCE")
            retained = tx.scope_attempts(self.scope_id)
            if any(
                row["request_hash"] == request and row["state"] == "success" for row in retained
            ):
                raise FixtureAccountingBlocked("PRIOR_SUCCESS_REQUIRES_EVIDENCE")
            if any(row["state"] in {"reserved", "intent", "unknown"} for row in retained):
                raise FixtureAccountingBlocked("SCOPE_HAS_UNRESOLVED_OWNER")
            tx.reserve_attempt(
                attempt,
                self.scope_id,
                self.policy,
                request_hash=request,
                charges=self.charges,
                bookkeeping_time_ms=at_ms,
            )
            tx.record_intent("intent_" + attempt.split("_", 1)[1], attempt)

        try:
            self._transaction(start)
        except FixtureAccountingBlocked:
            raise
        except DataError:
            raise FixtureAccountingBlocked("ALLOWANCE_OR_HISTORY_REFUSED") from None
        except Exception:
            persisted = self._unknown(ledger, attempt)
            raise FixtureAccountingBlocked(
                "RESERVATION_COMMIT_UNCERTAIN", reconciliation_persisted=persisted
            ) from None
        except BaseException:
            self._unknown(ledger, attempt)
            raise
        result: Mapping[str, object] | None = None
        try:
            self._owned(ledger)
            local_cancel = self._is_cancelled()
            if not local_cancel:
                result = acquire(*args, **parameters)  # Never inside a SQLite transaction.
                if (
                    not isinstance(result, Mapping)
                    or not isinstance(result.get("normalized_manifest_id"), str)
                    or re.fullmatch(r"[0-9a-f]{64}", str(result["normalized_manifest_id"])) is None
                    or result.get("state")
                    not in {"qualified", "warning", "quarantined", "unavailable"}
                ):
                    raise FixtureAccountingBlocked("DISPATCH_RESULT_INVALID")
                self._owned(ledger)
                local_cancel = self._is_cancelled()

            def settle(tx: AcquisitionTransactions) -> bool:
                self._scope(tx)
                row = tx.read_attempt(attempt)
                if (
                    row["state"] != "intent"
                    or row["scope"] != self.scope_id
                    or row["request_hash"] != request
                    or row["attempt_id"] != attempt
                ):
                    raise FixtureAccountingBlocked("INTENT_NO_LONGER_CURRENT")
                self._replay(tx, request, attempt, row)
                cancel = local_cancel or row["cancel_requested"]
                if cancel and not row["cancel_requested"]:
                    tx.request_cancel("cancel_" + attempt.split("_", 1)[1], attempt)
                reason = (
                    "result_discarded_cancel" if result is not None else "cancel_before_dispatch"
                )
                tx.record_outcome(
                    "settle_" + attempt.split("_", 1)[1],
                    attempt,
                    "cancelled" if cancel else "success",
                    reason if cancel else "dispatch_returned",
                )
                return not cancel

            accepted = self._transaction(settle)
        except Exception:
            persisted = self._unknown(ledger, attempt)
            raise FixtureAccountingBlocked(
                "DISPATCH_OR_SETTLEMENT_UNCERTAIN", reconciliation_persisted=persisted
            ) from None
        except BaseException:
            self._unknown(ledger, attempt)
            raise
        if not accepted:
            raise FixtureAccountingBlocked("CANCELLED_WITHOUT_REFUND")
        if not isinstance(result, Mapping):
            raise FixtureAccountingBlocked("DISPATCH_RESULT_INVALID")
        return result
