"""``/api/screener/*`` — 503 with setup instructions when the finnhub key is absent (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ALPHA_FINNHUB_API_KEY", raising=False)
    return TestClient(create_app())


def test_quote_unconfigured_is_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get("/api/screener/quote", params={"symbol": "AAPL"})
    assert resp.status_code == 503
    assert "ALPHA_FINNHUB_API_KEY" in resp.json()["detail"]


def test_news_unconfigured_is_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get("/api/screener/news", params={"symbol": "AAPL"})
    assert resp.status_code == 503
