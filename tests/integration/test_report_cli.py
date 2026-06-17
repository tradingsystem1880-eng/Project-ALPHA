"""`alpha report` re-displays a stored run from its manifest alone — no engine, no data needed."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_ARGS = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--train-size", "15", "--test-size", "5", "--embargo", "1",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
    "--tier1-paths", "50", "--tier2-paths", "8", "--n-resamples", "200",
]  # fmt: skip


def test_report_prints_stored_run_without_re_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    validate = runner.invoke(app, ["validate", "SPY", *_ARGS])
    assert validate.exit_code == 0, validate.output
    (rdir,) = list((tmp_path / "runs").iterdir())
    run_id = rdir.name

    # remove the data store: report must rely only on the manifest, never reload/re-run
    shutil.rmtree(tmp_path / "store")

    result = runner.invoke(app, ["report", run_id])
    assert result.exit_code == 0, result.output
    assert run_id in result.output
    assert "verdict:" in result.output
    assert "null[returns_level]" in result.output and "null[full_engine]" in result.output
    assert "CI[sharpe]" in result.output
    assert "gate[randomized_price_null]" in result.output


def test_report_unknown_run_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["report", "nonexistent"])
    assert result.exit_code != 0
