"""Subprocess core: run the `alpha` CLI and return the run it produced.

Research-run actions funnel through :func:`run_alpha`; bounded control-plane projections use
:func:`run_json`. Both run ``alpha <args>`` as a child process, share the server's ``data_dir`` via
the environment, and fail loud on a non-zero exit. ``run_alpha`` additionally parses the
``-> run <id>`` token and reads back the byte-stable ``manifest.json``. Commands that write no
manifest (``data pull``) pass ``run_type=None`` and get their stdout summary instead.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Any

from alpha_cli.durable_lease import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DurableJobLease,
    terminate_and_reap,
)
from alpha_cli.job_capacity import heavyweight_job_kind_for_command
from alpha_cli.run_store import RUN_DIRS
from alpha_mcp._runs import read_bounded_manifest

_ALPHA_BIN = "alpha"  # console script; resolvable on PATH inside the workspace venv
_RUN_ID_RE = re.compile(r"->\s+run\s+([0-9a-f]{16})\b")
_TIMEOUT_S = 3600.0  # generous ceiling for a full gauntlet; a hung child must not hang the server
_PROJECTION_TIMEOUT_S = 30.0
_MAX_STDOUT_CHARS = 16_384
_DURABLE_HEARTBEAT_INTERVAL_S = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
_DURABLE_HEARTBEAT_TIMEOUT_S = 5.0
_PROCESS_ENV_NAMES = frozenset(
    {
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "PATH",
        "PYTHONPATH",
        "TMPDIR",
        "TZ",
        "VIRTUAL_ENV",
    }
)
_DATA_ENV_NAMES = frozenset({"ALPHA_BULK_DATA_DIR", "ALPHA_BULK_VOLUME_UUID"})


def _cli_environment(data_dir: Path) -> dict[str, str]:
    """Build the closed environment allowed to cross the MCP-to-CLI boundary."""
    allowed = _PROCESS_ENV_NAMES | _DATA_ENV_NAMES
    environment = {name: value for name, value in os.environ.items() if name in allowed}
    environment["ALPHA_DATA_DIR"] = str(data_dir)
    return environment


def _reserve_heavyweight_job(args: list[str], *, data_dir: Path) -> str | None:
    kind = heavyweight_job_kind_for_command(args)
    if kind is None:
        return None
    row = run_json(
        [
            "project",
            "job-create",
            kind,
            "--request-json",
            json.dumps({"surface": "mcp", "argv": args}, sort_keys=True, separators=(",", ":")),
            "--json",
        ],
        data_dir=data_dir,
    )
    if not isinstance(row, dict):
        raise RuntimeError("heavyweight job reservation omitted its durable job id")
    job_id = row.get("job_id")
    if not isinstance(job_id, str):
        raise RuntimeError("heavyweight job reservation omitted its durable job id")
    return job_id


def _set_heavyweight_job_status(
    job_id: str | None,
    status: str,
    *,
    data_dir: Path,
    result_run_id: str | None = None,
    terminal_error: str | None = None,
    timeout_seconds: float | None = None,
) -> None:
    if job_id is None:
        return
    args = ["project", "job-status", job_id, status]
    if result_run_id is not None:
        args.extend(["--result-run-id", result_run_id])
    if terminal_error is not None:
        args.extend(["--terminal-error", terminal_error[:4096]])
    args.append("--json")
    if timeout_seconds is None:
        run_json(args, data_dir=data_dir)
    else:
        run_json(args, data_dir=data_dir, timeout_seconds=timeout_seconds)


def run_json(
    args: list[str], *, data_dir: Path, timeout_seconds: float = _PROJECTION_TIMEOUT_S
) -> Any:
    """Run one bounded ``alpha ... --json`` projection and decode its JSON response."""
    env = _cli_environment(data_dir)
    try:
        proc = subprocess.run(
            [_ALPHA_BIN, *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"`alpha {' '.join(args)}` projection exceeded {timeout_seconds:.0f}s"
        ) from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "(no output)"
        raise RuntimeError(f"`alpha {' '.join(args)}` failed (exit {proc.returncode}): {detail}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"`alpha {' '.join(args)}` returned invalid JSON") from exc


def _renew_job_heartbeat(job_id: str, *, data_dir: Path) -> bool:
    row = run_json(
        [
            "project",
            "job-event",
            job_id,
            "heartbeat",
            "--payload-json",
            '{"surface":"mcp"}',
            "--json",
        ],
        data_dir=data_dir,
        timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
    )
    if not isinstance(row, dict) or not isinstance(row.get("cancel_requested"), bool):
        raise RuntimeError("durable heartbeat omitted its cancellation state")
    return bool(row["cancel_requested"])


def _run_action_process(
    args: list[str], *, data_dir: Path, durable_job_id: str | None
) -> subprocess.CompletedProcess[str]:
    """Run one action, leasing durable heavyweight children until they terminate."""
    command = [_ALPHA_BIN, *args]
    env = _cli_environment(data_dir)
    if durable_job_id is None:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=_TIMEOUT_S,
        )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    cancel_state = [False]

    def renew() -> None:
        cancel_state[0] = _renew_job_heartbeat(durable_job_id, data_dir=data_dir)

    lease = DurableJobLease.start_for_process(
        process,
        renew=renew,
        fail_journal=lambda message: _set_heavyweight_job_status(
            durable_job_id,
            "failed",
            data_dir=data_dir,
            terminal_error=message,
            timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
        ),
        cancel_requested=lambda: cancel_state[0],
        cancel_journal=lambda: _set_heavyweight_job_status(
            durable_job_id,
            "cancelled",
            data_dir=data_dir,
            timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
        ),
        interval_seconds=_DURABLE_HEARTBEAT_INTERVAL_S,
        label="MCP heavyweight child",
    )
    try:
        try:
            stdout, stderr = process.communicate(timeout=_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            terminate_and_reap(process)
            process.communicate()
            raise
    finally:
        lease.stop()
        lease.raise_if_cancelled()
        lease.raise_if_failed()
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def run_alpha(args: list[str], *, data_dir: Path, run_type: str | None) -> dict[str, Any]:
    """Run ``alpha <args>`` and return the resulting run's manifest (or its stdout summary).

    ``run_type`` is the artifact subdirectory the command writes to (``"runs"``, ``"optim"``,
    ``"propfirm"``, …) or ``None`` for commands that persist nothing. Raises ``RuntimeError`` on a
    non-zero exit (carrying stderr), when no run id can be parsed from a run-producing command, or
    when the expected manifest is missing.
    """
    heavyweight_job_id = _reserve_heavyweight_job(args, data_dir=data_dir)
    try:
        _set_heavyweight_job_status(heavyweight_job_id, "running", data_dir=data_dir)
    except RuntimeError:
        with suppress(RuntimeError):
            _set_heavyweight_job_status(
                heavyweight_job_id,
                "failed",
                data_dir=data_dir,
                terminal_error="MCP could not start the durable heavyweight journal",
            )
        raise
    try:
        proc = _run_action_process(
            args,
            data_dir=data_dir,
            durable_job_id=heavyweight_job_id,
        )
    except subprocess.TimeoutExpired as exc:
        with suppress(RuntimeError):
            _set_heavyweight_job_status(
                heavyweight_job_id,
                "failed",
                data_dir=data_dir,
                terminal_error=f"alpha process exceeded {_TIMEOUT_S:.0f}s",
            )
        raise RuntimeError(
            f"`alpha {' '.join(args)}` exceeded {_TIMEOUT_S:.0f}s and was killed - a hung data "
            "pull or runaway run must not hang the MCP server"
        ) from exc
    except OSError as exc:
        with suppress(RuntimeError):
            _set_heavyweight_job_status(
                heavyweight_job_id,
                "failed",
                data_dir=data_dir,
                terminal_error=str(exc),
            )
        raise
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "(no output)"
        with suppress(RuntimeError):
            _set_heavyweight_job_status(
                heavyweight_job_id,
                "failed",
                data_dir=data_dir,
                terminal_error=detail,
            )
        raise RuntimeError(f"`alpha {' '.join(args)}` failed (exit {proc.returncode}): {detail}")

    if run_type is None:
        stdout = proc.stdout.strip()
        if len(stdout) > _MAX_STDOUT_CHARS:
            with suppress(RuntimeError):
                _set_heavyweight_job_status(
                    heavyweight_job_id,
                    "failed",
                    data_dir=data_dir,
                    terminal_error="alpha action output exceeded the bounded response size",
                )
            raise ValueError(f"alpha action output exceeds {_MAX_STDOUT_CHARS} characters")
        try:
            _set_heavyweight_job_status(heavyweight_job_id, "succeeded", data_dir=data_dir)
        except RuntimeError:
            with suppress(RuntimeError):
                _set_heavyweight_job_status(
                    heavyweight_job_id,
                    "failed",
                    data_dir=data_dir,
                    terminal_error="MCP could not complete the durable heavyweight journal",
                )
            raise
        return {"stdout": stdout}

    if run_type not in RUN_DIRS:
        with suppress(RuntimeError):
            _set_heavyweight_job_status(
                heavyweight_job_id,
                "failed",
                data_dir=data_dir,
                terminal_error=f"unsupported run type {run_type!r}",
            )
        raise ValueError(f"unsupported run type {run_type!r}")

    match = _RUN_ID_RE.search(proc.stdout)
    if match is None:
        with suppress(RuntimeError):
            _set_heavyweight_job_status(
                heavyweight_job_id,
                "failed",
                data_dir=data_dir,
                terminal_error="alpha action produced no parseable run id",
            )
        raise RuntimeError(
            f"could not parse a run id from `alpha {' '.join(args)}` output:\n{proc.stdout.strip()}"
        )
    run_id = match.group(1)
    run_dir = data_dir / run_type / run_id
    try:
        manifest = read_bounded_manifest(run_dir)
    except FileNotFoundError as exc:
        with suppress(RuntimeError):
            _set_heavyweight_job_status(
                heavyweight_job_id,
                "failed",
                data_dir=data_dir,
                terminal_error=f"run {run_id} produced no manifest",
            )
        raise RuntimeError(f"run {run_id} produced no manifest under {run_dir}") from exc
    except Exception as exc:
        with suppress(RuntimeError):
            _set_heavyweight_job_status(
                heavyweight_job_id,
                "failed",
                data_dir=data_dir,
                terminal_error=str(exc),
            )
        raise
    try:
        _set_heavyweight_job_status(
            heavyweight_job_id,
            "succeeded",
            data_dir=data_dir,
            result_run_id=run_id,
        )
    except RuntimeError:
        with suppress(RuntimeError):
            _set_heavyweight_job_status(
                heavyweight_job_id,
                "failed",
                data_dir=data_dir,
                terminal_error="MCP could not complete the durable heavyweight journal",
            )
        raise
    return manifest
