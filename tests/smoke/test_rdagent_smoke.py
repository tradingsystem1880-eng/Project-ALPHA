"""Workflow 7, RD-Agent: the pinned upstream loop runs, then the installed programs read its job.

Nothing in ``alpha`` starts an RD-Agent run (there is no public launch command), so each check
creates its disposable, synthetic-only job the way the native tests do: the public test helpers
write an approved, reserved fixture job into a fresh ``synthetic_workspace()``, and the existing
retained owner (``start_synthetic_owner``) launches the worker. These approvals are fixture
records in a throwaway store, not the owner's. Everything after the launch is read back by the
installed ``alpha`` and ``alpha-web`` programs, each in a new process. All results stay
synthetic and ``not_admitted``; no model, provider or market data is involved.

Prerequisites, provisioned by ``scripts/setup_rdagent.sh``: ``ALPHA_RDAGENT_SOURCE`` (the derived,
digest-verified pinned source) for the native fixture loop, plus ``ALPHA_STOCK_PYTHON`` (a stock
runtime bundle's ``venv/bin/python``, built by ``--with-stock-runtime``) for the stock ``RDLoop``
check. Without them they skip.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.smoke._harness import child_env, get_json, program, web_server

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

WORKER_PYTHON = Path(__file__).resolve().parents[2] / "workers/rdagent/.venv/bin/python"
# workers/rdagent/source_pin.py: digest of every file under rdagent/ at the pinned commit.
SOURCE_TREE_SHA256 = "0266b2d63328f88fcaf6f239bf6d67f29c896b8161566f794ef69465b7788707"
NO_SOURCE = "RD-Agent not provisioned: run scripts/setup_rdagent.sh and export ALPHA_RDAGENT_SOURCE"
NO_STOCK = (
    "stock RD-Agent runtime not provisioned: ALPHA_STOCK_PYTHON (a runtime bundle's "
    "venv/bin/python) is unset; run scripts/setup_rdagent.sh --with-stock-runtime"
)


def _source() -> Path:
    configured = os.environ.get("ALPHA_RDAGENT_SOURCE", "").strip()
    if not configured or not WORKER_PYTHON.is_file():
        pytest.skip(NO_SOURCE)
    return Path(configured).resolve()


def _alpha(root: Path, *args: str, expect: int = 0) -> Any:
    """Run the installed ``alpha`` with the synthetic workspace as its data directory."""
    env = child_env(root, ALPHA_DATA_DIR=str(root), ALPHA_BULK_DATA_DIR=str(root / "bulk"))
    proc = subprocess.run(
        [str(program("alpha")), *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == expect, f"alpha {' '.join(args)}: {proc.stdout[-2000:]}{proc.stderr}"
    return json.loads(proc.stdout)


def _wait(owner: subprocess.Popen[bytes], timeout: float) -> int:
    try:
        return owner.wait(timeout=timeout)
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.wait(timeout=5)


def test_native_fixture_loop_runs_and_alpha_shows_its_job() -> None:
    source = _source()
    from alpha_cli._native_loop_admission import NativeLaunch
    from alpha_cli.control_store import ControlStore
    from alpha_cli.native_supervisor import start_synthetic_owner, synthetic_workspace
    from tests.unit.test_native_w04_admission import JOB
    from tests.unit.test_research_control_store import (
        PROJECT_ID,
        _approved_native_d1,
        _native_d1_job,
        _project,
    )

    launch = NativeLaunch(source, "SUPPORTED")  # verifies the pinned source digest first
    with synthetic_workspace() as root:
        store = ControlStore(root)
        _project(store)
        contract, _ = _approved_native_d1(
            store, loop_steps=5, implementation_fingerprints=launch.implementation_fingerprints()
        )
        _native_d1_job(store, contract, job_id=JOB, manifest_sha256=launch.fingerprint)
        owner = start_synthetic_owner(root, JOB, fixture="native_loop", native=launch, seconds=10)
        assert _wait(owner, 30) == 0

        receipt = json.loads((root / f"payload-{JOB}" / "receipt.json").read_text())
        assert receipt["synthetic"] is True
        assert receipt["scientific_acceptance"] == "not_admitted"
        assert receipt["authority"] == "none"
        assert receipt["checks"]["label"] == "SUPPORTED"  # a supplied synthetic label
        stages = ["direct_exp_gen", "coding", "running", "feedback", "record"]
        assert receipt["checks"]["events"] == stages  # upstream LoopBase ran all five
        assert receipt["source_pin"]["verified"]["source_tree_sha256"] == SOURCE_TREE_SHA256
        assert "rdagent/utils/workflow/loop.py" in receipt["imported_source_sha256"]

        status = _alpha(root, "research", "status", PROJECT_ID, "--json")
        assert status["active_job_id"] == JOB
        assert status["execution_state"] == "running"  # pending scientific admission, never done
        (row,) = _alpha(root, "research", "list", "--json")["items"]
        assert row["case_id"] == PROJECT_ID

        with web_server(root, ALPHA_DATA_DIR=str(root)) as base:
            served = get_json(f"{base}/api/research/cases/{PROJECT_ID}/status")
            assert served["active_job_id"] == JOB
            assert served["execution_state"] == "running"


def test_stock_rdloop_result_is_read_by_alpha_and_the_web_app() -> None:
    _source()
    if not os.environ.get("ALPHA_STOCK_PYTHON", "").strip():
        pytest.skip(NO_STOCK)
    from alpha_cli.native_supervisor import start_synthetic_owner
    from tests.unit.test_native_stock_dispatch import JOB, case

    with case() as (root, _store, launch):
        owner = start_synthetic_owner(root, JOB, fixture="native_loop", seconds=40, native=launch)
        assert _wait(owner, 50) == 0
        selectors = (
            "--profile-source", str(launch.source),
            "--profile-runtime", str(launch.stock_runtime),
            "--profile-mode", "resume",
        )  # fmt: skip
        body = _alpha(
            root, "research", "diagnostic", "native-result",
            "--data-dir", str(root), "--job-id", JOB, *selectors,
        )  # fmt: skip
        assert body["status"] == "completed"
        assert body["result"] == {"synthetic_score": -0.125, "unit": "fixture_only"}
        assert body["scientific_acceptance"] == "not_admitted"
        assert body["resume_allowed"] is False

        with web_server(
            root,
            ALPHA_DATA_DIR=str(root),
            ALPHA_NATIVE_RESULT_SOURCE=str(launch.source),
            ALPHA_NATIVE_RESULT_RUNTIME=str(launch.stock_runtime),
            ALPHA_NATIVE_RESULT_MODE="resume",
        ) as base:
            served = get_json(f"{base}/api/native-jobs/{JOB}/result")
            assert served["status"] == "completed"
            assert served["result"] == body["result"]
            assert served["scientific_acceptance"] == "not_admitted"
