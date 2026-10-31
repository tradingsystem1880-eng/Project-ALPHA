"""Closed Docker payload boundary for the registered daily rule, never a coordinator.

The retained native owner owns this exact container through cleanup. No daemon socket,
credentials, arbitrary shell, source checkout parent or mutable package path enters it.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any, TypedDict

from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_core import DataError

_DOCKER = next(
    (path for path in (Path("/usr/local/bin/docker"), Path("/usr/bin/docker")) if path.is_file()),
    Path("/usr/bin/docker"),
)
_SOCKET = "unix:///var/run/docker.sock"
_ID = re.compile(r"[0-9a-f]{64}")
_IMAGE = re.compile(r"sha256:[0-9a-f]{64}")
_PROXY_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


class _Policy(TypedDict):
    schema: str
    image_id: str
    memory_bytes: int
    cpuset_cpu: str
    nano_cpus: int
    pids_limit: int
    network: str
    readonly_root: bool
    tmpfs_bytes: int
    readonly_mounts: list[str]
    work_mount: str
    environment: dict[str, str]
    user: str
    artifact_file_bytes: int
    cpu_seconds: int
    deadline_monotonic_ns: int


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _docker(arguments: list[str], *, timeout: float = 10) -> subprocess.CompletedProcess[bytes]:
    environment = {"PATH": os.defpath, "LANG": "C.UTF-8"}
    if "DOCKER_CONFIG" in os.environ:
        environment["DOCKER_CONFIG"] = os.environ["DOCKER_CONFIG"]
    return subprocess.run(
        [str(_DOCKER), "--host=" + _SOCKET, *arguments],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=environment,
    )


def daily_container_security_arguments(
    *, memory_bytes: int, cpuset_cpu: str, user: str, artifact_file_bytes: int, cpu_seconds: int
) -> list[str]:
    """One closed payload security/resource policy, reused by runtime qualification."""
    if (
        type(memory_bytes) is not int
        or not 256 * 1024 * 1024 <= memory_bytes <= 2 * 1024 * 1024 * 1024
        or re.fullmatch(r"[0-9]+", cpuset_cpu) is None
        or re.fullmatch(r"[0-9]+:[0-9]+", user) is None
        or type(artifact_file_bytes) is not int
        or not 0 < artifact_file_bytes <= 32 * 1024 * 1024
        or type(cpu_seconds) is not int
        or not 0 < cpu_seconds <= 60
    ):
        raise DataError("daily container resource policy is invalid")
    return [
        *("--env=" + key + "=" for key in _PROXY_KEYS),
        "--network=none",
        "--read-only",
        "--memory=" + str(memory_bytes),
        "--memory-swap=" + str(memory_bytes),
        "--cpuset-cpus=" + cpuset_cpu,
        "--cpus=1",
        "--pids-limit=64",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=" + user,
        "--tmpfs=/tmp:rw,noexec,nosuid,size=67108864",
        "--ulimit=fsize=" + str(artifact_file_bytes) + ":" + str(artifact_file_bytes),
        "--ulimit=cpu=" + str(cpu_seconds) + ":" + str(cpu_seconds),
    ]


def daily_container_profile() -> dict[str, str]:
    from alpha_cli._native_loop_admission import WORKER

    config = WORKER.parents[1] / ".alpha/state/runtime/daily-container.json"
    if config.is_symlink() or any(parent.is_symlink() for parent in config.parents):
        raise DataError("daily container profile path is unsafe")
    try:
        with config.open("rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise DataError("daily container profile exceeds its bound")
        profile = json.loads(raw)
    except (OSError, ValueError) as error:
        raise DataError("daily physical-memory container profile is unavailable") from error
    if (
        not isinstance(profile, dict)
        or set(profile) != {"schema", "image_id"}
        or profile.get("schema") != "DailyRuleContainerProfileV1"
        or not isinstance(profile.get("image_id"), str)
        or _IMAGE.fullmatch(profile["image_id"]) is None
        or not _DOCKER.is_file()
    ):
        raise DataError("daily container profile requires an exact immutable local image")
    return {
        "image_id": profile["image_id"],
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "docker_sha256": hashlib.sha256(_DOCKER.read_bytes()).hexdigest(),
    }


class DailyRuleContainer:
    """Exact-name, exact-label ownership; uncertain creates are inspected, never retried."""

    def __init__(
        self,
        *,
        work: Path,
        source: Path,
        study: DailyRuleStudyV1,
        job_id: str,
        owner_id: str,
        reservation_id: str,
        spec_sha256: str,
        cpu_milliseconds: int,
        deadline_monotonic_ns: int,
    ):
        from alpha_cli._native_daily_rule_protocol import DAILY_CHILD_ENV
        from alpha_cli._native_loop_admission import WORKER

        self.profile = daily_container_profile()
        if self.profile["image_id"] != study.container_image_id:
            raise DataError("daily container image differs from owner-frozen study")
        self.work = work
        self.name = "alpha-daily-" + _sha([job_id, reservation_id, owner_id])[:40]
        self.labels = {
            "alpha.job": job_id,
            "alpha.owner": owner_id,
            "alpha.reservation": reservation_id,
            "alpha.spec": spec_sha256,
        }
        python_prefix = (WORKER / ".venv-economics-qualified/bin/python").resolve().parents[1]
        mounts = tuple(dict.fromkeys((WORKER.resolve(), source.resolve(), python_prefix)))
        if any(path.is_symlink() or not path.is_dir() for path in mounts):
            raise DataError("daily container requires its reviewed readonly source/runtime mounts")
        cpus = sorted(os.sched_getaffinity(0))
        if not cpus:
            raise DataError("daily container has no available CPU")
        self.policy: _Policy = {
            "schema": "DailyContainerResourcesV1",
            "image_id": self.profile["image_id"],
            "memory_bytes": study.resources.max_memory_bytes,
            "cpuset_cpu": str(cpus[0]),
            "nano_cpus": 1_000_000_000,
            "pids_limit": 64,
            "network": "none",
            "readonly_root": True,
            "tmpfs_bytes": 64 * 1024 * 1024,
            "readonly_mounts": [str(path) for path in mounts],
            "work_mount": str(work),
            "environment": {**DAILY_CHILD_ENV, **dict.fromkeys(_PROXY_KEYS, "")},
            "user": str(os.getuid()) + ":" + str(os.getgid()),
            "artifact_file_bytes": study.resources.max_artifact_bytes,
            "cpu_seconds": math.ceil(cpu_milliseconds / 1000),
            "deadline_monotonic_ns": deadline_monotonic_ns,
        }
        self.resource_fingerprint = _sha(self.policy)
        self.cid: str | None = None
        self.create_attempted = False
        self.removed = False
        self.exit_code: int | None = None
        self.mounts = mounts

    def binding(self) -> dict[str, object]:
        return {
            "container_name": self.name,
            "image_id": self.profile["image_id"],
            "resource_fingerprint": self.resource_fingerprint,
            "deadline_monotonic_ns": self.policy["deadline_monotonic_ns"],
        }

    def _inspect(self) -> dict[str, Any] | None:
        result = _docker(["inspect", "--type=container", self.cid or self.name])
        if result.returncode != 0:
            if b"No such object" in result.stderr or b"No such container" in result.stderr:
                return None
            raise DataError("daily container state cannot be verified")
        try:
            values = json.loads(result.stdout)
            observed = values[0]
        except (ValueError, TypeError, IndexError) as error:
            raise DataError("daily container inspection is invalid") from error
        if (
            not isinstance(observed, dict)
            or len(values) != 1
            or observed.get("Name") != "/" + self.name
            or observed.get("Config", {}).get("Labels") != self.labels
            or observed.get("Image") != self.profile["image_id"]
            or not isinstance(observed.get("Id"), str)
            or _ID.fullmatch(observed["Id"]) is None
            or (self.cid is not None and observed["Id"] != self.cid)
        ):
            raise DataError(
                "daily container identity does not match retained owner/name/image/labels"
            )
        return observed

    def create(self, command: list[str]) -> None:
        if self.create_attempted:
            raise DataError("daily container creation already attempted; inspect only")
        self.create_attempted = True
        from alpha_cli._native_loop_admission import WORKER

        if command != [
            str(WORKER / ".venv-economics-qualified/bin/python"),
            "-I",
            "-B",
            str(WORKER / "fixture_entry.py"),
            str(self.mounts[1]),
            "admitted",
            "@daily-admission.json",
        ]:
            raise DataError("daily container refuses an unregistered payload command")
        wrapped = [
            command[0],
            "-I",
            "-B",
            str(WORKER / "daily_container_entry.py"),
            str(self.mounts[1]),
            str(self.policy["deadline_monotonic_ns"]),
        ]
        image_result = _docker(["image", "inspect", self.profile["image_id"]])
        if image_result.returncode != 0:
            raise DataError("daily container exact local image is unavailable")
        image = json.loads(image_result.stdout)[0]
        image_env = dict(item.split("=", 1) for item in image.get("Config", {}).get("Env", []))
        if set(image_env) - {"PATH", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256"}:
            raise DataError("daily container image has unregistered environment defaults")
        args = [
            "create",
            "--pull=never",
            "--name",
            self.name,
            "--workdir=" + str(self.work),
            "--entrypoint=" + wrapped[0],
            *daily_container_security_arguments(
                memory_bytes=self.policy["memory_bytes"],
                cpuset_cpu=self.policy["cpuset_cpu"],
                user=self.policy["user"],
                artifact_file_bytes=self.policy["artifact_file_bytes"],
                cpu_seconds=self.policy["cpu_seconds"],
            ),
        ]
        for key, value in self.labels.items():
            args += ["--label", key + "=" + value]
        for mount in self.mounts:
            args += ["--mount", "type=bind,src=" + str(mount) + ",dst=" + str(mount) + ",readonly"]
        args += ["--mount", "type=bind,src=" + str(self.work) + ",dst=" + str(self.work)]
        environment = {
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "TMPDIR": "/tmp",
            "HOME": "/tmp",
            **self.policy["environment"],
        }
        for key, value in environment.items():
            args += ["--env", key + "=" + value]
        result = _docker([*args, self.profile["image_id"], *wrapped[1:]], timeout=20)
        if result.returncode != 0:
            # No retry. A response failure may still have created the named resource.
            observed = self._inspect()
            if observed is not None:
                self.cid = observed["Id"]
            raise DataError(
                "daily container create failed; retained owner must reconcile exact resource"
            )
        cid = result.stdout.decode().strip()
        if _ID.fullmatch(cid) is None:
            raise DataError("daily container create returned no exact immutable container ID")
        self.cid = cid
        observed = self._inspect()
        if observed is None or observed.get("State", {}).get("Running") is not False:
            raise DataError("daily container must be verified created and stopped before start")
        host = observed.get("HostConfig", {})
        security_options = host.get("SecurityOpt")
        if (
            host.get("Memory") != self.policy["memory_bytes"]
            or host.get("MemorySwap") != self.policy["memory_bytes"]
            or host.get("NanoCpus") != 1_000_000_000
            or host.get("PidsLimit") != 64
            or host.get("CpusetCpus") != self.policy["cpuset_cpu"]
            or host.get("NetworkMode") != "none"
            or host.get("ReadonlyRootfs") is not True
            or host.get("CapDrop") != ["ALL"]
            or not isinstance(security_options, list)
            or "no-new-privileges" not in security_options
        ):
            raise DataError("daily container resource/security policy differs before start")
        config = observed.get("Config", {})
        actual_env = dict(item.split("=", 1) for item in config.get("Env", []))
        expected_env = {**image_env, **environment}
        actual_mounts = {
            (item.get("Type"), item.get("Source"), item.get("Destination"), item.get("RW"))
            for item in observed.get("Mounts", [])
        }
        expected_mounts = {("bind", str(path), str(path), False) for path in self.mounts} | {
            ("bind", str(self.work), str(self.work), True)
        }
        ulimits = {
            item.get("Name"): (item.get("Soft"), item.get("Hard"))
            for item in host.get("Ulimits", [])
        }
        if (
            config.get("User") != self.policy["user"]
            or config.get("WorkingDir") != str(self.work)
            or config.get("Entrypoint") != [wrapped[0]]
            or config.get("Cmd") != wrapped[1:]
            or actual_env != expected_env
            or actual_mounts != expected_mounts
            or host.get("Tmpfs") != {"/tmp": "rw,noexec,nosuid,size=67108864"}
            or ulimits
            != {
                "fsize": (self.policy["artifact_file_bytes"], self.policy["artifact_file_bytes"]),
                "cpu": (self.policy["cpu_seconds"], self.policy["cpu_seconds"]),
            }
        ):
            raise DataError("daily container mounts/user/environment/limits differ before start")

    def command(self) -> list[str]:
        if self.cid is None or self.removed:
            raise DataError("daily container has no created retained identity")
        return [str(_DOCKER), "--host=" + _SOCKET, "start", "--attach", self.cid]

    def cleanup(self) -> None:
        if self.removed:
            return
        observed = self._inspect()
        if observed is None:
            if self.cid is not None:
                raise DataError("daily container disappeared before verified cleanup")
            self.removed = True
            return
        self.cid = observed["Id"]
        if observed.get("State", {}).get("Running") is True:
            result = _docker(["stop", "--time=1", self.cid], timeout=5)
            if result.returncode != 0:
                raise DataError("daily container stop was not verified")
        stopped = self._inspect()
        if stopped is None or stopped.get("State", {}).get("Running") is not False:
            raise DataError("daily container remains running or unknown")
        exit_code = stopped.get("State", {}).get("ExitCode")
        if type(exit_code) is not int:
            raise DataError("daily container stopped without a verified exit code")
        state = stopped.get("State", {})
        self.exit_code = (
            exit_code
            if state.get("Status") in {"exited", "dead"}
            and isinstance(state.get("StartedAt"), str)
            and not state["StartedAt"].startswith("0001-")
            else None
        )
        result = _docker(["rm", self.cid])
        if result.returncode != 0 or self._inspect() is not None:
            raise DataError("daily container removal was not verified")
        self.removed = True
