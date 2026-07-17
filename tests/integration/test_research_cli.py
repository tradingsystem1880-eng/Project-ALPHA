"""``alpha research compare`` — rank the strategies by a full backtest of each."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()


def test_compare_ranks_strategies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=400)
    result = runner.invoke(app, ["research", "compare", "SPY", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "SPY" and payload["n_bars"] == 400
    assert len(payload["ranked"]) == 4  # the 4 engine strategies (kronos excluded — needs a cache)
    rets = [r["total_return"] for r in payload["ranked"] if r["total_return"] is not None]
    assert rets == sorted(rets, reverse=True)  # ranked best-first


def test_compare_subset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=400)
    result = runner.invoke(app, ["research", "compare", "SPY", "--strategies", "ma_crossover"])
    assert result.exit_code == 0
    assert "ma_crossover" in result.stdout


def test_compare_no_bars_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["research", "compare", "NOPE", "--json"])
    assert result.exit_code != 0
