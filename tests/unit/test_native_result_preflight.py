"""Server-owned native-result deployment settings and profile preflight on synthetic assets.

The read-only CLI child is the only seam replaced (by its JSON response); the deployment
settings, the asset preflight and the response contract run as production code.
"""

from __future__ import annotations

import signal
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from alpha_cli.native_supervisor import synthetic_workspace
from alpha_core import DataError
from alpha_web._native_results import (
    NativeResultDeployment,
    ServerNativeProfile,
    _profile_preflight,
    _read_cli,
    native_result_deployment,
    read_native_result,
    unavailable,
)

JOB = "00000000-0000-4000-8000-000000000001"
OTHER_JOB = "00000000-0000-4000-8000-000000000002"


@pytest.fixture
def deployment(tmp_path: Path) -> Iterator[NativeResultDeployment]:
    base = tmp_path.resolve()
    source, runtime = base / "source", base / "runtime"
    (source / "rdagent" / "core").mkdir(parents=True)
    (source / "rdagent" / "__init__.py").write_text("# synthetic\n")
    (source / "rdagent" / "core" / "loop.py").write_text("class LoopBase: ...\n")
    (runtime / "venv" / "bin").mkdir(parents=True)
    (runtime / "venv" / "bin" / "python").write_bytes(b"synthetic metadata; never executed")
    (runtime / "venv" / "pyvenv.cfg").write_text("synthetic fixture only")
    (runtime / "dependencies.lock.txt").write_text("public fixture")
    with synthetic_workspace() as root:
        yield NativeResultDeployment(root, ServerNativeProfile(source, runtime, "resume"))


def _response(job_id: str, status: str = "invalid") -> dict[str, object]:
    return {
        "schema": "NativeStockOperatorResultV1",
        "operation": "recover_native_stock_result",
        "classification": "synthetic_only_unqualified",
        "status": status,
        "reason": "advisory_progress_validation_failed",
        "dispatch": {
            "job_id": job_id,
            "reservation_id": "reservation",
            "owner_id": "owner",
            "spec_sha256": "a" * 64,
            "profile_sha256": "b" * 64,
        },
        "provenance": None,
        "resume_allowed": False,
        "scientific_acceptance": "not_admitted",
    }


# --- deployment settings ---------------------------------------------------------------------


def test_deployment_requires_all_three_server_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("SOURCE", "RUNTIME", "MODE"):
        monkeypatch.delenv(f"ALPHA_NATIVE_RESULT_{name}", raising=False)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "data"))
    assert native_result_deployment() is None
    monkeypatch.setenv("ALPHA_NATIVE_RESULT_SOURCE", str(tmp_path / "source"))
    monkeypatch.setenv("ALPHA_NATIVE_RESULT_RUNTIME", str(tmp_path / "runtime"))
    assert native_result_deployment() is None
    monkeypatch.setenv("ALPHA_NATIVE_RESULT_MODE", "cancel")
    configured = native_result_deployment()
    assert configured == NativeResultDeployment(
        tmp_path / "data",
        ServerNativeProfile(tmp_path / "source", tmp_path / "runtime", "cancel"),
    )


def test_deployment_with_an_unsupported_mode_is_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALPHA_NATIVE_RESULT_SOURCE", str(tmp_path / "source"))
    monkeypatch.setenv("ALPHA_NATIVE_RESULT_RUNTIME", str(tmp_path / "runtime"))
    monkeypatch.setenv("ALPHA_NATIVE_RESULT_MODE", "SUPPORTED")
    assert native_result_deployment() is None


def test_unavailable_never_grants_resume_or_admission() -> None:
    body = unavailable("reason_code")
    assert body["status"] == "unavailable"
    assert body["reason"] == "reason_code"
    assert body["resume_allowed"] is False
    assert body["scientific_acceptance"] == "not_admitted"


# --- profile preflight -----------------------------------------------------------------------


def test_preflight_accepts_bounded_public_assets_and_a_python_link(
    deployment: NativeResultDeployment,
) -> None:
    _profile_preflight(deployment)
    python = deployment.profile.runtime / "venv" / "bin" / "python"
    real = deployment.profile.runtime / "venv" / "bin" / "python3.12"
    python.rename(real)
    python.symlink_to(real)
    _profile_preflight(deployment)


def test_preflight_refuses_a_non_synthetic_root(
    deployment: NativeResultDeployment, tmp_path: Path
) -> None:
    elsewhere = NativeResultDeployment(tmp_path, deployment.profile)
    with pytest.raises(DataError, match="not a synthetic fixture"):
        _profile_preflight(elsewhere)
    (deployment.root / "daily-rule-workspace.json").write_text("{}")
    with pytest.raises(DataError, match="synthetic-only"):
        _profile_preflight(deployment)


@pytest.mark.parametrize("name", [".env", ".env.local", "credentials", "auth.json"])
def test_preflight_refuses_credential_shaped_source_files(
    deployment: NativeResultDeployment, name: str
) -> None:
    (deployment.profile.source / "rdagent" / "core" / name).write_text("not profile material")
    with pytest.raises(DataError, match="not public profile material"):
        _profile_preflight(deployment)


def test_preflight_refuses_credential_directories_in_the_profile(
    deployment: NativeResultDeployment,
) -> None:
    hidden = deployment.profile.source.parent / ".ssh" / "source"
    hidden.parent.mkdir()
    deployment.profile.source.rename(hidden)
    moved = NativeResultDeployment(
        deployment.root, ServerNativeProfile(hidden, deployment.profile.runtime, "resume")
    )
    with pytest.raises(DataError, match="not public profile material"):
        _profile_preflight(moved)


def test_preflight_refuses_missing_or_linked_profile_directories(
    deployment: NativeResultDeployment,
) -> None:
    profile = deployment.profile
    missing = NativeResultDeployment(
        deployment.root, ServerNativeProfile(profile.source / "absent", profile.runtime, "resume")
    )
    with pytest.raises(DataError, match="directory is unavailable"):
        _profile_preflight(missing)
    (profile.runtime / "venv" / "bin" / "python").unlink()
    (profile.runtime / "venv" / "bin").rmdir()
    (profile.runtime / "bin").mkdir()
    (profile.runtime / "venv" / "bin").symlink_to(profile.runtime / "bin")
    with pytest.raises(DataError, match="directory is unavailable"):
        _profile_preflight(deployment)


def test_preflight_refuses_source_symlinks_and_linked_assets(
    deployment: NativeResultDeployment,
) -> None:
    profile = deployment.profile
    link = profile.source / "rdagent" / "core" / "alias.py"
    link.symlink_to(profile.source / "rdagent" / "core" / "loop.py")
    with pytest.raises(DataError, match="source scan exceeds safe bounds"):
        _profile_preflight(deployment)
    link.unlink()
    lock = profile.runtime / "dependencies.lock.txt"
    real = profile.runtime / "real.lock.txt"
    lock.rename(real)
    lock.symlink_to(real)
    with pytest.raises(DataError, match="asset symlink is unsupported"):
        _profile_preflight(deployment)


def test_preflight_bounds_the_number_of_source_files(
    deployment: NativeResultDeployment,
) -> None:
    bulk = deployment.profile.source / "rdagent" / "bulk"
    bulk.mkdir()
    for index in range(2_047):
        (bulk / f"m{index}.py").write_bytes(b"")
    # Two files already exist: 2,049 regular files exceed the 2,048 file bound.
    with pytest.raises(DataError, match="source bytes exceed read bounds"):
        _profile_preflight(deployment)
    (bulk / "m0.py").unlink()
    _profile_preflight(deployment)


# --- reading the server-selected job ---------------------------------------------------------


def test_reader_returns_the_validated_response_for_the_selected_job(
    deployment: NativeResultDeployment,
) -> None:
    with patch("alpha_web._native_results._read_cli", return_value=_response(JOB)) as child:
        body = read_native_result(deployment, JOB)
    assert body["status"] == "invalid"
    assert body["dispatch"] == _response(JOB)["dispatch"]
    assert "provenance" not in body  # None fields are not projected.
    assert body["resume_allowed"] is False
    args, root = child.call_args.args
    assert root == deployment.root
    assert args[:3] == ["research", "diagnostic", "native-result"]
    assert args[args.index("--job-id") + 1] == JOB
    assert args[args.index("--profile-mode") + 1] == "resume"
    assert args[args.index("--profile-source") + 1] == str(deployment.profile.source)


def test_reader_refuses_a_response_for_another_job(deployment: NativeResultDeployment) -> None:
    with patch("alpha_web._native_results._read_cli", return_value=_response(OTHER_JOB)):
        body = read_native_result(deployment, JOB)
    assert body == unavailable("native_result_evidence_unavailable_or_invalid")


def test_reader_refuses_a_failed_preflight_before_any_child(
    deployment: NativeResultDeployment,
) -> None:
    (deployment.profile.runtime / "venv" / "pyvenv.cfg").unlink()
    with patch("alpha_web._native_results._read_cli") as child:
        body = read_native_result(deployment, JOB)
    assert body["status"] == "unavailable"
    child.assert_not_called()


def test_child_read_requires_the_default_sigchld_disposition(tmp_path: Path) -> None:
    previous = signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    try:
        with patch("alpha_web._native_results.subprocess.Popen") as spawn:
            with pytest.raises(DataError, match="retained Linux child ownership"):
                _read_cli(["research", "diagnostic", "native-result"], tmp_path)
            spawn.assert_not_called()
    finally:
        signal.signal(signal.SIGCHLD, previous)
    assert signal.getsignal(signal.SIGCHLD) == previous
