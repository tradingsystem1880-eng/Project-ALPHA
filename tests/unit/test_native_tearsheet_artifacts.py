"""Deterministic Parquet schemas for native Workstation analytics."""

from datetime import UTC, datetime, timedelta

import pytest

from alpha_cli._native_tearsheet import native_tearsheet_frames
from alpha_core import DataError
from alpha_validation.native_tearsheet import TradeObservation


def test_native_tearsheet_frames_have_stable_long_form_contracts() -> None:
    start = datetime(2022, 1, 3, tzinfo=UTC)
    equity = [
        (start + timedelta(days=index), 100.0 * (1.001 if index % 2 else 0.999) ** index)
        for index in range(140)
    ]

    frames = native_tearsheet_frames(equity, periods_per_year=252)

    assert set(frames) == {
        "calendar_returns.parquet",
        "benchmark_comparison.parquet",
        "exposure_turnover.parquet",
        "return_distribution.parquet",
        "rolling_metrics.parquet",
        "trade_statistics.parquet",
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
        "gross_exposure",
        "net_exposure",
        "turnover",
        "exposure_available",
        "turnover_available",
    ]
    assert frames["rolling_metrics.parquet"].height == 14
    assert frames["rolling_metrics.parquet"].get_column("gross_exposure").null_count() == 14
    assert (
        frames["rolling_metrics.parquet"].get_column("exposure_available").to_list() == [False] * 14
    )
    assert frames["benchmark_comparison.parquet"].columns == [
        "ts",
        "strategy_equity",
        "benchmark_equity",
        "strategy_return",
        "benchmark_return",
        "excess_return",
        "available",
        "benchmark_kind",
        "unavailable_reason",
    ]
    assert frames["benchmark_comparison.parquet"].height == len(equity)
    assert frames["benchmark_comparison.parquet"].get_column("available").to_list() == [
        False
    ] * len(equity)
    exposure = frames["exposure_turnover.parquet"]
    assert exposure.columns == [
        "start_ts",
        "end_ts",
        "gross_exposure",
        "net_exposure",
        "turnover",
        "exposure_available",
        "turnover_available",
        "exposure_unavailable_reason",
        "turnover_unavailable_reason",
    ]
    assert exposure.get_column("exposure_available").to_list() == [False] * (len(equity) - 1)
    assert exposure.get_column("gross_exposure").null_count() == len(equity) - 1
    assert frames["trade_statistics.parquet"].columns == [
        "metric",
        "value",
        "unit",
        "available",
        "unavailable_reason",
    ]
    assert frames["trade_statistics.parquet"].height > 0
    assert (
        frames["trade_statistics.parquet"].get_column("available").to_list()
        == [False] * frames["trade_statistics.parquet"].height
    )


def test_native_tearsheet_frames_publish_only_supplied_execution_evidence() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    equity = [(start + timedelta(days=index), 100.0 + index) for index in range(4)]
    frames = native_tearsheet_frames(
        equity,
        periods_per_year=252,
        gross_exposure=[0.5, 0.75, 0.25],
        net_exposure=[0.5, -0.75, 0.25],
        turnover=[0.5, 1.25, 0.75],
        benchmark_equity=[1.0, 1.01, 1.00, 1.03],
        benchmark_kind="passive_open_to_open_price_only",
        trades=[
            TradeObservation(
                side="BUY",
                realized_pnl=10.0,
                realized_return=0.01,
                entry_ts=start,
                exit_ts=start + timedelta(days=1),
            )
        ],
    )

    benchmark = frames["benchmark_comparison.parquet"]
    assert benchmark.get_column("available").to_list() == [True] * 4
    assert benchmark.get_column("benchmark_kind").unique().to_list() == [
        "passive_open_to_open_price_only"
    ]
    exposure = frames["exposure_turnover.parquet"]
    assert exposure.get_column("gross_exposure").to_list() == [0.5, 0.75, 0.25]
    assert exposure.get_column("turnover").to_list() == [0.5, 1.25, 0.75]
    stats = frames["trade_statistics.parquet"]
    assert stats.filter(stats["metric"] == "trade_count").get_column("value").item() == 1.0


def test_benchmark_series_requires_named_provenance() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    equity = [(start, 100.0), (start + timedelta(days=1), 101.0)]
    with pytest.raises(DataError, match="benchmark_kind"):
        native_tearsheet_frames(
            equity,
            periods_per_year=252,
            benchmark_equity=[1.0, 1.01],
        )
