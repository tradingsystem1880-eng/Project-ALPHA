"""The live-desk activity stream: run-store + job-registry changes as SSE events.

The diff engine (``_activity.activity_events``) is exercised directly with anyio so the infinite
stream never has to terminate through HTTP; one thin TestClient test covers the route wiring.
Runs written by ANY producer (CLI, MCP, another process) must surface — the scan reads the store,
not the in-process job registry.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastapi.testclient import TestClient

from alpha_web import _activity, _invoke
from alpha_web.app import create_app

RUN_A = "aaaaaaaaaaaaaaaa"
RUN_B = "bbbbbbbbbbbbbbbb"


def _write_run(data_dir: Path, kind: str, run_id: str, **extra: Any) -> Path:
    rdir = data_dir / kind / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    mpath = rdir / "manifest.json"
    mpath.write_text(json.dumps({"run_id": run_id, "symbol": "SPY", **extra}), encoding="utf-8")
    return mpath


async def _collect(gen: Any, n: int, timeout: float = 5.0) -> list[dict[str, str]]:
    """Pull the next ``n`` events off the stream (bounded so a stall fails, not hangs)."""
    events: list[dict[str, str]] = []
    with anyio.fail_after(timeout):
        async for ev in gen:
            events.append(ev)
            if len(events) >= n:
                break
    return events


def test_snapshot_then_run_added(tmp_path: Path) -> None:
    _write_run(tmp_path, "runs", RUN_A)

    async def scenario() -> None:
        gen = _activity.activity_events(tmp_path, poll=0.02)
        (snap,) = await _collect(gen, 1)
        assert snap["event"] == "snapshot"
        assert json.loads(snap["data"])["runs"] == 1

        _write_run(tmp_path, "optim", RUN_B, command="optim_grid")
        (added,) = await _collect(gen, 1)
        assert added["event"] == "run_added"
        record = json.loads(added["data"])
        assert record["run_id"] == RUN_B
        assert record["kind"] == "optim"
        assert record["symbol"] == "SPY"
        await gen.aclose()

    anyio.run(scenario)


def test_run_updated_on_mtime_bump(tmp_path: Path) -> None:
    mpath = _write_run(tmp_path, "runs", RUN_A)

    async def scenario() -> None:
        gen = _activity.activity_events(tmp_path, poll=0.02)
        await _collect(gen, 1)  # snapshot
        os.utime(mpath, (time.time() + 5, time.time() + 5))
        (updated,) = await _collect(gen, 1)
        assert updated["event"] == "run_updated"
        assert json.loads(updated["data"])["run_id"] == RUN_A
        await gen.aclose()

    anyio.run(scenario)


def test_job_lifecycle_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_invoke, "JOBS", {})

    async def scenario() -> None:
        gen = _activity.activity_events(tmp_path, poll=0.02)
        await _collect(gen, 1)  # snapshot

        monkeypatch.setattr(_invoke, "_command", lambda args: ["python", "-c", "print('x')"])
        job = _invoke.launch(["info"], data_dir=tmp_path, run_type=None)
        (started,) = await _collect(gen, 1)
        assert started["event"] == "job_started"
        assert json.loads(started["data"])["job_id"] == job.job_id

        # ... and its terminal state (done) arrives once the subprocess exits
        (done,) = await _collect(gen, 1)
        assert done["event"] == "job_done"
        await gen.aclose()

    anyio.run(scenario)


def test_ignores_non_run_dirs_and_partial_writes(tmp_path: Path) -> None:
    (tmp_path / "runs" / "not-a-run").mkdir(parents=True)  # no manifest → invisible
    (tmp_path / "store").mkdir()

    async def scenario() -> None:
        gen = _activity.activity_events(tmp_path, poll=0.02)
        (snap,) = await _collect(gen, 1)
        assert json.loads(snap["data"])["runs"] == 0
        await gen.aclose()

    anyio.run(scenario)


def test_manifest_does_not_announce_missing_required_artifacts(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "optim",
        RUN_A,
        schema_version=1,
        command="optim_grid",
    )

    async def scenario() -> None:
        gen = _activity.activity_events(tmp_path, poll=0.02)
        (snap,) = await _collect(gen, 1)
        assert json.loads(snap["data"])["runs"] == 0
        await gen.aclose()

    anyio.run(scenario)


def test_stream_route_serves_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # max_events=1 bounds the otherwise-infinite stream so it can complete through a TestClient
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_run(tmp_path, "runs", RUN_A)
    client = TestClient(create_app())
    with client.stream("GET", "/api/activity/stream?poll=0.05&max_events=1") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    assert "event: snapshot" in body
    data_line = next(ln for ln in body.splitlines() if ln.startswith("data:"))
    assert json.loads(data_line.removeprefix("data:").strip())["runs"] == 1


def test_poll_clamped() -> None:
    assert _activity.clamp_poll(0.0) == 0.05
    assert _activity.clamp_poll(99.0) == 10.0
    assert _activity.clamp_poll(1.5) == 1.5
