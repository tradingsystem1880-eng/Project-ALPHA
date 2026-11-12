"""Participating sender exclusion and process termination: synthetic HTTP only."""

from __future__ import annotations

import multiprocessing
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.request import Request

import pytest

from alpha_cli._crypto_backfill_accounting import FixtureAccountingBlocked

from .test_accounted_backfill import attempt_rows, setup
from .test_accounted_backfill_process import PausedCommit, connect
from .test_accounted_http import POLICY, URL, Response, account, fetch, ledger


def worker(path: str, root: str, phase: str, entered: Any, release: Any, out: Any) -> None:
    conn = connect(
        path, PausedCommit if phase in {"before_commit", "after_commit"} else sqlite3.Connection
    )
    if isinstance(conn, PausedCommit):
        conn.entered, conn.release, conn.after = entered, release, phase == "after_commit"
    owner = ledger(Path(root))

    class Opener:
        def open(self, request: Request, **kwargs: Any) -> Response:
            Path(root, "send-marker").write_text("synthetic open entered")
            out.put("send")
            entered.set()
            if not release.wait(15):
                raise RuntimeError("fixture timeout")
            return Response(URL)

    try:
        with owner.exclusive(), patch("urllib.request.build_opener", lambda *a: Opener()):
            fetch(account(conn).bind(owner))
        out.put("done")
    except FixtureAccountingBlocked:
        out.put("blocked")
    finally:
        conn.close()


@pytest.mark.usefixtures("owned_test_process")
@pytest.mark.parametrize("phase", ["before_commit", "after_commit", "send"])
def test_kill_reopen_has_no_duplicate_send_or_refund(tmp_path: Path, phase: str) -> None:
    path = tmp_path / "a.sqlite"
    conn = setup(path, POLICY)
    ctx = multiprocessing.get_context("spawn")
    entered, release, out = ctx.Event(), ctx.Event(), ctx.Queue()
    child = ctx.Process(
        target=worker, args=(str(path), str(tmp_path), phase, entered, release, out)
    )
    try:
        child.start()
        assert entered.wait(10)
        child.terminate()
        child.join(5)
        assert not child.is_alive()
        rows = attempt_rows(conn)
        assert len(rows) == (0 if phase == "before_commit" else 1)
        assert (tmp_path / "send-marker").exists() == (phase == "send")
        if phase != "before_commit":
            assert rows[0]["state"] == "intent"
            owner = ledger(tmp_path)
            with owner.exclusive(), pytest.raises(FixtureAccountingBlocked):
                account(conn)._send(
                    owner, rows[0]["request_hash"], 0, lambda: pytest.fail("no repeated send")
                )
            assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
            with owner.exclusive():
                account(conn).reconcile_http_uncertain(owner, rows[0]["request_hash"], 0)
            assert attempt_rows(conn)[0]["state"] == "unknown"
    finally:
        if child.is_alive():
            child.kill()
        child.join(5)
        conn.close()


@pytest.mark.usefixtures("owned_test_process")
def test_other_process_same_scope_cannot_send_while_current_send_is_unresolved(
    tmp_path: Path,
) -> None:
    path = tmp_path / "a.sqlite"
    conn = setup(path, POLICY)
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    ctx = multiprocessing.get_context("spawn")
    entered, release, out = ctx.Event(), ctx.Event(), ctx.Queue()
    child = ctx.Process(target=worker, args=(str(path), str(one), "send", entered, release, out))
    try:
        child.start()
        assert entered.wait(10)
        assert out.get(timeout=5) == "send"
        owner = ledger(two)
        with owner.exclusive(), pytest.raises(FixtureAccountingBlocked, match="UNRESOLVED"):
            account(conn)._send(owner, "b" * 64, 0, lambda: pytest.fail("no competing send"))
        assert len(attempt_rows(conn)) == 1
        release.set()
        assert out.get(timeout=10) == "done"
        child.join(5)
        assert child.exitcode == 0
        assert attempt_rows(conn)[0]["state"] == "success"
    finally:
        if child.is_alive():
            child.kill()
        child.join(5)
        conn.close()
