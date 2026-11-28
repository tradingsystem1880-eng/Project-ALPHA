"""The live-desk activity stream scans the run store and data areas in a worker thread.

One SSE connection must not block the web server's event loop while ``snapshot_runs`` and
``snapshot_areas`` walk the disk; the event sequence a client sees stays the same.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import anyio
import pytest

from alpha_web import _activity

RUN_B = "bbbbbbbbbbbbbbbb"


def _write_run(data_dir: Path, kind: str, run_id: str, **extra: Any) -> Path:
    rdir = data_dir / kind / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    mpath = rdir / "manifest.json"
    mpath.write_text(json.dumps({"run_id": run_id, "symbol": "SPY", **extra}), encoding="utf-8")
    return mpath


def _record_scan_threads(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, threading.Thread]]:
    calls: list[tuple[str, threading.Thread]] = []
    real_runs = _activity.snapshot_runs
    real_areas = _activity.snapshot_areas

    def runs(data_dir: Path) -> dict[tuple[str, str], float]:
        calls.append(("runs", threading.current_thread()))
        return real_runs(data_dir)

    def areas(data_dir: Path) -> dict[str, float]:
        calls.append(("areas", threading.current_thread()))
        return real_areas(data_dir)

    monkeypatch.setattr(_activity, "snapshot_runs", runs)
    monkeypatch.setattr(_activity, "snapshot_areas", areas)
    return calls


async def _snapshot_then_one_tick(data_dir: Path) -> tuple[list[dict[str, str]], threading.Thread]:
    """Snapshot, then one tick that sees a new run and a changed data area."""
    loop_thread = threading.current_thread()
    events: list[dict[str, str]] = []
    gen = _activity.activity_events(data_dir, poll=0.02, max_events=3)
    with anyio.fail_after(5.0):
        async for ev in gen:
            events.append(ev)
            if len(events) == 1:
                # the generator is suspended here: both changes land in the same next tick
                _write_run(data_dir, "optim", RUN_B, command="optim_grid")
                card = data_dir / "ideas" / "card.toml"
                card.parent.mkdir(parents=True, exist_ok=True)
                card.write_text("x", encoding="utf-8")
    return events, loop_thread


def _check_sequence(events: list[dict[str, str]]) -> None:
    assert [ev["event"] for ev in events] == ["snapshot", "run_added", "store_changed"]
    assert json.loads(events[0]["data"])["runs"] == 0
    assert json.loads(events[1]["data"])["run_id"] == RUN_B
    assert json.loads(events[2]["data"])["area"] == "ideas"


def test_snapshot_then_tick_event_sequence_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _record_scan_threads(monkeypatch)
    result: dict[str, Any] = {}

    async def scenario() -> None:
        result["events"], _ = await _snapshot_then_one_tick(tmp_path)

    anyio.run(scenario)
    _check_sequence(result["events"])
    kinds = [kind for kind, _ in calls]
    assert kinds.count("runs") >= 2
    assert kinds.count("areas") >= 2


def test_store_scans_run_off_the_event_loop_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _record_scan_threads(monkeypatch)
    result: dict[str, Any] = {}

    async def scenario() -> None:
        result["events"], result["loop"] = await _snapshot_then_one_tick(tmp_path)

    anyio.run(scenario)
    _check_sequence(result["events"])
    assert {kind for kind, _ in calls} == {"runs", "areas"}
    on_loop = [kind for kind, thread in calls if thread is result["loop"]]
    assert on_loop == [], f"store scans ran on the event loop thread: {on_loop}"
