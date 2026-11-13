"""Owned-process synthetic SQLite tests. No sender, provider or real store."""

from __future__ import annotations

import hashlib
import multiprocessing
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
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


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


@contextmanager
def _write(conn: sqlite3.Connection) -> Iterator[AcquisitionTransactions]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield AcquisitionTransactions(conn)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def _policy() -> FixturePolicy:
    return FixturePolicy(
        "campaign",
        "fixture_generation",
        (
            Dimension("campaign", "total", 1, None, None, 1),
            Dimension("shared_rate", "period", 3, 0, 100, 1),
        ),
    )


def _reserve(
    tx: AcquisitionTransactions, event: str, *, request_hash: str = "a" * 64
) -> dict[str, Any]:
    return tx.reserve_attempt(
        event,
        "scope",
        _policy(),
        request_hash=request_hash,
        charges=(Charge("campaign", "total", 1), Charge("shared_rate", "period", 1)),
        bookkeeping_time_ms=10,
    )


def _setup(path: Path) -> None:
    conn = _connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(FIXTURE_DDL)
    with _write(conn) as tx:
        tx.record_fixture_scope("scope", _policy(), history_available=True)
    conn.close()


def _contend(path: str, event: str, start: Any, result: Any) -> None:
    conn = _connect(path)
    try:
        if not start.wait(10):
            raise RuntimeError("fixture barrier timeout")
        with _write(conn) as tx:
            _reserve(tx, event, request_hash=hashlib.sha256(event.encode()).hexdigest())
        result.put("reserved")
    except DataError as exc:
        result.put("exhausted" if "allowance exhausted" in str(exc) else "unexpected_refusal")
    finally:
        conn.close()


def _crash_boundary(path: str, committed: bool, ready: Any, finish: Any) -> None:
    conn = _connect(path)
    conn.execute("BEGIN IMMEDIATE")
    _reserve(AcquisitionTransactions(conn), "attempt")
    if committed:
        conn.commit()
    ready.send("at_boundary")
    finish.wait(30)
    conn.close()


def test_multiprocess_one_remaining_unit(
    tmp_path: Path,
    owned_test_process: None,
) -> None:
    path = tmp_path / "fixture.sqlite"
    _setup(path)
    ctx = multiprocessing.get_context("spawn")
    start, result = ctx.Event(), ctx.Queue()
    children = [
        ctx.Process(target=_contend, args=(str(path), f"r{i}", start, result)) for i in range(4)
    ]
    try:
        for child in children:
            child.start()
        start.set()
        outcomes = [result.get(timeout=15) for _ in children]
        for child in children:
            child.join(10)
            assert child.exitcode == 0
        assert outcomes.count("reserved") == 1
        assert outcomes.count("exhausted") == 3
        conn = _connect(str(path))
        with _write(conn):
            assert conn.execute("SELECT count(*) FROM md_acquisition_attempts").fetchone()[0] == 1
            assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 2
        conn.close()
    finally:
        for child in children:
            if child.is_alive():
                child.kill()
                child.join(10)
        result.close()
        result.join_thread()


@pytest.mark.parametrize("committed", [False, True])
def test_kill_reopen_and_same_key_commit_uncertainty(
    tmp_path: Path,
    owned_test_process: None,
    committed: bool,
) -> None:
    path = tmp_path / "fixture.sqlite"
    _setup(path)
    ctx = multiprocessing.get_context("spawn")
    parent, child_pipe = ctx.Pipe(duplex=False)
    finish = ctx.Event()
    child = ctx.Process(target=_crash_boundary, args=(str(path), committed, child_pipe, finish))
    try:
        child.start()
        assert parent.poll(15)
        assert parent.recv() == "at_boundary"
        child.kill()
        child.join(10)
        assert child.exitcode is not None and child.exitcode != 0
        conn = _connect(str(path))
        with _write(conn) as tx:
            count = conn.execute("SELECT count(*) FROM md_acquisition_attempts").fetchone()[0]
            assert count == int(committed)
            # The outer caller resolves the same stable event after lost acknowledgment.
            first = _reserve(tx, "attempt")
            assert _reserve(tx, "attempt") == first
            assert first["ordinal"] == 1
        conn.close()
        conn = _connect(str(path))
        with _write(conn):
            assert conn.execute("SELECT count(*) FROM md_acquisition_attempts").fetchone()[0] == 1
        conn.close()
    finally:
        if child.is_alive():
            child.kill()
            child.join(10)
        parent.close()
        child_pipe.close()


def test_multi_dimension_failure_leaves_all_projections_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "fixture.sqlite"
    _setup(path)
    conn = _connect(str(path))
    with _write(conn) as tx:
        _reserve(tx, "first")
    before = list(conn.iterdump())
    with pytest.raises(DataError, match="exhausted"), _write(conn) as tx:
        tx.reserve_attempt(
            "second",
            "scope",
            _policy(),
            request_hash="b" * 64,
            charges=(Charge("campaign", "total", 1), Charge("shared_rate", "period", 1)),
            bookkeeping_time_ms=11,
        )
    assert list(conn.iterdump()) == before
    conn.close()


def test_fixture_coexists_with_existing_schema_without_global_migration(tmp_path: Path) -> None:
    # Only a disposable schema fixture, never ControlStore._open or owner records.
    from alpha_cli._control_schema import _SCHEMA, _SCHEMA_V2, _SCHEMA_V3, _SCHEMA_V4

    conn = _connect(str(tmp_path / "fixture.sqlite"))
    for ddl in (_SCHEMA, _SCHEMA_V2, _SCHEMA_V3, _SCHEMA_V4):
        conn.executescript(ddl)
    conn.execute("PRAGMA user_version=7")
    before = list(conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name"))
    conn.executescript(FIXTURE_DDL)
    with _write(conn) as tx:
        tx.record_fixture_scope("scope", _policy(), history_available=True)
        _reserve(tx, "first")
    after = list(
        conn.execute(
            "SELECT name,sql FROM sqlite_master WHERE name NOT LIKE "
            "'md_acquisition_%' AND name NOT LIKE 'sqlite_autoindex_md_acquisition_%' "
            "ORDER BY name"
        )
    )
    assert after == before
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
    conn.close()


def test_second_dimension_exhaustion_rolls_back_whole_vector(tmp_path: Path) -> None:
    conn = _connect(str(tmp_path / "fixture.sqlite"))
    conn.executescript(FIXTURE_DDL)
    p = FixturePolicy(
        "campaign",
        "generation",
        (
            Dimension("a_campaign", "total", 3, None, None, 1),
            Dimension("z_rate", "period", 1, 0, 100, 1),
        ),
    )
    charges = (Charge("a_campaign", "total", 1), Charge("z_rate", "period", 1))
    with _write(conn) as tx:
        tx.record_fixture_scope("scope", p, history_available=True)
        tx.reserve_attempt(
            "first", "scope", p, request_hash="a" * 64, charges=charges, bookkeeping_time_ms=10
        )
    before = list(conn.iterdump())
    with pytest.raises(DataError, match="exhausted"), _write(conn) as tx:
        tx.reserve_attempt(
            "second", "scope", p, request_hash="b" * 64, charges=charges, bookkeeping_time_ms=11
        )
    assert list(conn.iterdump()) == before
    conn.close()


def test_caller_read_transaction_pins_one_wal_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "fixture.sqlite"
    _setup(path)
    first, second = _connect(str(path)), _connect(str(path))
    first.execute("PRAGMA query_only=ON")
    first.execute("BEGIN")
    view = AcquisitionTransactions(first)
    with _write(second) as tx:
        _reserve(tx, "new_attempt")
    with pytest.raises(DataError, match="attempt missing"):
        view.read_attempt("new_attempt")
    first.rollback()
    first.execute("BEGIN")
    assert AcquisitionTransactions(first).read_attempt("new_attempt")["ordinal"] == 1
    first.rollback()
    first.close()
    second.close()
