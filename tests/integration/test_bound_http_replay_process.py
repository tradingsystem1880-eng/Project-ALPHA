"""Disposable actual-process crash/concurrency boundaries for versioned bound resume."""

from __future__ import annotations

import json
import multiprocessing
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from alpha_cli._crypto_backfill_accounting import FixtureAccountingBlocked
from alpha_cli._market_data_acquisition_accounting import Dimension, FixturePolicy

from .test_accounted_backfill import attempt_rows, setup
from .test_accounted_backfill_process import connect
from .test_accounted_http import POLICY
from .test_bound_http_replay import bound, events, native, run, store_at


class FinalCommit(sqlite3.Connection):
    phase: str = ""
    entered: Any = None
    release: Any = None
    paused: bool = False

    def commit(self) -> None:
        final = False
        if self.in_transaction and not self.paused:
            final = any(
                json.loads(row[0])["reason"] is not None
                and json.loads(row[0])["reason"].startswith("w200_")
                for row in self.execute("SELECT body FROM md_acquisition_attempts")
            )
        if final and self.phase == "before_anchor":
            self.paused = True
            self.entered.set()
            if not self.release.wait(20):
                raise RuntimeError("fixture commit pause")
        super().commit()
        if final and self.phase == "after_anchor":
            self.paused = True
            self.entered.set()
            if not self.release.wait(20):
                raise RuntimeError("fixture ack pause")


def worker(root: str, phase: str, entered: Any, release: Any, out: Any) -> None:
    path = Path(root)
    store = store_at(path)
    conn = connect(str(path / "account.sqlite"), FinalCommit)
    assert isinstance(conn, FinalCommit)
    conn.phase, conn.entered, conn.release = phase, entered, release
    sends: list[str] = []
    publish = store._publish_manifest
    paused = False

    def pause_raw(body: dict[str, object]) -> dict[str, object]:
        nonlocal paused
        result = publish(body)
        receipt = body.get("receipt")
        if (
            phase in {"after_raw", "hold"}
            and not paused
            and isinstance(receipt, dict)
            and receipt.get("provider_schema") == "alpha-http-response-binding-v1"
            and dict(receipt["request"])["status"] == "200"
        ):
            paused = True
            entered.set()
            if not release.wait(20):
                raise RuntimeError("fixture raw pause")
        return result

    try:
        with native(store, sends), patch.object(store, "_publish_manifest", pause_raw):
            result = run(path, bound(conn, store))
        out.put({"result": result, "sends": len(sends)})
    except BaseException as error:
        out.put({"error": type(error).__name__ + ":" + str(error), "sends": len(sends)})
    finally:
        conn.close()


@pytest.mark.usefixtures("owned_test_process")
@pytest.mark.parametrize("phase", ["after_raw", "before_anchor", "after_anchor"])
def test_process_termination_preserves_spend_and_only_durable_final_anchor_can_recover(
    tmp_path: Path, phase: str
) -> None:
    (tmp_path / "bulk").mkdir()
    conn = setup(tmp_path / "account.sqlite", POLICY)
    store = store_at(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    entered, release, out = ctx.Event(), ctx.Event(), ctx.Queue()
    child = ctx.Process(target=worker, args=(str(tmp_path), phase, entered, release, out))
    try:
        child.start()
        assert entered.wait(15)
        child.terminate()
        child.join(5)
        assert not child.is_alive()
        before = events(conn)
        sends: list[str] = []
        with native(store, sends):
            if phase == "after_anchor":
                assert any(str(r["reason"]).startswith("w200_") for r in attempt_rows(conn))
                assert run(tmp_path, bound(conn, store))["done"] == 1
                assert run(tmp_path, bound(conn, store))["skipped"] == 1
            else:
                assert any(r["state"] == "intent" for r in attempt_rows(conn))
                with pytest.raises(FixtureAccountingBlocked):
                    run(tmp_path, bound(conn, store))
        assert sends == [] and events(conn) == before
    finally:
        if child.is_alive():
            child.kill()
        child.join(5)
        conn.close()


@pytest.mark.usefixtures("owned_test_process")
def test_simultaneous_different_ledger_owners_cannot_spend_during_pending_response(
    tmp_path: Path,
) -> None:
    (tmp_path / "bulk").mkdir()
    other = tmp_path / "other"
    other.mkdir()
    conn = setup(tmp_path / "account.sqlite", POLICY)
    store = store_at(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    entered, release, out = ctx.Event(), ctx.Event(), ctx.Queue()
    child = ctx.Process(target=worker, args=(str(tmp_path), "hold", entered, release, out))
    try:
        child.start()
        assert entered.wait(15)
        before = events(conn)
        sends: list[str] = []
        with native(store, sends), pytest.raises(FixtureAccountingBlocked):
            run(other, bound(conn, store))
        assert sends == [] and events(conn) == before
        release.set()
        reply = out.get(timeout=15)
        child.join(5)
        assert child.exitcode == 0 and "error" not in reply, reply
        assert reply["sends"] == 3 and reply["result"]["done"] == 1
        before = events(conn)
        with native(store, sends):
            assert run(other, bound(conn, store))["done"] == 1
        assert sends == [] and events(conn) == before
    finally:
        if child.is_alive():
            child.kill()
        child.join(5)
        conn.close()


class LostFinalAck(sqlite3.Connection):
    after: bool = True
    armed: bool = True

    def commit(self) -> None:
        final = (
            self.armed
            and self.in_transaction
            and any(
                str(json.loads(row[0])["reason"]).startswith("w200_")
                for row in self.execute("SELECT body FROM md_acquisition_attempts")
            )
        )
        if final and not self.after:
            self.armed = False
            raise sqlite3.OperationalError("synthetic commit not done")
        super().commit()
        if final:
            self.armed = False
            raise sqlite3.OperationalError("synthetic acknowledgment lost")


@pytest.mark.parametrize("after", [False, True])
def test_final_commit_uncertainty_fails_current_call_then_reopens_only_real_anchor(
    tmp_path: Path, after: bool
) -> None:
    (tmp_path / "bulk").mkdir()
    setup(tmp_path / "account.sqlite", POLICY).close()
    conn = connect(str(tmp_path / "account.sqlite"), LostFinalAck)
    assert isinstance(conn, LostFinalAck)
    conn.after = after
    store = store_at(tmp_path)
    sends: list[str] = []
    with (
        native(store, sends),
        pytest.raises(FixtureAccountingBlocked, match="BOUND_FINAL_COMMIT_UNCERTAIN"),
    ):
        run(tmp_path, bound(conn, store))
    before = events(conn)
    assert len(sends) == 3 and not (tmp_path / "progress.json").exists()
    conn.close()
    conn = connect(str(tmp_path / "account.sqlite"))
    with native(store, sends):
        if after:
            assert run(tmp_path, bound(conn, store))["done"] == 1
        else:
            with pytest.raises(FixtureAccountingBlocked):
                run(tmp_path, bound(conn, store))
    assert len(sends) == 3 and events(conn) == before
    conn.close()


def test_exhaustion_rolls_back_prior_settlement_and_next_debit_together(tmp_path: Path) -> None:
    (tmp_path / "bulk").mkdir()
    # Use the same explicit charge dimension as the shared synthetic policy, no quota inference.
    policy = FixturePolicy(
        POLICY.campaign_id,
        POLICY.generation,
        (Dimension(POLICY.dimensions[0].dimension, POLICY.dimensions[0].period, 2, None, None, 1),),
    )
    conn = setup(tmp_path / "account.sqlite", policy)
    store = store_at(tmp_path)
    sends: list[str] = []
    with native(store, sends), pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, bound(conn, store, policy=policy))
    rows = attempt_rows(conn)
    assert len(sends) == 2 and sorted(r["state"] for r in rows) == ["failure", "intent"]
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 2
    before = events(conn)
    with native(store, sends), pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, bound(conn, store, policy=policy))
    assert len(sends) == 2 and events(conn) == before and not (tmp_path / "progress.json").exists()
    conn.close()
