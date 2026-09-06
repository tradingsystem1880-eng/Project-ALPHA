"""``/api/overlays/{symbol}`` — indicator/pattern overlays relayed from ``alpha chart``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from alpha_web import _candles, _catalog
from alpha_web.app import create_app
from tests.fixtures.cli_fixtures import seed_store


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)
    return TestClient(create_app())


def test_overlays_endpoint_relays_series_and_annotations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get(
        "/api/overlays/SPY",
        params=[("indicator", "sma:20"), ("indicator", "macd:12:26:9"), ("pattern", "swings")],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authority"] == "none" and len(body["t"]) == 90
    assert [s["id"] for s in body["indicators"]] == [
        "sma:20",
        "macd:12:26:9:line",
        "macd:12:26:9:signal",
        "macd:12:26:9:hist",
    ]
    assert body["indicators"][0]["values"][:19] == [None] * 19
    assert body["annotations"] and set(body["annotations"][0]) >= {"kind", "label", "anchors"}
    candles = client.get("/api/candles/SPY").json()
    assert [b["t"] for b in candles["bars"]] == body["t"]  # same PIT window, index-aligned


def test_overlays_endpoint_is_cached_on_the_parquet_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    real = _catalog._run_json

    def spy(args: list[str], **kwargs: Any) -> Any:
        calls.append(args)
        return real(args, **kwargs)

    monkeypatch.setattr(_candles, "_run_json", spy)
    for _ in range(2):
        assert client.get("/api/overlays/SPY", params={"indicator": "sma:5"}).status_code == 200
    assert len(calls) == 1 and calls[0][:3] == ["chart", "overlays", "SPY"]


def test_overlays_endpoint_maps_cli_errors_to_400(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    bad = client.get("/api/overlays/SPY", params={"indicator": "sma:500"})
    assert bad.status_code == 400 and "needs more than 500 bars" in bad.text
    assert client.get("/api/overlays/NOPE").status_code == 400
    assert client.get("/api/overlays/SPY", params={"pattern": "cups"}).status_code == 400
