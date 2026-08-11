"""Immutable classical path-risk Monte Carlo runs from a verified validation source."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_VALIDATE = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--train-size", "30", "--test-size", "10", "--embargo", "1",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
    "--tier1-paths", "30", "--tier2-paths", "4", "--n-resamples", "100",
]  # fmt: skip


def test_classical_monte_carlo_publishes_three_auditable_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=120, sigma=0.02)
    validation = runner.invoke(app, ["validate", "SPY", *_VALIDATE])
    assert validation.exit_code == 0, validation.output
    source = next((tmp_path / "runs").iterdir()).name

    result = runner.invoke(
        app,
        [
            "monte-carlo",
            "classical",
            "--from-run",
            source,
            "--paths",
            "32",
            "--regime-window",
            "3",
            "--min-state-observations",
            "2",
            "--min-state-transitions",
            "1",
            "--seed",
            "19",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "iid_empirical" in result.output
    run_dirs = [path for path in (tmp_path / "runs").iterdir() if path.name != source]
    assert len(run_dirs) == 1
    rdir = run_dirs[0]
    manifest = json.loads((rdir / "manifest.json").read_text())

    assert manifest["command"] == "monte_carlo_classical"
    assert manifest["source_run_id"] == source
    assert {row["family"] for row in manifest["families"]} == {
        "iid_empirical",
        "regime_switching",
        "student_t",
    }
    paths = pl.read_parquet(rdir / "paths.parquet")
    metrics = pl.read_parquet(rdir / "path_metrics.parquet")
    assert paths.columns == ["family", "path_index", "step", "account_return"]
    assert paths.height == 3 * 32 * manifest["horizon"]
    assert metrics.height == 3 * 32
    assert (rdir / "regime_diagnostics.parquet").is_file()
    assert (rdir / "report.md").is_file()
    figures = runner.invoke(app, ["figures", "render", rdir.name, "--json"])
    assert figures.exit_code == 0, figures.output
    figure_payload = json.loads(figures.output)
    assert figure_payload["failed"] == []
    assert {row["figure_id"] for row in figure_payload["figures"]} == {
        "monte_carlo_equity_fans",
        "monte_carlo_terminal_returns",
        "monte_carlo_drawdown_ruin",
        "monte_carlo_regimes",
    }


def test_classical_monte_carlo_is_byte_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=120, sigma=0.02)
    validation = runner.invoke(app, ["validate", "SPY", *_VALIDATE])
    assert validation.exit_code == 0, validation.output
    source = next((tmp_path / "runs").iterdir()).name
    args = [
        "monte-carlo",
        "classical",
        "--from-run",
        source,
        "--paths",
        "16",
        "--regime-window",
        "3",
        "--min-state-observations",
        "2",
        "--min-state-transitions",
        "1",
        "--seed",
        "7",
    ]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    rdir = next(path for path in (tmp_path / "runs").iterdir() if path.name != source)
    before = {path.name: path.read_bytes() for path in rdir.iterdir()}
    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.output
    after = {path.name: path.read_bytes() for path in rdir.iterdir()}
    assert before == after


def test_classical_non_estimable_regime_publishes_fail_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=120, sigma=0.02)
    validation = runner.invoke(app, ["validate", "SPY", *_VALIDATE])
    assert validation.exit_code == 0, validation.output
    source = next((tmp_path / "runs").iterdir()).name
    result = runner.invoke(
        app,
        [
            "monte-carlo",
            "classical",
            "--from-run",
            source,
            "--paths",
            "8",
            "--regime-window",
            "3",
            "--min-state-observations",
            "1000",
        ],
    )
    assert result.exit_code == 0, result.output
    rdir = next(path for path in (tmp_path / "runs").iterdir() if path.name != source)
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["status"] == "fail"
    regime = next(row for row in manifest["families"] if row["family"] == "regime_switching")
    assert regime["status"] == "not_estimable"
    assert regime["n_paths"] == 0
    assert regime["terminal_return_q50"] is None
    assert pl.read_parquet(rdir / "paths.parquet")["family"].unique().sort().to_list() == [
        "iid_empirical",
        "student_t",
    ]


def test_kronos_monte_carlo_replays_fake_ohlcv_paths_through_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=120, sigma=0.02)
    validation = runner.invoke(app, ["validate", "SPY", *_VALIDATE])
    assert validation.exit_code == 0, validation.output
    source_dir = next((tmp_path / "runs").iterdir())
    evaluation = runner.invoke(
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
            "4",
            "--stride",
            "4",
            "--samples",
            "8",
        ],
    )
    assert evaluation.exit_code == 0, evaluation.output
    eval_dir = next((tmp_path / "forecast").iterdir())

    kronos_args = [
        "monte-carlo",
        "kronos",
        "--from-run",
        source_dir.name,
        "--forecast-eval-run",
        eval_dir.name,
        "--model",
        "fake",
        "--context",
        "20",
        "--paths",
        "2",
        "--seed",
        "23",
    ]
    result = runner.invoke(app, kronos_args)
    assert result.exit_code == 0, result.output
    run_dirs = [path for path in (tmp_path / "runs").iterdir() if path != source_dir]
    assert len(run_dirs) == 1
    rdir = run_dirs[0]
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["command"] == "monte_carlo_kronos"
    assert manifest["forecast_eval_run_id"] == eval_dir.name
    assert manifest["model"]["model_id"] == "fake"
    assert manifest["family"]["family"] == "kronos_synthetic"
    assert manifest["status"] == "warning"  # fixture lies wholly before the pretraining cutoff

    synthetic = pl.read_parquet(rdir / "synthetic_bars.parquet")
    paths = pl.read_parquet(rdir / "paths.parquet")
    metrics = pl.read_parquet(rdir / "path_metrics.parquet")
    source_manifest = json.loads((source_dir / "manifest.json").read_text())
    assert synthetic.height == 2 * (120 - source_manifest["metadata"]["train_size"])
    assert synthetic.select("path_index").n_unique() == 2
    assert paths.height == 2 * manifest["horizon"]
    assert metrics.height == 2
    assert (rdir / "model_diagnostics.json").is_file()
    assert (rdir / "report.md").is_file()
    figures = runner.invoke(app, ["figures", "render", rdir.name, "--json"])
    assert figures.exit_code == 0, figures.output
    figure_payload = json.loads(figures.output)
    assert figure_payload["failed"] == []
    assert {row["figure_id"] for row in figure_payload["figures"]} == {
        "monte_carlo_equity_fans",
        "monte_carlo_terminal_returns",
        "monte_carlo_drawdown_ruin",
        "kronos_monte_carlo_calibration",
    }
    before = {path.name: path.read_bytes() for path in rdir.iterdir()}
    repeated = runner.invoke(app, kronos_args)
    assert repeated.exit_code == 0, repeated.output
    assert {path.name: path.read_bytes() for path in rdir.iterdir()} == before
