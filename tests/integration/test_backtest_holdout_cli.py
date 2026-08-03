from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore
from tests.fixtures.cli_fixtures import seed_store


def test_locked_holdout_writes_scoped_causal_v3_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=100)
    create_snapshot(
        ParquetStore(tmp_path / "store"),
        tmp_path / "snapshots",
        "frozen",
        ["SPY"],
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    result = CliRunner().invoke(
        app,
        [
            "backtest",
            "holdout",
            "SPY",
            "--lookback",
            "5",
            "--skip",
            "1",
            "--vol-window",
            "3",
            "--rebalance-every",
            "2",
            "--fee-bps",
            "0",
            "--slippage-bps",
            "0",
            "--starting-cash",
            "100000",
            "--snapshot",
            "frozen",
            "--holdout-start",
            "2020-03-01",
            "--holdout-end",
            "2020-03-30",
            "--holdout-spec-hash",
            "a" * 64,
            "--min-sharpe",
            "-100",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "locked holdout SPY -> run" in result.output
    run_dir = next((tmp_path / "runs").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert manifest["command"] == "backtest_holdout"
    assert manifest["holdout_spec_hash"] == "a" * 64
    assert manifest["holdout_start"] == "2020-03-01"
    assert manifest["holdout_end"] == "2020-03-30"
    assert manifest["passed"] is True
    equity = pl.read_parquet(run_dir / "equity_curve.parquet")
    equity_min = equity["ts"].min()
    equity_max = equity["ts"].max()
    assert isinstance(equity_min, datetime)
    assert isinstance(equity_max, datetime)
    assert equity_min.date().isoformat() == "2020-03-01"
    assert equity_max.date().isoformat() == "2020-03-30"
    assert equity["equity"][0] == pytest.approx(100000.0)
    decisions = pl.read_parquet(run_dir / "decision_trace.parquet")
    orders = pl.read_parquet(run_dir / "orders.parquet")
    fills = pl.read_parquet(run_dir / "fills.parquet")
    decision_max = decisions["ts"].max()
    order_min = orders["ts"].min()
    fill_min = fills["ts"].min()
    assert isinstance(decision_max, datetime)
    assert isinstance(order_min, datetime)
    assert isinstance(fill_min, datetime)
    assert decision_max <= equity_max
    assert order_min >= equity_min
    assert fill_min >= equity_min
    trades = pl.read_parquet(run_dir / "trades.parquet")
    assert trades.filter(pl.col("entry_ts") < equity_min).is_empty()
    assert {
        "decision_trace.parquet",
        "orders.parquet",
        "fills.parquet",
        "benchmark_comparison.parquet",
        "exposure_turnover.parquet",
        "trade_statistics.parquet",
    } <= set(manifest["artifacts"])
