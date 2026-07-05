"""Web IDE forecast surface: fan-chart data reads + the server-side cone SVG."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from alpha_web import _charts, _runs

_BANDS = {
    "q05": [95.0, 92.0],
    "q25": [99.0, 98.0],
    "q50": [101.0, 103.0],
    "q75": [104.0, 108.0],
    "q95": [109.0, 115.0],
}


def _write_forecast_run(data_dir: Path, run_id: str, *, with_parquet: bool = True) -> None:
    rdir = data_dir / "forecast" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "command": "forecast_run",
        "run_id": run_id,
        "symbol": "BTC-USD",
        "pretrain": {"overlap": True, "cutoff": "2025-08-02"},
        "summary": {"prob_up": 0.61},
    }
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if not with_parquet:
        return
    t0 = datetime(2026, 6, 1, tzinfo=UTC)
    steps = [t0 + timedelta(days=i + 1) for i in range(2)]
    pl.DataFrame(
        {
            "step": [1, 2],
            "ts": steps,
            "q05": _BANDS["q05"],
            "q25": _BANDS["q25"],
            "q50": _BANDS["q50"],
            "q75": _BANDS["q75"],
            "q95": _BANDS["q95"],
            "mean": [100.5, 102.0],
        }
    ).write_parquet(rdir / "quantiles.parquet")
    hist_ts = [t0 - timedelta(days=3 - i) for i in range(3)]
    pl.DataFrame({"ts": hist_ts, "close": [98.0, 99.0, 100.0]}).write_parquet(
        rdir / "history.parquet"
    )


def test_fan_chart_data_reads_quantiles_and_history(tmp_path: Path) -> None:
    _write_forecast_run(tmp_path, "aaaa000000000001")
    data = _runs.fan_chart_data("aaaa000000000001", data_dir=tmp_path)
    assert data is not None
    assert data["history"] == [98.0, 99.0, 100.0]
    for key, expected in _BANDS.items():
        assert data[key] == expected


def test_fan_chart_data_none_without_quantiles(tmp_path: Path) -> None:
    _write_forecast_run(tmp_path, "bbbb000000000002", with_parquet=False)
    assert _runs.fan_chart_data("bbbb000000000002", data_dir=tmp_path) is None
    assert _runs.fan_chart_data("missing0000000ff", data_dir=tmp_path) is None


def test_list_runs_indexes_forecast_runs(tmp_path: Path) -> None:
    _write_forecast_run(tmp_path, "cccc000000000003")
    runs = {r["run_id"]: r for r in _runs.list_runs(data_dir=tmp_path)}
    assert runs["cccc000000000003"]["command"] == "forecast_run"
    assert runs["cccc000000000003"]["label"] == "BTC-USD"


def test_fan_chart_svg_draws_bands_and_median() -> None:
    svg = _charts.fan_chart_svg([98.0, 99.0, 100.0], _BANDS)
    assert svg.startswith("<svg")
    assert svg.count("<polygon") == 2  # q05-q95 outer + q25-q75 inner
    assert svg.count("<polyline") == 2  # history + dashed median
    assert "stroke-dasharray" in svg
    assert 'class="fan-chart"' in svg


def test_fan_chart_svg_has_price_scale_and_origin_marker() -> None:
    svg = _charts.fan_chart_svg([98.0, 99.0, 100.0], _BANDS)
    assert svg.count("<line") >= 5  # horizontal price gridlines + the origin marker
    assert "forecast start" in svg  # the origin marker is labeled
    assert 'text-anchor="end"' in svg  # right-edge price labels


def test_fan_chart_svg_placeholder_when_empty() -> None:
    svg = _charts.fan_chart_svg([], {k: [] for k in _BANDS})
    assert svg.startswith("<svg") and "<polygon" not in svg and "<polyline" not in svg


def test_fan_chart_svg_fails_loud_on_ragged_bands() -> None:
    bad = dict(_BANDS, q95=[109.0])  # length mismatch
    with pytest.raises(ValueError, match="length"):
        _charts.fan_chart_svg([100.0], bad)
