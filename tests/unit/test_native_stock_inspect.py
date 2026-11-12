"""New public inspection fixtures; no providers, owner data or private suite."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from alpha_cli.native_stock_fixture import StockFixtureRequest
from alpha_cli.native_stock_inspect import inspect_progress
from alpha_core import DataError
from tests.unit._native_stock_test_support import array, record

REQUEST = StockFixtureRequest("job", "reservation", "owner", "a" * 64, "b" * 64, 5, 2, 2, 1000)


class ProgressTests(unittest.TestCase):
    def test_missing_is_unavailable(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(inspect_progress(Path(directory), {})["status"], "unavailable")

    def test_rejects_duplicate_json_and_symlink_without_loading_checkpoint(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            path = work / "stock-progress.json"
            path.write_text('{"schema":1,"schema":2}')
            with self.assertRaises(DataError):
                inspect_progress(work, {})
            path.unlink()
            path.symlink_to(work / "elsewhere")
            with self.assertRaises(DataError):
                inspect_progress(work, {})

    def test_readonly_entry_rejects_missing_store_without_initializing(self) -> None:
        from alpha_cli.native_stock_inspect import inspect_run
        from alpha_cli.native_supervisor import synthetic_workspace

        with synthetic_workspace() as root, patch("subprocess.Popen") as spawn:
            with self.assertRaises(DataError):
                inspect_run(root, "c3ef36b2-4442-4b06-b56e-d0349da21209")
            self.assertFalse((root / "control").exists())
            spawn.assert_not_called()

    def test_invalid_job_never_opens_store(self) -> None:
        from alpha_cli.native_stock_inspect import inspect_run

        with patch("alpha_cli.control_store.ControlStore._open_readonly") as opened:
            with self.assertRaises(DataError):
                inspect_run(Path("/tmp"), "../escape")
            opened.assert_not_called()


# Native execution is opt-in and uses only already-installed pinned assets.


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ and "ALPHA_STOCK_PYTHON" in os.environ,
    "explicit installed synthetic native runtime required",
)
class NativeInspectionJourney(unittest.TestCase):
    def test_four_native_outcomes_reopen_without_dispatch_or_row_mutation(self) -> None:
        import hashlib
        import sqlite3
        import subprocess
        import sys

        from alpha_cli._native_stock_launch import StockFixtureLaunch
        from alpha_cli.control_store import ControlStore
        from alpha_cli.native_stock_inspect import inspect_run
        from alpha_cli.native_supervisor import start_synthetic_owner, synthetic_workspace
        from tests.unit.test_native_stock_dispatch import JOB
        from tests.unit.test_research_control_store import (
            _approved_native_d1,
            _native_d1_job,
            _project,
        )

        evidence = Path(os.environ["ALPHA_STOCK_RECEIPTS"]) / "inspection"
        evidence.mkdir()
        source = Path(os.environ["ALPHA_RDAGENT_SOURCE"])
        runtime = Path(os.environ["ALPHA_STOCK_PYTHON"]).parents[2]
        for mode, state, attempts in (
            ("resume", "completed", 5),
            ("cancel", "cancelled", 3),
            ("exhaust", "failed", 3),
            ("tamper", "checkpoint_rejected", 2),
        ):
            with self.subTest(mode=mode), synthetic_workspace() as root:
                launch = StockFixtureLaunch(source, mode, stock_runtime=runtime)
                store = ControlStore(root)
                _project(store)
                contract, _ = _approved_native_d1(
                    store,
                    loop_steps=5,
                    implementation_fingerprints=launch.implementation_fingerprints(),
                )
                _native_d1_job(store, contract, job_id=JOB, manifest_sha256=launch.fingerprint)
                process = start_synthetic_owner(
                    root, JOB, fixture="native_loop", seconds=40, native=launch
                )
                try:
                    process.wait(timeout=50)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)
                database = next((root / "control").glob("*.sqlite3"))
                with sqlite3.connect(database) as connection:
                    before = list(connection.iterdump())
                with (
                    patch("subprocess.Popen") as forbidden_spawn,
                    patch.object(ControlStore, "_open", side_effect=AssertionError("write route")),
                ):
                    report = inspect_run(root, JOB)
                    forbidden_spawn.assert_not_called()
                self.assertTrue(report["invocation_consumed"])
                self.assertFalse(report["resume_allowed"])
                self.assertEqual(record(report["progress"])["state"], state)
                self.assertEqual(
                    len(array(record(report["progress"])["attempted_stages"])), attempts
                )
                self.assertEqual(
                    record(report["progress"])["worker_profile_binding"],
                    "unverified_self_digest_only",
                )
                if mode == "exhaust":
                    self.assertEqual(record(report["progress"])["fake_model_attempts"], 1)
                    self.assertEqual(record(report["progress"])["simulated_model_counter"], 2)
                with sqlite3.connect(database) as connection:
                    self.assertEqual(before, list(connection.iterdump()))
                run = evidence / mode
                run.mkdir()
                (run / "inspection.json").write_text(json.dumps(report, sort_keys=True))
                work = root / f"payload-{JOB}"
                for name in ("stock-progress.json", "stock-receipt.json", "stock-trace.json"):
                    if (work / name).exists():
                        (run / name).write_bytes((work / name).read_bytes())
                # Reopen through the actual operator CLI in another Python process.
                cli = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "alpha_cli.native_stock_inspect",
                        "--data-dir",
                        str(root),
                        "--job-id",
                        JOB,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                self.assertEqual(json.loads(cli.stdout), report)
                (run / "cli.json").write_text(cli.stdout)
                (run / "hashes.json").write_text(
                    json.dumps(
                        {
                            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in run.iterdir()
                            if p.is_file()
                        },
                        sort_keys=True,
                    )
                )
                # Changed identity and checkpoint bytes must not borrow old evidence.
                progress = work / "stock-progress.json"
                original = progress.read_bytes()
                value = json.loads(original)
                record(value["request"])["owner_id"] = "wrong-owner"
                from alpha_cli.native_stock_fixture import digest

                value["request_sha256"] = digest(value["request"])
                progress.write_text(json.dumps(value))
                self.assertEqual(record(inspect_run(root, JOB)["progress"])["status"], "invalid")
                progress.write_bytes(original)
                checkpoint = work / "stock-checkpoint.bin"
                checkpoint.write_bytes(checkpoint.read_bytes() + b"changed")
                self.assertEqual(record(inspect_run(root, JOB)["progress"])["status"], "invalid")
                progress.unlink()
                self.assertEqual(
                    record(inspect_run(root, JOB)["progress"])["status"], "unavailable"
                )


class AdvisoryValidationTests(unittest.TestCase):
    def snapshot(self) -> dict[str, object]:
        from alpha_cli.native_stock_fixture import digest

        return {
            "schema": "StockRDLoopProgressV1",
            "request": REQUEST.payload(),
            "request_sha256": digest(REQUEST.payload()),
            "state": "running",
            "attempted_stages": [],
            "fake_model_attempts": 0,
            "simulated_model_counter": 0,
            "fake_tool_attempts": 0,
            "continuation_checkpoint_sha256": None,
            "actual_model_calls": 0,
            "scientific_acceptance": "not_admitted",
        }

    def test_advisory_empty_attempts_are_not_a_success_or_resume_receipt(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "stock-progress.json").write_text(json.dumps(self.snapshot()))
            report = inspect_progress(work, {"job_id": "job"})
            self.assertEqual(report["status"], "advisory_only")
            self.assertEqual(report["stage_completion"], "not_established_by_attempt_snapshot")
            self.assertEqual(report["continuation_checkpoint"], "unavailable")

    def test_rejects_bad_types_order_counters_and_completion_claims(self) -> None:
        import tempfile

        for key, value in (
            ("actual_model_calls", False),
            ("fake_tool_attempts", True),
            ("fake_model_attempts", 3),
            ("simulated_model_counter", True),
            ("state", "completed"),
            ("attempted_stages", ["running"]),
            ("request_sha256", "0" * 64),
            ("continuation_checkpoint_sha256", "0" * 64),
            ("scientific_acceptance", "accepted"),
        ):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                snapshot = self.snapshot()
                snapshot[key] = value
                (work / "stock-progress.json").write_text(json.dumps(snapshot))
                with self.assertRaises(DataError):
                    inspect_progress(work, {"job_id": "job"})

    def test_bounded_nonregular_and_deep_json(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            path = work / "stock-progress.json"
            for raw in (b"x" * 8193, b"[" * 2000 + b"]" * 2000, b"\xff"):
                path.write_bytes(raw)
                with self.assertRaises(DataError):
                    inspect_progress(work, {"job_id": "job"})
            path.unlink()
            os.mkfifo(path)
            with self.assertRaises(DataError):
                inspect_progress(work, {"job_id": "job"})

    def test_cli_sanitizes_errors(self) -> None:
        from alpha_cli.native_stock_inspect import main

        with (
            patch("sys.argv", ["inspect", "--data-dir", "/tmp", "--job-id", "bad"]),
            patch(
                "alpha_cli.native_stock_inspect.inspect_run",
                side_effect=DataError("invented-secret-do-not-log"),
            ),
            patch("builtins.print") as output,
        ):
            self.assertEqual(main(), 2)
            self.assertNotIn("invented-secret", str(output.call_args))

    def test_worker_manifest_is_explicitly_not_authenticated_by_self_digest(self) -> None:
        import tempfile

        from alpha_cli.native_stock_fixture import digest

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            snapshot = self.snapshot()
            record(snapshot["request"])["manifest_sha256"] = "c" * 64
            snapshot["request_sha256"] = digest(snapshot["request"])
            (work / "stock-progress.json").write_text(json.dumps(snapshot))
            self.assertEqual(
                inspect_progress(work, {"job_id": "job"})["worker_profile_binding"],
                "unverified_self_digest_only",
            )

    def test_journal_shape_errors_are_fixed_json_without_raw_details(self) -> None:
        # The query path still uses an existing synthetic store, with the underlying
        # malformed decoder represented by a deterministic error double.
        from alpha_cli.control_store import ControlStore
        from alpha_cli.native_stock_inspect import main
        from alpha_cli.native_supervisor import synthetic_workspace
        from tests.unit.test_native_stock_dispatch import JOB
        from tests.unit.test_research_control_store import _project

        with synthetic_workspace() as root:
            store = ControlStore(root)
            _project(store)
            for exception in (
                ValueError("dummy-secret"),
                AttributeError("dummy-secret"),
                RecursionError("dummy-secret"),
            ):
                with (
                    patch("sys.argv", ["inspect", "--data-dir", str(root), "--job-id", JOB]),
                    patch.object(ControlStore, "_require_job"),
                    patch("alpha_cli.native_stock_inspect._events", side_effect=exception),
                    patch("builtins.print") as output,
                ):
                    self.assertEqual(main(), 2)
                    self.assertNotIn("dummy-secret", str(output.call_args))
