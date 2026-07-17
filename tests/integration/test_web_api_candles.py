"""``/api/candles/{symbol}`` — the workstation price feed (real ``alpha`` subprocess, offline)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app
from tests.fixtures.cli_fixtures import seed_store


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=20)
    return TestClient(create_app())


def test_candles_endpoint_returns_ohlcv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = _client(tmp_path, monkeypatch).get("/api/candles/SPY").json()
    assert body["symbol"] == "SPY" and len(body["bars"]) == 20
    assert set(body["bars"][0]) == {"t", "o", "h", "l", "c", "v"}


def test_candles_endpoint_unknown_symbol_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _client(tmp_path, monkeypatch).get("/api/candles/NOPE").status_code == 404
