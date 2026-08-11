"""``alpha forecast eval``: rolling-origin skill manifest + origins parquet + report."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore
from alpha_research import MarketStateContractV1
from alpha_validation import ForecastCalibrationContractV1
from tests.fixtures.cli_fixtures import seed_store
from tests.fixtures.control_store_fixtures import mark_project_as_migrated_legacy

runner = CliRunner()

_ARGS = [
    "forecast",
    "eval",
    "SPY",
    "--model",
    "fake",
    "--context",
    "8",
    "--horizon",
    "4",
    "--stride",
    "4",
    "--samples",
    "16",
]


def _dirs(data_dir: Path) -> list[Path]:
    root = data_dir / "forecast"
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []


def test_forecast_eval_writes_manifest_and_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    assert "-> run " in result.output

    (rdir,) = _dirs(tmp_path)
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["command"] == "forecast_eval"
    assert manifest["model"]["model_id"] == "fake"
    summary = manifest["summary"]
    for key in ("crps_mean", "skill_vs_rw", "skill_vs_bootstrap", "coverage80", "hit_rate"):
        assert key in summary
    # 2020 fixture is entirely pre-cutoff: split populated on the pre side only
    assert manifest["n_origins_pre"] == summary["n_origins"]
    assert manifest["n_origins_post"] == 0
    assert manifest["summary_post_cutoff"] is None
    assert manifest["summary_pre_cutoff"]["n_origins"] == summary["n_origins"]

    origins = pl.read_parquet(rdir / "origins.parquet")
    assert origins.height == summary["n_origins"]
    for col in ("origin_ts", "realized_end_return", "crps", "crps_rw", "hit", "pre_cutoff"):
        assert col in origins.columns
    assert origins["pre_cutoff"].all()


def test_forecast_eval_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    first = runner.invoke(app, _ARGS)
    assert first.exit_code == 0, first.output
    (rdir,) = _dirs(tmp_path)
    manifest_bytes = (rdir / "manifest.json").read_bytes()

    second = runner.invoke(app, _ARGS)
    assert second.exit_code == 0, second.output
    assert _dirs(tmp_path) == [rdir]
    assert (rdir / "manifest.json").read_bytes() == manifest_bytes


def test_forecast_eval_warns_when_no_post_cutoff_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    assert "no post-cutoff origins" in result.output.lower()


def test_forecast_eval_fails_loud_when_nothing_fits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=10)
    result = runner.invoke(
        app, ["forecast", "eval", "SPY", "--model", "fake", "--context", "8", "--horizon", "8"]
    )
    assert result.exit_code != 0
    assert "origin" in result.output.lower()


def test_report_displays_forecast_eval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    (rdir,) = _dirs(tmp_path)

    report = runner.invoke(app, ["report", rdir.name])
    assert report.exit_code == 0, report.output
    assert "forecast_eval" in report.output
    assert "skill_vs_rw" in report.output
    assert "pre-cutoff" in report.output.lower()


def test_governed_forecast_eval_freezes_calibration_and_abstention_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    sessions: list[datetime] = []
    session = date(2020, 1, 2)
    while len(sessions) < 90:
        if session.weekday() < 5:
            sessions.append(datetime.combine(session, datetime.min.time(), tzinfo=UTC))
        session += timedelta(days=1)
    store = ParquetStore(tmp_path / "store")
    for offset, symbol in enumerate(("AAPL", "SPY")):
        rng = np.random.default_rng(10 + offset)
        closes = 100.0 * np.cumprod(1.0 + 0.001 + rng.normal(0.0, 0.01, len(sessions)))
        store.write_bars(
            symbol,
            pl.DataFrame(
                {
                    "ts": sessions,
                    "open": closes,
                    "high": closes * 1.01,
                    "low": closes * 0.99,
                    "close": closes,
                    "volume": [1_000_000.0] * len(sessions),
                }
            ),
        )
    create_snapshot(
        store,
        tmp_path / "snapshots",
        "governed-forecast",
        ["AAPL", "SPY"],
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 8, 11, tzinfo=UTC),
    )
    control = ControlStore(tmp_path)
    project = control.create_project(
        name="Governed Kronos calibration",
        hypothesis="Calibrated forecasts conditionally clear their frozen hurdle.",
        falsification_criterion="Reject when calibrated OOS skill or coverage misses its floor.",
        at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(control, project_id)
    version = control.create_strategy_version(
        project_id,
        strategy_name="kronos_calibrated",
        source_fingerprint="git:test",
        definition={"authority": "research_candidate_only"},
        parameter_space={},
    )
    market = MarketStateContractV1(
        universe=("AAPL", "SPY"),
        benchmark="SPY",
        calendar="equity",
        volatility_window=3,
        trend_window=3,
        correlation_window=3,
        annualization_sessions=252,
        volatility_thresholds=(0.10, 0.25),
        trend_threshold=0.01,
        breadth_thresholds=(0.25, 0.75),
        correlation_thresholds=(0.25, 0.75),
        minimum_state_samples=3,
    )
    calibration = ForecastCalibrationContractV1(
        coverage_level=0.8,
        residual_window=4,
        blend_weights=(0.0, 0.5, 1.0),
        minimum_validation_origins=8,
        minimum_empirical_coverage=0.5,
        minimum_edge=0.0,
        maximum_interval_width=1.0,
        minimum_state_samples=3,
    )
    experiment = control.create_experiment_spec(
        project_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="governed-forecast",
        universe=["AAPL", "SPY"],
        split_policy={"validation": 16, "test": 32},
        costs={"fee_bps": 1.0, "slippage_bps": 2.0},
        seeds={"master": 7},
        stage_config={
            "market_state": market.to_dict(),
            "kronos_calibration": calibration.to_dict(),
        },
    )

    result = runner.invoke(
        app,
        [
            "forecast",
            "eval",
            "SPY",
            "--model",
            "fake",
            "--context",
            "8",
            "--horizon",
            "2",
            "--stride",
            "2",
            "--samples",
            "8",
            "--project-id",
            project_id,
            "--experiment-id",
            str(experiment["experiment_id"]),
        ],
    )

    assert result.exit_code == 0, result.output
    (rdir,) = _dirs(tmp_path)
    manifest = json.loads((rdir / "manifest.json").read_text())
    governed = manifest["governed_calibration"]
    assert governed["authority"] == "research_candidate_only_no_paper_or_order_authority"
    assert governed["validation_origins"] == 8
    assert governed["oos_origins"] > 0
    for name in (
        "market_state.json",
        "market_state.parquet",
        "calibration_fit.json",
        "calibrated_origins.parquet",
        "state_performance.parquet",
        "calibration_reliability.parquet",
    ):
        assert name in manifest["artifacts"]
    calibrated = pl.read_parquet(rdir / "calibrated_origins.parquet")
    assert calibrated.get_column("calibration_fit_sha256").n_unique() == 1
    assert calibrated.get_column("blocker_codes").dtype == pl.List(pl.String)
