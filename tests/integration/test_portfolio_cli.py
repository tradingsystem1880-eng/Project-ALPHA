"""`alpha backtest portfolio` runs a basket on the offline fixture and writes a manifest."""

from __future__ import annotations

import json
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
]  # fmt: skip


def test_portfolio_writes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=80, seed=0)
    seed_store(tmp_path, symbol="QQQ", n=80, seed=1)

    result = runner.invoke(app, ["backtest", "portfolio", "SPY", "QQQ", *_ARGS])
    assert result.exit_code == 0, result.output
    assert "portfolio [QQQ, SPY]" in result.output  # canonical (sorted) symbol order

    (rdir,) = list((tmp_path / "portfolio").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["symbols"] == ["QQQ", "SPY"]  # canonical (sorted) order
    assert manifest["weighting"] == "equal"
    assert len(manifest["legs"]) == 2
    assert manifest["n_periods"] > 0
    assert "sharpe_ci" in manifest and "lower" in manifest["sharpe_ci"]
    assert (rdir / "tearsheet.html").exists()  # reporting parity with `alpha validate`

    # the stored run is re-displayable via `alpha report`
    report_out = runner.invoke(app, ["report", manifest["run_id"]])
    assert report_out.exit_code == 0, report_out.output
    assert "metrics:" in report_out.output and "leg[SPY]" in report_out.output


def test_portfolio_rejects_single_symbol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=80)
    result = runner.invoke(app, ["backtest", "portfolio", "SPY", *_ARGS])
    assert result.exit_code != 0  # a portfolio needs >= 2 symbols
