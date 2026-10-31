"""Artificial Docker responses test qualification control flow; no daemon acceptance claims."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from alpha_core import DataError

IMAGE = "sha256:" + "a" * 64
CID = "c" * 64


class FakeDocker:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.arguments: list[str] = []
        self.exists = False
        self.exit_code = 0
        self.fail_smoke = False
        self.wrong_policy = False
        self.installed = True
        self.daemon = True
        self.timeout_smoke = False
        self.removal_failed = False

    def __call__(
        self, arguments: list[str], *, timeout: float = 10
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(arguments)
        if arguments[0] == "info":
            return subprocess.CompletedProcess(arguments, 0 if self.daemon else 1, b"linux\n", b"")
        if arguments[:2] == ["image", "inspect"]:
            return subprocess.CompletedProcess(
                arguments, 0 if self.installed else 1, IMAGE.encode(), b""
            )
        if arguments[0] == "create":
            self.arguments = arguments
            self.exists = True
            return subprocess.CompletedProcess(arguments, 0, CID.encode(), b"")
        if arguments[0] == "inspect":
            if not self.exists:
                return subprocess.CompletedProcess(arguments, 1, b"", b"No such container")
            name = self.arguments[self.arguments.index("--name") + 1]
            label = self.arguments[self.arguments.index("--label") + 1]
            key, value = label.split("=", 1)
            cpu = next(
                arg.split("=", 1)[1] for arg in self.arguments if arg.startswith("--cpuset-cpus=")
            )
            inspection = {
                "Id": CID,
                "Name": "/" + name,
                "Image": IMAGE,
                "Config": {"Labels": {key: value}},
                "HostConfig": {
                    "Memory": 1 if self.wrong_policy else 1024 * 1024 * 1024,
                    "MemorySwap": 1024 * 1024 * 1024,
                    "NanoCpus": 1_000_000_000,
                    "CpusetCpus": cpu,
                    "PidsLimit": 64,
                    "NetworkMode": "none",
                    "ReadonlyRootfs": True,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges"],
                },
                "State": {"Running": False, "ExitCode": self.exit_code, "OOMKilled": False},
            }
            return subprocess.CompletedProcess(arguments, 0, json.dumps([inspection]).encode(), b"")
        if arguments[0] == "start":
            if self.timeout_smoke:
                raise subprocess.TimeoutExpired(arguments, timeout)
            self.exit_code = 1 if self.fail_smoke else 0
            return subprocess.CompletedProcess(
                arguments, self.exit_code, b"ALPHA_DAILY_RUNTIME_SMOKE_V1\n", b""
            )
        assert arguments[0] == "rm"
        if not self.removal_failed:
            self.exists = False
        return subprocess.CompletedProcess(arguments, 1 if self.removal_failed else 0, b"", b"")


@pytest.fixture
def qualifier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, FakeDocker]:
    source = Path(__file__).parents[2] / "workers/rdagent/qualify_daily_container.py"
    spec = importlib.util.spec_from_file_location("test_daily_container_qualifier", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    worker = tmp_path / "repo/workers/rdagent"
    executable = tmp_path / "repo/cpython/bin/python3.12"
    executable.parent.mkdir(parents=True)
    executable.write_text("artificial executable identity fixture")
    (worker / ".venv-economics-qualified/bin").mkdir(parents=True)
    (worker / ".venv-economics-qualified/bin/python").symlink_to(executable)
    docker = FakeDocker()
    monkeypatch.setattr(module, "_WORKER", worker)
    monkeypatch.setattr(module, "_docker", docker)
    monkeypatch.setattr(module, "measure_rule_environment", lambda costed: "f" * 64)
    monkeypatch.setattr(module.os, "sched_getaffinity", lambda pid: {2, 4})
    return module, docker


def test_success_smokes_closed_policy_then_atomically_publishes_two_fields(
    qualifier: tuple[ModuleType, FakeDocker],
) -> None:
    module, docker = qualifier
    path = module.qualify_daily_container(IMAGE)
    assert json.loads(path.read_text()) == {
        "schema": "DailyRuleContainerProfileV1",
        "image_id": IMAGE,
    }
    assert docker.exists is False
    args = docker.arguments
    for required in (
        "--pull=never",
        "--network=none",
        "--read-only",
        "--memory=1073741824",
        "--memory-swap=1073741824",
        "--cpus=1",
        "--cpuset-cpus=2",
        "--pids-limit=64",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=67108864",
    ):
        assert required in args
    mounts = [args[index + 1] for index, value in enumerate(args) if value == "--mount"]
    assert len(mounts) == 2 and all(mount.endswith(",readonly") for mount in mounts)
    assert not any("docker.sock" in mount or "credentials" in mount for mount in mounts)
    assert any(arg.startswith("--entrypoint=") and arg.endswith("/bin/python") for arg in args)
    assert args[-4:-1] == ["-I", "-B", "-c"]
    assert not any(call[0] in {"pull", "build", "login"} for call in docker.calls)
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.parametrize(
    "defect", ["fail_smoke", "wrong_policy", "timeout_smoke", "removal_failed"]
)
def test_failed_or_uncertain_qualification_never_publishes_profile(
    qualifier: tuple[ModuleType, FakeDocker], defect: str
) -> None:
    module, docker = qualifier
    setattr(docker, defect, True)
    with pytest.raises(DataError):
        module.qualify_daily_container(IMAGE)
    assert not module._profile_path().exists()
    if defect != "removal_failed":
        assert docker.exists is False


@pytest.mark.parametrize(
    "image", ["python:3.12-slim", "latest", "sha256:bad", "", "sha256:" + "A" * 64]
)
def test_explicit_exact_image_selector_is_mandatory(
    qualifier: tuple[ModuleType, FakeDocker], image: str
) -> None:
    module, docker = qualifier
    with pytest.raises(DataError, match="explicit immutable"):
        module.qualify_daily_container(image)
    assert docker.calls == []


def test_changed_image_cannot_overwrite_existing_profile_or_start_a_container(
    qualifier: tuple[ModuleType, FakeDocker],
) -> None:
    module, docker = qualifier
    path = module._profile_path()
    path.parent.mkdir(parents=True)
    original = json.dumps(
        {"schema": "DailyRuleContainerProfileV1", "image_id": "sha256:" + "b" * 64}
    ).encode()
    path.write_bytes(original)
    with pytest.raises(DataError, match="refusing overwrite"):
        module.qualify_daily_container(IMAGE)
    assert path.read_bytes() == original
    assert docker.calls == []


def test_unchanged_profile_keeps_bytes_and_rechecks_current_cpu_affinity(
    qualifier: tuple[ModuleType, FakeDocker], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, docker = qualifier
    path = module.qualify_daily_container(IMAGE)
    original = path.read_bytes()
    monkeypatch.setattr(module.os, "sched_getaffinity", lambda pid: {7, 9})
    assert module.qualify_daily_container(IMAGE) == path
    assert path.read_bytes() == original
    assert "--cpuset-cpus=7" in docker.arguments


@pytest.mark.parametrize("defect", ["daemon", "installed"])
def test_unavailable_daemon_or_missing_local_image_fails_without_pull(
    qualifier: tuple[ModuleType, FakeDocker], defect: str
) -> None:
    module, docker = qualifier
    setattr(docker, defect, False)
    with pytest.raises(DataError):
        module.qualify_daily_container(IMAGE)
    assert not any(call[0] in {"create", "pull", "build", "login"} for call in docker.calls)
    assert not module._profile_path().exists()


def test_local_daemon_client_clears_endpoint_and_tls_selectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import alpha_cli._native_daily_rule_container as container

    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        monkeypatch.setenv(name, "untrusted-remote-selector")
    observed: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        observed["command"] = command
        observed["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, b"linux", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert container._docker(["info"]).returncode == 0
    assert observed["command"][1] == "--host=unix:///var/run/docker.sock"
    assert not any(key.startswith("DOCKER_") for key in observed["env"])


def test_changed_site_identity_during_smoke_never_publishes(
    qualifier: tuple[ModuleType, FakeDocker], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, docker = qualifier
    measurements = iter(("a" * 64, "b" * 64))
    monkeypatch.setattr(module, "measure_rule_environment", lambda costed: next(measurements))
    with pytest.raises(DataError, match="runtime changed"):
        module.qualify_daily_container(IMAGE)
    assert not module._profile_path().exists()
    assert docker.exists is False
