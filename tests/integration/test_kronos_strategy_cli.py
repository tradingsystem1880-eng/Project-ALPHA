"""The ``kronos`` strategy end-to-end: backtest, full gauntlet, tier-2 model mode, optim.

All runs use ``ALPHA_FORECAST_MODEL=fake`` (the offline double) — model selection for
strategy runs comes from settings, never from float-valued strategy params.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_KNOBS = [
    "--strategy",
    "kronos",
    "--param",
    "context=6",
    "--param",
    "horizon=3",
    "--param",
    "samples=8",
    "--vol-window",
    "3",
    "--rebalance-every",
    "2",
    "--fee-bps",
    "0",
    "--slippage-bps",
    "0",
    "--starting-cash",
    "100000",
]
_WF = ["--train-size", "12", "--test-size", "6", "--embargo", "1"]


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, n: int = 60) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_FORECAST_MODEL", "fake")
    seed_store(tmp_path, symbol="SPY", n=n)


def _caches(tmp_path: Path) -> list[Path]:
    root = tmp_path / "forecasts"
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []


def test_kronos_backtest_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch)
    result = runner.invoke(app, ["backtest", "run", "SPY", *_KNOBS])
    assert result.exit_code == 0, result.output

    assert len(_caches(tmp_path)) == 1  # auto-precomputed signal cache
    (rdir,) = sorted((tmp_path / "runs").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["params"]["forecast_cache"] == _caches(tmp_path)[0].name
    assert manifest["forecast"]["cache_key"] == _caches(tmp_path)[0].name
    assert manifest["forecast"]["model"]["model_id"] == "fake"
    assert "pretrain" in manifest["forecast"]


def test_kronos_backtest_reuses_the_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch)
    first = runner.invoke(app, ["backtest", "run", "SPY", *_KNOBS])
    assert first.exit_code == 0, first.output
    second = runner.invoke(app, ["backtest", "run", "SPY", *_KNOBS])
    assert second.exit_code == 0, second.output
    assert len(_caches(tmp_path)) == 1  # same inputs -> same key -> no second cache


def test_kronos_validate_full_gauntlet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "validate",
            "SPY",
            *_KNOBS,
            *_WF,
            "--tier1-paths",
            "25",
            "--tier2-paths",
            "4",
            "--n-resamples",
            "50",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output or "FAIL" in result.output

    (rdir,) = sorted((tmp_path / "runs").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    forecast = manifest["forecast"]
    assert forecast["tier2_policy"] == "replay"
    assert forecast["cache_key"] in {p.name for p in _caches(tmp_path)}


def test_kronos_validate_tier2_model_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "validate",
            "SPY",
            *_KNOBS,
            *_WF,
            "--tier1-paths",
            "25",
            "--tier2-paths",
            "3",
            "--n-resamples",
            "50",
            "--tier2-mode",
            "model",
        ],
    )
    assert result.exit_code == 0, result.output
    # real-series cache + one cache per synthetic tier-2 path
    assert len(_caches(tmp_path)) == 1 + 3
    (rdir,) = sorted((tmp_path / "runs").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["forecast"]["tier2_policy"] == "model"


def test_tier2_model_mode_rejected_for_non_kronos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "validate",
            "SPY",
            "--lookback",
            "5",
            "--skip",
            "1",
            "--vol-window",
            "3",
            "--tier2-mode",
            "model",
        ],
    )
    assert result.exit_code != 0
    assert "kronos" in result.output


def test_kronos_optim_grid_per_config_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "optim",
            "grid",
            "SPY",
            "--grid",
            "min_edge=0,0.005",
            *_KNOBS,
            *_WF,
            "--n-resamples",
            "50",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(_caches(tmp_path)) == 2  # one signal cache per swept config
