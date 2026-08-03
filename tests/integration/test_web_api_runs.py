"""The workstation JSON API over the run store (FastAPI TestClient, offline).

Seeds several runs of different kinds into a temp store and asserts the ``/api/runs`` index
(filter / paginate / mtime-order), the run-detail endpoint (manifest + artifact flags), and the
equity / trades / forecast JSON projections. Mirrors ``tests/integration/test_web_app.py``.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from alpha_cli import run_projection
from alpha_cli.artifact_contract import artifact_contract
from alpha_web import _runs
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
        {
            "command": "backtest_run",
            "symbol": "SPY",
            "snapshot_id": "snapshot-2020-01",
            "snapshot_hash": "a" * 64,
            "passed": True,
        },
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
    assert first["snapshot_id"] == "snapshot-2020-01"
    assert first["snapshot_hash"] == "a" * 64


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


def test_native_tearsheet_endpoint_is_typed_and_legacy_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    legacy = client.get("/api/runs/aaaa000000000001/native-tearsheet")
    assert legacy.status_code == 200
    assert legacy.json()["available"] is False

    from alpha_cli._native_tearsheet import native_tearsheet_frames

    rdir = tmp_path / "runs" / "aaaa000000000001"
    start = datetime(2020, 1, 1, tzinfo=UTC)
    equity = [(datetime(2020, 1, 1 + i, tzinfo=UTC), 100.0 + i) for i in range(4)]
    for filename, frame in native_tearsheet_frames(equity, periods_per_year=252).items():
        frame.write_parquet(rdir / filename)

    body = client.get("/api/runs/aaaa000000000001/native-tearsheet").json()
    assert body["available"] is True
    assert body["calendar_returns"][0]["year"] == start.year
    assert body["yearly_returns"][0]["year"] == start.year
    assert len(body["histogram"]) == 20
    assert len(body["qq"]) == 3
    assert body["provenance"]["metric_namespace"] == "alpha_validation"


def test_native_tearsheet_projection_is_bounded_and_preserves_endpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    from alpha_cli._native_tearsheet import native_tearsheet_frames

    rdir = tmp_path / "runs" / "aaaa000000000001"
    start = datetime(2020, 1, 1, tzinfo=UTC)
    equity = [(start + timedelta(days=index), 100.0 * (1.0005**index)) for index in range(300)]
    for filename, frame in native_tearsheet_frames(equity, periods_per_year=252).items():
        frame.write_parquet(rdir / filename)

    direct = _runs.native_tearsheet(
        "aaaa000000000001",
        data_dir=tmp_path,
        point_limit=10,
    )
    assert len(direct["qq"]) == 10
    assert len(direct["rolling"]) == 10
    assert len(direct["exposure_turnover"]) == 10
    assert len(direct["benchmark"]) == 10
    assert direct["bounds"]["qq"] == {
        "original": 299,
        "returned": 10,
        "truncated": True,
        "sampling": "endpoint_uniform",
    }
    assert direct["rolling"][0]["ts"] < direct["rolling"][-1]["ts"]
    assert direct["benchmark"][0]["ts"] == start.timestamp()
    assert direct["benchmark"][-1]["ts"] == (start + timedelta(days=299)).timestamp()

    response = client.get("/api/runs/aaaa000000000001/native-tearsheet?point_limit=10")
    assert response.status_code == 200
    assert response.json()["bounds"] == direct["bounds"]
    assert (
        client.get("/api/runs/aaaa000000000001/native-tearsheet?point_limit=1").status_code == 422
    )
    assert (
        client.get("/api/runs/aaaa000000000001/native-tearsheet?point_limit=5001").status_code
        == 422
    )


def test_trades_endpoint_returns_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _client(tmp_path, monkeypatch).get("/api/runs/aaaa000000000001/trades").json()
    assert len(rows) == 1 and rows[0]["side"] == "BUY"
    assert isinstance(rows[0]["entry_ts"], str)  # datetime serialized to ISO


def test_trades_endpoint_empty_without_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _client(tmp_path, monkeypatch).get("/api/runs/cccc000000000003/trades").json() == []


def test_optional_series_are_404_for_unknown_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    unknown = "deadbeefdeadbeef"
    assert client.get(f"/api/runs/{unknown}/equity").status_code == 404
    assert client.get(f"/api/runs/{unknown}/trades").status_code == 404


def test_run_pagination_bounds_are_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    for query in ("limit=0", "limit=501", "offset=-1", "offset=1000001"):
        assert client.get(f"/api/runs?{query}").status_code == 422


def _write_returns_equity(data_dir: Path, kind: str, run_id: str, returns: list[float]) -> None:
    """Seed a portfolio/cross-sectional run's ``equity_curve.parquet`` (N+1 rows, base 1.0)."""
    rdir = data_dir / kind / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(
        json.dumps({"command": f"{kind}_run", "symbols": ["SPY", "TLT"]}), encoding="utf-8"
    )
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1.0 + r))
    ts = [datetime(2020, 1, 1 + i, tzinfo=UTC) for i in range(len(equity))]
    pl.DataFrame(
        {"ts": ts, "equity": equity},
        schema={"ts": pl.Datetime(time_unit="us", time_zone="UTC"), "equity": pl.Float64()},
    ).write_parquet(rdir / "equity_curve.parquet")


@pytest.mark.parametrize("kind", ["portfolio", "cross_sectional"])
def test_equity_endpoint_serves_returns_level_curves(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase-6 portfolio/cross-sectional curves flow through the same equity projection."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_returns_equity(tmp_path, kind, "dddd000000000004", [0.01, -0.02, 0.03])
    client = TestClient(create_app())
    body = client.get("/api/runs/dddd000000000004/equity").json()
    assert body["equity"][0] == 1.0 and len(body["equity"]) == 4
    assert body["equity"][1] == pytest.approx(1.01)
    assert body["equity"][3] == pytest.approx(1.01 * 0.98 * 1.03)
    assert len(body["ts"]) == 4 and body["ts"] == sorted(body["ts"])
    assert body["drawdown"][2] == pytest.approx(0.98 - 1.0)


def _write_forecast_run(
    data_dir: Path, run_id: str, *, n_samples: int = 0, complete_history: bool = False
) -> None:
    """A forecast run's cone artifacts: the CLI's ``quantiles.parquet`` + ``history.parquet``.

    With ``n_samples > 0`` also writes ``paths.parquet`` (per-sample OHLCV, long) with
    ``close = 100 + sample + step`` so per-sample assertions are trivial.
    """
    rdir = data_dir / "forecast" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(
        json.dumps({"command": "forecast_run", "symbol": "BTC-USD"}), encoding="utf-8"
    )
    t0 = datetime(2026, 6, 1, tzinfo=UTC)
    step_ts = [datetime(2026, 6, 2 + i, tzinfo=UTC) for i in range(3)]
    pl.DataFrame(
        {
            "step": [1, 2, 3],
            "ts": step_ts,
            "q05": [95.0, 93.0, 91.0],
            "q25": [99.0, 98.0, 97.0],
            "q50": [101.0, 102.0, 103.0],
            "q75": [104.0, 106.0, 108.0],
            "q95": [109.0, 112.0, 115.0],
            "mean": [100.9, 102.1, 103.2],
        }
    ).write_parquet(rdir / "quantiles.parquet")
    history = {"ts": [t0], "close": [100.0]}
    if complete_history:
        history.update({"open": [99.0], "high": [102.0], "low": [98.0], "volume": [1_234.0]})
    pl.DataFrame(history).write_parquet(rdir / "history.parquet")
    if n_samples:
        pl.DataFrame(
            [
                {
                    "sample": s,
                    "step": i + 1,
                    "ts": step_ts[i],
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0 + s + (i + 1),
                    "volume": 1.0,
                }
                for s in range(n_samples)
                for i in range(3)
            ]
        ).write_parquet(rdir / "paths.parquet")


def test_forecast_endpoint_reads_the_cone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_forecast_run(tmp_path, "ffff000000000009")
    client = TestClient(create_app())
    assert client.get("/api/runs/ffff000000000009").json()["has_forecast"] is True
    body = client.get("/api/runs/ffff000000000009/forecast").json()
    assert body["history"] == [100.0]
    assert body["history_bars"] == []
    assert body["history_ohlcv_available"] is False
    assert body["forecast"] == [101.0, 102.0, 103.0]  # q50 median line
    assert body["p10"] == [95.0, 93.0, 91.0]
    assert body["p90"] == [109.0, 112.0, 115.0]
    assert "q05" not in body and "q95" not in body  # established wire keys stay stable
    assert len(body["forecast_ts"]) == 3


def test_forecast_endpoint_replays_frozen_complete_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """New runs serve observed candles from their artifact, never the mutable candle endpoint."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_forecast_run(tmp_path, "ffff000000000009", complete_history=True)
    body = TestClient(create_app()).get("/api/runs/ffff000000000009/forecast").json()
    assert body["history_ohlcv_available"] is True
    assert body["history_bars"] == [
        {
            "t": datetime(2026, 6, 1, tzinfo=UTC).timestamp(),
            "o": 99.0,
            "h": 102.0,
            "l": 98.0,
            "c": 100.0,
            "v": 1_234.0,
        }
    ]


def test_forecast_endpoint_404_for_non_forecast_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        _client(tmp_path, monkeypatch).get("/api/runs/aaaa000000000001/forecast").status_code == 404
    )


def test_forecast_endpoint_includes_full_quantiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cone response carries q25/q75/mean alongside the pre-existing SPA keys."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_forecast_run(tmp_path, "ffff000000000009")
    body = TestClient(create_app()).get("/api/runs/ffff000000000009/forecast").json()
    assert body["q25"] == [99.0, 98.0, 97.0]
    assert body["q75"] == [104.0, 106.0, 108.0]
    assert body["mean"] == [100.9, 102.1, 103.2]
    # the pre-existing keys are untouched — the SPA fan chart depends on them
    assert body["history"] == [100.0] and body["forecast"] == [101.0, 102.0, 103.0]
    assert body["p10"] == [95.0, 93.0, 91.0] and body["p90"] == [109.0, 112.0, 115.0]
    assert len(body["history_ts"]) == 1 and len(body["forecast_ts"]) == 3


def test_forecast_paths_returns_first_n_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_forecast_run(tmp_path, "ffff000000000009", n_samples=5)
    client = TestClient(create_app())
    body = client.get("/api/runs/ffff000000000009/forecast/paths?n=3").json()
    assert [s["sample"] for s in body["samples"]] == [0, 1, 2]  # first n, deterministic
    assert body["samples"][0]["opens"] == [100.0, 100.0, 100.0]
    assert body["samples"][0]["highs"] == [101.0, 101.0, 101.0]
    assert body["samples"][0]["lows"] == [99.0, 99.0, 99.0]
    assert body["samples"][0]["closes"] == [101.0, 102.0, 103.0]  # 100 + sample + step
    assert body["samples"][0]["volumes"] == [1.0, 1.0, 1.0]
    assert body["samples"][2]["closes"] == [103.0, 104.0, 105.0]
    assert len(body["ts"]) == 3 and body["ts"] == sorted(body["ts"])


def test_forecast_paths_default_and_bounds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_forecast_run(tmp_path, "ffff000000000009", n_samples=50)
    client = TestClient(create_app())
    assert len(client.get("/api/runs/ffff000000000009/forecast/paths").json()["samples"]) == 20
    assert client.get("/api/runs/ffff000000000009/forecast/paths?n=45").status_code == 422
    assert client.get("/api/runs/ffff000000000009/forecast/paths?n=0").status_code == 422


def test_forecast_paths_404_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_forecast_run(tmp_path, "ffff000000000009")  # cone only, no paths.parquet
    _seed(tmp_path)
    client = TestClient(create_app())
    assert client.get("/api/runs/ffff000000000009/forecast/paths").status_code == 404
    assert client.get("/api/runs/aaaa000000000001/forecast/paths").status_code == 404


def _write_trace_run(data_dir: Path, run_id: str) -> None:
    rdir = data_dir / "runs" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    ts = [datetime(2020, 1, 1 + i, tzinfo=UTC) for i in range(4)]
    pl.DataFrame({"ts": ts, "equity": [100.0, 101.0, 102.0, 103.0]}).write_parquet(
        rdir / "equity_curve.parquet"
    )
    pl.DataFrame(
        {
            "instrument_id": ["SPY.SIM"] * 3,
            "side": ["BUY"] * 3,
            "quantity": [10.0] * 3,
            "entry_price": [99.0, 100.0, 101.0],
            "exit_price": [100.0, 101.0, 102.0],
            "entry_ts": ts[:3],
            "exit_ts": ts[1:],
            "realized_pnl": [10.0] * 3,
            "realized_return": [0.01] * 3,
        }
    ).write_parquet(rdir / "trades.parquet")
    pl.DataFrame(
        {
            "sequence_id": [1, 2, 3],
            "event_type": ["decision", "order", "fill"],
            "ts": ts[:3],
            "parent_sequence_id": [None, 1, 2],
            "instrument_id": ["SPY.SIM"] * 3,
            "side": [None, "BUY", "BUY"],
            "quantity": [10.0, 10.0, 10.0],
            "filled_quantity": [None, 10.0, 10.0],
            "price": [None, None, 102.0],
            "status": [None, "FILLED", None],
            "signal": [1, None, None],
            "decision_reason": ["target", None, None],
            "entry_ts": [None, None, None],
            "exit_ts": [None, None, None],
            "entry_price": [None, None, None],
            "exit_price": [None, None, None],
            "realized_pnl": [None, None, None],
            "realized_return": [None, None, None],
        }
    ).write_parquet(rdir / "execution_trace.parquet")
    pl.DataFrame(
        {
            "sequence_id": [1, 2, 3, 4],
            "decision_sequence_id": [1, None, None, None],
            "ts": ts,
            "instrument_id": ["SPY.SIM"] * 4,
            "name": ["close"] * 4,
            "value": [100.0, 101.0, 102.0, 103.0],
            "unit": ["price"] * 4,
        }
    ).write_parquet(rdir / "indicator_series.parquet")
    pl.DataFrame(
        {
            "annotation_id": [1, 1, 2, 2, 3, 3],
            "decision_sequence_id": [1, 1, 2, 2, 3, 3],
            "kind": ["line"] * 6,
            "label": ["before", "before", "inside", "inside", "after", "after"],
            "unit": ["price"] * 6,
            "reason": ["causal"] * 6,
            "anchor_index": [0, 1, 0, 1, 0, 1],
            "ts": [ts[0], ts[1], ts[1], ts[2], ts[2], ts[3]],
            "value": [100.0, 101.0, 101.0, 102.0, 102.0, 103.0],
        }
    ).write_parquet(rdir / "chart_annotations.parquet")
    for filename in ("decision_trace.parquet", "orders.parquet", "fills.parquet"):
        pl.DataFrame({"placeholder": []}, schema={"placeholder": pl.Int64()}).write_parquet(
            rdir / filename
        )
    (rdir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "run_identity_version": 3,
                "artifact_contract_version": 3,
                "run_id": run_id,
                "command": "backtest_run",
                "symbol": "SPY",
                "snapshot_id": "snapshot-trace",
                "snapshot_hash": "b" * 64,
                "execution_fingerprint": "c" * 64,
                "strategy_fingerprint": "d" * 64,
                "source_fingerprint": "e" * 64,
                "artifacts": artifact_contract(rdir),
            }
        ),
        encoding="utf-8",
    )


def test_chart_bundle_is_bounded_and_old_runs_report_trace_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    old = client.get("/api/runs/aaaa000000000001/chart-bundle?limit=2")
    assert old.status_code == 200
    assert old.json()["trace_status"] == "trace_unavailable"
    assert old.json()["trace"] == []
    assert len(old.json()["equity"]["ts"]) == 2
    assert old.json()["truncated"]["equity"] is True

    run_id = "dddd000000000004"
    _write_trace_run(tmp_path, run_id)
    body = client.get(f"/api/runs/{run_id}/chart-bundle?limit=2").json()
    assert body["trace_status"] == "available"
    assert body["bars_status"] == "snapshot_unavailable"
    assert body["bars"] == []
    assert [event["sequence_id"] for event in body["trace"]] == [1, 2]
    assert body["truncated"]["trace"] is True
    assert body["trace"][1]["parent_sequence_id"] == 1
    artifact_hashes = body["provenance"].pop("artifact_sha256")
    assert set(artifact_hashes) == set(artifact_contract(tmp_path / "runs" / run_id))
    assert body["provenance"] == {
        "command": "backtest_run",
        "symbol": "SPY",
        "symbols": None,
        "snapshot_id": "snapshot-trace",
        "snapshot_hash": "b" * 64,
        "timezone": "UTC",
        "price_unit": "native_quote",
        "artifact_contract_version": 3,
        "as_of": body["equity"]["ts"][-1],
    }
    assert [event["sequence_id"] for event in body["decisions"]] == [1]
    assert [event["sequence_id"] for event in body["orders"]] == [2]
    assert [event["sequence_id"] for event in body["fills"]] == [3]
    assert body["folds"] == []
    assert body["forecast"] is None
    assert body["indicators"][0]["name"] == "close"
    assert [anchor["anchor_index"] for anchor in body["annotations"][0]["anchors"]] == [0, 1]


def test_chart_bundle_windows_bars_and_every_causal_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = "dddd000000000004"
    _write_trace_run(tmp_path, run_id)
    candle_ts = [datetime(2020, 1, 1 + index, tzinfo=UTC).timestamp() for index in range(4)]
    monkeypatch.setattr(
        run_projection,
        "_candle_rows",
        lambda *args, **kwargs: [
            {"t": ts, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 1_000.0}
            for ts in candle_ts
        ],
    )

    response = TestClient(create_app()).get(
        f"/api/runs/{run_id}/chart-bundle?start=2020-01-02&end=2020-01-03"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["t"] for row in body["bars"]] == candle_ts[1:3]
    assert [row["sequence_id"] for row in body["trace"]] == [2, 3]
    assert body["decisions"] == []
    assert [row["sequence_id"] for row in body["orders"]] == [2]
    assert [row["sequence_id"] for row in body["fills"]] == [3]
    assert [row["exit_ts"] for row in body["trades"]] == candle_ts[1:3]
    assert [row["sequence_id"] for row in body["indicators"]] == [2, 3]
    assert [row["annotation_id"] for row in body["annotations"]] == [2]
    assert [anchor["ts"] for anchor in body["annotations"][0]["anchors"]] == candle_ts[1:3]
    assert body["equity"]["ts"] == candle_ts[1:3]


def test_chart_bundle_bounds_are_validated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/runs/aaaa000000000001/chart-bundle?limit=0").status_code == 422
    assert (
        client.get(
            f"/api/runs/aaaa000000000001/chart-bundle?limit={run_projection.MAX_CHART_POINTS + 1}"
        ).status_code
        == 422
    )


# --- phase-7 projections: null distributions, optim trials, propfirm paths, eval origins -------


def _write_nulls(data_dir: Path, run_id: str) -> None:
    """Seed a gauntlet run's ``nulls.parquet`` (two tiers, sorted (tier, path_index))."""
    rdir = data_dir / "runs" / run_id
    pl.DataFrame(
        {
            "tier": ["full_engine"] * 3 + ["returns_level"] * 4,
            "path_index": [0, 1, 2, 0, 1, 2, 3],
            "statistic": [0.1, -0.2, 0.3, 0.5, 0.6, -0.7, 0.8],
        },
        schema={"tier": pl.String(), "path_index": pl.Int64(), "statistic": pl.Float64()},
    ).write_parquet(rdir / "nulls.parquet")


def _write_trials(data_dir: Path, run_id: str) -> None:
    """Seed an optim run's ``trials.parquet`` (2 trials x 3 steps, sorted (trial, step))."""
    rdir = data_dir / "optim" / run_id
    pl.DataFrame(
        {
            "trial": [0, 0, 0, 1, 1, 1],
            "step": [0, 1, 2, 0, 1, 2],
            "oos_return": [0.01, -0.02, 0.03, 0.04, 0.05, -0.06],
        },
        schema={"trial": pl.Int64(), "step": pl.Int64(), "oos_return": pl.Float64()},
    ).write_parquet(rdir / "trials.parquet")


def _write_propfirm_run(data_dir: Path, run_id: str, *, legacy_filename: bool = False) -> None:
    """Seed a propfirm run + its ``propfirm_paths.parquet`` (NaN days_to_pass = never passed)."""
    rdir = data_dir / "propfirm" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "command": "propfirm_run", "symbol": "SPY"}),
        encoding="utf-8",
    )
    pl.DataFrame(
        {
            "path_index": [0, 1, 2],
            "passed": [True, False, True],
            "busted": [False, True, False],
            "days_to_pass": [12.0, float("nan"), 30.0],
            "payout": [4500.0, 0.0, 1200.0],
        },
        schema={
            "path_index": pl.Int64(),
            "passed": pl.Boolean(),
            "busted": pl.Boolean(),
            "days_to_pass": pl.Float64(),
            "payout": pl.Float64(),
        },
    ).write_parquet(rdir / ("paths.parquet" if legacy_filename else "propfirm_paths.parquet"))


def _write_forecast_eval_run(data_dir: Path, run_id: str) -> None:
    """Seed a forecast-eval run: manifest + ``origins.parquet`` (no cone artifacts)."""
    rdir = data_dir / "forecast" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(
        json.dumps({"command": "forecast_eval", "symbol": "BTC-USD"}), encoding="utf-8"
    )
    pl.DataFrame(
        {
            "origin_index": [10, 31],
            "origin_ts": [datetime(2025, 1, 2, tzinfo=UTC), datetime(2025, 2, 3, tzinfo=UTC)],
            "pre_cutoff": [True, False],
            "realized_end_return": [0.05, -0.03],
            "median_end_return": [0.01, 0.02],
            "crps": [0.011, 0.022],
            "crps_rw": [0.013, 0.021],
            "crps_bootstrap": [0.012, 0.023],
            "pinball_q25": [0.004, 0.005],
            "pinball_q75": [0.006, 0.007],
            "cover50": [True, False],
            "cover80": [True, True],
            "cover90": [True, True],
            "hit": [True, False],
        }
    ).write_parquet(rdir / "origins.parquet")


def test_nulls_endpoint_groups_by_tier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _write_nulls(tmp_path, "aaaa000000000001")
    assert client.get("/api/runs/aaaa000000000001").json()["has_nulls"] is True
    body = client.get("/api/runs/aaaa000000000001/nulls").json()
    assert [t["tier"] for t in body["tiers"]] == ["full_engine", "returns_level"]
    assert body["tiers"][0]["statistics"] == [0.1, -0.2, 0.3]
    assert body["tiers"][1]["statistics"] == [0.5, 0.6, -0.7, 0.8]


def test_nulls_endpoint_404_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/runs/bbbb000000000002").json()["has_nulls"] is False
    assert client.get("/api/runs/bbbb000000000002/nulls").status_code == 404


def test_trials_endpoint_groups_by_trial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _write_trials(tmp_path, "cccc000000000003")
    assert client.get("/api/runs/cccc000000000003").json()["has_trials"] is True
    body = client.get("/api/runs/cccc000000000003/trials").json()
    assert [t["trial"] for t in body["trials"]] == [0, 1]
    assert body["trials"][0]["returns"] == [0.01, -0.02, 0.03]
    assert body["trials"][1]["returns"] == [0.04, 0.05, -0.06]


def test_trials_endpoint_404_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/runs/cccc000000000003").json()["has_trials"] is False
    assert client.get("/api/runs/cccc000000000003/trials").status_code == 404


def test_propfirm_paths_endpoint_columnar_nan_to_null(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_propfirm_run(tmp_path, "eeee000000000005")
    client = TestClient(create_app())
    detail = client.get("/api/runs/eeee000000000005").json()
    assert detail["has_propfirm_paths"] is True
    assert detail["has_forecast_paths"] is False  # no forecast paths artifact here
    body = client.get("/api/runs/eeee000000000005/propfirm-paths").json()
    assert body["paths"]["passed"] == [True, False, True]
    assert body["paths"]["busted"] == [False, True, False]
    assert body["paths"]["days_to_pass"] == [12.0, None, 30.0]  # NaN -> null for JSON safety
    assert body["paths"]["payout"] == [4500.0, 0.0, 1200.0]
    # the forecast-paths projection reads paths.parquet, which a propfirm run does not write
    assert client.get("/api/runs/eeee000000000005/forecast/paths").status_code == 404


def test_complete_legacy_propfirm_paths_remain_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = "eeee000000000006"
    _write_propfirm_run(tmp_path, run_id, legacy_filename=True)
    client = TestClient(create_app())

    assert _runs.run_artifacts_readable("propfirm", run_id, data_dir=tmp_path)
    assert client.get(f"/api/runs/{run_id}").json()["has_propfirm_paths"] is True
    assert client.get(f"/api/runs/{run_id}/propfirm-paths").status_code == 200
    assert client.get(f"/api/runs/{run_id}/forecast/paths").status_code == 404


def test_propfirm_paths_endpoint_404_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_forecast_run(tmp_path, "ffff000000000009", n_samples=2)
    _seed(tmp_path)
    client = TestClient(create_app())
    assert client.get("/api/runs/aaaa000000000001/propfirm-paths").status_code == 404
    # a forecast run writes paths.parquet, not propfirm_paths.parquet — still 404
    detail = client.get("/api/runs/ffff000000000009").json()
    assert detail["has_forecast_paths"] is True
    assert detail["has_propfirm_paths"] is False
    assert client.get("/api/runs/ffff000000000009/propfirm-paths").status_code == 404


def test_origins_endpoint_columnar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _write_forecast_eval_run(tmp_path, "abcd000000000006")
    client = TestClient(create_app())
    detail = client.get("/api/runs/abcd000000000006").json()
    assert detail["has_origins"] is True
    assert detail["has_forecast"] is False  # eval runs write no cone
    body = client.get("/api/runs/abcd000000000006/origins").json()
    assert body["origin_ts"] == [
        datetime(2025, 1, 2, tzinfo=UTC).timestamp(),
        datetime(2025, 2, 3, tzinfo=UTC).timestamp(),
    ]
    assert body["pre_cutoff"] == [True, False]
    assert body["crps"] == [0.011, 0.022]
    assert body["crps_rw"] == [0.013, 0.021]
    assert body["crps_bootstrap"] == [0.012, 0.023]
    assert body["realized_end_return"] == [0.05, -0.03]
    assert body["median_end_return"] == [0.01, 0.02]
    assert body["hit"] == [True, False]
    assert body["cover50"] == [True, False]
    assert body["cover80"] == [True, True] and body["cover90"] == [True, True]


def test_origins_endpoint_404_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/runs/aaaa000000000001").json()["has_origins"] is False
    assert client.get("/api/runs/aaaa000000000001/origins").status_code == 404
