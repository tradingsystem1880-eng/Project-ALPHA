"""`alpha backtest cross-sectional` runs on the offline fixture and writes a manifest."""

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
    "--top-quantile", "0.25",
]  # fmt: skip


def test_cross_sectional_writes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    for i, (sym, drift) in enumerate(
        {"AAA": 0.012, "BBB": -0.004, "CCC": -0.012, "DDD": 0.004}.items()
    ):
        seed_store(tmp_path, symbol=sym, n=120, seed=i, drift=drift, sigma=0.003)

    result = runner.invoke(app, ["backtest", "cross-sectional", "AAA", "BBB", "CCC", "DDD", *_ARGS])
    assert result.exit_code == 0, result.output
    assert "cross-sectional" in result.output

    (rdir,) = list((tmp_path / "cross_sectional").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["symbols"] == ["AAA", "BBB", "CCC", "DDD"]
    assert manifest["long_short"] is True
    assert manifest["n_periods"] > 0
    assert "sharpe_ci" in manifest


def test_cross_sectional_rejects_single_symbol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="AAA", n=120)
    result = runner.invoke(app, ["backtest", "cross-sectional", "AAA", *_ARGS])
    assert result.exit_code != 0  # needs >= 2 symbols
