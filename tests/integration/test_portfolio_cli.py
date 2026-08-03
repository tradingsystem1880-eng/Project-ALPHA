"""`alpha backtest portfolio` runs a basket on the offline fixture and writes a manifest."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_data.snapshot import create_snapshot, snapshot_manifest_hash
from alpha_data.store import ParquetStore
from alpha_web.app import create_app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_ARGS = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--train-size", "15", "--test-size", "5", "--embargo", "1",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
]  # fmt: skip


def test_portfolio_writes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=80, seed=0)
    seed_store(tmp_path, symbol="QQQ", n=80, seed=1)
    create_snapshot(
        ParquetStore(tmp_path / "store"),
        tmp_path / "snapshots",
        "portfolio-frozen",
        ["SPY", "QQQ"],
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 7, 19, tzinfo=UTC),
    )

    command = [
        "backtest",
        "portfolio",
        "SPY",
        "QQQ",
        *_ARGS,
        "--snapshot",
        "portfolio-frozen",
    ]
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output
    assert "portfolio [QQQ, SPY]" in result.output  # canonical (sorted) symbol order

    (rdir,) = list((tmp_path / "portfolio").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["symbols"] == ["QQQ", "SPY"]  # canonical (sorted) order
    assert manifest["weighting"] == "equal"
    assert manifest["snapshot_id"] == "portfolio-frozen"
    assert manifest["snapshot_hash"] == snapshot_manifest_hash(
        tmp_path / "snapshots" / "portfolio-frozen"
    )
    assert len(manifest["legs"]) == 2
    assert manifest["n_periods"] > 0
    assert "sharpe_ci" in manifest and "lower" in manifest["sharpe_ci"]
    assert (rdir / "tearsheet.html").exists()  # reporting parity with `alpha validate`

    # the combined OOS stream is persisted as an equity curve (validate-run schema: base 1.0)
    eq = pl.read_parquet(rdir / "equity_curve.parquet")
    assert eq.columns == ["ts", "equity"]
    assert eq.schema["ts"] == pl.Datetime(time_unit="us", time_zone="UTC")
    assert eq.schema["equity"] == pl.Float64
    assert eq.height == manifest["n_periods"] + 1  # baseline row + one point per combined return
    assert eq["equity"][0] == 1.0
    assert eq["ts"].is_sorted() and eq["ts"].n_unique() == eq.height  # strictly increasing
    # cumprod correctness: the stored curve's total return reproduces the manifest metric
    assert eq["equity"][-1] / eq["equity"][0] - 1.0 == pytest.approx(
        manifest["metrics"]["total_return"]
    )
    exposure = pl.read_parquet(rdir / "exposure_turnover.parquet")
    benchmark = pl.read_parquet(rdir / "benchmark_comparison.parquet")
    trade_statistics = pl.read_parquet(rdir / "trade_statistics.parquet")
    assert benchmark.get_column("available").to_list() == [False] * eq.height
    assert trade_statistics.get_column("available").to_list() == [False] * trade_statistics.height
    assert exposure.get_column("exposure_available").to_list() == [True] * (eq.height - 1)
    assert exposure.get_column("gross_exposure").null_count() == 0
    assert exposure.get_column("net_exposure").null_count() == 0
    assert exposure.get_column("turnover_available").to_list() == [False] * (eq.height - 1)

    allocations = pl.read_parquet(rdir / "portfolio_allocations.parquet")
    correlations = pl.read_parquet(rdir / "correlations.parquet")
    assert allocations.height == manifest["n_periods"] * len(manifest["symbols"])
    assert allocations.columns == [
        "source_run_id",
        "snapshot_id",
        "snapshot_hash",
        "research_cutoff",
        "frequency",
        "start_ts",
        "ts",
        "symbol",
        "weight",
        "leg_return",
        "contribution",
        "leg_gross_exposure",
        "leg_net_exposure",
        "weighted_gross_exposure",
        "weighted_net_exposure",
    ]
    assert correlations.height == len(manifest["symbols"]) ** 2
    assert correlations.get_column("metric_name").unique().to_list() == ["pearson_correlation"]
    assert correlations.get_column("metric_unit").unique().to_list() == ["coefficient"]
    assert correlations.get_column("aligned_oos").all()
    assert correlations.get_column("association_not_causation").all()
    assert correlations.get_column("snapshot_hash").unique().to_list() == [
        manifest["snapshot_hash"]
    ]
    assert correlations.filter(pl.col("sample_count") <= 1).is_empty()
    assert set(manifest["artifacts"]) >= {
        "portfolio_allocations.parquet",
        "correlations.parquet",
    }

    api_response = TestClient(create_app()).get(
        f"/api/runs/{manifest['run_id']}/portfolio-analytics"
    )
    assert api_response.status_code == 200, api_response.text
    analytics = api_response.json()
    assert analytics["symbols"] == manifest["symbols"]
    assert len(analytics["correlations"]) == len(manifest["symbols"]) ** 2
    assert analytics["provenance"]["source_run_id"] == manifest["run_id"]
    assert analytics["provenance"]["snapshot_hash"] == manifest["snapshot_hash"]
    assert analytics["provenance"]["association_label"] == "association, not causation"
    assert analytics["provenance"]["artifact_sha256"]["correlations.parquet"]
    versioned = TestClient(create_app()).get(
        f"/api/v3/runs/{manifest['run_id']}/portfolio-analytics"
    )
    assert versioned.status_code == 200, versioned.text
    assert versioned.json() == analytics

    deterministic_artifacts = {
        name: (rdir / name).read_bytes()
        for name in ("portfolio_allocations.parquet", "correlations.parquet", "manifest.json")
    }
    rerun = runner.invoke(app, command)
    assert rerun.exit_code == 0, rerun.output
    assert list((tmp_path / "portfolio").iterdir()) == [rdir]
    assert {
        name: (rdir / name).read_bytes() for name in deterministic_artifacts
    } == deterministic_artifacts

    # the stored run is re-displayable via `alpha report`
    report_out = runner.invoke(app, ["report", manifest["run_id"]])
    assert report_out.exit_code == 0, report_out.output
    assert "metrics:" in report_out.output and "leg[SPY]" in report_out.output

    # BONUS: with the equity curve stored, `alpha propfirm --from-run` resolves a portfolio run
    pf_args = ["--firm", "topstep", "--n-paths", "50", "--seed", "7"]
    pf = runner.invoke(app, ["propfirm", "run", "--from-run", manifest["run_id"], *pf_args])
    assert pf.exit_code == 0, pf.output
    assert f"run {manifest['run_id']}" in pf.output


def test_portfolio_rejects_single_symbol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=80)
    result = runner.invoke(app, ["backtest", "portfolio", "SPY", *_ARGS])
    assert result.exit_code != 0  # a portfolio needs >= 2 symbols
