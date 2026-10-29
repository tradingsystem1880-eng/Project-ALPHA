"""Explicit public probes of actual pinned RD-Agent in its isolated worker runtime."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import marshal
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "workers" / "rdagent"


@pytest.fixture
def source() -> Path:
    configured = os.environ.get("ALPHA_RDAGENT_SOURCE")
    if not configured:
        pytest.skip("explicit pinned ALPHA_RDAGENT_SOURCE required for native conformance")
    path = Path(configured).resolve()
    assert (WORKER / ".venv/bin/python").is_file(), "sync the isolated worker --locked first"
    assert path.is_dir(), "pinned RD-Agent source is unavailable"
    return path


def _run(
    source: Path, mode: str, *, worker: Path = WORKER
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="alpha-rdagent-conformance-") as directory:
        root = Path(directory)
        completed = subprocess.run(
            [
                str(WORKER / ".venv/bin/python"),
                "-I",
                str(worker / "fixture_entry.py"),
                str(source),
                mode,
            ],
            cwd=root,
            env={"HOME": directory, "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        receipt = root / "receipt.json"
        result = json.loads(receipt.read_text()) if receipt.exists() else {}
        destination = os.environ.get("ALPHA_RDAGENT_RECEIPTS")
        if destination:
            target = Path(destination)
            target.mkdir(parents=True, exist_ok=True)
            # Unique receipt files preserve failures across reruns.
            with tempfile.NamedTemporaryFile(
                mode="w", prefix=f"{mode}-", suffix=".json", dir=target, delete=False
            ) as output:
                json.dump(
                    {
                        "returncode": completed.returncode,
                        "receipt": result,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    },
                    output,
                    indent=2,
                )
        if completed.returncode == 0:
            # Every successful probe, including continuation-only probes, proves real imports.
            imported = result["imported_source_sha256"]
            for relative in (
                "rdagent/utils/workflow/loop.py",
                "rdagent/core/experiment.py",
                "rdagent/core/proposal.py",
                "rdagent/core/serialization.py",
            ):
                assert (
                    imported[relative]
                    == hashlib.sha256((source / relative).read_bytes()).hexdigest()
                )
            for name in ("source_pin", "conformance", "native_fixture", "fixture_owner"):
                assert (
                    result["imported_worker_sha256"][name]
                    == hashlib.sha256((worker / f"{name}.py").read_bytes()).hexdigest()
                )
        return completed, result


@pytest.mark.parametrize("label", ["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"])
def test_actual_native_stage_contracts_and_feedback_fidelity(source: Path, label: str) -> None:
    completed, result = _run(source, label)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["checks"]["label"] == label
    assert result["checks"]["metrics"] == [
        ["net_return", -0.125, "fraction"],
        ["cost", 0.03125, "fraction"],
    ]
    assert result["checks"]["native_roundtrip"] is True
    assert result["authority"] == "none" and result["routes_enabled"] is False
    pin = result["source_pin"]
    assert pin["expected"]["commit"] == "484776c211e4fbbeef03e0ec00d6bbee7362a4f4"
    assert pin["verified"] == {"source_tree_sha256": result["source_tree_sha256"]}
    assert result["source_tree_sha256"] == pin["expected"]["source_tree_sha256"]
    # The archive checksum is a pinned expectation, never reported as an observed measurement.
    assert pin["not_verified"] == ["commit", "archive_sha256"]
    assert "archive_sha256" not in pin["verified"] and "archive_sha256" not in result
    assert "upstream_commit" not in result
    assert result["loop_source_sha256"] == (
        "3850f9c32e81413f6e9fb39f239204554dceae9375ecdeffe57f0509dfa6c5a4"
    )
    assert "rdagent/core/serialization.py" in result["imported_source_sha256"]
    assert "rdagent/components/workflow/rd_loop.py" not in result["imported_source_sha256"]
    assert "rdagent/oai/llm_utils.py" not in result["imported_source_sha256"]


@pytest.mark.parametrize(
    "mode",
    [
        "resume",
        "cancel",
        "tamper",
        "zero_allowance",
        "partial_allowance",
        "unguarded",
        "post_effect_step_n",
    ],
)
def test_actual_native_continuation_and_effect_bounds(source: Path, mode: str) -> None:
    completed, result = _run(source, mode)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["mode"] == mode and result["scheduler"] == "upstream LoopBase.run"


def test_upstream_closure_drift_rejected_before_import(source: Path, tmp_path: Path) -> None:
    altered = tmp_path / "altered"
    shutil.copytree(
        source / "rdagent", altered / "rdagent", ignore=shutil.ignore_patterns("__pycache__")
    )
    # A transitive settings import is pinned too; no entry-file-only verification.
    dependency = altered / "rdagent" / "oai" / "llm_conf.py"
    dependency.write_text(dependency.read_text() + "\nraise RuntimeError('MUST NOT IMPORT')\n")
    completed, result = _run(altered, "resume")
    assert completed.returncode != 0 and not result
    assert "pinned RD-Agent source tree mismatch" in completed.stderr
    assert "MUST NOT IMPORT" not in completed.stderr


@pytest.mark.parametrize(
    "shadow",
    [
        "conformance.py",
        "native_fixture.py",
        "fixture_owner.py",
        "source_pin.py",
        "loguru.py",
        "loguru/__init__.py",
        "rdagent.py",
    ],
)
def test_source_root_shadows_rejected_before_execution(
    source: Path, tmp_path: Path, shadow: str
) -> None:
    altered = tmp_path / "shadow-source"
    shutil.copytree(
        source / "rdagent", altered / "rdagent", ignore=shutil.ignore_patterns("__pycache__")
    )
    sentinel = altered / shadow
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("raise RuntimeError('UNPINNED_SHADOW_EXECUTED')\n")
    completed, result = _run(altered, "resume")
    assert completed.returncode != 0 and not result
    assert "unpinned source-root import shadow" in completed.stderr
    assert "UNPINNED_SHADOW_EXECUTED" not in completed.stderr


def test_bootstrap_ignores_existing_worker_bytecode(source: Path, tmp_path: Path) -> None:
    worker = tmp_path / "worker"
    worker.mkdir()
    for path in WORKER.glob("*.py"):
        shutil.copy2(path, worker / path.name)
    bootstrap = worker / "source_pin.py"
    stat = bootstrap.stat()
    cache = Path(importlib.util.cache_from_source(str(bootstrap)))
    cache.parent.mkdir()
    # Fixed raise-only sentinel in an otherwise valid timestamp/size cache header.
    code = compile("raise RuntimeError('UNPINNED_BOOTSTRAP_BYTECODE')", str(bootstrap), "exec")
    cache.write_bytes(
        importlib.util.MAGIC_NUMBER
        + struct.pack("<III", 0, int(stat.st_mtime), stat.st_size)
        + marshal.dumps(code)
    )
    completed, result = _run(source, "zero_allowance", worker=worker)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["checks"]["effects"] == 0
    assert "UNPINNED_BOOTSTRAP_BYTECODE" not in completed.stderr
