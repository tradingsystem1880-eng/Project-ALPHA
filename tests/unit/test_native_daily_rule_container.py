"""Portable artificial Docker RPC fixtures; these are not container acceptance evidence."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import alpha_cli._native_daily_rule_container as containers
from alpha_cli._native_daily_rule_container import (
    DailyRuleContainer,
    daily_container_profile,
    daily_container_security_arguments,
)
from alpha_cli._native_daily_rule_protocol import DAILY_CHILD_ENV
from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_core import DataError
from tests.unit.test_native_daily_rule_study import _study

CID = "d" * 64
DEADLINE = 987_654_321_000


class DockerRPC:
    def __init__(self, owner: DailyRuleContainer, worker: Path) -> None:
        self.calls: list[tuple[list[str], float]] = []
        self.exists = False
        self.fail_create = False
        self.create_without_resource = False
        self.bad_create_id = False
        self.image_unavailable = False
        self.image_env = ["PATH=/usr/local/bin:/usr/bin", "LANG=C.UTF-8", "PYTHON_VERSION=3.12"]
        self.inspect_error: bytes | None = None
        self.inspect_payload: bytes | None = None
        self.stop_failed = False
        self.stop_still_running = False
        self.remove_failed = False
        self.remove_still_present = False
        policy = owner.policy
        environment = {
            **dict(item.split("=", 1) for item in self.image_env),
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "TMPDIR": "/tmp",
            "HOME": "/tmp",
            **policy["environment"],
        }
        self.observation: dict[str, Any] = {
            "Id": CID,
            "Name": "/" + owner.name,
            "Image": owner.profile["image_id"],
            "Config": {
                "Labels": owner.labels.copy(),
                "User": policy["user"],
                "WorkingDir": str(owner.work),
                "Entrypoint": [str(worker / ".venv-economics-qualified/bin/python")],
                "Cmd": [
                    "-I",
                    "-B",
                    str(worker / "daily_container_entry.py"),
                    str(owner.mounts[1]),
                    str(DEADLINE),
                ],
                "Env": [key + "=" + value for key, value in environment.items()],
            },
            "HostConfig": {
                "Memory": policy["memory_bytes"],
                "MemorySwap": policy["memory_bytes"],
                "NanoCpus": 1_000_000_000,
                "PidsLimit": 64,
                "CpusetCpus": "3",
                "NetworkMode": "none",
                "ReadonlyRootfs": True,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges"],
                "Tmpfs": {"/tmp": "rw,noexec,nosuid,size=67108864"},
                "Ulimits": [
                    {
                        "Name": "fsize",
                        "Soft": policy["artifact_file_bytes"],
                        "Hard": policy["artifact_file_bytes"],
                    },
                    {"Name": "cpu", "Soft": policy["cpu_seconds"], "Hard": policy["cpu_seconds"]},
                ],
            },
            "Mounts": [
                {"Type": "bind", "Source": str(path), "Destination": str(path), "RW": False}
                for path in owner.mounts
            ]
            + [
                {
                    "Type": "bind",
                    "Source": str(owner.work),
                    "Destination": str(owner.work),
                    "RW": True,
                }
            ],
            "State": {
                "Running": False,
                "ExitCode": 0,
                "Status": "created",
                "StartedAt": "0001-01-01T00:00:00Z",
            },
        }

    def __call__(
        self, args: list[str], *, timeout: float = 10
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((args, timeout))
        if args[:2] == ["image", "inspect"]:
            return subprocess.CompletedProcess(
                args,
                1 if self.image_unavailable else 0,
                json.dumps([{"Config": {"Env": self.image_env}}]).encode(),
                b"",
            )
        if args[0] == "create":
            self.exists = not self.create_without_resource
            return subprocess.CompletedProcess(
                args,
                1 if self.fail_create else 0,
                b"invalid" if self.bad_create_id else CID.encode(),
                b"create error" if self.fail_create else b"",
            )
        if args[0] == "inspect":
            if self.inspect_error is not None:
                return subprocess.CompletedProcess(args, 1, b"", self.inspect_error)
            if not self.exists:
                return subprocess.CompletedProcess(args, 1, b"", b"No such container")
            return subprocess.CompletedProcess(
                args,
                0,
                self.inspect_payload
                if self.inspect_payload is not None
                else json.dumps([self.observation]).encode(),
                b"",
            )
        if args[0] == "stop":
            if not self.stop_failed and not self.stop_still_running:
                self.observation["State"]["Running"] = False
                self.observation["State"]["Status"] = "exited"
            return subprocess.CompletedProcess(args, 1 if self.stop_failed else 0, b"", b"")
        assert args[0] == "rm"
        if not self.remove_failed and not self.remove_still_present:
            self.exists = False
        return subprocess.CompletedProcess(args, 1 if self.remove_failed else 0, b"", b"")


@dataclass
class Fixture:
    owner: DailyRuleContainer
    rpc: DockerRPC
    worker: Path
    source: Path
    work: Path
    study: DailyRuleStudyV1

    def command(self) -> list[str]:
        return [
            str(self.worker / ".venv-economics-qualified/bin/python"),
            "-I",
            "-B",
            str(self.worker / "fixture_entry.py"),
            str(self.source),
            "admitted",
            "@daily-admission.json",
        ]


@pytest.fixture
def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fixture:
    import alpha_cli._native_loop_admission as admission

    study = _study(tmp_path)
    worker = tmp_path / "repo/workers/rdagent"
    (worker / ".venv-economics-qualified/bin").mkdir(parents=True)
    executable = tmp_path / "repo/cpython/bin/python3.12"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"artificial python identity")
    (worker / ".venv-economics-qualified/bin/python").symlink_to(executable)
    docker = tmp_path / "docker"
    docker.write_bytes(b"artificial Docker RPC client identity")
    profile = worker.parents[1] / ".alpha/state/runtime/daily-container.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        json.dumps({"schema": "DailyRuleContainerProfileV1", "image_id": study.container_image_id})
    )
    source, work = tmp_path / "source", tmp_path / "work"
    source.mkdir()
    work.mkdir()
    monkeypatch.setattr(admission, "WORKER", worker)
    monkeypatch.setattr(containers, "_DOCKER", docker)
    monkeypatch.setattr(os, "sched_getaffinity", lambda _: {3, 7})
    owner = DailyRuleContainer(
        work=work,
        source=source,
        study=study,
        job_id="job",
        owner_id="owner",
        reservation_id="reservation",
        spec_sha256="f" * 64,
        cpu_milliseconds=2500,
        deadline_monotonic_ns=DEADLINE,
    )
    rpc = DockerRPC(owner, worker)
    monkeypatch.setattr(containers, "_docker", rpc)
    return Fixture(owner, rpc, worker, source, work, study)


def test_closed_policy_admission_command_and_verified_cleanup(fixture: Fixture) -> None:
    owner, rpc = fixture.owner, fixture.rpc
    assert owner.binding() == {
        "container_name": owner.name,
        "image_id": fixture.study.container_image_id,
        "resource_fingerprint": owner.resource_fingerprint,
        "deadline_monotonic_ns": DEADLINE,
    }
    assert owner.policy["cpuset_cpu"] == "3"
    assert owner.policy["cpu_seconds"] == 3
    assert all(owner.policy["environment"][key] == value for key, value in DAILY_CHILD_ENV.items())
    assert all(owner.policy["environment"][key] == "" for key in containers._PROXY_KEYS)
    with pytest.raises(DataError, match="no created retained identity"):
        owner.command()
    owner.create(fixture.command())
    created = next(args for args, _ in rpc.calls if args[0] == "create")
    assert "--pull=never" in created
    assert "--entrypoint=" + fixture.command()[0] in created
    assert created[-5:] == [
        "-I",
        "-B",
        str(fixture.worker / "daily_container_entry.py"),
        str(fixture.source),
        str(DEADLINE),
    ]
    mounts = [created[index + 1] for index, item in enumerate(created) if item == "--mount"]
    assert len(mounts) == 4 and sum(value.endswith(",readonly") for value in mounts) == 3
    assert not any("docker.sock" in mount for mount in mounts)
    assert owner.command()[-3:] == ["start", "--attach", CID]
    rpc.observation["State"].update(
        Running=True, Status="running", StartedAt="2026-01-01T00:00:00Z"
    )
    owner.cleanup()
    assert owner.removed is True and owner.exit_code == 0
    assert (["stop", "--time=1", CID], 5) in rpc.calls
    assert (["rm", CID], 10) in rpc.calls
    before = rpc.calls.copy()
    owner.cleanup()
    assert rpc.calls == before
    with pytest.raises(DataError):
        owner.command()


@pytest.mark.parametrize(
    "field",
    [
        "Memory",
        "MemorySwap",
        "NanoCpus",
        "PidsLimit",
        "CpusetCpus",
        "NetworkMode",
        "ReadonlyRootfs",
        "CapDrop",
        "SecurityOpt",
    ],
)
def test_actual_resource_policy_mismatch_is_refused_before_start(
    fixture: Fixture, field: str
) -> None:
    fixture.rpc.observation["HostConfig"][field] = None
    with pytest.raises(DataError, match="resource/security policy"):
        fixture.owner.create(fixture.command())
    assert not any(args[0] == "start" for args, _ in fixture.rpc.calls)


@pytest.mark.parametrize(
    "field", ["User", "WorkingDir", "Entrypoint", "Cmd", "Env", "Mounts", "Tmpfs", "Ulimits"]
)
def test_actual_entrypoint_user_environment_mount_and_limit_mismatch_is_refused(
    fixture: Fixture, field: str
) -> None:
    if field == "Mounts":
        fixture.rpc.observation[field] = []
    elif field in {"Tmpfs", "Ulimits"}:
        fixture.rpc.observation["HostConfig"][field] = {} if field == "Tmpfs" else []
    else:
        fixture.rpc.observation["Config"][field] = (
            [] if field in {"Entrypoint", "Cmd", "Env"} else "wrong"
        )
    with pytest.raises(DataError, match="mounts/user/environment/limits"):
        fixture.owner.create(fixture.command())


def test_image_defaults_and_unregistered_payloads_are_refused_before_container_effects(
    fixture: Fixture,
) -> None:
    fixture.rpc.image_env.append("UNREGISTERED_DEFAULT=fixture")
    with pytest.raises(DataError, match="unregistered environment"):
        fixture.owner.create(fixture.command())
    assert not any(args[0] == "create" for args, _ in fixture.rpc.calls)
    with pytest.raises(DataError, match="already attempted"):
        fixture.owner.create(fixture.command())


def test_arbitrary_payload_command_never_reaches_daemon(fixture: Fixture) -> None:
    with pytest.raises(DataError, match="unregistered payload"):
        fixture.owner.create(["/bin/sh", "-c", "echo fixture"])
    assert fixture.rpc.calls == []


def test_missing_local_image_never_pulls_or_creates(fixture: Fixture) -> None:
    fixture.rpc.image_unavailable = True
    with pytest.raises(DataError, match="exact local image"):
        fixture.owner.create(fixture.command())
    assert [args[0] for args, _ in fixture.rpc.calls] == ["image"]


@pytest.mark.parametrize("created", [True, False])
def test_uncertain_create_is_inspected_by_exact_name_and_never_retried(
    fixture: Fixture, created: bool
) -> None:
    fixture.rpc.fail_create = True
    fixture.rpc.create_without_resource = not created
    with pytest.raises(DataError, match="retained owner must reconcile"):
        fixture.owner.create(fixture.command())
    assert fixture.owner.cid == (CID if created else None)
    assert ["inspect", "--type=container", fixture.owner.name] in [
        args for args, _ in fixture.rpc.calls
    ]
    with pytest.raises(DataError, match="already attempted"):
        fixture.owner.create(fixture.command())
    assert sum(args[0] == "create" for args, _ in fixture.rpc.calls) == 1
    fixture.owner.cleanup()
    assert fixture.owner.removed is True
    assert fixture.owner.exit_code is None  # created or absent is not an executed completion


@pytest.mark.parametrize("mutation", ["bad_cid", "vanished", "running"])
def test_invalid_create_result_cannot_be_treated_as_ready(fixture: Fixture, mutation: str) -> None:
    fixture.rpc.bad_create_id = mutation == "bad_cid"
    fixture.rpc.create_without_resource = mutation == "vanished"
    fixture.rpc.observation["State"]["Running"] = mutation == "running"
    with pytest.raises(DataError):
        fixture.owner.create(fixture.command())


@pytest.mark.parametrize("field", ["Name", "Image", "Id", "Labels"])
def test_inspection_cannot_reassign_retained_identity(fixture: Fixture, field: str) -> None:
    fixture.rpc.exists = True
    if field == "Labels":
        fixture.rpc.observation["Config"][field] = {"alpha.owner": "foreign"}
    else:
        fixture.rpc.observation[field] = "foreign"
    with pytest.raises(DataError, match="identity does not match"):
        fixture.owner._inspect()
    assert not any(args[0] in {"stop", "rm"} for args, _ in fixture.rpc.calls)


def test_retained_cid_cannot_change_even_with_same_name_and_labels(fixture: Fixture) -> None:
    fixture.owner.create(fixture.command())
    fixture.rpc.observation["Id"] = "e" * 64
    with pytest.raises(DataError, match="identity does not match"):
        fixture.owner.cleanup()
    assert fixture.owner.removed is False


@pytest.mark.parametrize("payload", [b"not json", b"[]", b"[null]", b"[{},{}]"])
def test_malformed_inspection_is_refused(fixture: Fixture, payload: bytes) -> None:
    fixture.rpc.exists = True
    fixture.rpc.inspect_payload = payload
    with pytest.raises(DataError):
        fixture.owner._inspect()


@pytest.mark.parametrize(
    "failure",
    ["daemon", "vanished", "stop", "still_running", "exit_code", "remove", "still_present"],
)
def test_cleanup_uncertainty_propagates_without_false_clean_state(
    fixture: Fixture, failure: str
) -> None:
    fixture.owner.create(fixture.command())
    fixture.rpc.observation["State"].update(
        Running=True, Status="running", StartedAt="2026-01-01T00:00:00Z"
    )
    if failure == "daemon":
        fixture.rpc.inspect_error = b"daemon unavailable"
    elif failure == "vanished":
        fixture.rpc.exists = False
    elif failure == "stop":
        fixture.rpc.stop_failed = True
    elif failure == "still_running":
        fixture.rpc.stop_still_running = True
    elif failure == "exit_code":
        fixture.rpc.observation["State"]["ExitCode"] = True
    elif failure == "remove":
        fixture.rpc.remove_failed = True
    else:
        fixture.rpc.remove_still_present = True
    with pytest.raises(DataError):
        fixture.owner.cleanup()
    assert fixture.owner.removed is False


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "tag",
        "extra",
        "huge",
        "invalid_json",
        "missing",
        "symlink",
        "docker_missing",
        "image_changed",
    ],
)
def test_profile_bytes_schema_and_frozen_image_tampering_are_refused(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    path = fixture.worker.parents[1] / ".alpha/state/runtime/daily-container.json"
    value = json.loads(path.read_text())
    if mutation == "schema":
        value["schema"] = "Unsupported"
    elif mutation == "tag":
        value["image_id"] = "python:latest"
    elif mutation == "extra":
        value["allow_network"] = True
    elif mutation == "huge":
        path.write_bytes(b" " * 4097)
    elif mutation == "invalid_json":
        path.write_bytes(b"invalid-json")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "symlink":
        original = path.with_suffix(".original")
        path.rename(original)
        path.symlink_to(original)
    elif mutation == "docker_missing":
        monkeypatch.setattr(containers, "_DOCKER", fixture.work / "missing-docker")
    else:
        value["image_id"] = "sha256:" + "a" * 64
    if mutation in {"schema", "tag", "extra", "image_changed"}:
        path.write_text(json.dumps(value))
    if mutation == "image_changed":
        with pytest.raises(DataError, match="owner-frozen study"):
            DailyRuleContainer(
                work=fixture.work,
                source=fixture.source,
                study=fixture.study,
                job_id="job",
                owner_id="owner",
                reservation_id="reservation",
                spec_sha256="f" * 64,
                cpu_milliseconds=2500,
                deadline_monotonic_ns=DEADLINE,
            )
    else:
        with pytest.raises(DataError):
            daily_container_profile()


def test_profile_fingerprint_binds_exact_bytes_and_docker_binary(fixture: Fixture) -> None:
    profile = daily_container_profile()
    path = fixture.worker.parents[1] / ".alpha/state/runtime/daily-container.json"
    assert profile["config_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert profile["docker_sha256"] == hashlib.sha256(containers._DOCKER.read_bytes()).hexdigest()
    path.write_text(path.read_text() + "\n")
    assert daily_container_profile()["config_sha256"] != profile["config_sha256"]


def test_no_available_cpu_and_missing_mount_are_refused_before_rpc(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(os, "sched_getaffinity", lambda _: set())
    with pytest.raises(DataError, match="no available CPU"):
        DailyRuleContainer(
            work=fixture.work,
            source=fixture.source,
            study=fixture.study,
            job_id="job",
            owner_id="owner",
            reservation_id="reservation",
            spec_sha256="f" * 64,
            cpu_milliseconds=1,
            deadline_monotonic_ns=DEADLINE,
        )
    with pytest.raises(DataError, match="readonly source/runtime mounts"):
        DailyRuleContainer(
            work=fixture.work,
            source=fixture.source / "missing",
            study=fixture.study,
            job_id="job",
            owner_id="owner",
            reservation_id="reservation",
            spec_sha256="f" * 64,
            cpu_milliseconds=1,
            deadline_monotonic_ns=DEADLINE,
        )


@pytest.mark.parametrize(
    "change",
    [
        {"memory_bytes": True},
        {"memory_bytes": 1},
        {"cpuset_cpu": "1,2"},
        {"user": "root"},
        {"artifact_file_bytes": True},
        {"artifact_file_bytes": 32 * 1024 * 1024 + 1},
        {"cpu_seconds": 0},
        {"cpu_seconds": 61},
    ],
)
def test_closed_resource_argument_bounds(change: dict[str, Any]) -> None:
    options: dict[str, Any] = {
        "memory_bytes": 1024 * 1024 * 1024,
        "cpuset_cpu": "3",
        "user": "1000:1000",
        "artifact_file_bytes": 32 * 1024 * 1024,
        "cpu_seconds": 5,
    }
    options.update(change)
    with pytest.raises(DataError, match="resource policy"):
        daily_container_security_arguments(**options)


def test_local_daemon_rpc_keeps_config_but_clears_remote_selectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        monkeypatch.setenv(key, "untrusted-selector")
    monkeypatch.setenv("DOCKER_CONFIG", "/fixture/docker-config")
    observed: dict[str, Any] = {}

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        observed.update(args=args, **kwargs)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", run)
    containers._docker(["info"], timeout=7)
    assert observed["args"][1:] == ["--host=unix:///var/run/docker.sock", "info"]
    assert observed["timeout"] == 7
    assert observed["stdin"] == subprocess.DEVNULL
    assert observed["env"] == {
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "DOCKER_CONFIG": "/fixture/docker-config",
    }


def test_profile_size_cap_is_enforced_on_the_bounded_stream_read(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = fixture.worker.parents[1] / ".alpha/state/runtime/daily-container.json"
    profile.write_bytes(b" " * 4097)
    original = Path.open

    class CheckedReader:
        def __init__(self, stream: Any) -> None:
            self.stream = stream

        def __enter__(self) -> CheckedReader:
            return self

        def __exit__(self, *args: object) -> None:
            self.stream.close()

        def read(self, size: int = -1) -> bytes:
            assert 0 < size <= 4097, "profile read omitted its byte ceiling"
            value = self.stream.read(size)
            assert isinstance(value, bytes)
            return value

    def checked_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        stream = original(path, *args, **kwargs)
        return CheckedReader(stream) if path == profile else stream

    monkeypatch.setattr(Path, "open", checked_open)
    with pytest.raises(DataError, match="exceeds its bound"):
        daily_container_profile()
