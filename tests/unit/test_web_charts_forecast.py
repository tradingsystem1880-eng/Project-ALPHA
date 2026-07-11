"""forecast_svg: dashed continuation, band polygon, divider, placeholder."""

from __future__ import annotations

from alpha_web._charts import forecast_svg


def test_history_and_dashed_forecast() -> None:
    svg = forecast_svg([100.0, 101.0, 102.0], [103.0, 104.0])
    assert svg.count("<polyline") == 2
    assert 'stroke-dasharray="4 3"' in svg
    assert "<line" in svg  # boundary divider
    assert "<polygon" not in svg  # no band without p10/p90


def test_band_polygon_when_p10_p90() -> None:
    svg = forecast_svg([100.0, 101.0], [102.0, 103.0], p10=[101.0, 101.5], p90=[103.0, 104.5])
    assert "<polygon" in svg
    assert 'fill-opacity="0.12"' in svg


def test_placeholder_when_nothing_to_draw() -> None:
    assert "<polyline" not in forecast_svg([], [100.0])
    assert "<polyline" not in forecast_svg([100.0], [])


def test_forecast_line_starts_at_last_history_point() -> None:
    svg = forecast_svg([100.0, 102.0], [104.0])
    solid, dashed = (part.split('points="')[1].split('"')[0] for part in svg.split("<polyline")[1:])
    assert solid.split()[-1] == dashed.split()[0]
