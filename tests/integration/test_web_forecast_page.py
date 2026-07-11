"""The web IDE renders a forecast run: chart with dashed forecast + leakage warning."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app

_RUN_ID = "aaaa1111bbbb2222"


def _seed_forecast_run(data_dir: Path, *, with_band: bool = True) -> None:
    rdir = data_dir / "forecast" / _RUN_ID
    rdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "command": "forecast_run",
        "run_id": _RUN_ID,
        "symbol": "SPY",
        "model": {"name": "base"},
        "params": {"horizon": 3, "context": 4},
        "forecast": {"end_close": 106.0, "expected_log_return": 0.02, "direction": 1},
        "leakage_warning": "WARNING: weight-level look-ahead ... UPPER BOUND ...",
    }
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ts = [datetime(2026, 1, 5 + i, tzinfo=UTC) for i in range(4)]
    pl.DataFrame(
        {
            "ts": ts,
            "open": [100.0] * 4,
            "high": [101.0] * 4,
            "low": [99.0] * 4,
            "close": [100.0, 101.0, 102.0, 103.0],
            "volume": [1.0] * 4,
        }
    ).write_parquet(rdir / "history.parquet")
    fts = [datetime(2026, 1, 9 + i, tzinfo=UTC) for i in range(3)]
    fdata = {
        "ts": fts,
        "open": [104.0] * 3,
        "high": [107.0] * 3,
        "low": [103.0] * 3,
        "close": [104.0, 105.0, 106.0],
        "volume": [1.0] * 3,
    }
    if with_band:
        fdata["close_p10"] = [102.0, 102.5, 103.0]
        fdata["close_p90"] = [106.0, 107.0, 108.0]
    pl.DataFrame(fdata).write_parquet(rdir / "forecast.parquet")


def test_run_browser_lists_forecast_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed_forecast_run(tmp_path)
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    assert _RUN_ID in r.text
    assert "forecast_run" in r.text


def test_run_detail_renders_forecast_chart_and_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed_forecast_run(tmp_path)
    client = TestClient(create_app())
    r = client.get(f"/runs/{_RUN_ID}")
    assert r.status_code == 200
    assert "Forecast" in r.text
    assert 'stroke-dasharray="4 3"' in r.text  # dashed forecast continuation
    assert "<polygon" in r.text  # p10/p90 band
    assert "UPPER BOUND" in r.text  # leakage warning surfaced


def test_new_run_form_offers_forecast_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())
    r = client.get("/new")
    assert r.status_code == 200
    assert "forecast run" in r.text
