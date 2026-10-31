"""Explicit offline import qualification for one already-installed daily Docker image.

This is runtime setup only. It installs/pulls nothing, changes no Docker configuration,
and establishes no study, source, owner approval, or scientific authority.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from alpha_cli._native_daily_rule_container import _docker, daily_container_security_arguments
from alpha_cli._native_daily_rule_protocol import DAILY_CHILD_ENV
from alpha_cli._native_rule_environment import measure_rule_environment
from alpha_core import DataError

_WORKER = Path(__file__).resolve().parent
_IMAGE = re.compile(r"sha256:[0-9a-f]{64}")
_CID = re.compile(r"[0-9a-f]{64}")
_MEMORY = 1024 * 1024 * 1024
_ARTIFACT_BYTES = 32 * 1024 * 1024
_SMOKE = (
    "from alpha_backtest.engine import run_backtest;"
    "from alpha_backtest.feed import to_execution_feed;"
    "from alpha_strategies.rule_strategy import RuleStrategy;"
    "import alpha_data,numpy,polars;"
    "print('ALPHA_DAILY_RUNTIME_SMOKE_V1')"
)


def _profile_path() -> Path:
    return _WORKER.parents[1] / ".alpha/state/runtime/daily-container.json"


def _safe_path(path: Path) -> None:
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise DataError("daily runtime qualification path is unsafe")


def _existing(path: Path, expected: dict[str, str]) -> bool:
    _safe_path(path)
    if not path.exists():
        return False
    try:
        with path.open("rb") as stream:
            raw = stream.read(4097)
        value = json.loads(raw) if len(raw) <= 4096 else None
    except (OSError, ValueError) as error:
        raise DataError("existing daily container profile is invalid") from error
    if value != expected:
        raise DataError("existing daily container profile differs; refusing overwrite")
    return True


def _publish(path: Path, profile: dict[str, str]) -> None:
    if _existing(path, profile):
        return
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    _safe_path(path)
    fd, temporary = tempfile.mkstemp(prefix=".daily-container-", suffix=".tmp", dir=path.parent)
    staged = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(profile, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(staged, path)
        except FileExistsError:
            _existing(path, profile)
    finally:
        staged.unlink(missing_ok=True)


def _inspect(name: str, image_id: str, labels: dict[str, str]) -> dict[str, Any] | None:
    result = _docker(["inspect", "--type=container", name])
    if result.returncode:
        if b"No such object" in result.stderr or b"No such container" in result.stderr:
            return None
        raise DataError("daily runtime qualification container outcome is uncertain")
    try:
        values = json.loads(result.stdout)
    except ValueError as error:
        raise DataError("daily runtime qualification inspection is invalid") from error
    if (
        not isinstance(values, list)
        or len(values) != 1
        or not isinstance(values[0], dict)
        or values[0].get("Name") != "/" + name
        or values[0].get("Image") != image_id
        or not isinstance(values[0].get("Id"), str)
        or _CID.fullmatch(values[0]["Id"]) is None
        or not isinstance(values[0].get("Config"), dict)
        or values[0]["Config"].get("Labels") != labels
    ):
        raise DataError("daily runtime qualification ownership differs; no removal authorized")
    return values[0]


def _cleanup(name: str, image_id: str, labels: dict[str, str]) -> None:
    observed = _inspect(name, image_id, labels)
    if observed is None:
        return
    result = _docker(["rm", "--force", observed["Id"]])
    if result.returncode or _inspect(name, image_id, labels) is not None:
        raise DataError("daily runtime qualification cleanup is unverified")


def qualify_daily_container(image_id: str) -> Path:
    """Run a closed import smoke under the native security policy; publish only success."""
    if not isinstance(image_id, str) or _IMAGE.fullmatch(image_id) is None:
        raise DataError("qualification requires explicit immutable sha256 image ID")
    profile = {"schema": "DailyRuleContainerProfileV1", "image_id": image_id}
    path = _profile_path()
    _existing(path, profile)  # Refuse a different profile before any daemon effects.
    info = _docker(["info", "--format", "{{.OSType}}"])
    if info.returncode or info.stdout.strip() != b"linux":
        raise DataError("managed local Linux Docker daemon is unavailable")
    image = _docker(["image", "inspect", "--format", "{{.Id}}", image_id])
    if image.returncode or image.stdout.decode().strip() != image_id:
        raise DataError("explicit daily image is not already installed on the managed daemon")
    runtime = _WORKER / ".venv-economics-qualified"
    python = runtime / "bin/python"
    prefix = python.resolve(strict=True).parents[1]
    mounts = tuple(dict.fromkeys((_WORKER, prefix)))
    if any(not mount.is_absolute() or mount.is_symlink() or not mount.is_dir() for mount in mounts):
        raise DataError("qualification requires exact readonly worker and CPython roots")
    for mount in mounts:
        _safe_path(mount)
        if any(character in str(mount) for character in (",", "\n", "\r")):
            raise DataError("qualification mount path is unsupported")
    before = measure_rule_environment(True)
    cpus = sorted(os.sched_getaffinity(0))
    if not cpus:
        raise DataError("qualification has no available CPU")
    cpu = str(cpus[0])
    name = "alpha-daily-qualify-" + uuid.uuid4().hex
    labels = {"alpha.daily.runtime-qualification": name}
    arguments = [
        "create",
        "--pull=never",
        "--name",
        name,
        *daily_container_security_arguments(
            memory_bytes=_MEMORY,
            cpuset_cpu=cpu,
            user=f"{os.getuid()}:{os.getgid()}",
            artifact_file_bytes=_ARTIFACT_BYTES,
            cpu_seconds=30,
        ),
        "--workdir=/tmp",
    ]
    for key, value in labels.items():
        arguments += ["--label", key + "=" + value]
    for mount in mounts:
        arguments += ["--mount", f"type=bind,src={mount},dst={mount},readonly"]
    for key, value in {
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        **DAILY_CHILD_ENV,
    }.items():
        arguments += ["--env", key + "=" + value]
    arguments += ["--entrypoint=" + str(python), image_id, "-I", "-B", "-c", _SMOKE]
    try:
        created = _docker(arguments, timeout=20)
        if created.returncode or _CID.fullmatch(created.stdout.decode().strip()) is None:
            raise DataError("daily runtime qualification create failed or has uncertain outcome")
        observed = _inspect(name, image_id, labels)
        if observed is None or observed["Id"] != created.stdout.decode().strip():
            raise DataError("daily runtime qualification created identity differs")
        host = observed.get("HostConfig")
        if (
            not isinstance(host, dict)
            or any(
                host.get(key) != expected
                for key, expected in {
                    "Memory": _MEMORY,
                    "MemorySwap": _MEMORY,
                    "NanoCpus": 1_000_000_000,
                    "CpusetCpus": cpu,
                    "PidsLimit": 64,
                    "NetworkMode": "none",
                    "ReadonlyRootfs": True,
                    "CapDrop": ["ALL"],
                }.items()
            )
            or "no-new-privileges" not in host.get("SecurityOpt", [])
        ):
            raise DataError("daily runtime qualification enforced policy differs")
        smoke = _docker(["start", "--attach", observed["Id"]], timeout=60)
        stopped = _inspect(name, image_id, labels)
        state = stopped.get("State") if stopped is not None else None
        if (
            smoke.returncode != 0
            or smoke.stdout.strip() != b"ALPHA_DAILY_RUNTIME_SMOKE_V1"
            or not isinstance(state, dict)
            or state.get("Running") is not False
            or type(state.get("ExitCode")) is not int
            or state["ExitCode"] != 0
            or state.get("OOMKilled") is not False
            or measure_rule_environment(True) != before
        ):
            raise DataError("daily runtime qualification smoke failed or runtime changed")
    except (OSError, subprocess.SubprocessError) as error:
        raise DataError("daily runtime qualification failed; no profile published") from error
    finally:
        _cleanup(name, image_id, labels)
    _publish(path, profile)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True, help="already-installed immutable sha256 ID")
    args = parser.parse_args()
    try:
        print(qualify_daily_container(args.image_id))
    except (DataError, OSError) as error:
        parser.exit(1, str(error) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
