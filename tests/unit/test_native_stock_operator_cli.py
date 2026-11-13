"""Canonical console operator tests with synthetic native input and fixed error doubles."""

from __future__ import annotations

import os
import unittest

import typer
from typer.testing import CliRunner, Result

from alpha_cli.native_stock_cmds import native_result_command
from alpha_core import DataError
from tests.unit._native_stock_test_support import record


class OperatorTests(unittest.TestCase):
    def command(
        self, report: dict[str, object] | None = None, error: Exception | None = None
    ) -> Result:
        from unittest.mock import patch

        app = typer.Typer()
        app.command("native-result")(native_result_command)
        with patch(
            "alpha_cli.native_stock_inspect.inspect_run", return_value=report, side_effect=error
        ):
            return CliRunner().invoke(
                app,
                [
                    "--data-dir",
                    "/tmp/fixture",
                    "--job-id",
                    "00000000-0000-4000-8000-000000000001",
                    "--profile-source",
                    "/public/source",
                    "--profile-runtime",
                    "/public/runtime",
                    "--profile-mode",
                    "resume",
                ],
            )

    def report(self, state: str) -> dict[str, object]:
        return {
            "schema": "StockRDLoopInspectionV1",
            "resume_allowed": False,
            "scientific_acceptance": "not_admitted",
            "dispatch": {"job_id": "job"},
            "result_recovery": {
                "status": state,
                "reason": "fixed fixture",
                "owner_receipt_match": "verified",
            },
            "artifact_validation": {
                "status": "current_bytes_validated_only",
                "receipt_sha256": "a" * 64,
                "trace_sha256": "b" * 64,
                "checkpoint_sha256": "c" * 64,
                "validated_receipt": {"schema": "StockRDLoopReceiptV1"},
                "validated_trace": {
                    "result": {"synthetic_score": -0.125, "unit": "fixture_only"},
                    "decision": False,
                    "acceptable": False,
                },
            },
            "profile_verification": {"status": "verified"},
        }

    def test_completed_exposes_validated_receipt_and_result(self) -> None:
        import json

        result = self.command(self.report("verified"))
        self.assertEqual(result.exit_code, 0, result.output)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "completed")
        self.assertEqual(record(body["result"])["unit"], "fixture_only")
        self.assertEqual(record(body["receipt"])["schema"], "StockRDLoopReceiptV1")
        self.assertEqual(record(body["provenance"])["receipt_sha256"], "a" * 64)
        self.assertFalse(body["resume_allowed"])

    def test_fail_closed_status_exit_and_no_result_promotion(self) -> None:
        import json

        for state, code, status in (("mismatch", 2, "invalid"), ("unavailable", 3, "unavailable")):
            with self.subTest(state=state):
                result = self.command(self.report(state))
                self.assertEqual(result.exit_code, code, result.output)
                body = json.loads(result.stdout)
                self.assertEqual(body["status"], status)
                self.assertNotIn("result", body)
                self.assertNotIn("receipt", body)
        result = self.command(error=DataError("invented-secret-must-not-log"))
        self.assertEqual(result.exit_code, 3)
        self.assertNotIn("invented-secret", result.output)

    def test_corrupt_artifact_invalid_even_if_recovery_unavailable(self) -> None:
        import json

        report = self.report("unavailable")
        record(report["artifact_validation"])["status"] = "invalid"
        result = self.command(report)
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "invalid")
        record(report["result_recovery"])["status"] = "verified"
        result = self.command(report)
        self.assertEqual(result.exit_code, 2)
        self.assertNotIn("result", json.loads(result.stdout))

    def test_registry_discoverable_idempotent_and_not_launchable(self) -> None:
        from alpha_cli.info_cmds import _launchable
        from alpha_cli.main import _group
        from alpha_cli.research_diagnostic_cmds import diagnostic_app

        for _ in range(2):
            _group("research", "alpha_cli.research_cmds", "research_app")
        names = [info.name for info in diagnostic_app.registered_commands]
        self.assertEqual(names.count("native-result"), 1)
        self.assertFalse(_launchable("research diagnostic native-result"))

    def test_callback_does_not_construct_default_settings(self) -> None:
        from unittest.mock import patch

        from alpha_core.config import AlphaSettings

        with patch.object(
            AlphaSettings, "__init__", side_effect=AssertionError("no settings read")
        ):
            self.assertEqual(self.command(self.report("verified")).exit_code, 0)


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ and "ALPHA_STOCK_PYTHON" in os.environ,
    "explicit existing synthetic native assets required",
)
class NativeConsoleJourney(unittest.TestCase):
    def test_actual_alpha_command_completed_corruption_missing_owner_and_cancellation(self) -> None:
        import hashlib
        import json
        import subprocess
        import sys
        from pathlib import Path

        from alpha_cli.native_supervisor import start_synthetic_owner
        from tests.unit.test_native_stock_dispatch import JOB, case

        console = Path(sys.executable).parent / "alpha"
        self.assertTrue(console.is_file(), "installed console wrapper is required")
        evidence = Path(os.environ["ALPHA_STOCK_RECEIPTS"]) / "operator-cli"
        evidence.mkdir()
        with case() as (root, store, launch):
            owner = start_synthetic_owner(
                root, JOB, fixture="native_loop", seconds=40, native=launch
            )
            try:
                self.assertEqual(owner.wait(timeout=50), 0)
            finally:
                if owner.poll() is None:
                    owner.terminate()
                    owner.wait(timeout=5)
            argv = [
                str(console),
                "research",
                "diagnostic",
                "native-result",
                "--data-dir",
                str(root),
                "--job-id",
                JOB,
                "--profile-source",
                str(launch.source),
                "--profile-runtime",
                str(launch.stock_runtime),
                "--profile-mode",
                "resume",
            ]

            def command(name: str, code: int, status: str) -> dict[str, object]:
                completed = subprocess.run(argv, capture_output=True, text=True, timeout=25)
                (evidence / f"{name}.stdout.json").write_text(completed.stdout)
                (evidence / f"{name}.stderr.txt").write_text(completed.stderr)
                self.assertEqual(completed.returncode, code, completed.stderr)
                body = json.loads(completed.stdout)
                self.assertEqual(body["status"], status)
                self.assertFalse(body["resume_allowed"])
                self.assertEqual(body["scientific_acceptance"], "not_admitted")
                if code:
                    self.assertNotIn("result", body)
                    self.assertNotIn("receipt", body)
                return record(body)

            body = command("completed", 0, "completed")
            self.assertEqual(body["result"], {"synthetic_score": -0.125, "unit": "fixture_only"})
            self.assertEqual(body["feedback"], {"decision": False, "acceptable": False})
            self.assertTrue(record(body["receipt"])["resumed_without_repeating"])
            self.assertTrue(record(body["receipt"])["replay_rejected"])
            work = root / f"payload-{JOB}"
            receipt_path = work / "stock-receipt.json"
            original = receipt_path.read_bytes()
            self.assertEqual(
                record(body["provenance"])["receipt_sha256"], hashlib.sha256(original).hexdigest()
            )
            self.assertEqual(record(body["dispatch"])["job_id"], JOB)
            receipt_path.write_bytes(original + b" ")
            command("changed_exact_bytes", 2, "invalid")
            receipt_path.write_bytes(b"{not valid JSON")
            command("corrupt_receipt", 2, "invalid")
            receipt_path.write_bytes(original)
            receipt_path.unlink()
            command("missing_receipt", 3, "unavailable")
            receipt_path.write_bytes(original)
            # A different real reserved synthetic job has no owner claim or receipt.
            # Existing fixture setup is the same reusable public admission helper;
            # the canonical command itself never imports or runs test code.
            with case() as (unstarted, _, _):
                saved_root = argv[argv.index("--data-dir") + 1]
                argv[argv.index("--data-dir") + 1] = str(unstarted)
                command("missing_owner_binding", 3, "unavailable")
                argv[argv.index("--data-dir") + 1] = saved_root
            store.request_job_cancellation(JOB, actor="synthetic", reason="late operator fixture")
            command("late_cancellation", 3, "unavailable")
            (evidence / "command.json").write_text(
                json.dumps(
                    {
                        "wrapper": str(console),
                        "argv_without_ephemeral_root": [
                            "alpha",
                            "research",
                            "diagnostic",
                            "native-result",
                            "--data-dir",
                            "<fixture>",
                            "--job-id",
                            JOB,
                            "--profile-source",
                            str(launch.source),
                            "--profile-runtime",
                            str(launch.stock_runtime),
                            "--profile-mode",
                            "resume",
                        ],
                        "fixture_scope": "fresh admitted synthetic fixture; no providers/live data",
                    },
                    sort_keys=True,
                )
            )
