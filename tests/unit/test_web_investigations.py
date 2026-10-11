"""Investigation routes reject broad inputs before dispatching CLI work."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alpha_web import _investigations, _invoke
from alpha_web.api import investigations


def test_mutations_require_same_origin_and_closed_input(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(investigations.router)
    client = TestClient(app, base_url="http://localhost:8801")
    calls: list[list[str]] = []

    def project(args: list[str]) -> object:
        calls.append(args)
        raise RuntimeError("unexpected dispatch")

    monkeypatch.setattr(investigations, "project", project)
    for origin in (None, "https://evil.example", "http://localhost:8802"):
        headers = {} if origin is None else {"origin": origin}
        assert (
            client.post(
                "/api/investigations",
                headers=headers,
                json={"run_id": "a" * 16, "question": "Why?"},
            ).status_code
            == 403
        )
    assert (
        client.post(
            "/api/investigations",
            headers={"origin": "http://localhost:8801"},
            json={"run_id": "a" * 16, "question": "Why?", "path": "/owner"},
        ).status_code
        == 422
    )
    assert calls == []


def test_eligibility_uses_closed_cli_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(investigations.router)
    monkeypatch.setattr(
        investigations,
        "project",
        lambda args: {"run_id": args[1], "eligible": False, "reason": "research cutoff missing"},
    )
    client = TestClient(app)
    response = client.get("/api/investigations/eligibility/" + "a" * 16)
    assert response.status_code == 200
    assert response.json()["eligible"] is False
    assert client.get("/api/investigations/not-an-id").status_code == 422


def test_turn_dispatch_is_closed_and_busy_job_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    app = FastAPI()
    app.include_router(investigations.router)
    client = TestClient(app, base_url="http://localhost:8801")
    launched: list[list[str]] = []
    monkeypatch.setattr(investigations, "show", lambda identifier: {})
    monkeypatch.setattr(_invoke, "JOBS", {})

    def launch(args: list[str], **kwargs: object) -> object:
        launched.append(args)
        return SimpleNamespace(job_id="test-job", status="running", session_id=None)

    monkeypatch.setattr(_invoke, "launch", launch)
    identifier = "b" * 32
    response = client.post(
        f"/api/investigations/{identifier}/turns",
        headers={"origin": "http://localhost:8801"},
        json={"followup": "Check costs"},
    )
    assert response.status_code == 200, response.text
    assert launched == [
        [
            "research",
            "investigations",
            "run",
            identifier,
            "--request",
            '{"followup": "Check costs"}',
        ]
    ]
    monkeypatch.setattr(
        _invoke,
        "JOBS",
        {
            "busy": SimpleNamespace(
                args=["research", "investigations", "acquire", identifier], status="running"
            )
        },
    )
    response = client.post(
        f"/api/investigations/{identifier}/turns",
        headers={"origin": "http://localhost:8801"},
        json={},
    )
    assert response.status_code == 409
    assert len(launched) == 1


def test_projection_error_does_not_disclose_paths_or_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise RuntimeError("private-path /owner/private token=secret")

    monkeypatch.setattr(_investigations, "project", fail)
    app = FastAPI()
    app.include_router(investigations.router)
    response = TestClient(app).get("/api/investigations/eligibility/" + "a" * 16)
    assert response.status_code == 422
    assert "private" not in response.text and "secret" not in response.text


def test_real_cli_case_roundtrip_and_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_investigation_workspace import root_with_run

    root = root_with_run(tmp_path)
    monkeypatch.setattr(investigations, "data_dir", lambda: root)
    app = FastAPI()
    app.include_router(investigations.router)
    client = TestClient(app, base_url="http://localhost:8801")
    response = client.get("/api/investigations/eligibility/1234567890abcdef")
    assert response.status_code == 200 and response.json()["eligible"]
    response = client.post(
        "/api/investigations",
        headers={"origin": "http://localhost:8801"},
        json={"run_id": "1234567890abcdef", "question": "Why this loss?"},
    )
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["status"] == "ready" and view["turns_remaining"] == 4
    identifier = view["id"]
    assert client.get(f"/api/investigations/{identifier}").json() == view
    assert client.get("/api/investigations?run_id=1234567890abcdef").json() == [view]
    (root / "runs/1234567890abcdef/equity_curve.parquet").write_bytes(b"tampered")
    assert client.get(f"/api/investigations/{identifier}").status_code == 422
