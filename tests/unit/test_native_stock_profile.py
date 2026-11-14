"""Public-only current profile identity tests; no inference or resume authority."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from alpha_cli.native_stock_profile import (
    ProfileSelection,
    RecordedProfile,
    bind_profile_declaration,
    verify_selected_profile,
)
from alpha_core import DataError
from tests.unit._native_stock_test_support import record

HASHES: dict[str, str | None] = {
    key: "b" * 64 for key in ("code", "dependency_lock", "environment", "evaluator")
}
HASHES["data"] = None
RECORDED = RecordedProfile(
    {"native_manifest_sha256": "a" * 64, "implementation_fingerprints": HASHES}, 1000
)
SELECTION = ProfileSelection(Path("/public/source"), Path("/public/runtime"), "resume")


class ProfileTests(unittest.TestCase):
    def selected(self) -> Mock:
        measured = Mock()
        measured.fingerprint = "a" * 64
        measured.measure.return_value = "a" * 64
        measured.implementation_fingerprints.return_value = dict(HASHES)
        return measured

    def test_missing_inputs_fail_closed_without_measurement(self) -> None:
        with patch("alpha_cli.native_stock_profile.StockFixtureLaunch") as launch:
            self.assertEqual(verify_selected_profile(RECORDED, None)["status"], "unavailable")
            self.assertEqual(verify_selected_profile(None, SELECTION)["status"], "unavailable")
            launch.assert_not_called()

    def test_current_match_no_launch_or_historical_claim(self) -> None:
        selected = self.selected()
        with (
            patch("alpha_cli.native_stock_profile.StockFixtureLaunch", return_value=selected),
            patch("alpha_cli.native_stock_profile.stock_fixture_manifest", return_value="c" * 64),
        ):
            report = verify_selected_profile(RECORDED, SELECTION)
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["scope"], "current_files_match_recorded_only")
        self.assertFalse(report["resume_allowed"])
        selected.command.assert_not_called()
        selected.request.assert_not_called()
        selected.verify_result.assert_not_called()

    def test_mismatch_missing_unstable_and_sanitized_errors(self) -> None:
        for kind in ("profile", "implementation", "unstable", "missing", "pin"):
            with self.subTest(kind=kind):
                selected = self.selected()
                expected = "mismatch"
                if kind == "profile":
                    selected.fingerprint = "c" * 64
                    selected.measure.return_value = "c" * 64
                if kind == "implementation":
                    selected.implementation_fingerprints.return_value = dict(HASHES, code="c" * 64)
                if kind == "unstable":
                    selected.measure.return_value = "c" * 64
                    expected = "unavailable"
                error = None
                if kind in {"missing", "pin"}:
                    error = (
                        FileNotFoundError("invented-secret")
                        if kind == "missing"
                        else DataError("invented-secret")
                    )
                    expected = "unavailable"
                with (
                    patch(
                        "alpha_cli.native_stock_profile.StockFixtureLaunch",
                        return_value=selected,
                        side_effect=error,
                    ),
                    patch(
                        "alpha_cli.native_stock_profile.stock_fixture_manifest",
                        return_value="c" * 64,
                    ),
                ):
                    report = verify_selected_profile(RECORDED, SELECTION)
                self.assertEqual(report["status"], expected)
                self.assertNotIn("invented-secret", str(report))
                self.assertFalse(report["resume_allowed"])

    def test_declarations_cannot_choose_mode_profile_or_cpu(self) -> None:
        profile: dict[str, object] = {
            "status": "verified",
            "worker_manifest_sha256": "a" * 64,
            "selected_mode": "resume",
            "cpu_milliseconds": 1000,
        }
        evidence: dict[str, object] = {
            "status": "advisory_only",
            "declared_worker_manifest_sha256": "a" * 64,
            "declared_mode": "resume",
            "declared_cpu_milliseconds": 1000,
        }
        self.assertEqual(
            record(bind_profile_declaration(evidence, profile)["profile_declaration"])["status"],
            "verified",
        )
        for key, value in (
            ("declared_mode", "cancel"),
            ("declared_worker_manifest_sha256", "b" * 64),
            ("declared_cpu_milliseconds", 1001),
        ):
            self.assertEqual(
                record(
                    bind_profile_declaration(evidence | {key: value}, profile)[
                        "profile_declaration"
                    ]
                )["status"],
                "mismatch",
            )
        self.assertEqual(
            record(
                bind_profile_declaration(evidence, {"status": "unavailable"})["profile_declaration"]
            )["status"],
            "unavailable",
        )


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ and "ALPHA_STOCK_PYTHON" in os.environ,
    "explicit installed public synthetic assets required",
)
class NativeProfileJourney(unittest.TestCase):
    def test_native_outcomes_explicit_profile_cli_and_tampered_declarations(self) -> None:
        import hashlib
        import json
        import subprocess
        import sys

        from alpha_cli._native_stock_launch import StockFixtureLaunch
        from alpha_cli.control_store import ControlStore
        from alpha_cli.native_stock_fixture import digest
        from alpha_cli.native_stock_inspect import inspect_run
        from alpha_cli.native_supervisor import start_synthetic_owner, synthetic_workspace
        from tests.unit.test_native_stock_dispatch import JOB
        from tests.unit.test_research_control_store import (
            _approved_native_d1,
            _native_d1_job,
            _project,
        )

        source = Path(os.environ["ALPHA_RDAGENT_SOURCE"])
        runtime = Path(os.environ["ALPHA_STOCK_PYTHON"]).parents[2]
        evidence = Path(os.environ["ALPHA_STOCK_RECEIPTS"]) / "profile"
        evidence.mkdir()
        for mode in ("resume", "cancel", "exhaust", "tamper"):
            with self.subTest(mode=mode), synthetic_workspace() as root:
                launch = StockFixtureLaunch(source, mode, stock_runtime=runtime)
                selected = ProfileSelection(source, runtime, mode)
                store = ControlStore(root)
                _project(store)
                contract, _ = _approved_native_d1(
                    store,
                    loop_steps=5,
                    implementation_fingerprints=launch.implementation_fingerprints(),
                )
                _native_d1_job(store, contract, job_id=JOB, manifest_sha256=launch.fingerprint)
                process = start_synthetic_owner(
                    root,
                    JOB,
                    fixture="native_loop",
                    seconds=40,
                    native=launch,
                )
                try:
                    process.wait(timeout=50)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)
                with patch("subprocess.Popen") as forbidden:
                    report = inspect_run(root, JOB, profile_selection=selected)
                    forbidden.assert_not_called()
                run = evidence / mode
                run.mkdir()
                (run / "inspection.json").write_text(json.dumps(report, sort_keys=True))
                self.assertEqual(record(report["profile_verification"])["status"], "verified")
                self.assertEqual(
                    record(report["profile_verification"])["recorded_identity"], "identity_rebuilt"
                )
                self.assertEqual(
                    record(record(report["progress"])["profile_declaration"])["status"], "verified"
                )
                self.assertFalse(report["resume_allowed"])
                self.assertEqual(
                    record(report["profile_verification"])["historical_worker_execution"],
                    "unavailable",
                )
                if mode != "resume":
                    continue
                self.assertEqual(
                    record(record(report["artifact_validation"])["profile_declaration"])["status"],
                    "verified",
                )
                cli = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "alpha_cli.native_stock_inspect",
                        "--data-dir",
                        str(root),
                        "--job-id",
                        JOB,
                        "--profile-source",
                        str(source),
                        "--profile-runtime",
                        str(runtime),
                        "--profile-mode",
                        mode,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=True,
                )
                self.assertEqual(json.loads(cli.stdout), report)
                (run / "cli.json").write_text(cli.stdout)
                cases = {
                    "not_selected": None,
                    "mode_mismatch": ProfileSelection(source, runtime, "cancel"),
                    "missing_runtime": ProfileSelection(source, runtime / "missing", mode),
                }
                for name, selection in cases.items():
                    changed = inspect_run(root, JOB, profile_selection=selection)
                    expected = "mismatch" if name == "mode_mismatch" else "unavailable"
                    self.assertEqual(record(changed["profile_verification"])["status"], expected)
                    self.assertFalse(changed["resume_allowed"])
                    (run / f"{name}.json").write_text(json.dumps(changed, sort_keys=True))
                work = root / f"payload-{JOB}"
                progress = work / "stock-progress.json"
                value = json.loads(progress.read_bytes())
                record(value["request"])["manifest_sha256"] = "0" * 64
                value["request_sha256"] = digest(value["request"])
                progress.write_text(json.dumps(value))
                changed = inspect_run(root, JOB, profile_selection=selected)
                self.assertEqual(record(changed["profile_verification"])["status"], "verified")
                self.assertEqual(
                    record(record(changed["progress"])["profile_declaration"])["status"], "mismatch"
                )
                (run / "progress_profile_mismatch.json").write_text(
                    json.dumps(changed, sort_keys=True)
                )
                receipt_path, trace_path = work / "stock-receipt.json", work / "stock-trace.json"
                receipt, trace = (
                    json.loads(receipt_path.read_bytes()),
                    json.loads(trace_path.read_bytes()),
                )
                record(receipt["request"])["manifest_sha256"] = "0" * 64
                trace["request_sha256"] = digest(receipt["request"])
                trace_path.write_text(json.dumps(trace, sort_keys=True))
                receipt["trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
                receipt_path.write_text(json.dumps(receipt, sort_keys=True))
                changed = inspect_run(root, JOB, profile_selection=selected)
                self.assertEqual(
                    record(changed["artifact_validation"])["status"], "current_bytes_validated_only"
                )
                self.assertEqual(
                    record(record(changed["artifact_validation"])["profile_declaration"])["status"],
                    "mismatch",
                )
                (run / "receipt_profile_mismatch.json").write_text(
                    json.dumps(changed, sort_keys=True)
                )
                # A deterministic corrupted record double, never a ledger mutation.
                with store._readonly_transaction() as connection:
                    job = dict(ControlStore._require_job(connection, JOB))
                request = json.loads(job["request_json"])
                record(request["native_invocation_spec"])["spec_sha256"] = "0" * 64
                job["request_json"] = json.dumps(request)
                with patch.object(ControlStore, "_require_job", return_value=job):
                    changed = inspect_run(root, JOB, profile_selection=selected)
                self.assertEqual(record(changed["profile_verification"])["status"], "unavailable")
                self.assertEqual(
                    record(changed["profile_verification"])["recorded_identity"],
                    "invalid_or_unavailable",
                )
                (run / "invalid_record.json").write_text(json.dumps(changed, sort_keys=True))


class RecordedSchemaTests(unittest.TestCase):
    def test_bool_float_record_mutations_cannot_borrow_original_digest(self) -> None:
        import json

        from alpha_cli.control_store import ControlStore
        from alpha_cli.native_stock_profile import read_recorded_profile
        from alpha_cli.native_supervisor import synthetic_workspace
        from tests.unit.test_native_stock_dispatch import JOB
        from tests.unit.test_research_control_store import (
            _approved_native_d1,
            _native_d1_job,
            _project,
        )

        with synthetic_workspace() as root:
            store = ControlStore(root)
            _project(store)
            import hashlib

            schema_hashes = {
                key: hashlib.sha256(("public schema fixture " + key).encode()).hexdigest()
                if value is not None
                else None
                for key, value in HASHES.items()
            }
            contract, _ = _approved_native_d1(
                store, loop_steps=5, implementation_fingerprints=schema_hashes
            )
            _, reservation = _native_d1_job(store, contract, job_id=JOB, manifest_sha256="a" * 64)
            with store._readonly_transaction() as connection:
                job = dict(ControlStore._require_job(connection, JOB))
                original = json.loads(job["request_json"])
                spec = original["native_invocation_spec"]
                # Explicit synthetic protocol double, not a persisted owner claim.
                events = {
                    "native_claim": {
                        "reservation_id": reservation["reservation_id"],
                        "spec_sha256": spec["spec_sha256"],
                        "stock_profile_sha256": "a" * 64,
                    },
                    "native_invocation": {"profile_sha256": "a" * 64},
                }
                self.assertEqual(
                    read_recorded_profile(connection, JOB, events).cpu_milliseconds, 10000
                )
                for value in (True, 1.0):
                    changed = json.loads(job["request_json"])
                    record(changed["native_invocation_spec"])["schema_version"] = value
                    with (
                        self.subTest(schema_version=value),
                        patch.object(
                            ControlStore,
                            "_require_job",
                            return_value=(job | {"request_json": json.dumps(changed)}),
                        ),
                        self.assertRaises(DataError),
                    ):
                        read_recorded_profile(connection, JOB, events)
                changed = json.loads(job["request_json"])
                record(record(changed["native_invocation_spec"])["approved_budget"])[
                    "rdagent_native_v1_cpu_milliseconds"
                ] = 10000.0
                with (
                    patch.object(
                        ControlStore,
                        "_require_job",
                        return_value=(job | {"request_json": json.dumps(changed)}),
                    ),
                    self.assertRaises(DataError),
                ):
                    read_recorded_profile(connection, JOB, events)


def test_factor_profile_records_verifies_and_detects_mutation(tmp_path: Path) -> None:
    import importlib.util
    import json

    import pytest

    worker = Path(__file__).resolve().parents[2] / "workers/rdagent"
    spec = importlib.util.spec_from_file_location(
        "profile_helper", worker / "install_stock_profile.py"
    )
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    bundle = tmp_path / "bundle"
    site = bundle / "venv/lib/python3.11/site-packages"
    site.mkdir(parents=True)
    (bundle / "venv/pyvenv.cfg").write_text("version = 3.11.14\n")
    pins = helper.locked_pins((worker / "factor-requirements.lock").read_text())
    assert len(pins) == 79
    for name, version in pins.items():
        dist = site / f"{name}-{version}.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text(f"Name: {name}\nVersion: {version}\n")
    assert helper.main(["--profile", "factor", str(bundle)]) == 0
    profile = json.loads((bundle / "factor-profile.json").read_bytes())
    assert profile["schema"] == "AlphaFactorRuntimeProfileV1"
    assert not (bundle / "stock-profile.json").exists()
    assert helper.main(["--profile", "factor", "--verify", str(bundle)]) == 0
    (site / "changed.py").write_text("changed")
    assert helper.main(["--profile", "factor", "--verify", str(bundle)]) == 1
    with pytest.raises(ValueError, match="differs from lock"):
        helper.measure(bundle)  # the default is still the stock lock
