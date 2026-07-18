"""The live desk: a polling diff of the run store + job registry, streamed as SSE events.

Design: one async generator PER CONNECTION (no watcher thread, no lifespan wiring) — the same
shape as ``_invoke.event_stream``. Each tick stats ``manifest.json`` mtimes only; a manifest is
read (for the run record) exclusively when a run appears or changes. This is what lets work done
OUTSIDE the browser — the CLI, Claude over MCP, another terminal — surface in the UI live: the
scan watches the store, not this process's job registry.

Events: an initial ``snapshot`` (counts), then ``run_added`` / ``run_updated`` (data = run record
JSON) and ``job_started`` / ``job_done`` / ``job_failed`` / ``job_cancelled`` (data = job summary
JSON). No event ids: a reconnecting client refetches ``/api/runs`` instead of replaying (the
store is the durable record; the stream is only a change notification).
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import anyio

from alpha_cli import RUN_DIRS
from alpha_web import _invoke

_POLL_MIN = 0.05
_POLL_MAX = 10.0


def clamp_poll(poll: float) -> float:
    """Clamp the client-supplied poll interval to a sane range."""
    return min(_POLL_MAX, max(_POLL_MIN, poll))


def snapshot_runs(data_dir: Path) -> dict[tuple[str, str], float]:
    """(kind, run_id) → manifest mtime for every stored run. Stat-only — no manifest reads."""
    snap: dict[tuple[str, str], float] = {}
    for sub in RUN_DIRS:
        base = data_dir / sub
        if not base.is_dir():
            continue
        for rdir in base.iterdir():
            mpath = rdir / "manifest.json"
            try:
                snap[(sub, rdir.name)] = mpath.stat().st_mtime
            except OSError:
                continue  # no manifest yet (partial write) or dir vanished — invisible this tick
    return snap


def _run_record(data_dir: Path, kind: str, run_id: str) -> dict[str, Any]:
    """One run's browser record (same shape as the ``/api/runs`` index items)."""
    mpath = data_dir / kind / run_id / "manifest.json"
    manifest: dict[str, Any] = json.loads(mpath.read_text(encoding="utf-8"))
    symbols = manifest.get("symbols")
    verdict = manifest.get("verdict")
    return {
        "run_id": run_id,
        "kind": kind,
        "command": manifest.get("command"),
        "label": manifest.get("symbol")
        or (", ".join(symbols) if symbols else None)
        or manifest.get("source"),
        "symbol": manifest.get("symbol"),
        "symbols": symbols,
        "passed": manifest.get("passed"),
        "verdict": verdict.get("overall") if isinstance(verdict, dict) else None,
        "mtime": mpath.stat().st_mtime,
    }


def job_states() -> dict[str, str]:
    """job_id → status for every job in the in-process registry."""
    return {job_id: job.status for job_id, job in _invoke.JOBS.items()}


def _job_data(job_id: str) -> str:
    job = _invoke.JOBS.get(job_id)
    return json.dumps(job.summary()) if job is not None else json.dumps({"job_id": job_id})


async def activity_events(
    data_dir: Path, *, poll: float, max_events: int | None = None
) -> AsyncGenerator[dict[str, str], None]:
    """The per-connection event stream: snapshot, then run/job diffs every ``poll`` seconds.

    ``max_events`` bounds the stream (used by tests and one-shot diagnostic reads — an infinite
    SSE can't be driven to completion through a TestClient); None streams forever.
    """
    sent = 0

    def _bounded() -> bool:
        nonlocal sent
        sent += 1
        return max_events is not None and sent >= max_events

    runs = snapshot_runs(data_dir)
    jobs = job_states()
    running = sum(1 for s in jobs.values() if s == "running")
    yield {"event": "snapshot", "data": json.dumps({"runs": len(runs), "jobs_running": running})}
    if _bounded():
        return

    while True:
        await anyio.sleep(poll)

        new_runs = snapshot_runs(data_dir)
        for key, mtime in list(new_runs.items()):
            old_mtime = runs.get(key)
            if old_mtime is not None and mtime <= old_mtime:
                continue
            kind, run_id = key
            try:
                record = _run_record(data_dir, kind, run_id)
            except (OSError, json.JSONDecodeError):
                # manifest vanished or is mid-write; drop it this tick, the next scan retries
                del new_runs[key]
                continue
            event = "run_added" if old_mtime is None else "run_updated"
            yield {"event": event, "data": json.dumps(record)}
            if _bounded():
                return
        runs = new_runs

        new_jobs = job_states()
        for job_id, status in new_jobs.items():
            old = jobs.get(job_id)
            if old is None:
                yield {"event": "job_started", "data": _job_data(job_id)}
                if _bounded():
                    return
                # a job can start AND finish within one tick — announce both
                if status != "running":
                    yield {"event": f"job_{status}", "data": _job_data(job_id)}
                    if _bounded():
                        return
            elif old != status:
                yield {"event": f"job_{status}", "data": _job_data(job_id)}
                if _bounded():
                    return
        jobs = new_jobs
