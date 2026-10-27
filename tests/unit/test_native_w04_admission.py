"""Public synthetic ControlStore/native-loop integration; no scientific admission."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

if TYPE_CHECKING:
    from alpha_cli._native_loop_admission import NativeLaunch

from alpha_cli.control_store import ControlStore
from alpha_cli.native_supervisor import (
    Fixture,
    _open_lock,
    _Owner,
    start_synthetic_owner,
    synthetic_workspace,
)
from alpha_core import DataError
from tests.unit.test_native_fixture_lifecycle import _stop_test_owner
from tests.unit.test_research_control_store import (
    PROJECT_ID,
    START,
    _approved_native_d1,
    _native_d1_job,
    _project,
)

JOB = "4c657d82-fc1a-44d8-b49b-bfdcfe93c52c"


@pytest.mark.parametrize("fixture", ["success", "native_loop"])
def test_no_fixture_accepts_a_caller_defined_launch_object(
    case: tuple[Path, ControlStore], fixture: Fixture
) -> None:
    root, _ = case
    untrusted = cast("NativeLaunch", object())
    with _open_lock(root, JOB) as lock, pytest.raises(DataError, match="fixed launch identity"):
        _Owner(root, JOB, fixture, 10, lock, native=untrusted)
    with pytest.raises(DataError, match="fixed launch identity"):
        start_synthetic_owner(root, JOB, fixture=fixture, native=untrusted)


def test_unpinned_native_source_fails_closed_before_any_launch(tmp_path: Path) -> None:
    from alpha_cli._native_loop_admission import NativeLaunch, measure_native_proposal

    with pytest.raises(DataError, match="requires pinned source"):
        measure_native_proposal(tmp_path, "INCONCLUSIVE")
    package = tmp_path / "rdagent"
    package.mkdir()
    (package / "__init__.py").write_text("")
    with pytest.raises(DataError, match="source tree mismatch"):
        measure_native_proposal(tmp_path, "INCONCLUSIVE")
    with pytest.raises(DataError, match="source tree mismatch"):
        NativeLaunch(tmp_path, "INCONCLUSIVE")
    (package / "alias.py").symlink_to(package / "__init__.py")
    with pytest.raises(DataError, match="symlinks are unsupported"):
        measure_native_proposal(tmp_path, "INCONCLUSIVE")


def test_native_launch_rejects_mode_path_and_study_without_authority(tmp_path: Path) -> None:
    from alpha_cli._native_loop_admission import NativeLaunch

    with pytest.raises(DataError, match="invalid fixed native fixture source/mode"):
        NativeLaunch(tmp_path, "APPROVED")
    with pytest.raises(DataError, match="invalid fixed native fixture source/mode"):
        NativeLaunch(Path("relative-source"), "INCONCLUSIVE")
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path)
    with pytest.raises(DataError, match="invalid fixed native fixture source/mode"):
        NativeLaunch(alias, "INCONCLUSIVE")
    with pytest.raises(DataError, match="native scientific study blocked"):
        NativeLaunch(tmp_path, "INCONCLUSIVE", study=cast("Any", object()))


def test_rule_runtime_file_measurement_rejects_symlinks_and_bytecode(tmp_path: Path) -> None:
    from alpha_cli._native_rule_environment import _files

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "module.py").write_bytes(b"VALUE = 1\n")
    (tmp_path / "pkg" / "__pycache__").mkdir()
    (tmp_path / "pkg" / "__pycache__" / "module.cpython-312.pyc").write_bytes(b"\0")
    assert _files(tmp_path, source=True) == {
        "pkg/module.py": hashlib.sha256(b"VALUE = 1\n").hexdigest()
    }
    with pytest.raises(DataError, match="unqualified bytecode"):
        _files(tmp_path)
    root_alias = tmp_path.parent / f"{tmp_path.name}-alias"
    root_alias.symlink_to(tmp_path)
    with pytest.raises(DataError, match="root symlink is unsupported"):
        _files(root_alias)
    (tmp_path / "pkg" / "link.py").symlink_to(tmp_path / "pkg" / "module.py")
    with pytest.raises(DataError, match="package symlink is unsupported"):
        _files(tmp_path, source=True)


@pytest.fixture
def source() -> Path:
    configured = os.environ.get("ALPHA_RDAGENT_SOURCE")
    if not configured:
        pytest.skip("explicit pinned ALPHA_RDAGENT_SOURCE required")
    return Path(configured).resolve()


@pytest.fixture
def case() -> Iterator[tuple[Path, ControlStore]]:
    if sys.platform != "linux":
        pytest.skip("requires the Linux native owner profile")
    with synthetic_workspace() as root:
        store = ControlStore(root)
        _project(store)
        try:
            yield root, store
        finally:
            configured = os.environ.get("ALPHA_RDAGENT_RECEIPTS")
            if configured:
                destination = Path(tempfile.mkdtemp(prefix="w04-", dir=configured))
                for path in (root / f"payload-{JOB}").glob("*.json"):
                    shutil.copy2(path, destination / path.name)
                for path in (root / "control").glob("native-*.log"):
                    shutil.copy2(path, destination / path.name)


def test_native_claim_binds_actual_manifest_and_reserved_allowance(
    source: Path, case: tuple[Path, ControlStore]
) -> None:
    from alpha_cli._native_loop_admission import NativeLaunch

    root, store = case
    launch = NativeLaunch(source, "INCONCLUSIVE")
    contract, _ = _approved_native_d1(
        store, loop_steps=5, implementation_fingerprints=launch.implementation_fingerprints()
    )
    _, reservation = _native_d1_job(store, contract, job_id=JOB, manifest_sha256=launch.fingerprint)
    with _open_lock(root, JOB) as lock:
        owner = _Owner(root, JOB, "native_loop", 10, lock, native=launch)
        with pytest.raises(DataError, match="committed reservation"):
            owner.spawn()
        store.claim_native_fixture(JOB, owner)
        assert owner.native_admission is not None
        assert owner.native_admission["reservation_id"] == reservation["reservation_id"]
        assert owner.native_admission["loop_steps"] == 5
        assert owner.native_admission["manifest_sha256"] == launch.fingerprint
        assert not (root / f"payload-{JOB}").exists()


def test_native_claim_rejects_unverified_manifest_identity(
    source: Path, case: tuple[Path, ControlStore]
) -> None:
    from alpha_cli._native_loop_admission import NativeLaunch

    root, store = case
    contract, _ = _approved_native_d1(store, loop_steps=5)
    _native_d1_job(store, contract, job_id=JOB)
    with _open_lock(root, JOB) as lock:
        owner = _Owner(root, JOB, "native_loop", 10, lock, native=NativeLaunch(source, "INVALID"))
        with pytest.raises(DataError, match="manifest"):
            store.claim_native_fixture(JOB, owner)
        assert owner.native_admission is None
        assert store.native_fixture_status(JOB)["state"] == "unclaimed"


def _admit(
    source: Path,
    store: ControlStore,
    mode: str,
    *,
    steps: int = 5,
    variants: int = 128,
) -> tuple[NativeLaunch, dict[str, object]]:
    from alpha_cli._native_loop_admission import NativeLaunch

    launch = NativeLaunch(source, mode)
    contract, _ = _approved_native_d1(
        store,
        loop_steps=steps,
        variants=variants,
        implementation_fingerprints=launch.implementation_fingerprints(),
    )
    _, reservation = _native_d1_job(store, contract, job_id=JOB, manifest_sha256=launch.fingerprint)
    return launch, reservation


@pytest.mark.parametrize("mode", ["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID", "resume"])
def test_real_native_child_preserves_mapping_and_admitted_checkpoint(
    source: Path, case: tuple[Path, ControlStore], mode: str
) -> None:
    root, store = case
    launch, reservation = _admit(source, store, mode)
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    process = start_synthetic_owner(root, JOB, fixture="native_loop", native=launch, seconds=10)
    assert process.wait(timeout=15) == 0
    status = store.native_fixture_status(JOB, reconnect=True)
    assert status["state"] == "pending_scientific_admission", status
    receipt = json.loads((root / f"payload-{JOB}" / "receipt.json").read_text())
    assert receipt["admission"]["reservation_id"] == reservation["reservation_id"]
    assert receipt["admission"]["spec_sha256"] == reservation["config_fingerprint"]
    assert receipt["admission"]["manifest_sha256"] == launch.fingerprint
    assert receipt["checks"]["label"] == ("INCONCLUSIVE" if mode == "resume" else mode)
    assert receipt["checks"]["metrics"] == [
        ["net_return", -0.125, "fraction"],
        ["cost", 0.03125, "fraction"],
    ]
    assert receipt["scientific_acceptance"] == "not_admitted"
    assert receipt["checkpoint_binding_verified"] and receipt["duplicate_resume_rejected"]
    if mode == "resume":
        assert receipt["concurrent_resume_rejected"]
    assert store.get_job(JOB)["status"] == "running"
    assert store.heavyweight_job_capacity()["active_count"] == 1
    assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
    assert store.research_case_summary(PROJECT_ID)["terminal_attempt_count"] == 1
    with pytest.raises(DataError, match="reconnect only"):
        start_synthetic_owner(root, JOB, fixture="native_loop", native=launch)
    with pytest.raises(ProcessLookupError):
        os.killpg(int((root / f"payload-{JOB}" / "payload.pid").read_text()), 0)


def test_real_native_worker_runs_under_a_non_default_temp_root(
    source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires the Linux native owner profile")
    # Short and non-default: the owner's AF_UNIX control path must stay under the OS limit.
    temp = Path(tempfile.mkdtemp(prefix="t", dir="/tmp")).resolve()
    try:
        monkeypatch.setenv("TMPDIR", str(temp))
        monkeypatch.setattr(tempfile, "tempdir", None)
        with synthetic_workspace() as root:
            assert root.parent == temp
            store = ControlStore(root)
            _project(store)
            launch, reservation = _admit(source, store, "INCONCLUSIVE")
            process = start_synthetic_owner(
                root, JOB, fixture="native_loop", native=launch, seconds=10
            )
            try:
                assert process.wait(timeout=15) == 0
                status = store.native_fixture_status(JOB, reconnect=True)
                assert status["state"] == "pending_scientific_admission", status
                receipt = json.loads((root / f"payload-{JOB}" / "receipt.json").read_text())
                assert receipt["admission"]["reservation_id"] == reservation["reservation_id"]
                assert receipt["scientific_acceptance"] == "not_admitted"
            finally:
                if process.poll() is None:
                    _stop_test_owner(root, process)
    finally:
        temp.rmdir()


def test_admitted_worker_rejects_a_workspace_outside_its_temp_root(
    source: Path, tmp_path: Path
) -> None:
    from alpha_cli._native_loop_admission import WORKER

    if not (WORKER / ".venv/bin/python").is_file():
        pytest.skip("requires the locked workers/rdagent environment")
    payload = tmp_path / "alpha-native-fixture-outside" / f"payload-{JOB}"
    payload.mkdir(parents=True)
    (payload.parent / "synthetic-only").write_text("ALPHA synthetic native lifecycle v1\n")
    completed = subprocess.run(
        [
            str(WORKER / ".venv/bin/python"),
            "-I",
            str(WORKER / "fixture_entry.py"),
            str(source),
            "admitted",
            "{}",
        ],
        cwd=payload,
        env={"PATH": os.defpath, "LANG": "C.UTF-8", "TMPDIR": "/tmp"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode != 0
    assert "admitted probe requires its synthetic owner workspace" in completed.stderr
    assert list(payload.iterdir()) == []


def test_zero_variant_envelope_rejects_even_with_native_steps(
    source: Path, case: tuple[Path, ControlStore]
) -> None:
    from alpha_cli._native_loop_admission import NativeLaunch

    root, store = case
    launch = NativeLaunch(source, "SUPPORTED")
    contract, _ = _approved_native_d1(
        store,
        loop_steps=5,
        variants=6,
        implementation_fingerprints=launch.implementation_fingerprints(),
    )
    store.record_research_attempt(
        PROJECT_ID,
        contract,
        kind="d1-deep-research",
        status="failed",
        config_fingerprint="synthetic-previous-variant-allocation",
        budget_used={"variants": 5},
        details={"evidence_zone": "D1"},
        error="fixed synthetic predecessor failure",
        at=START + timedelta(minutes=9, seconds=1),
    )
    _, reservation = _native_d1_job(
        store,
        contract,
        job_id=JOB,
        attempt_number=2,
        manifest_sha256=launch.fingerprint,
    )
    budget = reservation["budget_reserved"]
    assert isinstance(budget, dict)
    assert budget["variants"] == 0 and budget["rdagent_native_v1_loop_steps"] == 5
    with _open_lock(root, JOB) as lock:
        owner = _Owner(root, JOB, "native_loop", 10, lock, native=launch)
        with pytest.raises(DataError, match="one reserved variant"):
            store.claim_native_fixture(JOB, owner)
        assert owner.native_admission is None and owner.process is None
        assert store.native_fixture_status(JOB)["state"] == "unclaimed"


def test_matching_manifest_cannot_override_approved_implementation(
    source: Path, case: tuple[Path, ControlStore]
) -> None:
    from alpha_cli._native_loop_admission import NativeLaunch

    root, store = case
    launch = NativeLaunch(source, "SUPPORTED")
    contract, _ = _approved_native_d1(store, loop_steps=5)
    _native_d1_job(store, contract, job_id=JOB, manifest_sha256=launch.fingerprint)
    with _open_lock(root, JOB) as lock:
        owner = _Owner(root, JOB, "native_loop", 10, lock, native=launch)
        with pytest.raises(DataError, match="approved implementation"):
            store.claim_native_fixture(JOB, owner)
        assert owner.native_admission is None


def test_native_child_requires_positive_reserved_cpu(
    source: Path, case: tuple[Path, ControlStore]
) -> None:
    from alpha_cli._native_loop_admission import NativeLaunch

    root, store = case
    launch = NativeLaunch(source, "SUPPORTED")
    contract, _ = _approved_native_d1(
        store,
        loop_steps=5,
        cpu_milliseconds=0,
        implementation_fingerprints=launch.implementation_fingerprints(),
    )
    _, reservation = _native_d1_job(
        store,
        contract,
        job_id=JOB,
        manifest_sha256=launch.fingerprint,
    )
    assert (
        cast(dict[str, object], reservation["budget_reserved"])[
            "rdagent_native_v1_cpu_milliseconds"
        ]
        == 0
    )
    with _open_lock(root, JOB) as lock:
        owner = _Owner(root, JOB, "native_loop", 10, lock, native=launch)
        with pytest.raises(DataError, match="positive reserved CPU"):
            store.claim_native_fixture(JOB, owner)
        assert owner.native_admission is None and owner.process is None


@pytest.mark.parametrize("defect", ["missing", "label", "binding", "cleanup", "publication"])
def test_actual_child_uncertainty_retains_capacity_and_full_charge(
    source: Path,
    case: tuple[Path, ControlStore],
    defect: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, store = case
    launch, _ = _admit(source, store, "SUPPORTED")
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    with _open_lock(root, JOB) as lock:
        owner = _Owner(root, JOB, "native_loop", 10, lock, native=launch)
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())
        try:
            deadline = time.monotonic() + 8
            while owner.observe_exit() is None:
                assert time.monotonic() < deadline
                time.sleep(0.02)
            path = root / f"payload-{JOB}" / "receipt.json"
            if defect == "missing":
                path.unlink()
            elif defect in {"label", "binding"}:
                result = json.loads(path.read_text())
                if defect == "label":
                    result["checks"]["label"] = "CONTRADICTED"
                else:
                    result["admission"]["reservation_id"] = "foreign"
                path.write_text(json.dumps(result))
            if defect == "cleanup":
                with monkeypatch.context() as scoped:

                    def uncertain() -> None:
                        raise DataError("injected unknown cleanup")

                    scoped.setattr(owner, "_cleanup_once", uncertain)
                    observation = owner.finish("exit")
            else:
                observation = owner.finish("exit")
            if defect == "publication":
                # Actual process was reaped, but publication is deliberately rolled back.
                from alpha_cli import _native_fixture_store as native_store

                original = native_store._append
                with monkeypatch.context() as scoped:

                    def interrupted(*args: object, **kwargs: object) -> None:
                        original(*args, **kwargs)  # type: ignore[arg-type]
                        raise RuntimeError("injected publication failure")

                    scoped.setattr(native_store, "_append", interrupted)
                    with pytest.raises(RuntimeError, match="publication failure"):
                        store.record_native_fixture_observation(JOB, observation)
            else:
                store.record_native_fixture_observation(JOB, observation)
        finally:
            owner._cleanup_once()
    assert store.native_fixture_status(JOB, reconnect=True)["state"] == "quarantined"
    assert store.get_job(JOB)["status"] == "running"
    assert store.heavyweight_job_capacity()["active_count"] == 1
    assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before


def test_rolled_back_claim_never_grants_native_spawn(
    source: Path, case: tuple[Path, ControlStore], monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import _native_fixture_store as native_store

    root, store = case
    launch, _ = _admit(source, store, "SUPPORTED")
    with _open_lock(root, JOB) as lock:
        owner = _Owner(root, JOB, "native_loop", 10, lock, native=launch)
        original = native_store._append

        def interrupted(*args: object, **kwargs: object) -> None:
            original(*args, **kwargs)  # type: ignore[arg-type]
            raise RuntimeError("injected claim rollback")

        monkeypatch.setattr(native_store, "_append", interrupted)
        with pytest.raises(RuntimeError, match="claim rollback"):
            store.claim_native_fixture(JOB, owner)
        with pytest.raises(DataError, match="committed reservation"):
            owner.spawn()
        assert store.native_fixture_status(JOB)["state"] == "unclaimed"


@pytest.mark.parametrize(
    "mode,steps,charged,completed",
    [
        ("INCONCLUSIVE", 0, 0, 0),
        ("INCONCLUSIVE", 2, 2, 2),
        ("failure", 5, 3, 2),
        ("foreign_binding", 5, 2, 2),
    ],
)
def test_actual_native_failure_and_preeffect_exhaustion_keep_full_reservation(
    source: Path,
    case: tuple[Path, ControlStore],
    mode: str,
    steps: int,
    charged: int,
    completed: int,
) -> None:
    root, store = case
    launch, _ = _admit(source, store, mode, steps=steps)
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    process = start_synthetic_owner(root, JOB, fixture="native_loop", native=launch, seconds=10)
    assert process.wait(timeout=15) == 0
    status = store.native_fixture_status(JOB)
    assert status["state"] == "closed", status
    assert store.get_job(JOB)["status"] == "failed"
    progress = json.loads((root / f"payload-{JOB}" / "progress.json").read_text())
    assert len(progress["charged_stages"]) == charged
    assert len(progress["completed_stages"]) == completed
    assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
    assert store.research_case_summary(PROJECT_ID)["unfinalized_launch_count"] == 0
    assert store.heavyweight_job_capacity()["active_count"] == 0


def test_actual_native_cancel_reaps_worker_and_reconciles_once(
    source: Path, case: tuple[Path, ControlStore]
) -> None:
    root, store = case
    launch, _ = _admit(source, store, "wait")
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    process = start_synthetic_owner(root, JOB, fixture="native_loop", native=launch, seconds=10)
    deadline = time.monotonic() + 8
    while not (root / f"payload-{JOB}" / "running.ready").exists():
        assert time.monotonic() < deadline, (root / "control" / f"native-{JOB}.log").read_text()
        time.sleep(0.02)
    store.cancel_native_fixture(JOB, reason="fixed native checkpoint cancellation")
    assert process.wait(timeout=5) == 0
    assert store.get_job(JOB)["status"] == "cancelled"
    assert store.cancel_native_fixture(JOB, reason="repeat")["state"] == "closed"
    assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
    assert store.research_case_summary(PROJECT_ID)["terminal_attempt_count"] == 2
    with pytest.raises(ProcessLookupError):
        os.killpg(int((root / f"payload-{JOB}" / "payload.pid").read_text()), 0)
