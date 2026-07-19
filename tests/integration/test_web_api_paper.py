"""Read-only paper-session monitor API over the public CLI journal seam."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_cli import paper_store
from alpha_web.app import create_app

SESSION_ID = "7e19841c-8bb3-4ab8-aeed-388f56ecfcf8"


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def _seed(tmp_path: Path) -> None:
    paper_store.create_session(
        tmp_path,
        provider="binance",
        symbol="BTC/USDT",
        instrument_id="BTCUSDT.BINANCE",
        strategy="ts_momentum",
        strategy_params={"lookback": 126},
        snapshot_id="crypto-warmup",
        pid=1234,
        session_id=SESSION_ID,
        started_at=datetime.now(UTC),
    )
    paper_store.set_session_status(tmp_path, SESSION_ID, "running", pid=1234)
    paper_store.append_event(tmp_path, SESSION_ID, "order", {"id": "O-1"})
    paper_store.append_event(tmp_path, SESSION_ID, "fill", {"id": "O-1", "quantity": 0.1})


def test_list_detail_and_incremental_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path)
    client = _client(tmp_path, monkeypatch)

    listed = client.get("/api/paper/sessions")
    assert listed.status_code == 200
    assert listed.json()[0]["session_id"] == SESSION_ID
    assert listed.json()[0]["sandbox"] is True

    detail = client.get(f"/api/paper/sessions/{SESSION_ID}")
    assert detail.status_code == 200
    assert detail.json()["instrument_id"] == "BTCUSDT.BINANCE"
    assert detail.json()["last_sequence"] == 2

    page = client.get(f"/api/paper/sessions/{SESSION_ID}/events?after=1")
    assert page.status_code == 200
    assert [event["sequence"] for event in page.json()] == [2]
    assert page.json()[0]["event_type"] == "fill"


def test_unknown_and_malformed_session_ids_are_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    unknown = "65046900-74a8-4b52-89bb-5a2f7126fa7e"
    assert client.get(f"/api/paper/sessions/{unknown}").status_code == 404
    assert client.get("/api/paper/sessions/not-a-uuid").status_code == 422
    assert client.get("/api/paper/sessions/not-a-uuid/events").status_code == 422


def test_event_after_query_is_nonnegative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path)
    response = _client(tmp_path, monkeypatch).get(
        f"/api/paper/sessions/{SESSION_ID}/events?after=-1"
    )
    assert response.status_code == 422


def test_stale_heartbeat_is_reported_without_process_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale_id = "65046900-74a8-4b52-89bb-5a2f7126fa7e"
    paper_store.create_session(
        tmp_path,
        provider="binance",
        symbol="ETH/USDT",
        instrument_id="ETHUSDT.BINANCE",
        strategy="breakout",
        strategy_params={},
        snapshot_id="eth-warmup",
        pid=999_999,
        session_id=stale_id,
        started_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    response = _client(tmp_path, monkeypatch).get(f"/api/paper/sessions/{stale_id}")
    assert response.status_code == 200
    assert response.json()["stale"] is True
    assert response.json()["pid"] == 999_999
