"""Built SPA/real backend/native receipt journey using new disposable public fixtures only."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.unit.test_native_result_api import SERVER_GUARD


def _owned_browser(
    command: list[str],
    *,
    repository: Path,
    cwd: Path,
    env: dict[str, str],
    evidence: Path,
    limit: float = 150,
) -> int:
    """Existing subreaper owns runner descendants, even on timeout or runner crash."""
    from alpha_cli.durable_lease import _observe_retained_child, terminate_and_reap

    status = None
    with (
        (evidence / "playwright.stdout.txt").open("w") as stdout,
        (evidence / "playwright.stderr.txt").open("w") as stderr,
    ):
        process = subprocess.Popen(
            [
                sys.executable,
                str(repository / "scripts/run_owned_test.py"),
                "--timeout",
                str(limit),
                "--",
                *command,
            ],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + limit + 20
            while (status := _observe_retained_child(process)) is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Owned browser wrapper did not finish within its bound")
                time.sleep(0.02)
        finally:
            terminate_and_reap(
                process,
                process_group_id=process.pid,
                retain_leader=True,
                grace_seconds=0.25 if status is not None else 8.0,
            )
    return status


@unittest.skipUnless(sys.platform == "linux", "Linux retained-child fixture supervision required")
class NativeBrowserOwnershipTests(unittest.TestCase):
    def test_existing_owner_cleans_descendants_on_runner_timeout_and_crash(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        for crash in (False, True):
            with tempfile.TemporaryDirectory(prefix="alpha-native-web-cleanup-") as directory:
                root = Path(directory)
                script = (
                    "import os,subprocess,sys,time; "
                    "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                    "print(child.pid,flush=True); " + ("os._exit(2)" if crash else "time.sleep(30)")
                )
                status = _owned_browser(
                    [sys.executable, "-c", script],
                    repository=repository,
                    cwd=root,
                    env={"PATH": os.defpath, "HOME": str(root)},
                    evidence=root,
                    limit=0.3,
                )
                self.assertEqual(status, 2 if crash else 124)
                pid = int((root / "playwright.stdout.txt").read_text().strip())
                self.assertFalse(Path(f"/proc/{pid}").exists(), "owned descendant not reaped")


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ
    and "ALPHA_STOCK_PYTHON" in os.environ
    and "ALPHA_NATIVE_WEB_EVIDENCE" in os.environ,
    "explicit installed assets and fresh evidence directory required",
)
class NativeWebJourney(unittest.TestCase):
    def test_built_spa_reads_native_owner_receipt_without_interception(self) -> None:
        from alpha_cli.native_supervisor import start_synthetic_owner
        from tests.unit.test_native_stock_dispatch import JOB, case

        repository = Path(__file__).resolve().parents[2]
        frontend = repository / "apps/alpha-web/frontend"
        evidence = Path(os.environ["ALPHA_NATIVE_WEB_EVIDENCE"])
        evidence.mkdir(parents=True, exist_ok=False)
        node = shutil.which("node")
        self.assertIsNotNone(node, "existing Node required; no installation allowed")
        assert node is not None
        self.assertTrue((frontend / "node_modules/@playwright/test/cli.js").is_file())
        with case() as (root, _, launch):
            owner = start_synthetic_owner(
                root, JOB, fixture="native_loop", seconds=40, native=launch
            )
            try:
                self.assertEqual(owner.wait(timeout=50), 0)
            finally:
                if owner.poll() is None:
                    owner.terminate()
                    owner.wait(timeout=5)
            receipt = root / f"payload-{JOB}" / "stock-receipt.json"
            original = receipt.read_bytes()
            database = root / "control/workstation.sqlite3"
            with sqlite3.connect(database) as connection:
                before = list(connection.iterdump())
            hook = root / "web-server-hook"
            hook.mkdir()
            # Reuse the preceding public audit: only explicit loopback bind is added for Uvicorn.
            guard = SERVER_GUARD.replace(
                "'socket.sendto','socket.bind','os.system',", "'socket.sendto','os.system',"
            )
            guard = guard.replace(
                "    if event == 'subprocess.Popen':",
                "    if event == 'socket.bind' and values[1][0] != '127.0.0.1':\n"
                "        raise RuntimeError('fixture denies non-loopback bind')\n"
                "    if event == 'subprocess.Popen':",
            )
            (hook / "sitecustomize.py").write_text(guard)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            server_env = {
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
                    str(repository / item)
                    for item in (
                        "apps/alpha-web/src",
                        "apps/alpha-cli/src",
                        "packages/alpha-core/src",
                        ".",
                    )
                ),
                "ALPHA_DATA_DIR": str(root),
                "ALPHA_BULK_DATA_DIR": str(root / "bulk"),
                "ALPHA_PAPER_ENABLED": "false",
                "ALPHA_IBKR_PAPER_ENABLED": "false",
                "ALPHA_NATIVE_RESULT_SOURCE": str(launch.source),
                "ALPHA_NATIVE_RESULT_RUNTIME": str(launch.stock_runtime),
            }
            fixture = root / "native-web-fixture.json"
            fixture.write_text(
                json.dumps(
                    {
                        "python": sys.executable,
                        "root": str(root),
                        "job": JOB,
                        "receipt": str(receipt),
                        "receipt_sha256": hashlib.sha256(original).hexdigest(),
                        "port": port,
                        "server_env": server_env,
                        "evidence": str(evidence),
                    }
                )
            )
            with tempfile.TemporaryDirectory(prefix="alpha-native-browser-home-") as browser_home:
                env = {
                    "PATH": os.defpath,
                    "HOME": browser_home,
                    "LANG": "C.UTF-8",
                    "ALPHA_NATIVE_WEB_FIXTURE": str(fixture),
                    "ALPHA_NATIVE_WEB_OUTPUT": str(evidence / "playwright"),
                }
                # Non-secret installed browser cache path supplied by the managed runtime.
                if "PLAYWRIGHT_BROWSERS_PATH" in os.environ:
                    env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
                status = _owned_browser(
                    [
                        node,
                        str(frontend / "node_modules/@playwright/test/cli.js"),
                        "test",
                        "--config",
                        str(frontend / "playwright.native-result.config.ts"),
                    ],
                    repository=repository,
                    cwd=frontend,
                    env=env,
                    evidence=evidence,
                )
            stdout = (evidence / "playwright.stdout.txt").read_text()
            stderr = (evidence / "playwright.stderr.txt").read_text()
            self.assertEqual(status, 0, stdout + stderr)
            self.assertEqual(receipt.read_bytes(), original)
            with sqlite3.connect(database) as connection:
                self.assertEqual(before, list(connection.iterdump()))
            audit = [
                json.loads(line)
                for line in (root / "api-read-audit.jsonl").read_text().splitlines()
            ]
            (evidence / "read-process-audit.json").write_text(json.dumps(audit, indent=2))
            self.assertTrue(audit)
            self.assertTrue(all(row["write_opens"] == 0 for row in audit))
            (evidence / "result.json").write_text(
                json.dumps(
                    {
                        "classification": "synthetic_only_unqualified",
                        "job_id": JOB,
                        "receipt_sha256": hashlib.sha256(original).hexdigest(),
                        "actual_model_calls": 0,
                        "native_stages": 5,
                        "store_rows_unchanged": True,
                        "process_audits": len(audit),
                        "browser_interception": False,
                        "server": "real loopback FastAPI/Uvicorn",
                        "frontend": "built production SPA served by real backend",
                        "private_full_qualification": "unverified",
                    },
                    indent=2,
                )
                + "\n"
            )
