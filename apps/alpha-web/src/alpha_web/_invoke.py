"""Background job runner: launch `alpha`, capture its streaming output, parse the run id.

Each launched run is its own subprocess (the engine never runs in the web process). A reader thread
pumps the merged stdout/stderr into the job's line buffer; the SSE route tails that buffer live. On
completion the ``-> run <id>`` token is parsed (when a ``run_type`` is known) so the console can
link to the finished run. Jobs live in an in-process registry keyed by an opaque id.
"""

from __future__ import annotations

import contextlib
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import anyio

from alpha_cli.catalog import COMMAND_RUN_TYPES

_ALPHA_BIN = "alpha"  # console script on the venv PATH
_RUN_ID_RE = re.compile(r"->\s+run\s+([0-9a-f]{16})\b")
_SESSION_ID_RE = re.compile(
    r"->\s+(?:paper\s+)?session\s+"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b"
)

# command-path -> artifact run-type dir (None = persists no manifest, e.g. data pull / console)
RUN_TYPE = COMMAND_RUN_TYPES


def _command(args: list[str]) -> list[str]:
    """The argv to spawn (seam: tests monkeypatch this with a fast fake command)."""
    return [_ALPHA_BIN, *args]


class Job:
    """One launched `alpha` run: its captured lines + terminal status, tailed live over SSE."""

    def __init__(self, args: list[str], run_type: str | None) -> None:
        self.job_id = uuid.uuid4().hex
        self.args = list(args)
        self.command_str = " ".join(args)
        self.run_type = run_type
        self.created_at = time.time()  # memory-only wall-clock; never enters a byte-stable manifest
        self.lines: list[str] = []
        self.finished = False
        self.cancelled = False
        self.returncode: int | None = None
        self.run_id: str | None = None
        self.session_id: str | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    @property
    def status(self) -> str:
        if not self.finished:
            return "running"
        if self.cancelled:
            return "cancelled"
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

    def summary(self) -> dict[str, Any]:
        """A compact status record for the job list / detail endpoints."""
        return {
            "job_id": self.job_id,
            "command": self.command_str,
            "kind": self.run_type,
            "status": self.status,
            "created_at": self.created_at,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "returncode": self.returncode,
            "n_lines": len(self.lines),
        }


JOBS: dict[str, Job] = {}


def list_jobs() -> list[dict[str, Any]]:
    """All known jobs (live + this-session-finished), newest first."""
    return [j.summary() for j in sorted(JOBS.values(), key=lambda j: j.created_at, reverse=True)]


def cancel_job(job_id: str) -> Job | None:
    """Cancel a job by id; returns the Job (post-signal) or None if unknown."""
    job = JOBS.get(job_id)
    if job is not None:
        job.cancel()
    return job


def launch(args: list[str], *, data_dir: Path, run_type: str | None) -> Job:
    """Spawn ``alpha <args>`` (sharing ``data_dir`` via the env) and tail its output in a thread."""
    job = Job(args, run_type)
    JOBS[job.job_id] = job
    env = {**os.environ, "ALPHA_DATA_DIR": str(data_dir)}
    proc = subprocess.Popen(
        _command(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        start_new_session=True,  # own process group → cancellation can killpg the whole tree
    )
    job._proc = proc
    threading.Thread(target=_pump, args=(job, proc), daemon=True).start()
    return job


def _pump(job: Job, proc: subprocess.Popen[str]) -> None:
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
                yield {"event": "failed", "data": f"exit {job.returncode}"}
            return
        await anyio.sleep(0.05)
