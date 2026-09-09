"""Thin data relays: snapshots and source-status are ``alpha data … --json`` subprocesses."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from alpha_web import _catalog
from alpha_web.app import create_app


def _capture(monkeypatch: pytest.MonkeyPatch, payload: object) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake(argv: list[str], **_kwargs: Any) -> object:
        calls.append(argv)
        return payload

    monkeypatch.setattr(_catalog, "_run_json", fake)
    return calls


def test_snapshots_relay(monkeypatch: pytest.MonkeyPatch) -> None:
    row = {
        "snapshot_id": "snap1",
        "created_at": "2026-01-01T00:00:00+00:00",
        "source": "tiingo",
        "adapter_version": "1",
        "parser_version": "1",
        "symbols": ["AAPL"],
        "manifest_sha256": "a" * 64,
    }
    calls = _capture(monkeypatch, {"snapshots": [row]})
    response = TestClient(create_app()).get("/api/data/snapshots")
    assert response.status_code == 200, response.text
    assert response.json() == {"snapshots": [row]}
    assert calls == [["data", "snapshots", "--json"]]


def test_source_status_relay_and_missing_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "symbol": "SPY",
        "provenance": {"source": "tiingo"},
        "promotion_pending": False,
        "candidates": [],
        "quarantined": ["tiingo:cand1"],
    }
    calls = _capture(monkeypatch, payload)
    client = TestClient(create_app())
    response = client.get("/api/data/source-status", params={"symbol": "SPY"})
    assert response.status_code == 200, response.text
    assert response.json() == payload
    assert calls == [["data", "source-status", "SPY", "--json"]]
    assert client.get("/api/data/source-status").status_code == 422


def test_source_status_relays_the_cli_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(argv: list[str], **_kwargs: Any) -> object:
        raise RuntimeError("Error: no provenance for NOPE")

    monkeypatch.setattr(_catalog, "_run_json", fail)
    response = TestClient(create_app()).get("/api/data/source-status", params={"symbol": "NOPE"})
    assert response.status_code == 422
    assert "no provenance for NOPE" in response.text
