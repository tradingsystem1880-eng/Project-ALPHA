"""``/api/options/*`` — Black-Scholes analytics (real ``alpha`` subprocess, offline)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_greeks_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get(
        "/api/options/greeks", params={"spot": 100, "strike": 100, "vol": 0.2, "days": 365}
    )
    assert resp.status_code == 200
    assert resp.json()["price"] == pytest.approx(10.4506, abs=1e-3)


def test_curve_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get(
        "/api/options/curve", params={"strike": 100, "vol": 0.2, "points": 9}
    )
    assert resp.status_code == 200
    assert len(resp.json()["points"]) == 9


def test_bad_input_is_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get(
        "/api/options/greeks", params={"spot": 100, "strike": 100, "vol": -0.2}
    )
    assert resp.status_code == 422
