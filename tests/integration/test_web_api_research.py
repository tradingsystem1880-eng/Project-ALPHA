"""``/api/research/compare`` — the AI Research leaderboard (real ``alpha`` subprocess, offline)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app
from tests.fixtures.cli_fixtures import seed_store


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_compare_endpoint_single_strategy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_store(tmp_path, symbol="SPY", n=400)
    resp = _client(tmp_path, monkeypatch).get(
        "/api/research/compare", params={"symbol": "SPY", "strategies": "ma_crossover"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "SPY"
    assert body["ranked"][0]["strategy"] == "ma_crossover"


def test_compare_no_bars_is_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get("/api/research/compare", params={"symbol": "NOPE"})
    assert resp.status_code == 422
