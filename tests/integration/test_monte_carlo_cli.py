"""Immutable classical path-risk Monte Carlo runs from a verified validation source."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from numpy.typing import NDArray
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_core import Bar
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_VALIDATE = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--train-size", "30", "--test-size", "10", "--embargo", "1",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
    "--tier1-paths", "30", "--tier2-paths", "4", "--tier3-paths", "4", "--n-resamples", "100",
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
    regime = next(row for row in manifest["families"] if row["family"] == "regime_switching")
    calm, volatile = manifest["regime_diagnostics"]["state_observations"]
    assert regime["caveats"][0].startswith("Causal states: calm")
    assert f"calm {calm} of {manifest['horizon']} OOS returns" in regime["caveats"][0]
    assert f"volatile {volatile} (" in regime["caveats"][0]
    shares = manifest["regime_diagnostics"]["state_shares"]
    assert sum(shares) == pytest.approx(1.0)
    assert shares == pytest.approx([calm / manifest["horizon"], volatile / manifest["horizon"]])
    for family in manifest["families"]:
        line = next(
            line for line in result.output.splitlines() if line.startswith(f"  {family['family']}:")
        )
        assert "median terminal" in line
        assert "P(ruin" in line
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


def test_classical_monte_carlo_discloses_imbalanced_regime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def imbalanced_states(
        bars: Sequence[Bar],
        return_timestamps: Sequence[datetime],
        *,
        train_size: int,
        window: int,
    ) -> tuple[NDArray[np.int8], float, NDArray[np.float64]]:
        horizon = len(return_timestamps)
        states = np.ones(horizon, dtype=np.int8)
        states[0] = 0
        return states, 0.01, np.full(horizon, 0.02)

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.monte_carlo_cmds._causal_regime_states", imbalanced_states)
    seed_store(tmp_path, symbol="SPY", n=120, sigma=0.02)
    validation = runner.invoke(app, ["validate", "SPY", *_VALIDATE])
    assert validation.exit_code == 0, validation.output
    source = next((tmp_path / "runs").iterdir()).name
    result = runner.invoke(
        app,
        [
            "monte-carlo", "classical", "--from-run", source, "--paths", "8",
            "--regime-window", "3", "--min-state-observations", "1",
            "--min-state-transitions", "1",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    rdir = next(path for path in (tmp_path / "runs").iterdir() if path.name != source)
    manifest = json.loads((rdir / "manifest.json").read_text())
    regime = next(row for row in manifest["families"] if row["family"] == "regime_switching")
    assert regime["status"] != "not_estimable"
    assert manifest["regime_diagnostics"]["state_observations"] == [1, manifest["horizon"] - 1]
    warning = "close to the IID empirical family"
    assert warning in regime["caveats"][1]
    report = (rdir / "report.md").read_text()
    assert f"Regime states: {regime['caveats'][0]} {regime['caveats'][1]}" in report
    assert warning in result.output.splitlines()[-1]


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
    assert regime["caveats"][0].startswith("state 0 needs at least 1000 observations")
    assert regime["caveats"][1].startswith("Causal states: calm")
    assert f"  regime_switching: not estimable; {regime['caveats'][0]}" in result.output
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
