"""``alpha_web.app.main`` port resolution: env-configurable, loopback-only, fail-loud.

The serve port comes from ``ALPHA_WEB_PORT`` first, then ``PORT``, defaulting to 8801.
Invalid values raise :class:`alpha_core.AlphaError` naming the bad value; the host is
always ``127.0.0.1``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alpha_core import AlphaError
from alpha_web import app as web_app_module
from alpha_web.app import create_app, main


class RunCapture:
    """Stand-in for ``uvicorn.run`` that records every call's args/kwargs."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> None:
        self.calls.append((args, kwargs))

    def only_call(self) -> tuple[tuple[object, ...], dict[str, object]]:
        assert len(self.calls) == 1, f"expected exactly one uvicorn.run call, got {self.calls}"
        return self.calls[0]


@pytest.fixture
def run_capture(monkeypatch: pytest.MonkeyPatch) -> RunCapture:
    """Patch ``uvicorn.run`` and clear both port env vars for a deterministic base state."""
    capture = RunCapture()
    monkeypatch.setattr(uvicorn, "run", capture)
    monkeypatch.delenv("ALPHA_WEB_PORT", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    return capture


def test_default_port_is_8801_on_loopback(run_capture: RunCapture) -> None:
    main()
    args, kwargs = run_capture.only_call()
    assert isinstance(args[0], FastAPI)
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8801


def test_alpha_web_port_env_sets_port(
    run_capture: RunCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_WEB_PORT", "8899")
    main()
    _args, kwargs = run_capture.only_call()
    assert kwargs["port"] == 8899
    assert kwargs["host"] == "127.0.0.1"


def test_port_env_used_when_alpha_web_port_absent(
    run_capture: RunCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORT", "8901")
    main()
    _args, kwargs = run_capture.only_call()
    assert kwargs["port"] == 8901
    assert kwargs["host"] == "127.0.0.1"


def test_alpha_web_port_wins_over_port(
    run_capture: RunCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_WEB_PORT", "8899")
    monkeypatch.setenv("PORT", "8901")
    main()
    _args, kwargs = run_capture.only_call()
    assert kwargs["port"] == 8899
    assert kwargs["host"] == "127.0.0.1"


@pytest.mark.parametrize(("raw", "expected"), [("1", 1), ("65535", 65535)])
def test_port_range_bounds_are_valid(
    run_capture: RunCapture, monkeypatch: pytest.MonkeyPatch, raw: str, expected: int
) -> None:
    monkeypatch.setenv("ALPHA_WEB_PORT", raw)
    main()
    _args, kwargs = run_capture.only_call()
    assert kwargs["port"] == expected
    assert kwargs["host"] == "127.0.0.1"


@pytest.mark.parametrize("bad", ["abc", "0", "70000"])
def test_invalid_alpha_web_port_fails_loud(
    run_capture: RunCapture, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    monkeypatch.setenv("ALPHA_WEB_PORT", bad)
    with pytest.raises(AlphaError) as excinfo:
        main()
    message = str(excinfo.value)
    assert bad in message
    assert "ALPHA_WEB_PORT" in message
    assert run_capture.calls == []  # fail loud: the server never starts


def test_invalid_port_env_fails_loud(
    run_capture: RunCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORT", "70000")
    with pytest.raises(AlphaError) as excinfo:
        main()
    message = str(excinfo.value)
    assert "70000" in message
    assert "PORT" in message
    assert run_capture.calls == []


def test_large_json_responses_use_gzip() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json", headers={"accept-encoding": "gzip"})

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"


def test_loopback_ip_redirects_to_exact_localhost_origin() -> None:
    with TestClient(create_app(), base_url="http://127.0.0.1:8801") as client:
        response = client.get("/owner-auth/enroll?step=1", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:8801/owner-auth/enroll?step=1"


def test_canonical_origin_serves_health_and_owner_enrollment() -> None:
    with TestClient(create_app(), base_url="http://localhost:8801") as client:
        health = client.get("/healthz")
        enrollment = client.get("/owner-auth/enroll")
    assert health.json() == {"status": "ok"}
    assert enrollment.status_code == 200
    assert "text/html" in enrollment.headers["content-type"]


def test_missing_spa_fails_with_build_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_app_module, "_APP_INDEX", tmp_path / "not-built.html")
    with TestClient(create_app(), base_url="http://localhost:8801") as client:
        response = client.get("/owner-auth/enroll")
    assert response.status_code == 503
    assert "npm run build" in response.json()["message"]
