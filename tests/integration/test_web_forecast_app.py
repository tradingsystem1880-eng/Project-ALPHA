"""Run-detail renders the forecast cone (TestClient, offline; artifacts hand-written)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app

_RUN_ID = "feedbeeffeedbeef"


def _seed_forecast_run(data_dir: Path) -> None:
    rdir = data_dir / "forecast" / _RUN_ID
    rdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "command": "forecast_run",
        "run_id": _RUN_ID,
        "symbol": "BTC-USD",
        "model": {"model_id": "fake", "determinism": "exact"},
        "pretrain": {"overlap": True, "cutoff": "2025-08-02"},
        "summary": {"prob_up": 0.61, "median_end_return": 0.021},
    }
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    t0 = datetime(2026, 6, 1, tzinfo=UTC)
    pl.DataFrame(
        {
            "step": [1, 2, 3],
            "ts": [t0 + timedelta(days=i + 1) for i in range(3)],
            "q05": [95.0, 93.0, 91.0],
            "q25": [99.0, 98.0, 97.0],
            "q50": [101.0, 102.0, 103.0],
            "q75": [104.0, 106.0, 108.0],
            "q95": [109.0, 112.0, 115.0],
            "mean": [100.9, 102.1, 103.2],
        }
    ).write_parquet(rdir / "quantiles.parquet")
    pl.DataFrame(
        {
            "ts": [t0 - timedelta(days=4 - i) for i in range(4)],
            "close": [97.0, 98.0, 99.0, 100.0],
        }
    ).write_parquet(rdir / "history.parquet")


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed_forecast_run(tmp_path)
    return TestClient(create_app(), base_url="http://127.0.0.1")


def test_run_detail_renders_forecast_cone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get(f"/runs/{_RUN_ID}")
    assert resp.status_code == 200
    body = resp.text
    assert "Forecast cone" in body
    assert "<polygon" in body  # quantile bands
    assert "pretraining" in body  # the overlap caveat is rendered


def test_index_lists_the_forecast_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get("/")
    assert resp.status_code == 200
    assert _RUN_ID in resp.text and "forecast_run" in resp.text and "BTC-USD" in resp.text


def test_new_run_form_lists_forecast_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resp = _client(tmp_path, monkeypatch).get("/new")
    assert resp.status_code == 200
    assert "forecast run" in resp.text
