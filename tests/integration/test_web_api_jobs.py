"""The workstation job-lifecycle API (FastAPI TestClient, offline, fake fast command).

``_invoke._command`` is monkeypatched to a tiny ``python -c`` so launch / list / stream-replay /
cancel are exercised without the engine.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from alpha_web import _invoke
from alpha_web.app import create_app


def _fake(monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    cmd: Callable[[list[str]], list[str]] = lambda args: ["python", "-c", script]  # noqa: E731
    monkeypatch.setattr(_invoke, "_command", cmd)


def _wait_status(client: TestClient, job_id: str, target: str, timeout: float = 5.0) -> str:
    end = time.time() + timeout
    status = ""
    while time.time() < end:
        status = str(client.get(f"/api/jobs/{job_id}").json()["status"])
        if status == target:
            return status
        time.sleep(0.02)
    return status


def _wait_line(client: TestClient, job_id: str, needle: str, timeout: float = 5.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if any(needle in ln for ln in client.get(f"/api/jobs/{job_id}").json()["lines"]):
            return
        time.sleep(0.02)
    raise AssertionError(f"line {needle!r} never appeared")


def test_launch_lists_and_gets(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, "print('hi from job')")
    client = TestClient(create_app())
    job_id = client.post("/api/jobs", json={"args": "info"}).json()["job_id"]
    assert _wait_status(client, job_id, "done") == "done"
    assert any(j["job_id"] == job_id for j in client.get("/api/jobs").json())
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert any("hi from job" in ln for ln in detail["lines"])


def test_launch_maps_run_type_and_parses_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, "print('validate SPY -> run 0123456789abcdef: PASS')")
    client = TestClient(create_app())
    job_id = client.post("/api/jobs", json={"command": "validate", "args": "SPY"}).json()["job_id"]
    _wait_status(client, job_id, "done")
    assert client.get(f"/api/jobs/{job_id}").json()["run_id"] == "0123456789abcdef"


def test_stream_replays_from_last_event_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, "print('L0'); print('L1'); print('L2')")
    client = TestClient(create_app())
    job_id = client.post("/api/jobs", json={"args": "info"}).json()["job_id"]
    _wait_status(client, job_id, "done")
    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers={"Last-Event-ID": "0"}) as r:
        body = "".join(r.iter_text())
    assert "L1" in body and "L2" in body and "L0" not in body  # only missed lines replayed


def test_cancel_running_job(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, "import time; print('started', flush=True); time.sleep(10)")
    client = TestClient(create_app())
    job_id = client.post("/api/jobs", json={"args": "sleep"}).json()["job_id"]
    _wait_line(client, job_id, "started")  # process is alive and in its own group
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert _wait_status(client, job_id, "cancelled") == "cancelled"


def test_cancel_unknown_is_404() -> None:
    assert TestClient(create_app()).delete("/api/jobs/nope").status_code == 404
