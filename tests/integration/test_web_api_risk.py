"""``/api/risk/scenario`` — stress a stored run (real ``alpha`` subprocess, offline)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app


def _seed_run(data_dir: Path, run_id: str, n: int = 150) -> None:
    rdir = data_dir / "runs" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text('{"command": "backtest_run"}', encoding="utf-8")
    rng = np.random.default_rng(1)
    equity = 1_000_000.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.01, n))
    ts = [datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(n)]
    pl.DataFrame({"ts": ts, "equity": equity.tolist()}).write_parquet(rdir / "equity_curve.parquet")


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_scenario_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_run(tmp_path, "1111222233334444")
    resp = _client(tmp_path, monkeypatch).get(
        "/api/risk/scenario", params={"run_id": "1111222233334444"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "1111222233334444"
    assert [s["name"] for s in body["scenarios"]][0] == "base"


def test_run_without_equity_is_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rdir = tmp_path / "optim" / "5555666677778888"
    rdir.mkdir(parents=True)
    (rdir / "manifest.json").write_text('{"command": "optim_grid"}', encoding="utf-8")
    resp = _client(tmp_path, monkeypatch).get(
        "/api/risk/scenario", params={"run_id": "5555666677778888"}
    )
    assert resp.status_code == 422


def test_unknown_run_is_404_and_confidence_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/risk/scenario?run_id=deadbeefdeadbeef").status_code == 404
    _seed_run(tmp_path, "1111222233334444")
    assert client.get("/api/risk/scenario?run_id=1111222233334444&confidence=1").status_code == 422
