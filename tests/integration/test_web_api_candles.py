"""``/api/candles/{symbol}`` — the workstation price feed (real ``alpha`` subprocess, offline)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_cli import paper_store
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


def test_candles_tail_returns_the_last_bars_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    full = client.get("/api/candles/SPY").json()["bars"]
    tail = client.get("/api/candles/SPY", params={"tail": 2}).json()["bars"]
    assert tail == full[-2:]
    assert len(client.get("/api/candles/SPY").json()["bars"]) == len(full)
    assert client.get("/api/candles/SPY", params={"tail": 0}).status_code == 422


def test_candles_endpoint_unknown_symbol_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _client(tmp_path, monkeypatch).get("/api/candles/NOPE").status_code == 404


def test_candles_include_low_volume_paper_order_and_fill_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    session = paper_store.create_session(
        tmp_path,
        provider="ibkr",
        symbol="SPY",
        instrument_id="SPY.ARCA",
        strategy="ts_momentum",
        strategy_params={},
        snapshot_id="spy",
        execution_mode="ibkr_paper",
        account_alias="DU1234567",
        risk_profile_id="ibkr-equity-paper-v1",
    )
    event_time = datetime(2020, 1, 10, 14, 30, tzinfo=UTC)
    paper_store.append_event(
        tmp_path,
        str(session["session_id"]),
        "fill",
        {"side": "BUY", "quantity": 1.0, "price": 101.5, "intent_id": "a" * 64},
        ts_event_ns=int(event_time.timestamp() * 1_000_000_000),
    )

    response = client.get("/api/candles/SPY")
    assert response.status_code == 200, response.text
    marker = response.json()["paper_markers"][0]
    assert marker["event_type"] == "fill"
    assert marker["execution_mode"] == "ibkr_paper"
    assert marker["exact_ts"] == int(event_time.timestamp())
