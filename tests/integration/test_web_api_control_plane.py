"""Provider/system control-plane HTTP projections remain redacted and local-only."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app


def test_provider_api_is_registry_derived_and_redacts_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_FINNHUB_API_KEY", "never-return-this-secret")
    response = TestClient(create_app()).get("/api/providers")

    assert response.status_code == 200
    providers = response.json()
    by_id = {provider["id"]: provider for provider in providers}
    assert {"yfinance", "ccxt", "stooq", "finnhub", "binance"} <= set(by_id)
    assert by_id["ccxt"]["options"]["exchange"]["choices"] == ["coinbase", "binance"]
    assert by_id["finnhub"]["credential_env"] == [
        {"name": "ALPHA_FINNHUB_API_KEY", "present": True}
    ]
    assert "never-return-this-secret" not in response.text


def test_system_api_reports_local_readiness_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "false")
    response = TestClient(create_app()).get("/api/system")

    assert response.status_code == 200
    status = response.json()
    assert status["data_dir"]["path"] == str(tmp_path)
    assert status["counts"] == {"symbols": 0, "snapshots": 0}
    assert status["nautilus"]["pinned_version"] == "1.228.0"
    assert status["paper_enabled"] is False
