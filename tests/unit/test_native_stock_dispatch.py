"""Public synthetic dispatch tests over the existing retained owner and journal."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import unittest
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO
from unittest.mock import patch

from alpha_cli._native_fixture_store import _events, _reservation
from alpha_cli._native_stock_launch import StockFixtureLaunch, consume_before_spawn
from alpha_cli.control_store import ControlStore
from alpha_cli.native_supervisor import (
    _open_lock,
    _Owner,
    start_synthetic_owner,
    synthetic_workspace,
)
from alpha_core import DataError
from tests.unit._native_stock_test_support import record
from tests.unit.test_research_control_store import _approved_native_d1, _native_d1_job, _project

JOB = "c3ef36b2-4442-4b06-b56e-d0349da21209"


@contextmanager
def case() -> Iterator[tuple[Path, ControlStore, StockFixtureLaunch]]:
    source = Path(os.environ["ALPHA_RDAGENT_SOURCE"])
    runtime = Path(os.environ["ALPHA_STOCK_PYTHON"]).parents[2]
    launch = StockFixtureLaunch(source, "resume", stock_runtime=runtime)
    with synthetic_workspace() as root:
        store = ControlStore(root)
        _project(store)
        contract, _ = _approved_native_d1(
            store, loop_steps=5, implementation_fingerprints=launch.implementation_fingerprints()
        )
        _native_d1_job(store, contract, job_id=JOB, manifest_sha256=launch.fingerprint)
        yield root, store, launch


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ and "ALPHA_STOCK_PYTHON" in os.environ,
    "explicit existing native assets required",
)
class DispatchTests(unittest.TestCase):
    def owner(self, root: Path, launch: StockFixtureLaunch, lock: BinaryIO) -> _Owner:
        return _Owner(root, JOB, "native_loop", 40, lock, native=launch)

    def test_consumption_is_once_across_reopen_and_race(self) -> None:
        with case() as (root, s, launch), _open_lock(root, JOB) as lock:
            o = self.owner(root, launch, lock)
            s.claim_native_fixture(JOB, o)

            def attempt(_: int) -> bool:
                try:
                    consume_before_spawn(o)
                    return True
                except DataError:
                    return False

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sum(pool.map(attempt, range(2))), 1)
            with ControlStore(root)._transaction(write=False) as c:
                self.assertIn("native_invocation", _events(c, JOB))
            with self.assertRaises(DataError):
                o.spawn()
            self.assertIsNone(o.process)
            with self.assertRaises(DataError):
                start_synthetic_owner(root, JOB, fixture="native_loop", native=launch)

    def test_consumption_rolls_back_before_spawn(self) -> None:
        import alpha_cli._native_fixture_store as journal

        with case() as (root, s, launch), _open_lock(root, JOB) as lock:
            o = self.owner(root, launch, lock)
            s.claim_native_fixture(JOB, o)
            original = journal._append

            def failing(
                c: sqlite3.Connection, job: str, kind: str, payload: dict[str, object]
            ) -> None:
                result = original(c, job, kind, payload)
                if kind == "native_invocation":
                    raise DataError("synthetic failure after journal insertion")
                return result

            with (
                patch.object(journal, "_append", side_effect=failing),
                patch("alpha_cli.native_supervisor.subprocess.Popen") as spawn,
            ):
                with self.assertRaises(DataError):
                    o.spawn()
                spawn.assert_not_called()
            with s._transaction(write=False) as c:
                self.assertNotIn("native_invocation", _events(c, JOB))

    def test_failed_spawn_retains_durable_consumption(self) -> None:
        with case() as (root, s, launch), _open_lock(root, JOB) as lock:
            o = self.owner(root, launch, lock)
            s.claim_native_fixture(JOB, o)
            with (
                patch(
                    "alpha_cli.native_supervisor.subprocess.Popen",
                    side_effect=OSError("synthetic spawn failure"),
                ),
                self.assertRaises(OSError),
            ):
                o.spawn()
            with s._transaction(write=False) as c:
                self.assertIn("native_invocation", _events(c, JOB))
            self.assertTrue(o.spawn_attempted)
            with self.assertRaises(DataError):
                o.spawn()

    def test_cancellation_prevents_consumption(self) -> None:
        with case() as (root, s, launch), _open_lock(root, JOB) as lock:
            o = self.owner(root, launch, lock)
            s.claim_native_fixture(JOB, o)
            s.request_job_cancellation(JOB, actor="synthetic", reason="cancel before spawn")
            with self.assertRaises(DataError):
                o.spawn()
            self.assertIsNone(o.process)
            with s._transaction(write=False) as c:
                self.assertNotIn("native_invocation", _events(c, JOB))

    def test_legacy_claim_cannot_gain_stock_consumption(self) -> None:
        from alpha_cli._native_fixture_store import _append

        with case() as (root, s, launch), _open_lock(root, JOB) as lock:
            o = _Owner(root, JOB, "success", 40, lock)
            s.claim_native_fixture(JOB, o)
            with s._transaction(write=True) as c:
                claim = _events(c, JOB)["native_claim"]
                _append(
                    c,
                    JOB,
                    "native_invocation",
                    {
                        k: claim[k]
                        for k in ("schema", "job_id", "reservation_id", "owner_id", "spec_sha256")
                    }
                    | {
                        "scope": "stock_rdloop_fixture_only",
                        "profile_sha256": None,
                        "loop_steps": 5,
                        "model_calls": 2,
                        "tool_calls": 2,
                    },
                )
                with self.assertRaises(DataError):
                    _events(c, JOB)

    def test_receipt_replacement_after_validation_rejected(self) -> None:
        with case() as (root, s, launch), _open_lock(root, JOB) as lock:
            o = self.owner(root, launch, lock)
            s.claim_native_fixture(JOB, o)
            work = root / "replacement-fixture"
            work.mkdir()
            path = work / "stock-receipt.json"
            path.write_bytes(b"original fixture bytes")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()

            def replaced(*args: object) -> dict[str, object]:
                path.write_bytes(b"replaced fixture bytes")
                return {"receipt_sha256": sha}

            with (
                patch(
                    "alpha_cli._native_stock_launch.validate_stock_artifacts", side_effect=replaced
                ),
                self.assertRaises(DataError),
            ):
                launch.verify_result(work, o.native_admission)

    def test_stop_after_commit_keeps_consumption_without_spawn(self) -> None:
        import alpha_cli._native_stock_launch as dispatch

        with case() as (root, s, launch), _open_lock(root, JOB) as lock:
            o = self.owner(root, launch, lock)
            s.claim_native_fixture(JOB, o)
            original = dispatch.consume_before_spawn

            def stop(owner: _Owner) -> None:
                original(owner)
                owner.request_stop("cancelled")

            with (
                patch.object(dispatch, "consume_before_spawn", side_effect=stop),
                patch("alpha_cli.native_supervisor.subprocess.Popen") as spawn,
            ):
                with self.assertRaises(DataError):
                    o.spawn()
                spawn.assert_not_called()
            with s._transaction(write=False) as c:
                self.assertIn("native_invocation", _events(c, JOB))
            self.assertFalse(o.spawn_attempted)

    def test_actual_retained_owner_dispatches_stock_loop(self) -> None:
        with case() as (root, s, launch):
            with s._transaction(write=False) as c:
                before = _reservation(c, JOB)["budget_reserved_json"]
            process = start_synthetic_owner(
                root, JOB, fixture="native_loop", seconds=40, native=launch
            )
            try:
                self.assertEqual(process.wait(timeout=50), 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
            status = s.native_fixture_status(JOB)
            evidence = Path(os.environ["ALPHA_STOCK_RECEIPTS"]) / "retained-owner"
            evidence.mkdir()
            (evidence / "status.json").write_text(json.dumps(status, indent=2))
            (evidence / "owner.log").write_bytes(
                (root / "control" / f"native-{JOB}.log").read_bytes()
            )
            self.assertEqual(record(status["outcome"])["reason"], "exit")
            self.assertEqual(record(status["outcome"])["returncode"], 0)
            with s._transaction(write=False) as c:
                events = _events(c, JOB)
                self.assertEqual(
                    list(events),
                    ["native_claim", "native_invocation", "native_started", "native_outcome"],
                )
                self.assertEqual(before, _reservation(c, JOB)["budget_reserved_json"])
            for name in ("stock-receipt.json", "stock-trace.json", "stock-checkpoint.bin"):
                (evidence / name).write_bytes((root / f"payload-{JOB}" / name).read_bytes())
            with self.assertRaises(DataError):
                start_synthetic_owner(root, JOB, fixture="native_loop", native=launch)


if __name__ == "__main__":
    unittest.main()
