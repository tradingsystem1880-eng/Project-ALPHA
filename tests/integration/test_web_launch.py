"""The web IDE launches runs and streams their output live over SSE (offline, fake command).

`_invoke._command` is monkeypatched to a fast `python -c` so the launcher + SSE plumbing is tested
without the engine: POST a run, then tail `/jobs/{id}/stream` to completion.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from alpha_web import _invoke
from alpha_web.app import create_app


def _fake(monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    cmd: Callable[[list[str]], list[str]] = lambda args: ["python", "-c", script]  # noqa: E731
    monkeypatch.setattr(_invoke, "_command", cmd)


def _stream_text(client: TestClient, job_id: str) -> str:
    with client.stream("GET", f"/jobs/{job_id}/stream") as r:
        return "".join(r.iter_text())


def test_new_and_console_pages_render() -> None:
    client = TestClient(create_app(), base_url="http://127.0.0.1")
    assert client.get("/new").status_code == 200
    assert client.get("/console").status_code == 200


def test_console_run_launches_and_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, "print('hello from alpha')")
    client = TestClient(create_app(), base_url="http://127.0.0.1")
    resp = client.post("/console/run", data={"args": "info"})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    body = _stream_text(client, job_id)
    assert "hello from alpha" in body and "done" in body


def test_structured_run_streams_and_links_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, "print('validate SPY -> run 0123456789abcdef: PASS')")
    client = TestClient(create_app(), base_url="http://127.0.0.1")
    resp = client.post("/runs", data={"command": "validate", "args": "SPY"})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    body = _stream_text(client, job_id)
    assert "0123456789abcdef" in body  # the parsed run id rides the terminal `done` event


def test_stream_unknown_job_is_404() -> None:
    assert TestClient(create_app(), base_url="http://127.0.0.1").get("/jobs/nope/stream").status_code == 404
