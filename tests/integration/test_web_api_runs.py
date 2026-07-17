"""The workstation JSON API over the run store (FastAPI TestClient, offline).

Seeds several runs of different kinds into a temp store and asserts the ``/api/runs`` index
(filter / paginate / mtime-order), the run-detail endpoint (manifest + artifact flags), and the
equity / trades / forecast JSON projections. Mirrors ``tests/integration/test_web_app.py``.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app


def _write_run(
    data_dir: Path,
    kind: str,
    run_id: str,
    manifest: dict[str, object],
    *,
    equity: list[float] | None = None,
    trades: list[dict[str, object]] | None = None,
    tearsheet: bool = False,
) -> None:
    rdir = data_dir / kind / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if equity is not None:
        ts = [datetime(2020, 1, 1 + i, tzinfo=UTC) for i in range(len(equity))]
        pl.DataFrame({"ts": ts, "equity": equity}).write_parquet(rdir / "equity_curve.parquet")
    if trades is not None:
        pl.DataFrame(trades).write_parquet(rdir / "trades.parquet")
    if tearsheet:
        (rdir / "tearsheet.html").write_text("<html><body>TS</body></html>")
    # make mtime deterministic & ordered by run_id suffix so the newest-first assertion is stable
    order = int(run_id[-1])
    stamp = time.time() + order
    os.utime(rdir / "manifest.json", (stamp, stamp))


def _seed(data_dir: Path) -> None:
    _write_run(
        data_dir,
        "runs",
        "aaaa000000000001",
        {"command": "backtest_run", "symbol": "SPY", "passed": True},
        equity=[100.0, 101.0, 99.5, 103.0],
        trades=[
            {
                "instrument_id": "SPY.SIM",
                "side": "BUY",
                "quantity": 10.0,
                "entry_price": 100.0,
                "exit_price": 103.0,
                "entry_ts": datetime(2020, 1, 1, tzinfo=UTC),
                "exit_ts": datetime(2020, 1, 4, tzinfo=UTC),
                "realized_pnl": 30.0,
                "realized_return": 0.03,
            }
        ],
        tearsheet=True,
    )
    _write_run(
        data_dir,
        "runs",
        "bbbb000000000002",
        {
            "run_id": "bbbb000000000002",
            "symbol": "AAPL",
            "passed": False,
            "verdict": {"overall": "D"},
        },
    )
    _write_run(data_dir, "optim", "cccc000000000003", {"command": "optim_grid", "symbol": "SPY"})


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed(tmp_path)
    return TestClient(create_app())


def test_runs_index_lists_all_kinds_newest_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = _client(tmp_path, monkeypatch).get("/api/runs").json()
    assert body["total"] == 3
    ids = [r["run_id"] for r in body["items"]]
    assert set(ids) == {"aaaa000000000001", "bbbb000000000002", "cccc000000000003"}
    # newest (largest mtime, suffix 3) first
    assert ids[0] == "cccc000000000003"
    first = next(r for r in body["items"] if r["run_id"] == "aaaa000000000001")
    assert first["kind"] == "runs"
    assert first["label"] == "SPY"
    assert first["command"] == "backtest_run"


def test_runs_index_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert {r["run_id"] for r in client.get("/api/runs?kind=optim").json()["items"]} == {
        "cccc000000000003"
    }
    assert {r["run_id"] for r in client.get("/api/runs?symbol=AAPL").json()["items"]} == {
        "bbbb000000000002"
    }
    assert {r["run_id"] for r in client.get("/api/runs?passed=true").json()["items"]} == {
        "aaaa000000000001"
    }
    assert {r["run_id"] for r in client.get("/api/runs?verdict=D").json()["items"]} == {
        "bbbb000000000002"
    }


def test_runs_index_paginates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = _client(tmp_path, monkeypatch).get("/api/runs?limit=1&offset=1").json()
    assert body["total"] == 3 and len(body["items"]) == 1


def test_run_detail_has_manifest_and_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = _client(tmp_path, monkeypatch).get("/api/runs/aaaa000000000001").json()
    assert body["manifest"]["symbol"] == "SPY"
    assert body["kind"] == "runs"
    assert body["has_equity"] and body["has_trades"] and body["has_tearsheet"]
    assert body["has_forecast"] is False


def test_run_detail_unknown_is_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _client(tmp_path, monkeypatch).get("/api/runs/deadbeefdeadbeef").status_code == 404


def test_equity_endpoint_returns_ts_equity_drawdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = _client(tmp_path, monkeypatch).get("/api/runs/aaaa000000000001/equity").json()
    assert body["equity"] == [100.0, 101.0, 99.5, 103.0]
    assert len(body["ts"]) == 4
    # drawdown: 0, 0, (99.5/101 - 1), 0
    assert body["drawdown"][0] == 0.0 and body["drawdown"][-1] == 0.0
    assert body["drawdown"][2] == pytest.approx(99.5 / 101.0 - 1.0)


def test_trades_endpoint_returns_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _client(tmp_path, monkeypatch).get("/api/runs/aaaa000000000001/trades").json()
    assert len(rows) == 1 and rows[0]["side"] == "BUY"
    assert isinstance(rows[0]["entry_ts"], str)  # datetime serialized to ISO


def test_trades_endpoint_empty_without_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _client(tmp_path, monkeypatch).get("/api/runs/cccc000000000003/trades").json() == []


def _write_forecast_run(data_dir: Path, run_id: str) -> None:
    """A forecast run's cone artifacts: the CLI's ``quantiles.parquet`` + ``history.parquet``."""
    rdir = data_dir / "forecast" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(
        json.dumps({"command": "forecast_run", "symbol": "BTC-USD"}), encoding="utf-8"
    )
    t0 = datetime(2026, 6, 1, tzinfo=UTC)
    pl.DataFrame(
        {
            "step": [1, 2, 3],
            "ts": [datetime(2026, 6, 2 + i, tzinfo=UTC) for i in range(3)],
            "q05": [95.0, 93.0, 91.0],
            "q25": [99.0, 98.0, 97.0],
            "q50": [101.0, 102.0, 103.0],
            "q75": [104.0, 106.0, 108.0],
            "q95": [109.0, 112.0, 115.0],
            "mean": [100.9, 102.1, 103.2],
        }
    ).write_parquet(rdir / "quantiles.parquet")
    pl.DataFrame({"ts": [t0], "close": [100.0]}).write_parquet(rdir / "history.parquet")


def test_forecast_endpoint_reads_the_cone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_forecast_run(tmp_path, "ffff000000000009")
    client = TestClient(create_app())
    assert client.get("/api/runs/ffff000000000009").json()["has_forecast"] is True
    body = client.get("/api/runs/ffff000000000009/forecast").json()
    assert body["history"] == [100.0]
    assert body["forecast"] == [101.0, 102.0, 103.0]  # q50 median line
    assert body["p10"] == [95.0, 93.0, 91.0] and body["p90"] == [109.0, 112.0, 115.0]  # q05..q95
    assert len(body["forecast_ts"]) == 3


def test_forecast_endpoint_404_for_non_forecast_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        _client(tmp_path, monkeypatch).get("/api/runs/aaaa000000000001/forecast").status_code == 404
    )
