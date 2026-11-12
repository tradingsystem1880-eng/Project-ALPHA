"""Public disposable accounting fixtures; no provider or production authority."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from alpha_cli._market_data_acquisition_accounting import (
    FIXTURE_DDL,
    AcquisitionTransactions,
    Charge,
    Dimension,
    FixturePolicy,
)
from alpha_core.errors import DataError


def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.executescript(FIXTURE_DDL)
    return conn


@contextmanager
def write(conn: sqlite3.Connection) -> Iterator[AcquisitionTransactions]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield AcquisitionTransactions(conn)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def policy(limit: int = 2) -> FixturePolicy:
    return FixturePolicy(
        "campaign", "fixture_generation", (Dimension("campaign", "total", limit, None, None, 1),)
    )


def seed(conn: sqlite3.Connection, limit: int = 2) -> None:
    with write(conn) as tx:
        tx.record_fixture_scope("scope", policy(limit), history_available=True)


def reserve(
    tx: AcquisitionTransactions, event: str = "reserve_1", *, time: int = 10
) -> dict[str, Any]:
    return tx.reserve_attempt(
        event,
        "scope",
        policy(),
        request_hash="a" * 64,
        charges=(Charge("campaign", "total", 1),),
        bookkeeping_time_ms=time,
    )


def test_transaction_owned_by_caller_and_idempotent() -> None:
    conn = connection()
    seed(conn)
    with pytest.raises(DataError, match="active"):
        AcquisitionTransactions(conn)
    with write(conn) as tx:
        first = reserve(tx)
        assert reserve(tx) == first
        assert conn.in_transaction
    with write(conn) as tx:
        assert reserve(tx) == first
        assert tx.read_scope("scope")["history_available"] is True
    conn.close()


def test_cancel_never_refunds_and_unknown_blocks() -> None:
    conn = connection()
    seed(conn)
    with write(conn) as tx:
        first = reserve(tx)
        tx.record_intent("intent_1", first["attempt_id"])
        tx.request_cancel("cancel_1", first["attempt_id"])
        tx.record_outcome("outcome_1", first["attempt_id"], "unknown", "transport_unknown")
    with pytest.raises(DataError, match="history"), write(conn) as tx:
        tx.reserve_attempt(
            "reserve_2",
            "scope",
            policy(),
            request_hash="b" * 64,
            charges=(Charge("campaign", "total", 1),),
            bookkeeping_time_ms=100,
        )
    conn.close()


def test_policy_conflict_and_incomplete_vector_are_atomic() -> None:
    conn = connection()
    seed(conn)
    with write(conn) as tx:
        first = reserve(tx)
    for kwargs in ({"charges": ()}, {"charges": (Charge("campaign", "total", 2),)}):
        with pytest.raises(DataError), write(conn) as tx:
            tx.reserve_attempt(
                "bad",
                "scope",
                policy(),
                request_hash="b" * 64,
                bookkeeping_time_ms=10,
                **kwargs,
            )
    with pytest.raises(DataError, match="policy mismatch"), write(conn) as tx:
        tx.reserve_attempt(
            "bad",
            "scope",
            policy(3),
            request_hash="b" * 64,
            charges=(Charge("campaign", "total", 1),),
            bookkeeping_time_ms=10,
        )
    with write(conn) as tx:
        assert tx.read_attempt("reserve_1") == first
        assert conn.execute("SELECT count(*) FROM md_acquisition_events").fetchone()[0] == 2
    conn.close()


def test_replay_conflicts_and_unresolved_predecessor() -> None:
    conn = connection()
    seed(conn)
    with write(conn) as tx:
        reserve(tx)
    with pytest.raises(DataError, match="conflicting replay"), write(conn) as tx:
        reserve(tx, time=11)
    with pytest.raises(DataError, match="unresolved"), write(conn) as tx:
        reserve(tx, "second")
    with write(conn) as tx:
        tx.record_intent("intent", "reserve_1")
        tx.record_outcome("outcome", "reserve_1", "failure", "schema_failure")
        assert reserve(tx, "second")["ordinal"] == 2
    conn.close()


@pytest.mark.parametrize("outcome", ["success", "failure", "cancelled"])
def test_terminal_outcomes_and_cancel_do_not_refund(outcome: str) -> None:
    conn = connection()
    seed(conn, 1)
    with write(conn) as tx:
        first = tx.reserve_attempt(
            "r1",
            "scope",
            policy(1),
            request_hash="a" * 64,
            charges=(Charge("campaign", "total", 1),),
            bookkeeping_time_ms=10,
        )
        tx.record_intent("i1", first["attempt_id"])
        tx.request_cancel("c1", first["attempt_id"])
        tx.record_outcome("o1", first["attempt_id"], outcome, "fixture_outcome")
        tx.record_outcome("o1", first["attempt_id"], outcome, "fixture_outcome")
    with pytest.raises(DataError, match="exhausted"), write(conn) as tx:
        tx.reserve_attempt(
            "r2",
            "scope",
            policy(1),
            request_hash="b" * 64,
            charges=(Charge("campaign", "total", 1),),
            bookkeeping_time_ms=10,
        )
    conn.close()


def test_cancel_before_intent_blocks_intent_without_release() -> None:
    conn = connection()
    seed(conn)
    with write(conn) as tx:
        reserve(tx)
        tx.request_cancel("cancel", "reserve_1")
    with pytest.raises(DataError, match="intent refused"), write(conn) as tx:
        tx.record_intent("intent", "reserve_1")
    with write(conn) as tx:
        assert tx.read_attempt("reserve_1")["state"] == "reserved"
        assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    conn.close()


def test_unavailable_history_is_not_zero_and_cannot_be_reset() -> None:
    conn = connection()
    with write(conn) as tx:
        tx.record_fixture_scope("scope", policy(), history_available=False)
    with pytest.raises(DataError, match="history"), write(conn) as tx:
        reserve(tx)
    with pytest.raises(DataError, match="conflicting"), write(conn) as tx:
        tx.record_fixture_scope("scope", policy(), history_available=True)
    assert conn.execute("SELECT count(*) FROM md_acquisition_debits").fetchone()[0] == 0
    conn.close()


def test_explicit_periods_unknown_rollover_and_clock() -> None:
    conn = connection()
    p = FixturePolicy(
        "campaign",
        "generation",
        (
            Dimension("rate", "p1", 2, 0, 10, 1),
            Dimension("rate", "p2", 2, 10, 20, 1),
        ),
    )
    with write(conn) as tx:
        tx.record_fixture_scope("scope", p, history_available=True)
        tx.reserve_attempt(
            "r1",
            "scope",
            p,
            request_hash="a" * 64,
            charges=(Charge("rate", "p1", 1),),
            bookkeeping_time_ms=9,
        )
        tx.record_outcome("unknown", "r1", "unknown", "fixture_unknown")
    with pytest.raises(DataError, match="history"), write(conn) as tx:
        tx.reserve_attempt(
            "r2",
            "scope",
            p,
            request_hash="b" * 64,
            charges=(Charge("rate", "p2", 1),),
            bookkeeping_time_ms=10,
        )
    conn.close()
    conn = connection()
    seed(conn)
    with write(conn) as tx:
        reserve(tx)
    with pytest.raises(DataError, match="clock"), write(conn) as tx:
        tx.reserve_attempt(
            "r2",
            "scope",
            policy(),
            request_hash="b" * 64,
            charges=(Charge("campaign", "total", 1),),
            bookkeeping_time_ms=9,
        )
    conn.close()


@pytest.mark.parametrize(
    "mutation",
    [
        "DROP TABLE md_acquisition_events",
        "UPDATE md_acquisition_attempts SET body='{}'",
        "UPDATE md_acquisition_debits SET units=2",
        "UPDATE md_acquisition_events SET payload='{}' WHERE sequence=2",
        "CREATE TRIGGER md_bad AFTER INSERT ON md_acquisition_scopes BEGIN SELECT 1; END",
        "ALTER TABLE md_acquisition_scopes ADD COLUMN extra TEXT",
    ],
)
def test_missing_schema_tampered_history_and_projections_refuse(mutation: str) -> None:
    conn = connection()
    seed(conn)
    with write(conn) as tx:
        reserve(tx)
    conn.execute(mutation)
    with pytest.raises(DataError), write(conn):
        pass
    conn.close()


@pytest.mark.parametrize(
    "dimensions",
    [
        (),
        (Dimension("d", "p", True, None, None, 1),),
        (Dimension("d", "p", 2, 1, 1, 1),),
        (Dimension("d", "p1", 2, 0, 10, 1), Dimension("d", "p2", 2, 5, 20, 1)),
        (Dimension("d", "total", 2, None, None, 1), Dimension("d", "p2", 2, 10, 20, 1)),
    ],
)
def test_invalid_policy_has_no_side_effect(dimensions: tuple[Dimension, ...]) -> None:
    conn = connection()
    with pytest.raises(DataError), write(conn) as tx:
        tx.record_fixture_scope(
            "scope", FixturePolicy("c", "g", dimensions), history_available=True
        )
    assert conn.execute("SELECT count(*) FROM md_acquisition_events").fetchone()[0] == 0
    conn.close()


def test_scope_history_mark_and_bound_read_results() -> None:
    conn = connection()
    seed(conn)
    with write(conn) as tx:
        reserve(tx)
        returned = tx.read_scope("scope")
        returned["history_available"] = False
        assert tx.read_scope("scope")["history_available"] is True
        tx.record_unavailable_history("legacy", "scope", "opaque_legacy_reference")
        assert tx.read_event("legacy")["kind"] == "unavailable"
    with pytest.raises(DataError, match="history"), write(conn) as tx:
        tx.record_intent("intent", "reserve_1")
    conn.close()


def test_row_factory_readonly_snapshot_and_no_connection_lifecycle() -> None:
    conn = connection()
    seed(conn)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("BEGIN")
    tx = AcquisitionTransactions(conn)
    assert tx.read_scope("scope")["history_available"] is True
    assert conn.in_transaction
    conn.rollback()
    assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
    conn.close()


def test_partial_sql_failure_undoes_operation_but_not_outer_transaction() -> None:
    conn = connection()
    seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    tx = AcquisitionTransactions(conn)
    before = conn.execute("SELECT count(*) FROM md_acquisition_events").fetchone()[0]

    def deny_attempt_insert(action: int, table: str | None, *_: object) -> int:
        if action == sqlite3.SQLITE_INSERT and table == "md_acquisition_attempts":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(deny_attempt_insert)
    with pytest.raises(sqlite3.DatabaseError):
        reserve(tx)
    conn.set_authorizer(None)
    assert conn.in_transaction
    assert conn.execute("SELECT count(*) FROM md_acquisition_events").fetchone()[0] == before
    assert conn.execute("SELECT count(*) FROM md_acquisition_attempts").fetchone()[0] == 0
    conn.commit()
    with write(conn) as tx:
        reserve(tx)
    conn.close()


def test_generation_mismatch_does_not_reset_allowance() -> None:
    conn = connection()
    seed(conn)
    other = FixturePolicy("campaign", "different_generation", policy().dimensions)
    with pytest.raises(DataError, match="policy mismatch"), write(conn) as tx:
        tx.reserve_attempt(
            "r1",
            "scope",
            other,
            request_hash="a" * 64,
            charges=(Charge("campaign", "total", 1),),
            bookkeeping_time_ms=10,
        )
    conn.close()


def test_explicit_period_boundaries_and_no_omitted_dimension() -> None:
    conn = connection()
    p = FixturePolicy(
        "campaign",
        "generation",
        (
            Dimension("rate", "p1", 2, 0, 10, 1),
            Dimension("rate", "p2", 2, 10, 20, 1),
            Dimension("campaign", "total", 4, None, None, 1),
        ),
    )
    with write(conn) as tx:
        tx.record_fixture_scope("scope", p, history_available=True)
    for charges in [
        (Charge("rate", "p1", 1), Charge("campaign", "total", 1)),
        (Charge("rate", "p2", 1),),
    ]:
        with pytest.raises(DataError), write(conn) as tx:
            tx.reserve_attempt(
                "invalid",
                "scope",
                p,
                request_hash="a" * 64,
                charges=charges,
                bookkeeping_time_ms=10,
            )
    with write(conn) as tx:
        tx.reserve_attempt(
            "r1",
            "scope",
            p,
            request_hash="a" * 64,
            charges=(Charge("rate", "p2", 1), Charge("campaign", "total", 1)),
            bookkeeping_time_ms=10,
        )
    conn.close()


@pytest.mark.parametrize("intent", [False, True])
def test_unfinished_prior_period_prevents_unsafe_rollover(intent: bool) -> None:
    conn = connection()
    p = FixturePolicy(
        "campaign",
        "generation",
        (
            Dimension("rate", "p1", 2, 0, 10, 1),
            Dimension("rate", "p2", 2, 10, 20, 1),
        ),
    )
    with write(conn) as tx:
        tx.record_fixture_scope("scope", p, history_available=True)
        tx.reserve_attempt(
            "r1",
            "scope",
            p,
            request_hash="a" * 64,
            charges=(Charge("rate", "p1", 1),),
            bookkeeping_time_ms=9,
        )
        if intent:
            tx.record_intent("intent", "r1")
    with pytest.raises(DataError, match="unresolved prior period"), write(conn) as tx:
        tx.reserve_attempt(
            "r2",
            "scope",
            p,
            request_hash="b" * 64,
            charges=(Charge("rate", "p2", 1),),
            bookkeeping_time_ms=10,
        )
    conn.close()


def test_event_and_retained_payload_limits_fail_without_healing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import alpha_cli._market_data_acquisition_accounting as accounting

    conn = connection()
    seed(conn)
    with write(conn) as tx:
        reserve(tx)
    monkeypatch.setattr(accounting, "_MAX_EVENTS", 2)
    with pytest.raises(DataError, match="event budget exhausted"), write(conn) as tx:
        tx.record_intent("intent", "reserve_1")
    assert conn.execute("SELECT count(*) FROM md_acquisition_events").fetchone()[0] == 2
    monkeypatch.setattr(accounting, "_MAX_EVENTS", 2048)
    conn.execute("UPDATE md_acquisition_events SET payload=? WHERE sequence=2", (" " * 8193,))
    with pytest.raises(DataError, match="payload budget"), write(conn):
        pass
    assert (
        conn.execute(
            "SELECT length(payload) FROM md_acquisition_events WHERE sequence=2"
        ).fetchone()[0]
        == 8193
    )
    conn.close()


@pytest.mark.parametrize("operation", ["intent", "cancel", "outcome"])
def test_terminal_state_cannot_reopen(operation: str) -> None:
    conn = connection()
    seed(conn)
    with write(conn) as tx:
        reserve(tx)
        tx.record_intent("intent", "reserve_1")
        tx.record_outcome("outcome", "reserve_1", "success", "fixture_success")
    with pytest.raises(DataError), write(conn) as tx:
        if operation == "intent":
            tx.record_intent("other", "reserve_1")
        elif operation == "cancel":
            tx.request_cancel("other", "reserve_1")
        else:
            tx.record_outcome("other", "reserve_1", "failure", "conflict")
    conn.close()


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE TEMP TABLE md_acquisition_scopes (scope_id TEXT, body TEXT)",
        "CREATE TEMP VIEW md_acquisition_attempts AS SELECT * FROM main.md_acquisition_attempts",
        "CREATE TEMP TRIGGER attached AFTER INSERT ON main.md_acquisition_events "
        "BEGIN SELECT 1; END",
    ],
)
def test_temporary_shadow_or_attached_trigger_is_refused(ddl: str) -> None:
    conn = connection()
    seed(conn)
    conn.execute(ddl)
    with pytest.raises(DataError, match="temporary schema"), write(conn):
        pass
    conn.close()


def test_unrelated_temporary_schema_remains_compatible() -> None:
    conn = connection()
    seed(conn)
    conn.execute("CREATE TEMP TABLE unrelated (value TEXT)")
    conn.execute(
        "CREATE TEMP TRIGGER unrelated_trigger AFTER INSERT ON unrelated BEGIN SELECT 1; END"
    )
    with write(conn) as tx:
        reserve(tx)
    assert conn.execute("SELECT count(*) FROM unrelated").fetchone()[0] == 0
    conn.close()
