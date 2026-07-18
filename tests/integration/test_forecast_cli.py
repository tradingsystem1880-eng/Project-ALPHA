"""``alpha forecast run``: artifacts, determinism, leakage warning, report display."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_ARGS = [
    "forecast",
    "run",
    "SPY",
    "--model",
    "fake",
    "--context",
    "8",
    "--horizon",
    "5",
    "--samples",
    "20",
]


def _forecast_dirs(data_dir: Path) -> list[Path]:
    root = data_dir / "forecast"
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []


def test_forecast_run_writes_manifest_paths_quantiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=30)

    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    assert "-> run " in result.output

    (rdir,) = _forecast_dirs(tmp_path)
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["command"] == "forecast_run"
    assert manifest["symbol"] == "SPY"
    assert manifest["model"]["model_id"] == "fake"
    assert manifest["params"]["horizon"] == 5
    assert manifest["params"]["samples"] == 20
    assert manifest["pretrain"]["overlap"] is True  # fixture bars are 2020 < default cutoff
    for key in ("median_end_return", "p05_end_return", "p95_end_return", "prob_up"):
        assert key in manifest["summary"]

    paths = pl.read_parquet(rdir / "paths.parquet")
    assert paths.height == 20 * 5
    assert set(paths.columns) == {"sample", "step", "ts", "open", "high", "low", "close", "volume"}
    quantiles = pl.read_parquet(rdir / "quantiles.parquet")
    assert quantiles.height == 5
    assert {"step", "ts", "q05", "q25", "q50", "q75", "q95", "mean"} == set(quantiles.columns)
    # per-step band ordering
    for row in quantiles.iter_rows(named=True):
        assert row["q05"] <= row["q25"] <= row["q50"] <= row["q75"] <= row["q95"]
    history = pl.read_parquet(rdir / "history.parquet")
    assert history.height == 30  # full fixture (< 120-bar tail cap)
    assert set(history.columns) == {"ts", "close"}


def test_forecast_run_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=30)

    first = runner.invoke(app, _ARGS)
    assert first.exit_code == 0, first.output
    (rdir,) = _forecast_dirs(tmp_path)
    manifest_bytes = (rdir / "manifest.json").read_bytes()

    second = runner.invoke(app, _ARGS)
    assert second.exit_code == 0, second.output
    assert _forecast_dirs(tmp_path) == [rdir]  # same run id -> same dir
    assert (rdir / "manifest.json").read_bytes() == manifest_bytes


def test_forecast_run_warns_on_pretrain_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=30)
    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    assert "pretrain" in result.output.lower()
    assert "warning" in result.output.lower()


def test_forecast_run_clean_when_post_cutoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_FORECAST_PRETRAIN_CUTOFF", "2019-01-01")  # fixture is 2020 > cutoff
    seed_store(tmp_path, symbol="SPY", n=30)
    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    assert "warning" not in result.output.lower()
    (rdir,) = _forecast_dirs(tmp_path)
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["pretrain"]["overlap"] is False


def test_forecast_run_fails_loud_below_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=10)
    result = runner.invoke(app, ["forecast", "run", "SPY", "--model", "fake", "--context", "100"])
    assert result.exit_code != 0
    assert "100" in result.output and "10" in result.output


def test_forecast_run_threads_offline_settings_into_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import Any

    from alpha_cli import forecast_cmds
    from alpha_forecast import FakeForecaster

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_FORECAST_HUB_CACHE", "data/models")
    monkeypatch.setenv("ALPHA_FORECAST_LOCAL_ONLY", "1")
    seed_store(tmp_path, symbol="SPY", n=30)

    calls: list[dict[str, Any]] = []

    def recording_factory(**kwargs: Any) -> FakeForecaster:
        calls.append(kwargs)
        return FakeForecaster()

    # forecast_cmds binds the factory at import time — patch its module-level name
    monkeypatch.setattr(forecast_cmds, "_forecaster_factory", recording_factory)

    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    (call,) = calls
    assert call["hub_cache"] == Path("data/models")
    assert call["local_files_only"] is True


def test_report_displays_forecast_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=30)
    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    (rdir,) = _forecast_dirs(tmp_path)

    report = runner.invoke(app, ["report", rdir.name])
    assert report.exit_code == 0, report.output
    assert "forecast_run" in report.output
    assert "fake" in report.output
    assert "PRETRAIN OVERLAP" in report.output
