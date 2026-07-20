"""The optimizer publishes all negative configurations before reporting aggregate failure."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import _optim
from alpha_cli.main import app
from alpha_core import DataError
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()


def test_optim_cli_publishes_ledger_when_only_one_config_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)

    def one_success(task: _optim._ConfigTask) -> np.ndarray:
        if task.spec.lookback == 5:
            raise DataError("deliberate failed grid configuration")
        return np.asarray(
            [0.01, -0.004, 0.006, -0.002, 0.008, -0.003, 0.005, -0.001],
            dtype=np.float64,
        )

    monkeypatch.setattr(_optim, "_oos_returns_for", one_success)
    result = runner.invoke(
        app,
        [
            "optim",
            "grid",
            "SPY",
            "--grid",
            "lookback=3,5",
            "--skip",
            "1",
            "--vol-window",
            "3",
            "--rebalance-every",
            "2",
            "--train-size",
            "15",
            "--test-size",
            "5",
            "--embargo",
            "1",
            "--fee-bps",
            "0",
            "--slippage-bps",
            "0",
            "--starting-cash",
            "100000",
            "--pbo-blocks",
            "6",
            "--n-resamples",
            "40",
            "--seed",
            "7",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "FAIL over 2 declared configs (1 successful)" in result.output
    (rdir,) = list((tmp_path / "optim").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["passed"] is False
    assert manifest["n_configs"] == 2
    assert manifest["n_successful_configs"] == 1
    assert manifest["analysis_error"] == (
        "optimization analysis requires >= 2 successful aligned configs, got 1 of 2"
    )
    assert manifest["sharpes"][0] is not None
    assert manifest["sharpes"][1] is None
    assert set(manifest["artifacts"]) >= {"trials.parquet", "trial_ledger.parquet"}

    ledger = pl.read_parquet(rdir / "trial_ledger.parquet")
    assert ledger["trial"].to_list() == [0, 1]
    assert ledger["status"].to_list() == ["passed", "failed"]
    assert ledger["error"].to_list() == [None, "DataError: deliberate failed grid configuration"]
    assert ledger["oos_returns"].list.len().to_list() == [8, 0]

    trials = pl.read_parquet(rdir / "trials.parquet")
    assert trials["trial"].unique().to_list() == [0]
    assert _optim.read_trial_ledger(rdir)[1].status == "failed"


def test_optim_cli_publishes_machine_readable_result_when_every_config_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)

    def all_fail(task: _optim._ConfigTask) -> np.ndarray:
        raise DataError(f"trial lookback {task.spec.lookback} failed")

    monkeypatch.setattr(_optim, "_oos_returns_for", all_fail)
    result = runner.invoke(
        app,
        [
            "optim",
            "grid",
            "SPY",
            "--grid",
            "lookback=3,5",
            "--skip",
            "1",
            "--vol-window",
            "3",
            "--rebalance-every",
            "2",
            "--train-size",
            "15",
            "--test-size",
            "5",
            "--embargo",
            "1",
            "--pbo-blocks",
            "6",
            "--n-resamples",
            "40",
            "--seed",
            "7",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "FAIL over 2 declared configs (0 successful)" in result.output
    (rdir,) = list((tmp_path / "optim").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["analysis_status"] == "failed"
    assert manifest["trial_status_counts"] == {
        "failed": 2,
        "passed": 0,
        "pruned": 0,
        "rejected": 0,
    }
    assert manifest["best_config"] == []
    assert manifest["dsr"] is None
    assert pl.read_parquet(rdir / "trials.parquet").is_empty()
    assert [row.status for row in _optim.read_trial_ledger(rdir)] == ["failed", "failed"]
