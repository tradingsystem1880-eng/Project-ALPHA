"""Mounted native-job read contract on public synthetic fixtures, never live inference."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from alpha_web._native_results import (
    NativeResultDeployment,
    ServerNativeProfile,
    native_result_deployment,
)
from alpha_web.app import create_app
from tests.unit._native_stock_test_support import array, record


class NativeAPIContractTests(unittest.TestCase):
    def client(self, configuration: NativeResultDeployment | None = None) -> TestClient:
        app = create_app()
        app.dependency_overrides[native_result_deployment] = lambda: configuration
        return TestClient(app)

    def test_mounted_unconfigured_is_unavailable_without_reader(self) -> None:
        with (
            self.client() as client,
            patch("alpha_web.api.native_results.read_native_result") as read,
        ):
            reply = client.get("/api/native-jobs/00000000-0000-4000-8000-000000000001/result")
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()["status"], "unavailable")
        self.assertNotIn("receipt", reply.json())
        read.assert_not_called()

    def test_query_body_invalid_identity_and_method_cannot_select_paths(self) -> None:
        endpoint = "/api/native-jobs/00000000-0000-4000-8000-000000000001/result"
        with (
            self.client() as client,
            patch("alpha_web.api.native_results.read_native_result") as read,
        ):
            for query in (
                "?data_dir=/private/never",
                "?profile_source=/private/never",
                "?mode=resume",
            ):
                reply = client.get(endpoint + query)
                self.assertEqual(reply.status_code, 422)
                self.assertNotIn("/private/never", reply.text)
            self.assertEqual(
                client.request("GET", endpoint, json={"path": "/private/never"}).status_code, 422
            )
            self.assertEqual(client.get("/api/native-jobs/not-a-uuid/result").status_code, 422)
            self.assertEqual(client.post(endpoint).status_code, 405)
            self.assertIn(
                client.get("/api/native-jobs/%2e%2e%2fprivate/result").status_code, {404, 422}
            )
            read.assert_not_called()

    def test_openapi_exposes_only_uuid_identity(self) -> None:
        operation = record(
            record(record(create_app().openapi()["paths"])["/api/native-jobs/{job_id}/result"])[
                "get"
            ]
        )
        self.assertEqual(
            [(record(p)["name"], record(p)["in"]) for p in array(operation["parameters"])],
            [("job_id", "path")],
        )
        self.assertNotIn("requestBody", operation)
        self.assertEqual(operation["tags"], ["native-results"])

    def test_bad_backend_state_and_paths_do_not_escape(self) -> None:
        from pathlib import Path

        from alpha_web._native_results import read_native_result

        configuration = NativeResultDeployment(
            Path("/tmp/public"),
            ServerNativeProfile(Path("/public/source"), Path("/public/runtime"), "resume"),
        )
        with (
            patch("alpha_web._native_results._profile_preflight"),
            patch(
                "alpha_web._native_results._read_cli",
                side_effect=ValueError("dummy-secret /private/owner"),
            ),
        ):
            body = read_native_result(configuration, "00000000-0000-4000-8000-000000000001")
        self.assertEqual(body["status"], "unavailable")
        self.assertNotIn("dummy-secret", str(body))
        self.assertNotIn("/private/owner", str(body))
        self.assertNotIn("receipt", body)

    def test_profile_preflight_blocks_special_files_and_oversized_assets(self) -> None:

        from alpha_cli.native_supervisor import synthetic_workspace
        from alpha_web._native_results import read_native_result

        with synthetic_workspace() as root:
            source, runtime = root / "source", root / "runtime"
            (source / "rdagent").mkdir(parents=True)
            (runtime / "venv/bin").mkdir(parents=True)
            (runtime / "venv/bin/python").write_bytes(b"synthetic metadata; never executed")
            (runtime / "venv/pyvenv.cfg").write_text("synthetic fixture only")
            lock = runtime / "dependencies.lock.txt"
            lock.write_bytes(b"public fixture")
            configuration = NativeResultDeployment(
                root, ServerNativeProfile(source, runtime, "resume")
            )
            import os

            fifo = source / "rdagent/fifo"
            os.mkfifo(fifo)
            with patch("alpha_web._native_results._read_cli") as inspect:
                self.assertEqual(read_native_result(configuration, "job")["status"], "unavailable")
                inspect.assert_not_called()
            fifo.unlink()
            with lock.open("wb") as stream:
                stream.truncate(1024 * 1024 + 1)
            with patch("alpha_web._native_results._read_cli") as inspect:
                self.assertEqual(read_native_result(configuration, "job")["status"], "unavailable")
                inspect.assert_not_called()


SERVER_GUARD = r"""
import atexit, json, os, pathlib, sys
sys.dont_write_bytecode=True
from unittest.mock import patch

def guard(event, values):
    if event in {
        'socket.connect','socket.getaddrinfo','socket.gethostbyname',
        'socket.sendto','socket.bind','os.system',
    }:
        raise RuntimeError('server fixture denies external effects')
    if event == 'subprocess.Popen':
        argv=list(values[1])
        if argv[:4] != ['alpha','research','diagnostic','native-result'] and tuple(argv) not in {
            ('uname','-p'),('/sbin/ldconfig','-p'),
        }:
            raise RuntimeError('server fixture denies non-read process execution')
    if event == 'open' and isinstance(values[0],str):
        path=pathlib.Path(values[0])
        if {'.codex','.aws','.ssh','.azure'}.intersection(path.parts) or path.name in {
            'auth.json','credentials','application_default_credentials.json',
        }:
            raise RuntimeError('server fixture denies credential reads')
sys.addaudithook(guard)
from alpha_cli.control_store import ControlStore
write_opens=0
def no_write(self):
    global write_opens
    write_opens+=1
    raise AssertionError('fixture denies write-open')
ControlStore._open=no_write
def receipt():
    with pathlib.Path('api-read-audit.jsonl').open('a') as out:
        out.write(json.dumps({'pid':os.getpid(),'write_opens':write_opens})+'\n')
atexit.register(receipt)
"""

SERVER_REQUEST = r"""
import json, pathlib, sys
from unittest.mock import patch

def guard(event, values):
    if event in {
        'socket.connect','socket.getaddrinfo','socket.gethostbyname',
        'socket.sendto','socket.bind','os.system',
    }:
        raise RuntimeError('server fixture denies external effects')
    if event == 'subprocess.Popen':
        argv=list(values[1])
        if argv[:4] != ['alpha','research','diagnostic','native-result'] and tuple(argv) not in {
            ('uname','-p'),('/sbin/ldconfig','-p'),
        }:
            raise RuntimeError('server fixture denies non-read process execution')
    if event == 'open' and isinstance(values[0],str):
        path=pathlib.Path(values[0])
        if {'.codex','.aws','.ssh','.azure'}.intersection(path.parts) or path.name in {
            'auth.json','credentials','application_default_credentials.json',
        }:
            raise RuntimeError('server fixture denies credential reads')
sys.addaudithook(guard)
from fastapi.testclient import TestClient
from alpha_cli.control_store import ControlStore
from alpha_web.app import create_app

with patch.object(
    ControlStore,'_open',side_effect=AssertionError('write route forbidden')
) as writes:
    with TestClient(create_app()) as client:
        response=client.get('/api/native-jobs/'+sys.argv[1]+'/result')
print(json.dumps({'http_status':response.status_code,'body':response.json(),'write_route_calls':writes.call_count},sort_keys=True))
"""


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ and "ALPHA_STOCK_PYTHON" in os.environ,
    "explicit installed synthetic native assets required",
)
class NativeAPIServerJourney(unittest.TestCase):
    def test_native_owner_receipt_to_fresh_server_and_negative_bindings(self) -> None:
        import hashlib
        import json
        import sqlite3
        import subprocess
        import sys
        from pathlib import Path

        from pydantic import ValidationError

        from alpha_cli.native_supervisor import start_synthetic_owner, synthetic_workspace
        from alpha_web.api.native_result_models import NativeJobResultV1
        from tests.unit.test_native_stock_dispatch import JOB, case

        repository = Path(__file__).resolve().parents[2]
        evidence = Path(os.environ["ALPHA_STOCK_RECEIPTS"]) / "api"
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
            database = root / "control/workstation.sqlite3"
            with sqlite3.connect(database) as connection:
                before = list(connection.iterdump())
            hook = root / "server-test-hook"
            hook.mkdir()
            (hook / "sitecustomize.py").write_text(SERVER_GUARD)
            environment = {
                "PATH": str(Path(sys.executable).parent) + ":" + os.defpath,
                "LANG": "C.UTF-8",
                "HOME": str(root),
                "HF_HUB_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "LITELLM_LOCAL_MODEL_COST_MAP": "True",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "PYTHONPATH": str(hook)
                + ":"
                + ":".join(
                    str(repository / path)
                    for path in (
                        "apps/alpha-web/src",
                        "apps/alpha-cli/src",
                        "packages/alpha-core/src",
                        ".",
                    )
                ),
                "ALPHA_DATA_DIR": str(root),
                "ALPHA_NATIVE_RESULT_SOURCE": str(launch.source),
                "ALPHA_NATIVE_RESULT_RUNTIME": str(launch.stock_runtime),
                "ALPHA_NATIVE_RESULT_MODE": "resume",
            }

            def request(
                name: str,
                expected: str,
                *,
                changes: dict[str, Path | str | None] | None = None,
                job: str = JOB,
            ) -> dict[str, object]:
                env = dict(environment)
                for key, value in (changes or {}).items():
                    if value is None:
                        env.pop(key, None)
                    else:
                        env[key] = str(value)
                completed = subprocess.run(
                    [sys.executable, "-B", "-c", SERVER_REQUEST, job],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                (evidence / f"{name}.stdout.json").write_text(completed.stdout)
                (evidence / f"{name}.stderr.txt").write_text(completed.stderr)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                reply = json.loads(completed.stdout)
                self.assertEqual(reply["http_status"], 200)
                self.assertEqual(reply["write_route_calls"], 0)
                body = reply["body"]
                self.assertEqual(body["status"], expected)
                self.assertFalse(body["resume_allowed"])
                self.assertEqual(body["scientific_acceptance"], "not_admitted")
                self.assertNotIn(str(launch.source), completed.stdout)
                self.assertNotIn(str(launch.stock_runtime), completed.stdout)
                if expected != "completed":
                    self.assertNotIn("receipt", body)
                    self.assertNotIn("result", body)
                return record(body)

            body = request("completed", "completed")
            self.assertEqual(body["result"], {"synthetic_score": -0.125, "unit": "fixture_only"})
            self.assertTrue(record(body["receipt"])["resumed_without_repeating"])
            from alpha_web._native_results import read_native_result

            configured = NativeResultDeployment(
                root, ServerNativeProfile(launch.source, launch.stock_runtime, "resume")
            )
            with (
                patch("alpha_web._native_results._profile_preflight"),
                patch("alpha_web._native_results._read_cli", return_value=body),
            ):
                wrong_job = read_native_result(configured, "00000000-0000-4000-8000-000000000001")
            self.assertEqual(wrong_job["status"], "unavailable")
            self.assertNotIn("receipt", wrong_job)
            work = root / f"payload-{JOB}"
            receipt_path = work / "stock-receipt.json"
            original = receipt_path.read_bytes()
            self.assertEqual(
                record(body["provenance"])["receipt_sha256"], hashlib.sha256(original).hexdigest()
            )
            for field, value in (("resume_allowed", True), ("status", "invalid")):
                changed = dict(body, **{field: value})
                with self.subTest(invalid_contract=field), self.assertRaises(ValidationError):
                    NativeJobResultV1.model_validate(changed)
            changed = json.loads(json.dumps(body))
            record(changed["receipt"])["actual_model_calls"] = False
            with self.assertRaises(ValidationError):
                NativeJobResultV1.model_validate(changed)
            request(
                "missing_configuration", "unavailable", changes={"ALPHA_NATIVE_RESULT_MODE": None}
            )
            request(
                "invalid_server_mode",
                "unavailable",
                changes={"ALPHA_NATIVE_RESULT_MODE": "unsupported"},
            )
            request("profile_mismatch", "invalid", changes={"ALPHA_NATIVE_RESULT_MODE": "cancel"})
            request("unknown_job", "unavailable", job="00000000-0000-4000-8000-000000000001")
            receipt_path.write_bytes(original + b" ")
            request("changed_exact_bytes", "invalid")
            receipt_path.write_bytes(b"{not JSON")
            request("corrupt_receipt", "invalid")
            receipt_path.unlink()
            request("missing_receipt", "unavailable")
            receipt_path.write_bytes(original)
            with case() as (ownerless, _, _):
                request("missing_owner", "unavailable", changes={"ALPHA_DATA_DIR": ownerless})
            with synthetic_workspace() as invalid:
                (invalid / "control").mkdir()
                (invalid / "control/workstation.sqlite3").write_bytes(b"synthetic corrupt SQLite")
                request("corrupt_store", "unavailable", changes={"ALPHA_DATA_DIR": invalid})
            with sqlite3.connect(database) as connection:
                self.assertEqual(before, list(connection.iterdump()))
            store.request_job_cancellation(JOB, actor="synthetic", reason="late API fixture")
            with sqlite3.connect(database) as connection:
                after_cancel = list(connection.iterdump())
            request("late_cancellation", "unavailable")
            with sqlite3.connect(database) as connection:
                self.assertEqual(after_cancel, list(connection.iterdump()))
            audit = [
                json.loads(line)
                for line in (root / "api-read-audit.jsonl").read_text().splitlines()
            ]
            self.assertTrue(audit)
            self.assertTrue(all(row["write_opens"] == 0 for row in audit))
            (evidence / "read-process-audit.json").write_text(json.dumps(audit, sort_keys=True))


class NativeTransportTests(unittest.TestCase):
    def test_bounded_transport_preserves_state_exit_and_rejects_malformed_output(self) -> None:
        import json
        import sys
        import tempfile
        from pathlib import Path

        from alpha_core import DataError
        from alpha_web._native_results import _read_cli

        body = {
            "schema": "NativeStockOperatorResultV1",
            "operation": "recover_native_stock_result",
            "classification": "synthetic_only_unqualified",
            "status": "unavailable",
            "reason": "synthetic_transport",
            "resume_allowed": False,
            "scientific_acceptance": "not_admitted",
        }
        for script, succeeds in (
            (f"import sys; print({json.dumps(body)!r}); sys.exit(3)", True),
            ("print('{not-json')", False),
            ('print(\'{"status":"completed","status":"completed"}\')', False),
            (f"print({json.dumps(body)!r})", False),
            ("print('x' * 131073)", False),
            ("import sys; sys.stderr.write('x' * 8193)", False),
        ):
            with (
                tempfile.TemporaryDirectory() as directory,
                self.subTest(succeeds=succeeds),
                patch(
                    "alpha_web._native_results._command",
                    return_value=[sys.executable, "-B", "-c", script],
                ),
                patch(
                    "alpha_web._native_results._cli_environment", return_value={"PATH": os.defpath}
                ),
            ):
                if succeeds:
                    self.assertEqual(_read_cli([], Path(directory)), body)
                else:
                    with self.assertRaises(DataError):
                        _read_cli([], Path(directory))

    def test_timeout_does_not_wait_for_slow_reader(self) -> None:
        import sys
        import tempfile
        import time
        from pathlib import Path

        from alpha_core import DataError
        from alpha_web._native_results import _read_cli

        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "alpha_web._native_results._command",
                return_value=[sys.executable, "-B", "-c", "import time; time.sleep(5)"],
            ),
            patch("alpha_web._native_results._cli_environment", return_value={"PATH": os.defpath}),
            patch("alpha_web._native_results._CLI_TIMEOUT", 0.1),
        ):
            before = time.monotonic()
            with self.assertRaises(DataError):
                _read_cli([], Path(directory))
            self.assertLess(time.monotonic() - before, 3.0)

    def test_exited_leader_does_not_leave_live_descendant(self) -> None:
        import json
        import sys
        import tempfile
        import time
        from contextlib import suppress
        from pathlib import Path

        from alpha_cli.durable_lease import DurableLeaseError
        from alpha_core import DataError
        from alpha_web._native_results import _read_cli

        for hold_pipes in (True, False):
            with tempfile.TemporaryDirectory() as directory, self.subTest(hold_pipes=hold_pipes):
                marker = Path(directory) / "descendant.pid"
                body = json.dumps({"status": "unavailable"})
                script = (
                    "import os,sys,time,pathlib\n"
                    "child=os.fork()\n"
                    "if child==0:\n"
                    f" pathlib.Path({str(marker)!r}).write_text(str(os.getpid()))\n"
                    + ("" if hold_pipes else " os.close(1); os.close(2)\n")
                    + " time.sleep(5); os._exit(0)\n"
                    + f"print({body!r},flush=True); sys.exit(3)\n"
                )
                with (
                    patch(
                        "alpha_web._native_results._command",
                        return_value=[sys.executable, "-B", "-c", script],
                    ),
                    patch(
                        "alpha_web._native_results._cli_environment",
                        return_value={"PATH": os.defpath},
                    ),
                    patch("alpha_web._native_results._CLI_TIMEOUT", 0.3),
                    suppress(DataError, DurableLeaseError),
                ):
                    # Unreaped adopted zombies leave cleanup proof unavailable;
                    # no retry of a released numeric group is permitted.
                    _read_cli([], Path(directory))
                self.assertTrue(marker.exists())
                child = int(marker.read_text())
                status = Path(f"/proc/{child}/stat")
                deadline = time.monotonic() + 2
                live = True
                while time.monotonic() < deadline:
                    try:
                        live = status.read_text().rsplit(")", 1)[1].split()[0] != "Z"
                    except FileNotFoundError:
                        live = False
                    if not live:
                        break
                    time.sleep(0.01)
                self.assertFalse(live, "owned read descendant survived exited leader")
