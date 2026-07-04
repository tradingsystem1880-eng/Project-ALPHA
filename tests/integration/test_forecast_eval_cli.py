"""``alpha forecast eval``: rolling-origin skill manifest + origins parquet + report."""

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
    "16",
]


def _dirs(data_dir: Path) -> list[Path]:
    root = data_dir / "forecast"
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []


def test_forecast_eval_writes_manifest_and_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    assert "-> run " in result.output

    (rdir,) = _dirs(tmp_path)
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["command"] == "forecast_eval"
    assert manifest["model"]["model_id"] == "fake"
    summary = manifest["summary"]
    for key in ("crps_mean", "skill_vs_rw", "skill_vs_bootstrap", "coverage80", "hit_rate"):
        assert key in summary
    # 2020 fixture is entirely pre-cutoff: split populated on the pre side only
    assert manifest["n_origins_pre"] == summary["n_origins"]
    assert manifest["n_origins_post"] == 0
    assert manifest["summary_post_cutoff"] is None
    assert manifest["summary_pre_cutoff"]["n_origins"] == summary["n_origins"]

    origins = pl.read_parquet(rdir / "origins.parquet")
    assert origins.height == summary["n_origins"]
    for col in ("origin_ts", "realized_end_return", "crps", "crps_rw", "hit", "pre_cutoff"):
        assert col in origins.columns
    assert origins["pre_cutoff"].all()


def test_forecast_eval_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    first = runner.invoke(app, _ARGS)
    assert first.exit_code == 0, first.output
    (rdir,) = _dirs(tmp_path)
    manifest_bytes = (rdir / "manifest.json").read_bytes()

    second = runner.invoke(app, _ARGS)
    assert second.exit_code == 0, second.output
    assert _dirs(tmp_path) == [rdir]
    assert (rdir / "manifest.json").read_bytes() == manifest_bytes


def test_forecast_eval_warns_when_no_post_cutoff_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    assert "no post-cutoff origins" in result.output.lower()


def test_forecast_eval_fails_loud_when_nothing_fits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=10)
    result = runner.invoke(
        app, ["forecast", "eval", "SPY", "--model", "fake", "--context", "8", "--horizon", "8"]
    )
    assert result.exit_code != 0
    assert "origin" in result.output.lower()


def test_report_displays_forecast_eval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(app, _ARGS)
    assert result.exit_code == 0, result.output
    (rdir,) = _dirs(tmp_path)

    report = runner.invoke(app, ["report", rdir.name])
    assert report.exit_code == 0, report.output
    assert "forecast_eval" in report.output
    assert "skill_vs_rw" in report.output
    assert "pre-cutoff" in report.output.lower()
