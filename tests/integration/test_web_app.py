"""The web IDE's read pages render stored runs (FastAPI TestClient, offline).

Hand-writes a run into a temp store and asserts the run browser, run detail (manifest + inline
equity SVG + embedded tear sheet), and the tear-sheet file route. The launcher/console slices have
their own tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app

_RUN_ID = "1111222233334444"


def _seed_run(data_dir: Path) -> None:
    rdir = data_dir / "runs" / _RUN_ID
    rdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "command": "validate",
        "run_id": _RUN_ID,
        "symbol": "SPY",
        "passed": True,
        "oos_metrics": {"sharpe": 0.81, "max_drawdown": -0.07},
        "verdict": {"overall": "B", "edge": "B", "robustness": "A", "risk": "C", "sample": "A"},
    }
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ts = [datetime(2020, 1, 1 + i, tzinfo=UTC) for i in range(5)]
    pl.DataFrame({"ts": ts, "equity": [1.0, 1.02, 1.01, 1.05, 1.04]}).write_parquet(
        rdir / "equity_curve.parquet"
    )
    (rdir / "tearsheet.html").write_text("<html><body>TEARSHEET-MARKER</body></html>")


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed_run(tmp_path)
    return TestClient(create_app())


def test_index_lists_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get("/")
    assert resp.status_code == 200
    assert _RUN_ID in resp.text and "validate" in resp.text and "SPY" in resp.text


def test_run_detail_renders_manifest_chart_and_tearsheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resp = _client(tmp_path, monkeypatch).get(f"/runs/{_RUN_ID}")
    assert resp.status_code == 200
    body = resp.text
    assert "<polyline" in body  # the inline equity SVG
    assert "sharpe" in body  # manifest metrics summarized
    assert f"/runs/{_RUN_ID}/tearsheet" in body  # embedded tear-sheet iframe


def test_run_detail_unknown_is_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _client(tmp_path, monkeypatch).get("/runs/deadbeefdeadbeef").status_code == 404


def test_tearsheet_route_serves_the_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get(f"/runs/{_RUN_ID}/tearsheet")
    assert resp.status_code == 200 and "TEARSHEET-MARKER" in resp.text
