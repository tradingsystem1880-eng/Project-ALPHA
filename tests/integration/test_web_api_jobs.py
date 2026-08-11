"""The workstation job-lifecycle API (FastAPI TestClient, offline, fake fast command).

``_invoke._command`` is monkeypatched to a tiny ``python -c`` so launch / list / stream-replay /
cancel are exercised without the engine.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_cli.control_store import ControlStore
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
    assert detail["session_id"] is None
    assert detail["command_path"] == "info"
    assert detail["progress_mode"] == "terminal"
    assert detail["progress_fraction"] == 1.0
    assert detail["elapsed_seconds"] >= 0
    assert detail["finished_at"] is not None


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("research approve", "project-1 exploration --actor owner"),
        ("research", "reject project-1 exploration --actor owner --reason no"),
        ("", "research decide project-1 INCONCLUSIVE park --actor owner"),
        ("research run", "deep project-1"),
        ("", "research run confirm project-1"),
    ],
)
def test_generic_job_route_rejects_governed_research_commands_before_launch(
    command: str,
    args: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launched: list[list[str]] = []

    def fake_launch(argv: list[str], *, data_dir: Path, run_type: str | None) -> _invoke.Job:
        del data_dir
        launched.append(argv)
        return _invoke.Job(argv, run_type)

    monkeypatch.setattr(_invoke, "launch", fake_launch)
    response = TestClient(create_app()).post("/api/jobs", json={"command": command, "args": args})

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "governed research commands are unavailable through the generic job API; "
        "use the bounded research API or trusted-local CLI"
    )
    assert launched == []


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("research compare", "SPY"),
        ("research", "compare SPY"),
        ("", "research compare SPY"),
    ],
)
def test_generic_job_route_retains_legacy_research_compare(
    command: str,
    args: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launched: list[list[str]] = []

    def fake_launch(argv: list[str], *, data_dir: Path, run_type: str | None) -> _invoke.Job:
        del data_dir
        launched.append(argv)
        return _invoke.Job(argv, run_type)

    monkeypatch.setattr(_invoke, "launch", fake_launch)
    response = TestClient(create_app()).post("/api/jobs", json={"command": command, "args": args})

    assert response.status_code == 200, response.text
    assert launched == [["research", "compare", "SPY"]]


def test_running_job_estimate_uses_only_comparable_successful_session_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous = _invoke.Job(["forecast", "eval", "SPY", "--horizon", "21"], "forecast")
    previous.created_at = 100.0
    previous.finished_at = 220.0
    previous.finished = True
    previous.returncode = 0
    current = _invoke.Job(["forecast", "eval", "AMZN", "--horizon", "21"], "forecast")
    current.created_at = 300.0
    monkeypatch.setattr(_invoke, "JOBS", {previous.job_id: previous, current.job_id: current})

    summary = current.summary(now=360.0)

    assert summary["command_path"] == "forecast eval"
    assert summary["progress_mode"] == "estimated"
    assert summary["progress_fraction"] == pytest.approx(0.5)
    assert summary["eta_seconds"] == pytest.approx(60.0)
    assert summary["eta_sample_count"] == 1


def test_running_job_without_history_is_indeterminate_and_names_current_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _invoke.Job(["validate", "AAPL"], "runs")
    job.created_at = 100.0
    job._append("\x1b[32mloading causal artifacts\x1b[0m")
    monkeypatch.setattr(_invoke, "JOBS", {job.job_id: job})

    summary = job.summary(now=145.0)

    assert summary["progress_mode"] == "indeterminate"
    assert summary["progress_fraction"] is None
    assert summary["eta_seconds"] is None
    assert summary["elapsed_seconds"] == pytest.approx(45.0)
    assert summary["current_step"] == "loading causal artifacts"


def test_job_projects_paper_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = "7e19841c-8bb3-4ab8-aeed-388f56ecfcf8"
    _fake(monkeypatch, f"print('paper BTC/USDT -> session {session_id}: SANDBOX')")
    client = TestClient(create_app())
    job_id = client.post("/api/jobs", json={"command": "paper run", "args": "BTC/USDT"}).json()[
        "job_id"
    ]
    assert _wait_status(client, job_id, "done") == "done"
    assert client.get(f"/api/jobs/{job_id}").json()["session_id"] == session_id


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


def test_direct_kronos_launches_share_durable_atomic_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    priorities: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        os,
        "setpriority",
        lambda which, pid, priority: priorities.append((which, pid, priority)),
    )
    _fake(monkeypatch, "import time; print('started', flush=True); time.sleep(10)")
    client = TestClient(create_app())

    first = client.post("/api/jobs", json={"command": "forecast run", "args": "SPY --model fake"})
    assert first.status_code == 200, first.text
    job_id = first.json()["job_id"]
    durable = ControlStore(tmp_path).get_job(job_id)
    assert durable["kind"] == "kronos_forecast"
    assert durable["status"] == "running"
    process = _invoke.JOBS[job_id]._proc
    assert process is not None
    assert priorities == [(os.PRIO_PROCESS, process.pid, 10)]

    blocked = client.post("/api/jobs", json={"args": "forecast eval SPY --model fake"})
    assert blocked.status_code == 409, blocked.text
    assert "heavyweight job capacity is occupied" in blocked.json()["detail"]

    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert _wait_status(client, job_id, "cancelled") == "cancelled"
    assert ControlStore(tmp_path).get_job(job_id)["status"] == "cancelled"

    released = client.post("/api/jobs", json={"args": "forecast eval SPY --model fake"})
    assert released.status_code == 200, released.text
    released_job_id = released.json()["job_id"]
    assert client.delete(f"/api/jobs/{released_job_id}").status_code == 200
    assert _wait_status(client, released_job_id, "cancelled") == "cancelled"
