from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store


def test_fixed_rule_oos_command_is_explicitly_no_refit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=100)
    result = CliRunner().invoke(
        app,
        [
            "backtest",
            "oos",
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
            "--train-size",
            "30",
            "--test-size",
            "10",
            "--embargo",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "fixed parameters, no refit" in result.output
    run_dir = next((tmp_path / "runs").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "backtest_oos"
    assert manifest["oos_semantics"] == "fixed_rule_evaluation_no_refit"
    assert manifest["schema_version"] == 3
    assert len(manifest["folds"]) >= 2
    equity = pl.read_parquet(run_dir / "equity_curve.parquet")
    assert equity.height == 1 + sum(row["n_test"] for row in manifest["folds"])
    assert equity["equity"][0] == pytest.approx(1.0)
    first_fold = manifest["folds"][0]
    last_fold = manifest["folds"][-1]
    first_scored = datetime.fromisoformat(first_fold["test_start_ts"])
    first_decision = datetime.fromisoformat(first_fold["test_decision_start_ts"])
    final_scored = datetime.fromisoformat(last_fold["test_end_ts"])
    decisions = pl.read_parquet(run_dir / "decision_trace.parquet")
    fills = pl.read_parquet(run_dir / "fills.parquet")
    trades = pl.read_parquet(run_dir / "trades.parquet")
    assert decisions.filter(pl.col("ts") < first_decision).is_empty()
    assert decisions.filter(pl.col("ts").dt.date() >= final_scored.date()).is_empty()
    assert fills.filter(pl.col("ts") < first_scored).is_empty()
    assert fills.filter(pl.col("ts") > final_scored).is_empty()
    assert trades.filter(pl.col("entry_ts") < first_scored).is_empty()
    assert manifest["oos_execution_boundary"].startswith("fresh_portfolio")
    assert {
        "decision_trace.parquet",
        "orders.parquet",
        "fills.parquet",
        "calendar_returns.parquet",
        "benchmark_comparison.parquet",
        "exposure_turnover.parquet",
        "trade_statistics.parquet",
    } <= set(manifest["artifacts"])
