"""Deterministic Parquet schemas for native Workstation analytics."""

from datetime import UTC, datetime, timedelta

from alpha_cli._native_tearsheet import native_tearsheet_frames


def test_native_tearsheet_frames_have_stable_long_form_contracts() -> None:
    start = datetime(2022, 1, 3, tzinfo=UTC)
    equity = [
        (start + timedelta(days=index), 100.0 * (1.001 if index % 2 else 0.999) ** index)
        for index in range(140)
    ]

    frames = native_tearsheet_frames(equity, periods_per_year=252)

    assert set(frames) == {
        "calendar_returns.parquet",
        "return_distribution.parquet",
        "rolling_metrics.parquet",
    }
    assert frames["calendar_returns.parquet"].columns == [
        "period_type",
        "year",
        "month",
        "return_value",
    ]
    assert frames["return_distribution.parquet"].columns == [
        "kind",
        "index",
        "left",
        "right",
        "count",
        "probability",
        "theoretical",
        "sample",
    ]
    assert frames["rolling_metrics.parquet"].columns == [
        "ts",
        "window",
        "return_value",
        "volatility",
        "sharpe",
    ]
    assert frames["rolling_metrics.parquet"].height == 14
