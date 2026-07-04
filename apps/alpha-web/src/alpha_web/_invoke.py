"""Background job runner: launch `alpha`, capture its streaming output, parse the run id.

Each launched run is its own subprocess (the engine never runs in the web process). A reader thread
pumps the merged stdout/stderr into the job's line buffer; the SSE route tails that buffer live. On
completion the ``-> run <id>`` token is parsed (when a ``run_type`` is known) so the console can
link to the finished run. Jobs live in an in-process registry keyed by an opaque id.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import anyio

_ALPHA_BIN = "alpha"  # console script on the venv PATH
_RUN_ID_RE = re.compile(r"->\s+run\s+([0-9a-f]{16})\b")

# command-path -> artifact run-type dir (None = persists no manifest, e.g. data pull / console)
RUN_TYPE: dict[str, str] = {
    "validate": "runs",
    "backtest run": "runs",
    "backtest portfolio": "portfolio",
    "backtest cross-sectional": "cross_sectional",
    "optim grid": "optim",
    "propfirm run": "propfirm",
    "forecast run": "forecast",
}


def _command(args: list[str]) -> list[str]:
    """The argv to spawn (seam: tests monkeypatch this with a fast fake command)."""
    return [_ALPHA_BIN, *args]


class Job:
    """One launched `alpha` run: its captured lines + terminal status, tailed live over SSE."""

    def __init__(self, args: list[str], run_type: str | None) -> None:
        self.job_id = uuid.uuid4().hex
        self.args = list(args)
        self.run_type = run_type
        self.lines: list[str] = []
        self.finished = False
        self.returncode: int | None = None
        self.run_id: str | None = None
        self._lock = threading.Lock()

    @property
    def status(self) -> str:
        if not self.finished:
            return "running"
        return "done" if self.returncode == 0 else "failed"

    def tail(self, start: int) -> list[str]:
        """A copy of the lines from index ``start`` onward (thread-safe snapshot)."""
        with self._lock:
            return self.lines[start:]

    def _append(self, line: str) -> None:
        with self._lock:
            self.lines.append(line)


JOBS: dict[str, Job] = {}
_MAX_JOBS = 100  # completed jobs kept for the console; oldest finished ones are pruned


def _prune_finished() -> None:
    """Drop the oldest FINISHED jobs once the registry exceeds ``_MAX_JOBS`` (insertion order)."""
    excess = len(JOBS) - _MAX_JOBS
    if excess <= 0:
        return
    for job_id in [k for k, j in JOBS.items() if j.finished][:excess]:
        JOBS.pop(job_id, None)


def launch(args: list[str], *, data_dir: Path, run_type: str | None) -> Job:
    """Spawn ``alpha <args>`` (sharing ``data_dir`` via the env) and tail its output in a thread."""
    job = Job(args, run_type)
    JOBS[job.job_id] = job
    _prune_finished()
    env = {**os.environ, "ALPHA_DATA_DIR": str(data_dir)}
    proc = subprocess.Popen(
        _command(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    threading.Thread(target=_pump, args=(job, proc), daemon=True).start()
    return job


def _pump(job: Job, proc: subprocess.Popen[str]) -> None:
    if proc.stdout is not None:
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            job._append(line)
            if job.run_type is not None and job.run_id is None:
                match = _RUN_ID_RE.search(line)
                if match is not None:
                    job.run_id = match.group(1)
    proc.wait()
    job.returncode = proc.returncode
    job.finished = True


async def event_stream(job: Job) -> AsyncIterator[dict[str, str]]:
    """SSE events for a job: a ``line`` per output line, then a terminal ``done`` / ``failed``."""
    sent = 0
    while True:
        for line in job.tail(sent):
            sent += 1
            yield {"event": "line", "data": line}
        if job.finished:
            if job.status == "done":
                yield {"event": "done", "data": job.run_id or ""}
            else:
                yield {"event": "failed", "data": f"exit {job.returncode}"}
            return
        await anyio.sleep(0.05)
