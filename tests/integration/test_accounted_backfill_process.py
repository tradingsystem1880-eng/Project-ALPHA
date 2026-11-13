"""Participating current-code dispatch ownership and crash boundaries on disposable SQLite."""

from __future__ import annotations

import multiprocessing
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._crypto_backfill import Ledger
from alpha_cli._crypto_backfill_accounting import FixtureAccountingBlocked
from alpha_cli._market_data_acquisition_accounting import Dimension, FixturePolicy
from alpha_core import DataError

from .test_accounted_backfill import POLICY, attempt_rows, bridge, run, setup


def connect(path: str, factory: Any = sqlite3.Connection) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=0.5, isolation_level=None, factory=factory)
    assert isinstance(conn, sqlite3.Connection)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def contender(
    path: str,
    root: str,
    symbol: str,
    policy: FixturePolicy,
    start: Any,
    entered: Any,
    release: Any,
    out: Any,
) -> None:
    conn = connect(path)
    try:
        if not start.wait(10):
            raise RuntimeError("fixture start timeout")

        def acquire(*a: Any, **k: Any) -> dict[str, object]:
            out.put(("dispatch", symbol))
            entered.set()
            if not release.wait(10):
                raise RuntimeError("fixture release timeout")
            return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

        result = run(Path(root), bridge(conn, policy=policy), acquire, symbols=[symbol])
        out.put(("done", str(result["done"])))
    except DataError as exc:
        out.put(("blocked", type(exc).__name__))
    finally:
        conn.close()


def stop(children: list[Any], release: Any) -> None:
    release.set()
    for child in children:
        child.join(5)
        if child.is_alive():
            child.terminate()
            child.join(5)


@pytest.mark.usefixtures("owned_test_process")
@pytest.mark.parametrize("same_request", [True, False])
def test_competing_processes_one_dispatch_no_double_spending(
    tmp_path: Path, same_request: bool
) -> None:
    path = tmp_path / "account.sqlite"
    policy = (
        POLICY
        if same_request
        else FixturePolicy(
            "campaign",
            "synthetic_generation",
            (Dimension("dispatches", "total", 1, None, None, 1),),
        )
    )
    conn = setup(path, policy)
    ctx = multiprocessing.get_context("spawn")
    start, entered, release, out = ctx.Event(), ctx.Event(), ctx.Event(), ctx.Queue()
    symbols = ["BTCUSDT"] * 4 if same_request else ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    children = [
        ctx.Process(
            target=contender,
            args=(str(path), str(tmp_path / str(i)), symbol, policy, start, entered, release, out),
        )
        for i, symbol in enumerate(symbols)
    ]
    try:
        for child in children:
            child.start()
        start.set()
        assert entered.wait(10)
        assert len(attempt_rows(conn)) == 1 and attempt_rows(conn)[0]["state"] == "intent"
        release.set()
        messages = [out.get(timeout=15) for _ in range(5)]
        assert sum(kind == "dispatch" for kind, _ in messages) == 1
        assert sum(kind == "done" for kind, _ in messages) == 1
        assert sum(kind == "blocked" for kind, _ in messages) == 3
        assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    finally:
        stop(children, release)
        conn.close()


class PausedCommit(sqlite3.Connection):
    entered: Any
    release: Any
    after: bool

    def commit(self) -> None:
        if self.after:
            super().commit()
        self.entered.set()
        if not self.release.wait(20):
            raise RuntimeError("fixture commit timeout")
        if not self.after:
            super().commit()


def crash_worker(path: str, root: str, phase: str, entered: Any, release: Any) -> None:
    conn = connect(path, PausedCommit if phase != "callback" else sqlite3.Connection)
    if isinstance(conn, PausedCommit):
        conn.entered = entered
        conn.release = release
        conn.after = phase == "after_commit"

    def acquire(*a: Any, **k: Any) -> dict[str, object]:
        entered.set()
        if not release.wait(20):
            raise RuntimeError("fixture callback timeout")
        return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

    try:
        run(Path(root), bridge(conn), acquire)
    finally:
        conn.close()


@pytest.mark.usefixtures("owned_test_process")
@pytest.mark.parametrize("phase", ["before_commit", "after_commit", "callback"])
def test_process_termination_reopen_and_conservative_reconciliation(
    tmp_path: Path, phase: str
) -> None:
    path = tmp_path / "account.sqlite"
    conn = setup(path)
    ctx = multiprocessing.get_context("spawn")
    entered, release = ctx.Event(), ctx.Event()
    child = ctx.Process(
        target=crash_worker, args=(str(path), str(tmp_path), phase, entered, release)
    )
    try:
        child.start()
        assert entered.wait(10)
        child.terminate()
        child.join(5)
        assert not child.is_alive()
        calls = []

        def acquire(*a: Any, **k: Any) -> dict[str, object]:
            calls.append(a)
            return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

        if phase == "before_commit":
            assert attempt_rows(conn) == []
            assert run(tmp_path, bridge(conn), acquire)["done"] == 1 and len(calls) == 1
        else:
            assert attempt_rows(conn)[0]["state"] == "intent"
            with pytest.raises(FixtureAccountingBlocked):
                run(tmp_path, bridge(conn), acquire)
            assert calls == []
            ledger = Ledger.open(
                tmp_path / "progress.json",
                provider="bybit",
                family="funding",
                category="linear",
                frequency="1h",
            )
            with ledger.exclusive(refresh=True):
                bridge(conn).reconcile_uncertain(
                    ledger,
                    ("bybit", "funding", "BTCUSDT"),
                    {
                        "base": "BTC",
                        "quote": "USDT",
                        "category": "linear",
                        "frequency": "1h",
                        "period": None,
                        "start": "2024-01-01T00:00:00Z",
                        "end": "2024-02-01T00:00:00Z",
                    },
                )
            assert attempt_rows(conn)[0]["state"] == "unknown"
            with pytest.raises(FixtureAccountingBlocked):
                run(tmp_path, bridge(conn, attempt_label="try2"), acquire)
            assert calls == []
        assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    finally:
        # A forcibly killed process may have held Event's internal lock. Never touch
        # that shared synchronization object after killing it; reap only this child.
        if child.is_alive():
            child.kill()
        child.join(5)
        conn.close()


class LostAck(sqlite3.Connection):
    commits: int = 0
    fail_on: int = 1

    def commit(self) -> None:
        super().commit()
        self.commits += 1
        if self.commits == self.fail_on:
            raise sqlite3.OperationalError("synthetic ack uncertainty")


@pytest.mark.parametrize("commit_number", [1, 2])
def test_commit_ack_uncertainty_cannot_dispatch_again_or_publish_progress(
    tmp_path: Path, commit_number: int
) -> None:
    path = tmp_path / "account.sqlite"
    setup(path).close()
    conn = connect(str(path), LostAck)
    assert isinstance(conn, LostAck)
    conn.fail_on = commit_number
    calls = []

    def acquire(*a: Any, **k: Any) -> dict[str, object]:
        calls.append(a)
        return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

    with pytest.raises(FixtureAccountingBlocked) as failure:
        run(tmp_path, bridge(conn), acquire)
    assert failure.value.reconciliation_persisted is True
    assert len(calls) == commit_number - 1 and not (tmp_path / "progress.json").exists()
    assert attempt_rows(conn)[0]["state"] == ("unknown" if commit_number == 1 else "success")
    with pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, bridge(conn, attempt_label="try2"), acquire)
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    conn.close()


@pytest.mark.usefixtures("owned_test_process")
def test_current_ledger_owner_prevents_other_accounted_owner_before_reservation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "account.sqlite"
    conn = setup(path)
    ledger = Ledger.open(
        tmp_path / "progress.json",
        provider="bybit",
        family="funding",
        category="linear",
        frequency="1h",
    )
    ctx = multiprocessing.get_context("spawn")
    start, entered, release, out = ctx.Event(), ctx.Event(), ctx.Event(), ctx.Queue()
    child = ctx.Process(
        target=contender,
        args=(str(path), str(tmp_path), "BTCUSDT", POLICY, start, entered, release, out),
    )
    try:
        with ledger.exclusive(refresh=True):
            child.start()
            start.set()
            assert out.get(timeout=10)[0] == "blocked"
            assert not entered.is_set() and attempt_rows(conn) == []
    finally:
        stop([child], release)
        conn.close()
