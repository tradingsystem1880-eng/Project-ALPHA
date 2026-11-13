"""Server-owned bounded native-result reader. No run publication or execution authority."""

from __future__ import annotations

import json
import os
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from alpha_cli.durable_lease import (
    DurableLeaseError,
    _observe_retained_child,
    terminate_and_reap,
)
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_web._catalog import _cli_environment, _command
from alpha_web.api.native_result_models import NativeJobResultV1


class NativeResultSettings(AlphaSettings):
    """Existing ALPHA_ env/.env deployment mechanism; no client-set configuration."""

    native_result_source: Path | None = None
    native_result_runtime: Path | None = None
    native_result_mode: Literal["resume", "cancel", "exhaust", "tamper"] | None = None


@dataclass(frozen=True)
class ServerNativeProfile:
    source: Path
    runtime: Path
    mode: str


@dataclass(frozen=True)
class NativeResultDeployment:
    root: Path
    profile: ServerNativeProfile


def native_result_deployment() -> NativeResultDeployment | None:
    try:
        settings = NativeResultSettings()
    except (ValidationError, OSError, ValueError):
        return None
    if (
        settings.native_result_source is None
        or settings.native_result_runtime is None
        or settings.native_result_mode is None
    ):
        return None
    return NativeResultDeployment(
        settings.data_dir,
        ServerNativeProfile(
            settings.native_result_source,
            settings.native_result_runtime,
            settings.native_result_mode,
        ),
    )


def unavailable(reason: str) -> dict[str, object]:
    return {
        "schema": "NativeStockOperatorResultV1",
        "operation": "recover_native_stock_result",
        "classification": "synthetic_only_unqualified",
        "status": "unavailable",
        "reason": reason,
        "resume_allowed": False,
        "scientific_acceptance": "not_admitted",
    }


def _safe_name(path: Path) -> None:
    if (
        {".codex", ".aws", ".ssh", ".azure"}.intersection(path.parts)
        or path.name in {"auth.json", "credentials", "application_default_credentials.json"}
        or path.name == ".env"
        or path.name.startswith(".env.")
    ):
        raise DataError("native deployment asset is not public profile material")


def _regular(path: Path, cap: int, *, python_link: bool = False) -> int:
    _safe_name(path)
    if path.is_symlink() and not python_link:
        raise DataError("native deployment asset symlink is unsupported")
    resolved = path.resolve(strict=True)
    _safe_name(resolved)
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > cap:
        raise DataError("native deployment asset type or size is unsupported")
    return info.st_size


def _profile_preflight(deployment: NativeResultDeployment) -> None:
    """API engineering caps on trusted stable assets, not admission or OS isolation."""
    root, selected = deployment.root, deployment.profile
    if (
        root.is_symlink()
        or root != root.resolve()
        or root.parent != Path(tempfile.gettempdir()).resolve()
        or not root.name.startswith("alpha-native-fixture-")
    ):
        raise DataError("native result root is not a synthetic fixture")
    if (root / "daily-rule-workspace.json").exists():
        raise DataError("native result reader is synthetic-only")
    _regular(root / "synthetic-only", 64)
    for path in (
        selected.source,
        selected.runtime,
        selected.source / "rdagent",
        selected.runtime / "venv",
        selected.runtime / "venv/bin",
    ):
        _safe_name(path)
        if path.is_symlink() or path != path.resolve() or not path.is_dir():
            raise DataError("native deployment directory is unavailable")
    pending = [selected.source / "rdagent"]
    nodes = files = size = 0
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                nodes += 1
                if nodes > 4096 or entry.is_symlink():
                    raise DataError("native source scan exceeds safe bounds")
                path = Path(entry.path)
                _safe_name(path)
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                else:
                    files += 1
                    size += _regular(path, 4 * 1024 * 1024)
                    if files > 2048 or size > 32 * 1024 * 1024:
                        raise DataError("native source bytes exceed read bounds")
    _regular(selected.runtime / "dependencies.lock.txt", 1024 * 1024)
    _regular(selected.runtime / "venv/pyvenv.cfg", 64 * 1024)
    _regular(selected.runtime / "venv/bin/python", 64 * 1024 * 1024, python_link=True)


_CLI_TIMEOUT = 30.0
_MAX_OUTPUT = 128 * 1024
_MAX_ERROR = 8192


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise DataError("duplicate native result response key")
        result[key] = value
    return result


def _read_cli(args: list[str], root: Path) -> dict[str, object]:
    """Fixed read-only command, existing command-scoped environment; bounded pipes/time."""
    if sys.platform != "linux" or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        raise DataError("native result read requires retained Linux child ownership")
    process = subprocess.Popen(
        _command(args),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_cli_environment(root, args),
        start_new_session=True,
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + _CLI_TIMEOUT
    try:
        assert process.stdout is not None and process.stderr is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DataError("native result read timed out")
                for key, _ in selector.select(remaining):
                    name = key.data
                    cap = _MAX_OUTPUT if name == "stdout" else _MAX_ERROR
                    chunk = os.read(key.fd, min(65536, cap + 1 - len(buffers[name])))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffers[name].extend(chunk)
                    if len(buffers[name]) > cap:
                        raise DataError("native result read exceeds output bound")
        while (code := _observe_retained_child(process)) is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DataError("native result read timed out")
            time.sleep(min(0.01, remaining))
        try:
            body = json.loads(buffers["stdout"], object_pairs_hook=_pairs)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise DataError("native result response is not valid JSON") from error
        if not isinstance(body, dict):
            raise DataError("native result response is not an object")
        status = body.get("status")
        if (
            type(status) is not str
            or {"completed": 0, "invalid": 2, "unavailable": 3}.get(status) != code
        ):
            raise DataError("native result response exit/state binding differs")
        return body
    finally:
        try:
            # Preserve the waitable leader as group authority even after it exits.
            # This existing platform helper signals before final reap; no numeric retry.
            terminate_and_reap(
                process, process_group_id=process.pid, retain_leader=True, grace_seconds=0.25
            )
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()


def read_native_result(deployment: NativeResultDeployment, job_id: str) -> dict[str, object]:
    try:
        _profile_preflight(deployment)
        selected = deployment.profile
        args = [
            "research",
            "diagnostic",
            "native-result",
            "--data-dir",
            str(deployment.root),
            "--job-id",
            job_id,
            "--profile-source",
            str(selected.source),
            "--profile-runtime",
            str(selected.runtime),
            "--profile-mode",
            selected.mode,
        ]
        model = NativeJobResultV1.model_validate(_read_cli(args, deployment.root))
        if model.dispatch is not None and str(model.dispatch.job_id) != job_id:
            raise DataError("native result response belongs to a different job")
        body = model.model_dump(mode="json", by_alias=True, exclude_none=True)
        if len(json.dumps(body, allow_nan=False).encode()) > _MAX_OUTPUT:
            raise DataError("native result response exceeds read bound")
        return body
    except (
        DataError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        subprocess.TimeoutExpired,
        DurableLeaseError,
    ):
        return unavailable("native_result_evidence_unavailable_or_invalid")
