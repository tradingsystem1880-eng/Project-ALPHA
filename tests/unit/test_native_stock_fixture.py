"""Public scratch-only stock native workflow and diagnostic boundary tests."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from collections.abc import Callable, Iterator
from pathlib import Path

from alpha_cli.control_store import ControlStore
from alpha_cli.native_stock_fixture import (
    StockFixtureRequest,
    digest,
    request_from_owner,
    validate_stock_artifacts,
)
from alpha_cli.native_supervisor import _open_lock, _Owner, synthetic_workspace
from alpha_core import DataError
from tests.unit._native_stock_test_support import record
from tests.unit.test_research_control_store import _approved_native_d1, _native_d1_job, _project

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "workers/rdagent"
JOB = "5ff4f384-7859-4e73-b4ad-b731ab5e78e0"


def fingerprint() -> str:
    return digest(
        {
            name: hashlib.sha256((WORKER / name).read_bytes()).hexdigest()
            for name in ("stock_fixture.py", "stock_fixture_entry.py", "source_pin.py")
        }
    )


@contextlib.contextmanager
def reserved(
    *, loop_steps: int = 5, approved: bool = True, mode: str = "resume"
) -> Iterator[tuple[ControlStore, _Owner, Callable[[], StockFixtureRequest]]]:
    with synthetic_workspace() as root:
        store = ControlStore(root)
        _project(store)
        manifest = fingerprint()
        contract, _ = _approved_native_d1(
            store,
            loop_steps=loop_steps,
            implementation_fingerprints={"evaluator": manifest} if approved else None,
        )
        _native_d1_job(store, contract, job_id=JOB, manifest_sha256=manifest)
        with _open_lock(root, JOB) as lock:
            owner = _Owner(root, JOB, "success", 60, lock)
            try:
                store.claim_native_fixture(JOB, owner)
                yield (
                    store,
                    owner,
                    lambda: request_from_owner(
                        store, JOB, owner, manifest_sha256=manifest, mode=mode
                    ),
                )
            finally:
                owner.close_control()


class RequestTests(unittest.TestCase):
    def test_rejects_insufficient_or_boolean_budgets(self) -> None:
        for value in (0, 1, True):
            with self.subTest(value=value), self.assertRaises(DataError):
                StockFixtureRequest(
                    "job", "reservation", "owner", "a" * 64, "b" * 64, 5, value, 2, 1000
                )

    def test_existing_reservation_and_approval_required(self) -> None:
        with reserved() as (store, owner, request):
            value = request()
            self.assertEqual((value.loop_steps, value.model_calls, value.tool_calls), (5, 2, 2))
            store.request_job_cancellation(JOB, actor="synthetic", reason="fixture cancellation")
            with self.assertRaises(DataError):
                request()
        with reserved(loop_steps=3) as (_, _, request), self.assertRaises(DataError):
            request()
        with reserved(approved=False) as (_, _, request), self.assertRaises(DataError):
            request()


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ and "ALPHA_STOCK_PYTHON" in os.environ,
    "explicit pinned native assets not supplied",
)
class NativeTests(unittest.TestCase):
    def execute(
        self,
        request: StockFixtureRequest,
        work: Path,
        *,
        payload: dict[str, object] | None = None,
        expected_exit: int = 0,
    ) -> dict[str, object]:
        env = {
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "HOME": str(work),
            "TMPDIR": str(work),
            "LOG_TRACE_PATH": str(work / "logs"),
            "ARTIFACT_SIGNING_KEY": "synthetic-public-test-material-0000000000000000",
            "ARTIFACT_SIGNING_KEY_PATH": str(work / "synthetic.key"),
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "STEP_SEMAPHORE": "1",
            "SUBPROC_STEP": "False",
            "ENABLE_MLFLOW": "False",
        }
        result = subprocess.run(
            [
                str(Path(os.environ["ALPHA_STOCK_PYTHON"]).absolute()),
                "-I",
                "-B",
                str(WORKER / "stock_fixture_entry.py"),
                os.environ["ALPHA_RDAGENT_SOURCE"],
            ],
            input=json.dumps(request.payload() if payload is None else payload),
            text=True,
            env=env,
            cwd=work,
            capture_output=True,
            timeout=40,
        )
        evidence = Path(os.environ["ALPHA_STOCK_RECEIPTS"])
        run = Path(tempfile.mkdtemp(prefix=request.mode + "-", dir=evidence))
        (run / "stdout.log").write_text(result.stdout)
        (run / "stderr.log").write_text(result.stderr)
        (run / "exit.json").write_text(
            json.dumps({"exit_code": result.returncode, "request": request.payload()})
        )
        self.assertEqual(
            result.returncode, expected_exit, f"native fixture failed; evidence: {run}"
        )
        for name in ("stock-receipt.json", "stock-trace.json", "stock-checkpoint.bin"):
            if (work / name).exists():
                (run / name).write_bytes((work / name).read_bytes())
        if expected_exit:
            self.assertFalse(result.stdout)
            self.assertEqual(list(work.iterdir()), [])
            return {"status": "rejected_before_import"}
        return record(json.loads(result.stdout))

    def test_actual_stock_loop_resume_and_artifact_ingestion(self) -> None:
        with (
            reserved() as (s, o, request),
            tempfile.TemporaryDirectory(prefix="alpha-stock-rdloop-") as scratch,
        ):
            from alpha_cli._native_fixture_store import _reservation

            with s._transaction(write=False) as c:
                before = _reservation(c, JOB)["budget_reserved_json"]
            req = request()
            work = Path(scratch)
            result = self.execute(req, work)
            self.assertEqual(result["status"], "completed")
            diagnostic = validate_stock_artifacts(work, req)
            self.assertFalse(diagnostic["production_dispatch"])
            with s._transaction(write=False) as c:
                self.assertEqual(before, _reservation(c, JOB)["budget_reserved_json"])
            raw = (work / "stock-trace.json").read_bytes()
            receipt_raw = (work / "stock-receipt.json").read_bytes()
            for key, value in (
                ("decision", True),
                ("decision", 0),
                ("hist_count", True),
                ("hist_count", 1.0),
            ):
                trace = json.loads(raw)
                trace[key] = value
                (work / "stock-trace.json").write_text(json.dumps(trace))
                # Update the receipt hash too: schema validation must reject the
                # wrong type independently of ordinary hash mismatch detection.
                receipt = json.loads(receipt_raw)
                receipt["trace_sha256"] = hashlib.sha256(
                    (work / "stock-trace.json").read_bytes()
                ).hexdigest()
                (work / "stock-receipt.json").write_text(json.dumps(receipt))
                with self.assertRaises(DataError):
                    validate_stock_artifacts(work, req)
            (work / "stock-trace.json").write_bytes(raw)
            for key, value in (
                ("actual_model_calls", False),
                ("routes_enabled", 0),
                ("fake_model_attempts", 2.0),
            ):
                receipt = json.loads(receipt_raw)
                receipt[key] = value
                (work / "stock-receipt.json").write_text(json.dumps(receipt))
                with self.assertRaises(DataError):
                    validate_stock_artifacts(work, req)
            (work / "stock-receipt.json").write_bytes(receipt_raw)
            # These schema/size/symlink checks operate on own generated artifacts only.
            trace_path = work / "stock-trace.json"
            trace_path.write_text('{"duplicate":1,"duplicate":2}')
            with self.assertRaisesRegex(DataError, "duplicate"):
                validate_stock_artifacts(work, req)
            trace_path.write_bytes(raw)
            target = work / "trace-target.json"
            target.write_bytes(raw)
            trace_path.unlink()
            trace_path.symlink_to(target)
            with self.assertRaisesRegex(DataError, "unsafe"):
                validate_stock_artifacts(work, req)
            trace_path.unlink()
            trace_path.write_bytes(raw)
            checkpoint = work / "stock-checkpoint.bin"
            checkpoint_raw = checkpoint.read_bytes()
            checkpoint.write_bytes(b"x" * 1_048_577)
            with self.assertRaisesRegex(DataError, "exceeds fixed bound"):
                validate_stock_artifacts(work, req)
            checkpoint.write_bytes(checkpoint_raw + b"tamper")
            with self.assertRaises(DataError):
                validate_stock_artifacts(work, req)

    def test_worker_rejects_bad_bindings_before_import(self) -> None:
        with reserved() as (_, _, request):
            req = request()
            for key, value in (
                ("owner_id", None),
                ("manifest_sha256", "f" * 64),
                # Derived exact three-file manifest from preserved910ee456 worker.
                (
                    "manifest_sha256",
                    "14a31445abf42b35165cb4b016bb227f9451f731bd9694938e43ce879d9c209d",
                ),
                ("extra", "x" * 8193),
            ):
                with (
                    self.subTest(key=key),
                    tempfile.TemporaryDirectory(prefix="alpha-stock-rdloop-") as scratch,
                ):
                    payload = req.payload()
                    payload[key] = value
                    self.execute(req, Path(scratch), payload=payload, expected_exit=1)

    def test_cancel_exhaust_and_tampered_checkpoint(self) -> None:
        for mode, status in (
            ("cancel", "cancelled"),
            ("exhaust", "attempt_limit_rejected"),
            ("tamper", "checkpoint_rejected"),
        ):
            with (
                self.subTest(mode=mode),
                reserved(mode=mode) as (_, _, request),
                tempfile.TemporaryDirectory(prefix="alpha-stock-rdloop-") as scratch,
            ):
                result = self.execute(request(), Path(scratch))
                self.assertEqual(result["status"], status)
                if mode == "cancel":
                    self.assertTrue(result["cancelled_continuation_rejected"])
                    self.assertTrue(result["checkpoint_preserved"])
                    self.assertEqual(
                        result["charged_stages"], ["direct_exp_gen", "coding", "running"]
                    )
                self.assertFalse((Path(scratch) / "stock-receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
