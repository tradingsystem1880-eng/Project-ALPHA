"""`alpha backtest run` drives the engine on a committed offline fixture and writes artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_SMALL = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
]  # fmt: skip


def test_backtest_run_writes_trade_log_and_equity_curve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    result = runner.invoke(app, ["backtest", "run", "SPY", *_SMALL])
    assert result.exit_code == 0, result.output
    assert "run" in result.output and "final equity" in result.output

    runs = list((tmp_path / "runs").iterdir())
    assert len(runs) == 1
    rdir = runs[0]
    assert (rdir / "manifest.json").exists()
    equity = pl.read_parquet(rdir / "equity_curve.parquet")
    assert equity.columns == ["ts", "equity"] and equity.height == 60  # one mark per session
    assert (rdir / "trades.parquet").exists()
    calendar = pl.read_parquet(rdir / "calendar_returns.parquet")
    distribution = pl.read_parquet(rdir / "return_distribution.parquet")
    rolling = pl.read_parquet(rdir / "rolling_metrics.parquet")
    benchmark = pl.read_parquet(rdir / "benchmark_comparison.parquet")
    exposure = pl.read_parquet(rdir / "exposure_turnover.parquet")
    trade_statistics = pl.read_parquet(rdir / "trade_statistics.parquet")
    assert calendar.columns == ["period_type", "year", "month", "return_value"]
    assert {"histogram", "qq"} <= set(distribution["kind"].to_list())
    assert rolling.columns == [
        "ts",
        "window",
        "return_value",
        "volatility",
        "sharpe",
        "gross_exposure",
        "net_exposure",
        "turnover",
        "exposure_available",
        "turnover_available",
    ]
    assert benchmark.get_column("available").to_list() == [True] * equity.height
    assert benchmark.get_column("benchmark_kind").unique().to_list() == [
        "passive_open_to_open_price_only"
    ]
    assert exposure.get_column("exposure_available").to_list() == [True] * (equity.height - 1)
    assert exposure.get_column("turnover_available").to_list() == [True] * (equity.height - 1)
    assert exposure.get_column("gross_exposure").null_count() == 0
    assert exposure.get_column("turnover").null_count() == 0
    assert (
        trade_statistics.filter(pl.col("metric") == "trade_count").get_column("available").item()
        is True
    )
    decisions = pl.read_parquet(rdir / "decision_trace.parquet")
    orders = pl.read_parquet(rdir / "orders.parquet")
    fills = pl.read_parquet(rdir / "fills.parquet")
    indicators = pl.read_parquet(rdir / "indicator_series.parquet")
    annotations = pl.read_parquet(rdir / "chart_annotations.parquet")
    assert orders["sequence_id"].to_list() == list(range(1, orders.height + 1))
    assert fills["sequence_id"].to_list() == list(range(1, fills.height + 1))
    assert orders["decision_sequence_id"].drop_nulls().len() == orders.height
    assert set(fills["order_sequence_id"].to_list()) <= set(orders["sequence_id"].to_list())
    assert {"close", "momentum_return", "momentum_recent", "momentum_past"} <= set(
        indicators["name"].to_list()
    )
    assert indicators["decision_sequence_id"].null_count() == 0
    assert annotations.columns == [
        "annotation_id",
        "decision_sequence_id",
        "kind",
        "label",
        "unit",
        "reason",
        "anchor_index",
        "ts",
        "value",
    ]
    assert "indicator" not in decisions.columns and "pattern" not in decisions.columns
    trace = pl.read_parquet(rdir / "execution_trace.parquet")
    assert trace["sequence_id"].to_list() == list(range(1, trace.height + 1))
    assert {"decision", "order", "fill"} <= set(trace["event_type"].to_list())
    trace_decision_ids = trace.filter(pl.col("event_type") == "decision")["sequence_id"].to_list()
    assert decisions["sequence_id"].to_list() == trace_decision_ids
    assert set(indicators["decision_sequence_id"].to_list()) <= set(trace_decision_ids)
    assert set(annotations["decision_sequence_id"].to_list()) <= set(trace_decision_ids)
    assert "indicator" not in trace.columns and "pattern" not in trace.columns
    for row in trace.filter(pl.col("event_type") == "order").iter_rows(named=True):
        assert row["parent_sequence_id"] is not None
        decision = trace.filter(pl.col("sequence_id") == row["parent_sequence_id"]).row(
            0, named=True
        )
        assert decision["event_type"] == "decision"
        assert decision["ts"] < row["ts"]
    manifest = json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert {
        "decision_trace.parquet",
        "orders.parquet",
        "fills.parquet",
        "execution_trace.parquet",
        "indicator_series.parquet",
        "chart_annotations.parquet",
        "calendar_returns.parquet",
        "benchmark_comparison.parquet",
        "exposure_turnover.parquet",
        "return_distribution.parquet",
        "rolling_metrics.parquet",
        "trade_statistics.parquet",
    } <= set(manifest["artifacts"])


def test_unknown_symbol_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(app, ["backtest", "run", "NOPE", *_SMALL])
    # Clean, actionable error — a typed DataError surfaces as a tidy BadParameter (exit 2), NOT a
    # raw Python traceback. No run directory is written.
    assert result.exit_code == 2
    assert "Traceback" not in result.output
    assert not (tmp_path / "runs").exists()


def test_breakout_run_persists_causal_vector_channel_annotations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    result = runner.invoke(
        app,
        [
            "backtest",
            "run",
            "SPY",
            "--strategy",
            "breakout",
            "--param",
            "window=5",
            *_SMALL,
        ],
    )
    assert result.exit_code == 0, result.output
    rdir = next((tmp_path / "runs").iterdir())
    annotations = pl.read_parquet(rdir / "chart_annotations.parquet")
    decisions = pl.read_parquet(rdir / "decision_trace.parquet")

    assert annotations.height > 0
    assert set(annotations["label"].to_list()) == {"channel_high", "channel_low"}
    assert set(annotations["kind"].to_list()) == {"line"}
    for part in annotations.partition_by("annotation_id", maintain_order=True):
        assert part["anchor_index"].to_list() == [0, 1]
        decision_id = part["decision_sequence_id"][0]
        decision_ts = decisions.filter(pl.col("sequence_id") == decision_id)["ts"][0]
        assert max(part["ts"].to_list()) == decision_ts


def test_bad_account_type_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fail-loud golden rule: a typo'd --account-type must error, not silently run as CASH.
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(app, ["backtest", "run", "SPY", "--account-type", "BOGUS", *_SMALL])
    assert result.exit_code == 2
    assert "CASH" in result.output and "MARGIN" in result.output
    assert "Traceback" not in result.output


def test_account_type_is_case_insensitive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # "margin" (lowercase) is accepted as MARGIN, not silently coerced to an unlevered CASH account.
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(
        app,
        ["backtest", "run", "SPY", "--account-type", "margin", "--max-leverage", "2.0", *_SMALL],
    )
    assert result.exit_code == 0, result.output


def test_stored_dividends_flow_into_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # End-to-end: a DIVIDEND action in the store must raise the run's final equity by the credit.
    import json
    from datetime import date

    from alpha_core import ActionType, CorporateAction
    from alpha_data.store import ParquetStore

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60, seed=0, drift=0.002)
    runner = CliRunner()
    args = [
        "backtest",
        "run",
        "SPY",
        "--lookback",
        "5",
        "--skip",
        "1",
        "--vol-window",
        "5",
        "--rebalance-every",
        "5",
        "--fee-bps",
        "0",
        "--slippage-bps",
        "0",
    ]

    plain = runner.invoke(app, args)
    assert plain.exit_code == 0, plain.output

    # add a mid-series dividend (ex + pay well inside the window) and re-run
    ParquetStore(tmp_path / "store").write_actions(
        "SPY",
        [
            CorporateAction(
                symbol="SPY",
                action_type=ActionType.DIVIDEND,
                ex_date=date(2020, 2, 15),
                pay_date=date(2020, 2, 20),
                amount=1.0,
            )
        ],
    )
    paid = runner.invoke(app, args)
    assert paid.exit_code == 0, paid.output

    def final_equity(output: str) -> float:
        return float(output.split("final equity ")[1].split(" ")[0].rstrip("\n"))

    # Mutable source content is part of run identity. The dividend revision therefore publishes a
    # second immutable run instead of replacing the first run's evidence in place.
    assert final_equity(paid.output) > final_equity(plain.output)
    plain_run_id = plain.output.split("-> run ")[1].split(":")[0]
    paid_run_id = paid.output.split("-> run ")[1].split(":")[0]
    assert paid_run_id != plain_run_id
    plain_manifest = json.loads((tmp_path / "runs" / plain_run_id / "manifest.json").read_text())
    paid_manifest = json.loads((tmp_path / "runs" / paid_run_id / "manifest.json").read_text())
    assert plain_manifest["source_fingerprint"] != paid_manifest["source_fingerprint"]
    assert float(plain_manifest["final_equity"]) == pytest.approx(
        final_equity(plain.output), abs=0.01
    )
    assert float(paid_manifest["final_equity"]) == pytest.approx(
        final_equity(paid.output), abs=0.01
    )
