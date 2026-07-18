"""`alpha optim grid` runs a sweep on the offline fixture and writes a verdict manifest."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from click import unstyle
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_validation.metrics import sharpe_ratio
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_ARGS = [
    "--grid", "lookback=3,5",
    "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--train-size", "15", "--test-size", "5", "--embargo", "1",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
    "--pbo-blocks", "6", "--n-resamples", "120", "--seed", "7",
]  # fmt: skip


def test_optim_writes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)

    result = runner.invoke(app, ["optim", "grid", "SPY", *_ARGS])
    assert result.exit_code == 0, result.output
    assert "optim SPY" in result.output
    assert "PASS" in result.output or "FAIL" in result.output

    (rdir,) = list((tmp_path / "optim").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["n_configs"] == 2
    assert len(manifest["sharpes"]) == 2
    assert set(manifest) >= {"best_config", "dsr", "pbo", "spa", "reality_check", "passed"}
    assert isinstance(manifest["passed"], bool)

    # the per-trial OOS return matrix rides alongside the manifest (trials.parquet)
    trials = pl.read_parquet(rdir / "trials.parquet")
    assert trials.columns == ["trial", "step", "oos_return"]
    assert trials.schema["trial"] == pl.Int64
    assert trials.schema["step"] == pl.Int64
    assert trials.schema["oos_return"] == pl.Float64
    assert trials.height == manifest["n_configs"] * manifest["n_oos"]
    assert trials.sort(["trial", "step"]).equals(trials)  # stored in (trial, step) order
    # per-trial reconstruction: the best trial's rows reproduce the manifest's best_sharpe
    best_idx = int(np.argmax(manifest["sharpes"]))
    best = trials.filter(pl.col("trial") == best_idx).sort("step")["oos_return"].to_numpy()
    assert best.size == manifest["n_oos"]
    assert sharpe_ratio(best, periods_per_year=252) == pytest.approx(
        manifest["best_sharpe"], rel=1e-12
    )


def test_optim_rejects_empty_grid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)
    result = runner.invoke(app, ["optim", "grid", "SPY", "--train-size", "15"])
    assert result.exit_code != 0  # no --grid axis provided


def test_optim_rejects_duplicate_normalized_axes() -> None:
    result = runner.invoke(
        app,
        [
            "optim",
            "grid",
            "SPY",
            "--grid",
            "vol-window=2",
            "--grid",
            "vol_window=4",
        ],
    )
    assert result.exit_code != 0
    assert "duplicate --grid axis 'vol_window'" in unstyle(result.output)


def test_optim_grid_accepts_hyphenated_axis_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CLI-conventional `vol-window` must map to the canonical RunSpec field `vol_window`, not
    # silently become an ignored strategy param that leaves vol_window fixed at its default.
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)
    args = [
        "--grid", "vol-window=2,4",  # hyphenated axis — must normalize to vol_window
        "--lookback", "5", "--skip", "1", "--rebalance-every", "2",
        "--train-size", "15", "--test-size", "5", "--embargo", "1",
        "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
        "--pbo-blocks", "6", "--n-resamples", "120", "--seed", "7",
    ]  # fmt: skip
    result = runner.invoke(app, ["optim", "grid", "SPY", *args])
    assert result.exit_code == 0, result.output

    (rdir,) = list((tmp_path / "optim").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    axis_names = {name for config in manifest["configs"] for name, _ in config}
    assert axis_names == {"vol_window"}  # normalized to the canonical field, swept as intended
