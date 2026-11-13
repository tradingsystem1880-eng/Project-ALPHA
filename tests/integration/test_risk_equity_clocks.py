"""Risk projection must consume a real chronological recorded-equity path."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app

RUN_ID = "c040000000000001"


def _seed(data: Path, timestamps: pl.Series, values: list[float]) -> None:
    run = data / "runs" / RUN_ID
    run.mkdir(parents=True)
    (run / "manifest.json").write_text('{"command":"SYNTHETIC_CLOCK_FIXTURE_NO_FIT"}')
    pl.DataFrame({"ts": timestamps, "equity": values}).write_parquet(run / "equity_curve.parquet")


def _timestamps() -> list[datetime]:
    # Deliberately ragged: this projection's explicit annualization factor is
    # per observation, not a new calendar-frequency inference.
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return [start, start + timedelta(days=2), start + timedelta(days=7)]


@pytest.mark.parametrize("values", [[100.0, 95.0, 100.0], [100.0, 100.0, 100.0]])
@pytest.mark.parametrize("include_basis", [False, True])
def test_ordered_utc_path_retains_metric_values_and_legacy_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, values: list[float], include_basis: bool
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed(tmp_path, pl.Series("ts", _timestamps()), values)
    args = ["risk", "scenario", "--from-run", RUN_ID, "--json"]
    if include_basis:
        args.append("--include-metric-basis")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    body = json.loads(result.stdout)
    base = body["scenarios"][0]
    # Direct level-path oracle: peak100 -> trough95 -> recovery100;
    # flat100 has no loss. Neither path has an invented pre-anchor return.
    expected_drawdown = -0.05 if values[1] == 95.0 else 0.0
    assert base["max_drawdown"] == pytest.approx(expected_drawdown, abs=1e-12, rel=0)
    assert base["total_return"] == pytest.approx(0.0, abs=1e-12, rel=0)
    assert body["provenance"]["as_of"] == _timestamps()[-1].isoformat()
    assert body["provenance"]["periods_per_year"] == 252
    assert ("metric_basis" in body["provenance"]) == include_basis
    if include_basis:
        assert body["provenance"]["metric_basis"]["anchor_value"] == values[0]
        assert body["provenance"]["metric_basis"]["initial_capital_status"] == "unknown"
    assert len(body["scenarios"]) == 5


@pytest.mark.parametrize(
    "kind", ["disordered", "duplicate", "null", "naive", "non_utc", "date", "string"]
)
@pytest.mark.parametrize("include_basis", [False, True])
def test_invalid_equity_clocks_reject_before_publishing_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, include_basis: bool
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    timestamps = _timestamps()
    values = [100.0, 95.0, 100.0]
    if kind == "disordered":
        # Same recorded observations, shuffled. Old file-order calculation
        # reported zero base drawdown instead of the chronological -5%.
        series = pl.Series("ts", [timestamps[1], timestamps[0], timestamps[2]])
        values = [95.0, 100.0, 100.0]
    elif kind == "duplicate":
        series = pl.Series("ts", [timestamps[0], timestamps[0], timestamps[2]])
    elif kind == "null":
        series = pl.Series("ts", [None, timestamps[1], timestamps[2]])
    elif kind == "naive":
        series = pl.Series("ts", [ts.replace(tzinfo=None) for ts in timestamps])
    elif kind == "non_utc":
        series = pl.Series("ts", timestamps).dt.convert_time_zone("Etc/GMT-1")
    elif kind == "date":
        series = pl.Series("ts", [ts.date() for ts in timestamps])
    else:
        series = pl.Series("ts", [ts.isoformat() for ts in timestamps])
    _seed(tmp_path, series, values)
    args = ["risk", "scenario", "--from-run", RUN_ID, "--json"]
    if include_basis:
        args.append("--include-metric-basis")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2, result.output
    message = "strictly increasing" if kind in {"disordered", "duplicate"} else "timezone-aware UTC"
    assert message in result.output
    assert '"scenarios"' not in result.stdout


def test_human_projection_also_rejects_disordered_equity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    timestamps = _timestamps()
    _seed(tmp_path, pl.Series("ts", timestamps[::-1]), [100.0, 95.0, 100.0])
    result = CliRunner().invoke(app, ["risk", "scenario", "--from-run", RUN_ID])
    assert result.exit_code == 2
    assert "strictly increasing" in result.output
    assert "maxdd=" not in result.stdout


@pytest.mark.parametrize("disordered", [False, True])
@pytest.mark.parametrize("include_basis", [False, True])
def test_web_projection_consumes_actual_cli_clock_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, disordered: bool, include_basis: bool
) -> None:
    from fastapi.testclient import TestClient

    from alpha_web.app import create_app

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    timestamps = _timestamps()
    if disordered:
        timestamps = [timestamps[1], timestamps[0], timestamps[2]]
    _seed(tmp_path, pl.Series("ts", timestamps), [100.0, 95.0, 100.0])
    # The production API invokes the actual alpha executable. No CLI result,
    # metrics implementation, reader or HTTP response is replaced by this test.
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/risk/scenario", params={"run_id": RUN_ID, "include_metric_basis": include_basis}
        )
    if disordered:
        assert response.status_code == 422
        assert "strictly increasing" in response.json()["message"]
        assert "scenarios" not in response.json()
    else:
        assert response.status_code == 200
        assert response.json()["scenarios"][0]["max_drawdown"] == pytest.approx(
            -0.05, abs=1e-12, rel=0
        )


@pytest.mark.parametrize("include_basis", [False, True])
def test_invalid_clocks_stop_before_return_computation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, include_basis: bool
) -> None:
    import alpha_validation.metrics as metrics

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed(tmp_path, pl.Series("ts", _timestamps()[::-1]), [100.0, 95.0, 100.0])
    calls = []

    def unexpected_returns(values: object) -> None:
        calls.append(values)
        raise AssertionError("return computation must not consume invalid clocks")

    monkeypatch.setattr(metrics, "to_returns", unexpected_returns)
    args = ["risk", "scenario", "--from-run", RUN_ID, "--json"]
    if include_basis:
        args.append("--include-metric-basis")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert "strictly increasing" in result.output
    assert calls == []
