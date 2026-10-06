"""Archive chart routes preserve exact selected identity and expose discovery status."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_cli import paper_store
from alpha_web import _candles
from alpha_web.api import candles as candle_api
from alpha_web.app import create_app


def test_archive_discovery_is_a_typed_cli_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    calls: list[list[str]] = []

    def project(args: list[str], **kwargs: object) -> dict[str, object]:
        calls.append(args)
        return {"datasets": [], "authority": "none", "state": "unconfigured"}

    monkeypatch.setattr(candle_api, "_run_json", project)
    response = TestClient(create_app()).get("/api/chart-datasets")
    assert response.status_code == 200
    assert response.json() == {"datasets": [], "authority": "none", "state": "unconfigured"}
    assert calls == [["data", "chart-datasets", "--json"]]


def test_archive_candles_forward_manifest_and_do_not_mix_paper_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    selected = "a" * 64
    calls: list[dict[str, object]] = []

    def project(symbol: str, **kwargs: object) -> dict[str, object]:
        calls.append({"symbol": symbol, **kwargs})
        return {"symbol": symbol, "bars": [{"t": 1, "o": 1, "h": 2, "l": 1, "c": 2, "v": 1}]}

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("archive read scanned canonical paper sessions")

    monkeypatch.setattr(_candles, "candles", project)
    monkeypatch.setattr(paper_store, "list_sessions", forbidden)
    result = candle_api.candles("BTCUSDT", manifest_id=selected)
    assert result["paper_markers"] == []
    assert calls[0]["manifest_id"] == selected
    assert calls[0]["symbol"] == "BTCUSDT"
