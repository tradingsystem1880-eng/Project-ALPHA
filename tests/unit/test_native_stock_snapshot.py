"""Public synthetic tests for one-byte-snapshot validation, no authority."""

from __future__ import annotations

import os
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from unittest.mock import patch

from alpha_cli.native_stock_fixture import validate_stock_snapshot
from alpha_core import DataError
from tests.unit._native_stock_test_support import record


class SnapshotTests(unittest.TestCase):
    def test_rejects_missing_extra_nonbytes_and_oversized_snapshot(self) -> None:
        from tests.unit.test_native_stock_inspect import REQUEST

        for artifacts in (
            {},
            {"elsewhere": b""},
            {
                "stock-receipt.json": b"x" * 100_001,
                "stock-trace.json": b"{}",
                "stock-checkpoint.bin": b"fixture",
            },
            {
                "stock-receipt.json": "{}",
                "stock-trace.json": b"{}",
                "stock-checkpoint.bin": b"fixture",
            },
        ):
            with self.subTest(artifacts=list(artifacts)), self.assertRaises(DataError):
                # Deliberately malformed non-bytes transport tests the runtime rejection.
                validate_stock_snapshot(cast(Mapping[str, bytes], artifacts), REQUEST)

    def test_path_wrapper_reads_each_artifact_exactly_once(self) -> None:
        from pathlib import Path

        from alpha_cli.native_stock_fixture import validate_stock_artifacts
        from tests.unit.test_native_stock_inspect import REQUEST

        artifacts = {
            "stock-receipt.json": b"receipt",
            "stock-trace.json": b"trace",
            "stock-checkpoint.bin": b"checkpoint",
        }
        calls = []

        def read(work: Path, name: str, cap: int) -> bytes:
            calls.append(name)
            return artifacts[name]

        with (
            patch("alpha_cli.native_stock_fixture._read", side_effect=read),
            patch(
                "alpha_cli.native_stock_fixture.validate_stock_snapshot", return_value={}
            ) as validate,
        ):
            validate_stock_artifacts(Path("/unused"), REQUEST)
            self.assertCountEqual(calls, list(artifacts))
            self.assertEqual(len(calls), 3)
            self.assertEqual(validate.call_args.args, (artifacts, REQUEST))


def fixture_snapshot() -> dict[str, bytes]:
    import hashlib
    import json

    from alpha_cli.native_stock_fixture import RESULT, SOURCE_SHA256, STAGES, digest
    from tests.unit.test_native_stock_inspect import REQUEST

    trace = {
        "schema": "StockRDLoopTraceV1",
        "request_sha256": digest(REQUEST.payload()),
        "native_class": "rdagent.components.workflow.rd_loop.RDLoop",
        "stages": STAGES,
        "hist_count": 1,
        "dag_parent": [[]],
        "idx2loop_id": {"0": 0},
        "hypothesis": "fixed synthetic stock hypothesis",
        "result": RESULT,
        "decision": False,
        "acceptable": False,
        "scientific_acceptance": "not_admitted",
    }
    trace_raw = json.dumps(trace).encode()
    checkpoint = b"synthetic bytes only; intentionally never unpickled"
    receipt = {
        "schema": "StockRDLoopReceiptV1",
        "request": REQUEST.payload(),
        "source_sha256": SOURCE_SHA256,
        "trace_sha256": hashlib.sha256(trace_raw).hexdigest(),
        "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
        "charged_stages": STAGES,
        "fake_model_attempts": 2,
        "fake_tool_attempts": 2,
        "actual_model_calls": 0,
        "resumed_without_repeating": True,
        "checkpoint_unchanged": True,
        "replay_rejected": True,
        "routes_enabled": False,
        "scientific_acceptance": "not_admitted",
    }
    return {
        "stock-receipt.json": json.dumps(receipt).encode(),
        "stock-trace.json": trace_raw,
        "stock-checkpoint.bin": checkpoint,
    }


class SnapshotSemanticsTests(unittest.TestCase):
    def test_actual_validator_reads_hashes_same_snapshot_without_pickle(self) -> None:
        import hashlib
        from pathlib import Path

        from alpha_cli.native_stock_fixture import validate_stock_artifacts
        from tests.unit.test_native_stock_inspect import REQUEST

        artifacts = fixture_snapshot()
        calls = []

        def read(work: Path, name: str, cap: int) -> bytes:
            if name in calls:
                raise AssertionError("second artifact generation must never be read")
            calls.append(name)
            return artifacts[name]

        with patch("alpha_cli.native_stock_fixture._read", side_effect=read):
            report = validate_stock_artifacts(Path("/unused"), REQUEST)
        self.assertEqual(len(calls), 3)
        self.assertEqual(
            report["receipt_sha256"], hashlib.sha256(artifacts["stock-receipt.json"]).hexdigest()
        )
        self.assertFalse(report["production_dispatch"])

    def test_changed_trace_checkpoint_request_and_nonfinite_values_are_rejected(self) -> None:
        import json

        from tests.unit.test_native_stock_inspect import REQUEST

        for name in fixture_snapshot():
            artifacts = fixture_snapshot()
            artifacts[name] += b"changed"
            with self.subTest(name=name), self.assertRaises(DataError):
                validate_stock_snapshot(artifacts, REQUEST)
        for key, value in (("actual_model_calls", False), ("fake_model_attempts", float("nan"))):
            artifacts = fixture_snapshot()
            receipt = json.loads(artifacts["stock-receipt.json"])
            receipt[key] = value
            artifacts["stock-receipt.json"] = json.dumps(receipt).encode()
            with self.subTest(key=key), self.assertRaises(DataError):
                validate_stock_snapshot(artifacts, REQUEST)

    def test_inspector_current_only_independent_of_progress_and_no_owner_receipt_claim(
        self,
    ) -> None:
        import tempfile
        from pathlib import Path

        from alpha_cli.native_stock_inspect import inspect_current_artifacts
        from tests.unit.test_native_stock_inspect import REQUEST

        binding = {
            key: REQUEST.payload()[key]
            for key in (
                "job_id",
                "reservation_id",
                "owner_id",
                "spec_sha256",
            )
        }
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            self.assertEqual(inspect_current_artifacts(work, binding)["status"], "unavailable")
            for name, raw in fixture_snapshot().items():
                (work / name).write_bytes(raw)
            report = inspect_current_artifacts(work, binding)
            self.assertEqual(report["status"], "current_bytes_validated_only")
            self.assertEqual(
                report["durable_owner_receipt_binding"],
                "unavailable_stock_outcome_has_no_receipt_hash",
            )
            self.assertEqual(report["worker_profile_binding"], "unverified")
            self.assertFalse((work / "stock-progress.json").exists())
            with self.assertRaises(DataError):
                inspect_current_artifacts(work, binding | {"owner_id": "wrong"})
            (work / "stock-trace.json").unlink()
            with self.assertRaises(DataError):
                inspect_current_artifacts(work, binding)


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ and "ALPHA_STOCK_PYTHON" in os.environ,
    "explicit installed synthetic assets required",
)
class NativeSnapshotJourney(unittest.TestCase):
    def test_actual_owner_success_inspection_without_durable_hash_or_resume_authority(self) -> None:
        import hashlib
        import json
        from pathlib import Path

        from alpha_cli._native_fixture_store import _events
        from alpha_cli.native_stock_inspect import inspect_run
        from alpha_cli.native_supervisor import start_synthetic_owner
        from tests.unit.test_native_stock_dispatch import JOB, case

        with case() as (root, store, launch):
            process = start_synthetic_owner(
                root, JOB, fixture="native_loop", seconds=40, native=launch
            )
            try:
                self.assertEqual(process.wait(timeout=50), 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
            report = inspect_run(root, JOB)
            self.assertEqual(
                record(report["artifact_validation"])["status"], "current_bytes_validated_only"
            )
            self.assertFalse(report["resume_allowed"])
            with store._readonly_transaction() as connection:
                outcome = _events(connection, JOB)["native_outcome"]
            self.assertNotIn("rule_result", outcome)
            # Advisory corruption must not hide independently valid success bytes.
            progress = root / f"payload-{JOB}" / "stock-progress.json"
            progress.write_bytes(b"{malformed advisory snapshot")
            report = inspect_run(root, JOB)
            self.assertEqual(record(report["progress"])["status"], "invalid")
            self.assertEqual(
                record(report["artifact_validation"])["status"], "current_bytes_validated_only"
            )
            self.assertFalse(report["resume_allowed"])
            raw = (root / f"payload-{JOB}" / "stock-receipt.json").read_bytes()
            self.assertEqual(
                record(report["artifact_validation"])["receipt_sha256"],
                hashlib.sha256(raw).hexdigest(),
            )
            evidence = Path(os.environ["ALPHA_STOCK_RECEIPTS"]) / "snapshot-native"
            evidence.mkdir()
            (evidence / "inspection.json").write_text(json.dumps(report, sort_keys=True))
            (evidence / "stock-receipt.json").write_bytes(raw)
            (evidence / "owner-outcome.json").write_text(json.dumps(outcome, sort_keys=True))
