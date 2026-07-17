"""``alpha risk scenario`` — stress a stored run's return stream."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app

runner = CliRunner()


def _seed_run_with_equity(data_dir: Path, run_id: str, n: int = 150) -> None:
    rdir = data_dir / "runs" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text('{"command": "backtest_run"}', encoding="utf-8")
    rng = np.random.default_rng(1)
    equity = 1_000_000.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.01, n))
    ts = [datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(n)]
    pl.DataFrame({"ts": ts, "equity": equity.tolist()}).write_parquet(rdir / "equity_curve.parquet")


def test_scenario_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed_run_with_equity(tmp_path, "1111222233334444")
    result = runner.invoke(app, ["risk", "scenario", "--from-run", "1111222233334444", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["run_id"] == "1111222233334444"
    names = [s["name"] for s in payload["scenarios"]]
    assert names[0] == "base" and len(names) == 5
    assert set(payload["scenarios"][0]) >= {"annual_vol", "max_drawdown", "value_at_risk"}


def test_unknown_run_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["risk", "scenario", "--from-run", "deadbeefdeadbeef", "--json"])
    assert result.exit_code != 0


def test_run_without_equity_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    rdir = tmp_path / "optim" / "5555666677778888"
    rdir.mkdir(parents=True)
    (rdir / "manifest.json").write_text('{"command": "optim_grid"}', encoding="utf-8")
    result = runner.invoke(app, ["risk", "scenario", "--from-run", "5555666677778888", "--json"])
    assert result.exit_code != 0  # optim runs have no equity curve
