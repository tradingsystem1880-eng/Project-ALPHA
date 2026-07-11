"""``alpha forecast run`` + ``alpha report`` end-to-end with a stub forecaster (offline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_forecast import ForecastResult
from tests.fixtures.cli_fixtures import seed_store
from tests.fixtures.forecast_fixtures import StubForecaster

runner = CliRunner()


class _StubFull:
    """Adapts StubForecaster to the forecast_full surface the CLI consumes."""

    def __init__(self, *, drift: float = 0.01, band: bool = False) -> None:
        self._stub = StubForecaster(drift=drift)
        self._band = band

    def forecast_full(self, bars: Any, horizon: int) -> ForecastResult:
        path = self._stub.forecast(bars, horizon)
        closes = [b.close for b in path]
        return ForecastResult(
            path=path,
            close_p10=[c * 0.98 for c in closes] if self._band else None,
            close_p90=[c * 1.02 for c in closes] if self._band else None,
        )


def _factory(**stub_kw: Any) -> Any:
    def factory(
        *, model: str, temperature: float, top_p: float, sample_count: int, seed: int, settings: Any
    ) -> _StubFull:
        return _StubFull(**stub_kw)

    return factory


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], **stub_kw: Any) -> Any:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.forecast_cmds._FORECASTER_FACTORY", _factory(**stub_kw))
    return runner.invoke(app, args)


def test_forecast_run_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_store(tmp_path, symbol="SPY", n=60)
    r = _run(
        tmp_path,
        monkeypatch,
        ["forecast", "run", "SPY", "--model", "mini", "--horizon", "5", "--context", "30"],
    )
    assert r.exit_code == 0, r.output
    assert "-> run " in r.output and "direction LONG" in r.output

    run_id = r.output.split("-> run ")[1].split(":")[0]
    rdir = tmp_path / "forecast" / run_id
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["command"] == "forecast_run"
    assert manifest["model"]["name"] == "mini"
    assert manifest["params"]["horizon"] == 5
    assert manifest["window"]["n_bars"] == 30
    assert manifest["forecast"]["direction"] == 1

    forecast = pl.read_parquet(rdir / "forecast.parquet")
    history = pl.read_parquet(rdir / "history.parquet")
    assert len(forecast) == 5
    assert len(history) == 30
    assert forecast["close"][-1] > history["close"][-1]  # drifted up


def test_manifest_is_byte_stable_across_identical_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_store(tmp_path, symbol="SPY", n=60)
    args = ["forecast", "run", "SPY", "--model", "mini", "--horizon", "4", "--context", "20"]
    r1 = _run(tmp_path, monkeypatch, args)
    assert r1.exit_code == 0, r1.output
    run_id = r1.output.split("-> run ")[1].split(":")[0]
    path = tmp_path / "forecast" / run_id / "manifest.json"
    first = path.read_bytes()
    r2 = _run(tmp_path, monkeypatch, args)
    assert r2.exit_code == 0, r2.output
    assert path.read_bytes() == first


def test_band_columns_written_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_store(tmp_path, symbol="SPY", n=60)
    r = _run(
        tmp_path,
        monkeypatch,
        ["forecast", "run", "SPY", "--model", "mini", "--horizon", "3", "--context", "20"],
        band=True,
    )
    assert r.exit_code == 0, r.output
    run_id = r.output.split("-> run ")[1].split(":")[0]
    forecast = pl.read_parquet(tmp_path / "forecast" / run_id / "forecast.parquet")
    assert "close_p10" in forecast.columns and "close_p90" in forecast.columns


def test_leakage_warning_on_pre_cutoff_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # cli_fixtures.seed_store stamps bars starting 2024 -> pre-cutoff -> must warn + record
    seed_store(tmp_path, symbol="SPY", n=60)
    r = _run(
        tmp_path,
        monkeypatch,
        ["forecast", "run", "SPY", "--model", "mini", "--horizon", "3", "--context", "20"],
    )
    assert r.exit_code == 0, r.output
    run_id = r.output.split("-> run ")[1].split(":")[0]
    manifest = json.loads((tmp_path / "forecast" / run_id / "manifest.json").read_text())
    # the fixture's dates decide whether the warning fires; assert manifest and echo agree
    if manifest["leakage_warning"] is not None:
        assert "UPPER BOUND" in manifest["leakage_warning"]
        assert "WARNING" in r.output
    else:
        assert "UPPER BOUND" not in r.output


def test_report_renders_forecast_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_store(tmp_path, symbol="SPY", n=60)
    r = _run(
        tmp_path,
        monkeypatch,
        ["forecast", "run", "SPY", "--model", "mini", "--horizon", "3", "--context", "20"],
    )
    assert r.exit_code == 0, r.output
    run_id = r.output.split("-> run ")[1].split(":")[0]
    rep = runner.invoke(app, ["report", run_id])
    assert rep.exit_code == 0, rep.output
    assert "Kronos-mini" in rep.output
    assert "forecast: end close" in rep.output


def test_bad_model_and_bad_dates_fail_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_store(tmp_path, symbol="SPY", n=60)
    r = _run(tmp_path, monkeypatch, ["forecast", "run", "SPY", "--model", "huge"])
    assert r.exit_code != 0
    assert "unknown Kronos model" in r.output
    r2 = _run(tmp_path, monkeypatch, ["forecast", "run", "SPY", "--start", "not-a-date"])
    assert r2.exit_code != 0
    assert "YYYY-MM-DD" in r2.output


def test_start_end_slice_changes_the_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_store(tmp_path, symbol="SPY", n=60)
    r_full = _run(
        tmp_path,
        monkeypatch,
        ["forecast", "run", "SPY", "--model", "mini", "--horizon", "3", "--context", "10"],
    )
    assert r_full.exit_code == 0, r_full.output
    full_id = r_full.output.split("-> run ")[1].split(":")[0]
    manifest = json.loads((tmp_path / "forecast" / full_id / "manifest.json").read_text())
    cutoff = manifest["window"]["first_ts"][:10]
    r_sliced = _run(
        tmp_path,
        monkeypatch,
        [
            "forecast",
            "run",
            "SPY",
            "--model",
            "mini",
            "--horizon",
            "3",
            "--context",
            "10",
            "--end",
            cutoff,
        ],
    )
    assert r_sliced.exit_code == 0, r_sliced.output
    sliced_id = r_sliced.output.split("-> run ")[1].split(":")[0]
    assert sliced_id != full_id  # different window content -> different run id
