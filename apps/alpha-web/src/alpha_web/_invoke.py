"""Background job runner: launch `alpha`, capture its streaming output, parse the run id.

Each launched run is its own subprocess (the engine never runs in the web process). A reader thread
pumps the merged stdout/stderr into the job's line buffer; the SSE route tails that buffer live. On
completion the ``-> run <id>`` token is parsed (when a ``run_type`` is known) so the console can
link to the finished run. Jobs live in an in-process registry keyed by an opaque id.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import statistics
import subprocess
import threading
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import anyio

from alpha_cli.catalog import COMMAND_RUN_TYPES
from alpha_cli.durable_lease import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DurableJobLease,
    DurableLeaseCancelled,
    DurableLeaseError,
    terminate_and_reap,
)
from alpha_cli.job_capacity import heavyweight_job_kind_for_command
from alpha_web._catalog import _cli_environment, _run_json

_ALPHA_BIN = "alpha"  # console script on the venv PATH
_RUN_ID_RE = re.compile(r"->\s+run\s+([0-9a-f]{16})\b")
_SESSION_ID_RE = re.compile(
    r"->\s+(?:paper\s+)?session\s+"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b"
)

# command-path -> artifact run-type dir (None = persists no manifest, e.g. data pull / console)
RUN_TYPE = COMMAND_RUN_TYPES
_DURABLE_HEARTBEAT_INTERVAL_S = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
_DURABLE_HEARTBEAT_TIMEOUT_S = 5.0
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_UI_HEAVYWEIGHT_NICE = 10


def _command(args: list[str]) -> list[str]:
    """The argv to spawn (seam: tests monkeypatch this with a fast fake command)."""
    return [_ALPHA_BIN, *args]


class Job:
    """One launched `alpha` run: its captured lines + terminal status, tailed live over SSE."""

    def __init__(
        self,
        args: list[str],
        run_type: str | None,
        *,
        job_id: str | None = None,
        durable: bool = False,
    ) -> None:
        self.job_id = uuid.uuid4().hex if job_id is None else job_id
        self.args = list(args)
        self.command_str = " ".join(args)
        self.run_type = run_type
        self.created_at = time.time()  # memory-only wall-clock; never enters a byte-stable manifest
        self.finished_at: float | None = None
        self.lines: list[str] = []
        self.finished = False
        self.cancelled = False
        self.returncode: int | None = None
        self.run_id: str | None = None
        self.session_id: str | None = None
        self.terminal_error: str | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._lease: DurableJobLease | None = None
        self._lock = threading.Lock()
        self._durable = durable

    @property
    def status(self) -> str:
        if not self.finished:
            return "running"
        if self.cancelled:
            return "cancelled"
        if self.terminal_error is not None:
            return "failed"
        return "done" if self.returncode == 0 else "failed"

    def tail(self, start: int) -> list[str]:
        """A copy of the lines from index ``start`` onward (thread-safe snapshot)."""
        with self._lock:
            return self.lines[start:]

    def _append(self, line: str) -> None:
        with self._lock:
            self.lines.append(line)

    def cancel(self) -> None:
        """Terminate the job's process group (engine + any grandchildren). Idempotent."""
        with self._lock:
            if self.finished or self._proc is None:
                return
            self.cancelled = True
            pid = self._proc.pid
        # already gone / not our group — `_pump` still finalizes the terminal status
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(pid), signal.SIGTERM)

    @property
    def command_path(self) -> str:
        """Stable command-family label used for honest same-session duration estimates."""
        matches = [path for path in RUN_TYPE if self.command_str.startswith(f"{path} ")]
        if self.command_str in RUN_TYPE:
            matches.append(self.command_str)
        if matches:
            return max(matches, key=len)
        return " ".join(self.args[:2]) if len(self.args) > 1 else self.command_str

    def _current_step(self) -> str:
        with self._lock:
            lines = list(reversed(self.lines))
        for raw in lines:
            line = _ANSI_ESCAPE_RE.sub("", raw).strip()
            if line:
                return line[:160]
        return f"Running alpha {self.command_path}"

    def summary(self, *, now: float | None = None) -> dict[str, Any]:
        """A compact status record for the job list / detail endpoints."""
        observed_at = time.time() if now is None else now
        elapsed_seconds = max(0.0, (self.finished_at or observed_at) - self.created_at)
        samples = [
            candidate.finished_at - candidate.created_at
            for candidate in list(JOBS.values())
            if candidate is not self
            and candidate.status == "done"
            and candidate.command_path == self.command_path
            and candidate.finished_at is not None
        ]
        estimate_seconds = statistics.median(samples) if samples else None
        if self.finished:
            progress_mode = "terminal"
            progress_fraction = 1.0
            eta_seconds = None
        elif estimate_seconds is None:
            progress_mode = "indeterminate"
            progress_fraction = None
            eta_seconds = None
        else:
            progress_mode = "estimated"
            progress_fraction = min(elapsed_seconds / max(estimate_seconds, 0.001), 0.95)
            eta_seconds = max(0.0, estimate_seconds - elapsed_seconds)
        return {
            "job_id": self.job_id,
            "command": self.command_str,
            "kind": self.run_type,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": elapsed_seconds,
            "command_path": self.command_path,
            "current_step": self._current_step(),
            "progress_mode": progress_mode,
            "progress_fraction": progress_fraction,
            "eta_seconds": eta_seconds,
            "eta_sample_count": len(samples),
            "run_id": self.run_id,
            "session_id": self.session_id,
            "returncode": self.returncode,
            "n_lines": len(self.lines),
        }


JOBS: dict[str, Job] = {}


def list_jobs() -> list[dict[str, Any]]:
    """All known jobs (live + this-session-finished), newest first."""
    return [j.summary() for j in sorted(JOBS.values(), key=lambda j: j.created_at, reverse=True)]


def cancel_job(job_id: str, *, data_dir: Path | None = None) -> Job | None:
    """Cancel a job by id; returns the Job (post-signal) or None if unknown."""
    job = JOBS.get(job_id)
    if job is not None:
        if job._durable:
            if data_dir is None:
                raise RuntimeError("durable job cancellation requires data_dir")
            _run_json(
                [
                    "project",
                    "job-cancel",
                    job.job_id,
                    "--actor",
                    "workstation-owner",
                    "--reason",
                    "owner cancelled live workstation job",
                    "--json",
                ],
                data_dir=data_dir,
                timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
            )
        job.cancel()
    return job


def _reserve_heavyweight_job(args: list[str], *, data_dir: Path) -> str | None:
    kind = heavyweight_job_kind_for_command(args)
    if kind is None:
        return None
    row = _run_json(
        [
            "project",
            "job-create",
            kind,
            "--request-json",
            json.dumps(
                {"surface": "workstation", "argv": args},
                sort_keys=True,
                separators=(",", ":"),
            ),
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


def _set_durable_status(
    job: Job,
    status: str,
    *,
    data_dir: Path,
    terminal_error: str | None = None,
    timeout_seconds: float | None = None,
) -> None:
    if not job._durable:
        return
    args = ["project", "job-status", job.job_id, status]
    if status == "succeeded" and job.run_id is not None:
        args.extend(["--result-run-id", job.run_id])
    if terminal_error is not None:
        args.extend(["--terminal-error", terminal_error[:4096]])
    args.append("--json")
    if timeout_seconds is None:
        _run_json(args, data_dir=data_dir)
    else:
        _run_json(args, data_dir=data_dir, timeout_seconds=timeout_seconds)


def _abort_before_pump(
    job: Job,
    proc: subprocess.Popen[str],
    *,
    data_dir: Path,
    reason: str,
) -> None:
    """Stop a spawned child before terminalizing a journal that has no active pump."""
    try:
        terminate_and_reap(proc, process_group_id=proc.pid)
    except Exception as cleanup_exc:
        job.terminal_error = str(cleanup_exc)
        job._append(f"startup process-group cleanup failed: {cleanup_exc}")
        retained = (
            "heavyweight capacity remains reserved"
            if job._durable
            else "live job handle remains registered"
        )
        raise RuntimeError(
            f"workstation could not start its job monitor and the child process group could "
            f"not be verified stopped; {retained}"
        ) from cleanup_exc
    lease = job._lease
    if lease is not None:
        lease.stop()
        job._lease = None
    if proc.stdout is not None:
        with contextlib.suppress(OSError):
            proc.stdout.close()
    job.returncode = proc.returncode
    job.terminal_error = reason
    with contextlib.suppress(RuntimeError, ValueError, OSError):
        _set_durable_status(job, "failed", data_dir=data_dir, terminal_error=reason)
    JOBS.pop(job.job_id, None)


def _renew_durable_heartbeat(job: Job, *, data_dir: Path) -> bool:
    if not job._durable:
        return False
    row = _run_json(
        [
            "project",
            "job-event",
            job.job_id,
            "heartbeat",
            "--payload-json",
            '{"surface":"workstation"}',
            "--json",
        ],
        data_dir=data_dir,
        timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
    )
    if not isinstance(row, dict) or not isinstance(row.get("cancel_requested"), bool):
        raise RuntimeError("durable heartbeat omitted its cancellation state")
    return bool(row["cancel_requested"])


def _mark_durable_cancelled(job: Job, *, data_dir: Path) -> None:
    job.cancelled = True
    _set_durable_status(
        job,
        "cancelled",
        data_dir=data_dir,
        timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
    )


def launch(
    args: list[str],
    *,
    data_dir: Path,
    run_type: str | None,
    run_context: dict[str, object] | None = None,
) -> Job:
    """Spawn ``alpha <args>`` (sharing ``data_dir`` via the env) and tail its output in a thread."""
    durable_job_id = _reserve_heavyweight_job(args, data_dir=data_dir)
    job = Job(args, run_type, job_id=durable_job_id, durable=durable_job_id is not None)
    JOBS[job.job_id] = job
    env = _cli_environment(data_dir, args, run_context=run_context)
    try:
        proc = subprocess.Popen(
            _command(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            start_new_session=True,  # own process group → cancellation can killpg the whole tree
        )
    except OSError as exc:
        with contextlib.suppress(RuntimeError, ValueError, OSError):
            _set_durable_status(job, "failed", data_dir=data_dir, terminal_error=str(exc))
        JOBS.pop(job.job_id, None)
        raise
    job._proc = proc
    if durable_job_id is not None and hasattr(os, "setpriority"):
        # UI-launched Kronos/Qlib work may saturate several cores for minutes. Lower scheduling
        # priority protects chart/input responsiveness without changing the analytical command.
        with contextlib.suppress(OSError):
            os.setpriority(os.PRIO_PROCESS, proc.pid, _UI_HEAVYWEIGHT_NICE)
    try:
        _set_durable_status(job, "running", data_dir=data_dir)
    except (RuntimeError, ValueError, OSError):
        _abort_before_pump(
            job,
            proc,
            data_dir=data_dir,
            reason="workstation could not start the durable heavyweight journal",
        )
        raise
    if job._durable:
        cancel_state = [False]

        def renew() -> None:
            cancel_state[0] = _renew_durable_heartbeat(job, data_dir=data_dir)

        try:
            job._lease = DurableJobLease.start_for_process(
                proc,
                renew=renew,
                fail_journal=lambda message: _set_durable_status(
                    job,
                    "failed",
                    data_dir=data_dir,
                    terminal_error=message,
                    timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
                ),
                cancel_requested=lambda: cancel_state[0],
                cancel_journal=lambda: _mark_durable_cancelled(job, data_dir=data_dir),
                interval_seconds=_DURABLE_HEARTBEAT_INTERVAL_S,
                label="workstation heavyweight child",
            )
        except (DurableLeaseError, RuntimeError, ValueError, OSError) as exc:
            _abort_before_pump(
                job,
                proc,
                data_dir=data_dir,
                reason="workstation could not start the durable heartbeat lease",
            )
            raise RuntimeError("workstation could not start the durable heartbeat lease") from exc
    pump = threading.Thread(target=_pump, args=(job, proc, data_dir), daemon=True)
    try:
        pump.start()
    except Exception as exc:
        _abort_before_pump(
            job,
            proc,
            data_dir=data_dir,
            reason="workstation could not start the background job monitor",
        )
        raise RuntimeError("workstation could not start the background job monitor") from exc
    return job


def _pump(job: Job, proc: subprocess.Popen[str], data_dir: Path) -> None:
    lease = job._lease
    try:
        if proc.stdout is not None:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                job._append(line)
                if job.run_type is not None and job.run_id is None:
                    match = _RUN_ID_RE.search(line)
                    if match is not None:
                        job.run_id = match.group(1)
                if job.session_id is None:
                    session_match = _SESSION_ID_RE.search(line)
                    if session_match is not None:
                        job.session_id = session_match.group(1)
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
        proc.wait()
        job.returncode = proc.returncode
        if lease is not None:
            lease.stop()
            try:
                lease.raise_if_cancelled()
            except DurableLeaseCancelled as exc:
                job._append(str(exc))
                job.cancelled = True
                job._lease = None
                job.finished_at = time.time()
                job.finished = True
                return
            try:
                lease.raise_if_failed()
            except DurableLeaseError as exc:
                job._append(str(exc))
                job.terminal_error = str(exc)
                job._lease = None
                job.finished_at = time.time()
                job.finished = True
                return
            job._lease = None
        terminal = (
            "cancelled" if job.cancelled else ("succeeded" if proc.returncode == 0 else "failed")
        )
        terminal_error = None if terminal != "failed" else f"alpha process exited {proc.returncode}"
        try:
            _set_durable_status(
                job,
                terminal,
                data_dir=data_dir,
                terminal_error=terminal_error,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            job.terminal_error = f"durable journal terminal update failed: {exc}"
            with contextlib.suppress(RuntimeError, ValueError, OSError):
                _set_durable_status(
                    job,
                    "failed",
                    data_dir=data_dir,
                    terminal_error="workstation could not complete the durable heavyweight journal",
                )
            job._append(job.terminal_error)
        job.finished_at = time.time()
        job.finished = True


async def event_stream(job: Job, start: int = 0) -> AsyncIterator[dict[str, str]]:
    """SSE events for a job: a ``line`` per output line (carrying its ``id`` for ``Last-Event-ID``
    replay), then a terminal ``done`` / ``failed`` / ``cancelled``. ``start`` resumes at a line
    index (a reconnecting client passes ``Last-Event-ID`` so only missed lines are re-sent)."""
    sent = start
    while True:
        for line in job.tail(sent):
            yield {"event": "line", "id": str(sent), "data": line}
            sent += 1
        if job.finished:
            if job.status == "cancelled":
                yield {"event": "cancelled", "data": f"exit {job.returncode}"}
            elif job.status == "done":
                yield {"event": "done", "data": job.run_id or ""}
            else:
                yield {
                    "event": "failed",
                    "data": job.terminal_error or f"exit {job.returncode}",
                }
            return
        await anyio.sleep(0.05)
