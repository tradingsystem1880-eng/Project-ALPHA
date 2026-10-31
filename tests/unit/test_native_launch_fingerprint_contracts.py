"""Portable checksum/admission contracts, never pinned-runtime or process acceptance.

The tiny source/runtime bytes deliberately are not executable. Replacing the expected
source pin and external profile observation gives the checksum code ordinary test
inputs; no container, native continuation, or research effect is claimed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from alpha_cli import _native_daily_rule_container as containers
from alpha_cli import _native_loop_admission as admission
from alpha_cli import _native_rule_environment as environment
from alpha_core import DataError
from tests.unit.test_native_daily_rule_study import _study


def _checksum(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.fixture
def checksum_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    source, worker = tmp_path / "source", tmp_path / "worker"
    (tmp_path / "query").mkdir()
    package = source / "rdagent"
    package.mkdir(parents=True)
    source_bytes = b"# artificial checksum input, never imported\n"
    (package / "__init__.py").write_bytes(source_bytes)
    monkeypatch.setattr(
        admission,
        "SOURCE_SHA256",
        _checksum({"rdagent/__init__.py": hashlib.sha256(source_bytes).hexdigest()}),
    )
    worker.mkdir()
    for name in {
        *admission.WORKER_FILES,
        *environment.RULE_FILES,
        *environment.COSTED_FILES,
        "daily_container_entry.py",
    }:
        (worker / name).write_text("artificial checksum bytes for " + name)
    for runtime in (".venv", ".venv-rule-qualified", ".venv-economics-qualified"):
        directory = worker / runtime
        (directory / "bin").mkdir(parents=True)
        (directory / "bin/python").write_bytes(b"not an executable runtime")
        (directory / "pyvenv.cfg").write_text("artificial checksum configuration")
    monkeypatch.setattr(admission, "WORKER", worker)
    monkeypatch.setattr(environment, "WORKER", worker)
    monkeypatch.setattr(environment, "measure_rule_environment", lambda costed=False: "a" * 64)
    monkeypatch.setattr(
        containers,
        "daily_container_profile",
        lambda: {"schema": "DailyRuleContainerProfileV1", "image_id": "sha256:" + "c" * 64},
    )
    return source, worker


@pytest.mark.parametrize("changed", ["python", "configuration", "worker", "lock"])
def test_existing_launch_rejects_execution_identity_drift_before_command(
    checksum_tree: tuple[Path, Path], changed: str
) -> None:
    source, worker = checksum_tree
    launch = admission.NativeLaunch(source, "SUPPORTED")
    fingerprints = launch.implementation_fingerprints()
    assert fingerprints["data"] is None
    assert len(str(fingerprints["environment"])) == 64
    command = launch.command({"reservation_id": "artificial-contract-only"})
    assert command[:2] == [str(worker / ".venv/bin/python"), "-I"]
    target = {
        "python": worker / ".venv/bin/python",
        "configuration": worker / ".venv/pyvenv.cfg",
        "worker": worker / "admitted_probe.py",
        "lock": worker / "uv.lock",
    }[changed]
    target.write_bytes(target.read_bytes() + b"\nchanged after reservation")
    with pytest.raises(DataError, match="bytes changed after admission"):
        launch.command({"reservation_id": "artificial-contract-only"})


def test_command_requires_reservation_even_for_checksum_only_fixture(
    checksum_tree: tuple[Path, Path],
) -> None:
    launch = admission.NativeLaunch(checksum_tree[0], "SUPPORTED")
    with pytest.raises(DataError, match="committed reservation"):
        launch.command(None)


@pytest.mark.parametrize("changed", ["source_bytes", "source_link", "worker_link"])
def test_checksum_measurement_refuses_changed_pin_or_symlinked_inputs(
    checksum_tree: tuple[Path, Path], tmp_path: Path, changed: str
) -> None:
    source, worker = checksum_tree
    if changed == "source_bytes":
        (source / "rdagent/__init__.py").write_text("a different source tree")
        expected = "source tree mismatch"
    elif changed == "source_link":
        (source / "rdagent/alias.py").symlink_to(source / "rdagent/__init__.py")
        expected = "source symlinks"
    else:
        original = worker / "admitted_probe.py"
        replacement = tmp_path / "replacement.py"
        replacement.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(replacement)
        expected = "worker source must not be a symlink"
    with pytest.raises(DataError, match=expected):
        admission.measure_native_proposal(source, "SUPPORTED")


def test_daily_proposal_binds_query_profile_and_controller_watchdog_bytes(
    checksum_tree: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, worker = checksum_tree
    study = _study(tmp_path / "query")
    original = admission.measure_native_proposal(source, "INCONCLUSIVE", study)
    assert original == admission.measure_native_proposal(source, "INCONCLUSIVE", study)
    changed_study = study.model_copy(update={"runtime_profile_sha256": "d" * 64})
    assert admission.measure_native_proposal(source, "INCONCLUSIVE", changed_study) != original
    watchdog = worker / "daily_container_entry.py"
    watchdog.write_bytes(watchdog.read_bytes() + b"\nchanged watchdog")
    assert admission.measure_native_proposal(source, "INCONCLUSIVE", study) != original
    watchdog.write_text("artificial checksum bytes for daily_container_entry.py")
    assert admission.measure_native_proposal(source, "INCONCLUSIVE", study) == original
    guard = Path(environment.__file__).with_name("_native_daily_rule_restore.py")
    read_bytes = Path.read_bytes

    def changed_guard(path: Path) -> bytes:
        raw = read_bytes(path)
        return raw + b"\nchanged approved guard" if path == guard else raw

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", changed_guard)
        assert admission.measure_native_proposal(source, "INCONCLUSIVE", study) != original
    assert admission.measure_native_proposal(source, "INCONCLUSIVE", study) == original


def test_daily_proposal_refuses_image_replacement_and_linked_costed_helper(
    checksum_tree: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, worker = checksum_tree
    study = _study(tmp_path / "query")
    with monkeypatch.context() as patch:
        patch.setattr(
            containers,
            "daily_container_profile",
            lambda: {"schema": "DailyRuleContainerProfileV1", "image_id": "sha256:" + "d" * 64},
        )
        with pytest.raises(DataError, match="image differs from exact owner-approved"):
            admission.measure_native_proposal(source, "INCONCLUSIVE", study)
    helper = worker / "install_rule_profile.py"
    replacement = worker / "equivalent-bytes.py"
    replacement.write_bytes(helper.read_bytes())
    helper.unlink()
    helper.symlink_to(replacement)
    with pytest.raises(DataError, match="rule worker source symlink"):
        admission.measure_native_proposal(source, "INCONCLUSIVE", study)


@pytest.mark.parametrize("target", ["controller", "watchdog"])
def test_daily_code_identity_refuses_symlinked_approval_guards(
    checksum_tree: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    _, worker = checksum_tree
    study = _study(tmp_path / "query")
    selected = (
        Path(environment.__file__).with_name("_native_daily_rule_restore.py")
        if target == "controller"
        else worker / "daily_container_entry.py"
    )
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == selected or original(path))
    with pytest.raises(DataError, match="daily approval (guard|watchdog) source symlink"):
        environment.rule_implementation_fingerprints(True, daily_study=study)
