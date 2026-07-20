"""Python-authoritative native tear-sheet series for the Workstation."""

from datetime import UTC, datetime

import pytest

from alpha_core import DataError
from alpha_validation.native_tearsheet import TradeObservation, build_native_tearsheet


def _ts(*values: tuple[int, int, int]) -> list[datetime]:
    return [datetime(year, month, day, tzinfo=UTC) for year, month, day in values]


def test_builds_calendar_distribution_qq_and_rolling_series() -> None:
    report = build_native_tearsheet(
        _ts(
            (2024, 1, 30),
            (2024, 1, 31),
            (2024, 2, 1),
            (2024, 2, 29),
            (2024, 3, 1),
            (2024, 3, 29),
        ),
        [100.0, 110.0, 99.0, 108.0, 118.8, 124.74],
        periods_per_year=252,
        rolling_window=3,
        histogram_bins=4,
    )

    assert [(row.year, row.month) for row in report.monthly] == [
        (2024, 1),
        (2024, 2),
        (2024, 3),
    ]
    assert [row.return_value for row in report.monthly] == pytest.approx(
        [0.1, -0.0181818181818182, 0.155]
    )
    assert [row.year for row in report.yearly] == [2024]
    assert [row.return_value for row in report.yearly] == pytest.approx([0.2474])
    assert sum(row.count for row in report.histogram) == 5
    assert len(report.qq) == 5
    assert [row.sample for row in report.qq] == sorted(row.sample for row in report.qq)
    assert len(report.rolling) == 3
    assert report.rolling[0].ts == datetime(2024, 2, 29, tzinfo=UTC)
    assert report.rolling[0].return_value == pytest.approx(0.08)
    assert report.rolling[0].volatility > 0.0
    assert report.rolling[0].sharpe is not None


def test_rejects_misaligned_disordered_or_naive_timestamps() -> None:
    ordered = _ts((2024, 1, 1), (2024, 1, 2), (2024, 1, 3))

    with pytest.raises(DataError, match="same length"):
        build_native_tearsheet(ordered, [100.0, 101.0])
    with pytest.raises(DataError, match="strictly increasing"):
        build_native_tearsheet([ordered[0], ordered[2], ordered[1]], [100.0, 101.0, 102.0])
    with pytest.raises(DataError, match="timezone-aware"):
        build_native_tearsheet(
            [datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)],
            [100.0, 101.0, 102.0],
        )


def test_flat_rolling_window_reports_undefined_sharpe_without_fabricating_value() -> None:
    report = build_native_tearsheet(
        _ts((2024, 1, 1), (2024, 1, 2), (2024, 1, 3), (2024, 1, 4)),
        [100.0, 100.0, 100.0, 100.0],
        rolling_window=2,
    )

    assert all(row.volatility == 0.0 for row in report.rolling)
    assert all(row.sharpe is None for row in report.rolling)


def test_builds_exposure_turnover_benchmark_and_trade_statistics_from_supplied_evidence() -> None:
    timestamps = _ts(
        (2024, 1, 1),
        (2024, 1, 2),
        (2024, 1, 3),
        (2024, 1, 4),
    )
    report = build_native_tearsheet(
        timestamps,
        [100.0, 102.0, 101.0, 104.0],
        rolling_window=2,
        gross_exposure=[0.5, 0.75, 0.25],
        net_exposure=[0.5, -0.75, 0.25],
        turnover=[0.5, 1.25, 0.75],
        benchmark_equity=[1.0, 1.01, 1.00, 1.03],
        trades=[
            TradeObservation(
                side="BUY",
                realized_pnl=20.0,
                realized_return=0.02,
                entry_ts=timestamps[0],
                exit_ts=timestamps[1],
            ),
            TradeObservation(
                side="SELL",
                realized_pnl=-5.0,
                realized_return=-0.01,
                entry_ts=timestamps[1],
                exit_ts=timestamps[3],
            ),
        ],
    )

    assert report.exposure_available is True
    assert report.turnover_available is True
    assert report.benchmark_available is True
    assert report.trade_statistics_available is True
    assert report.rolling[0].gross_exposure == pytest.approx(0.625)
    assert report.rolling[0].net_exposure == pytest.approx(-0.125)
    assert report.rolling[0].turnover == pytest.approx(1.75)
    assert report.benchmark[-1].benchmark_equity == pytest.approx(1.03)
    assert report.benchmark[-1].excess_return == pytest.approx(
        (104.0 / 101.0 - 1.0) - (1.03 / 1.0 - 1.0)
    )
    stats = {row.metric: row for row in report.trade_statistics}
    assert stats["trade_count"].value == 2.0
    assert stats["win_rate"].value == pytest.approx(0.5)
    assert stats["profit_factor"].value == pytest.approx(4.0)
    assert stats["average_holding_seconds"].value == pytest.approx(129_600.0)


def test_optional_native_analytics_are_explicitly_unavailable_not_zero_filled() -> None:
    timestamps = _ts((2024, 1, 1), (2024, 1, 2), (2024, 1, 3))
    report = build_native_tearsheet(
        timestamps,
        [100.0, 101.0, 102.0],
        rolling_window=2,
    )

    assert report.exposure_available is False
    assert report.turnover_available is False
    assert report.benchmark_available is False
    assert report.trade_statistics_available is False
    assert report.rolling[0].gross_exposure is None
    assert report.rolling[0].turnover is None
    assert all(row.gross_exposure is None for row in report.exposure_turnover)
    assert all(row.turnover is None for row in report.exposure_turnover)
    assert all(row.benchmark_equity is None for row in report.benchmark)
    assert all(row.available is False for row in report.trade_statistics)


def test_rejects_misaligned_or_impossible_optional_native_analytics() -> None:
    timestamps = _ts((2024, 1, 1), (2024, 1, 2), (2024, 1, 3))
    with pytest.raises(DataError, match="gross_exposure must have 2 values"):
        build_native_tearsheet(timestamps, [100.0, 101.0, 102.0], gross_exposure=[0.5])
    with pytest.raises(DataError, match="net exposure magnitude"):
        build_native_tearsheet(
            timestamps,
            [100.0, 101.0, 102.0],
            gross_exposure=[0.5, 0.5],
            net_exposure=[0.75, 0.5],
        )
    with pytest.raises(DataError, match="benchmark_equity must have 3 values"):
        build_native_tearsheet(
            timestamps,
            [100.0, 101.0, 102.0],
            benchmark_equity=[1.0, 1.01],
        )
