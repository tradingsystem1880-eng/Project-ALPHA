"""Serialize Python-authoritative native tear-sheet analytics into stable Parquet frames."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import polars as pl

from alpha_core import DataError
from alpha_validation.native_tearsheet import TradeObservation, build_native_tearsheet


def native_tearsheet_frames(
    equity: Sequence[tuple[datetime, float]],
    *,
    periods_per_year: int,
    gross_exposure: Sequence[float] | None = None,
    net_exposure: Sequence[float] | None = None,
    turnover: Sequence[float] | None = None,
    benchmark_equity: Sequence[float] | None = None,
    benchmark_kind: str | None = None,
    trades: Sequence[TradeObservation] | None = None,
) -> dict[str, pl.DataFrame]:
    """Build additive v3 analytics sidecars without writing any files."""

    if benchmark_equity is not None and not benchmark_kind:
        raise DataError("benchmark_equity requires a non-empty benchmark_kind")
    if benchmark_equity is None and benchmark_kind is not None:
        raise DataError("benchmark_kind cannot be supplied without benchmark_equity")

    report = build_native_tearsheet(
        [ts for ts, _ in equity],
        [value for _, value in equity],
        periods_per_year=periods_per_year,
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        turnover=turnover,
        benchmark_equity=benchmark_equity,
        trades=trades,
    )
    calendar_rows = [
        {
            "period_type": "month",
            "year": row.year,
            "month": row.month,
            "return_value": row.return_value,
        }
        for row in report.monthly
    ] + [
        {
            "period_type": "year",
            "year": row.year,
            "month": None,
            "return_value": row.return_value,
        }
        for row in report.yearly
    ]
    calendar = pl.DataFrame(
        calendar_rows,
        schema={
            "period_type": pl.String(),
            "year": pl.Int64(),
            "month": pl.Int64(),
            "return_value": pl.Float64(),
        },
    )

    distribution_rows = [
        {
            "kind": "histogram",
            "index": index,
            "left": row.left,
            "right": row.right,
            "count": row.count,
            "probability": None,
            "theoretical": None,
            "sample": None,
        }
        for index, row in enumerate(report.histogram)
    ] + [
        {
            "kind": "qq",
            "index": index,
            "left": None,
            "right": None,
            "count": None,
            "probability": row.probability,
            "theoretical": row.theoretical,
            "sample": row.sample,
        }
        for index, row in enumerate(report.qq)
    ]
    distribution = pl.DataFrame(
        distribution_rows,
        schema={
            "kind": pl.String(),
            "index": pl.Int64(),
            "left": pl.Float64(),
            "right": pl.Float64(),
            "count": pl.Int64(),
            "probability": pl.Float64(),
            "theoretical": pl.Float64(),
            "sample": pl.Float64(),
        },
    )

    rolling = pl.DataFrame(
        [
            {
                "ts": row.ts,
                "window": 126,
                "return_value": row.return_value,
                "volatility": row.volatility,
                "sharpe": row.sharpe,
                "gross_exposure": row.gross_exposure,
                "net_exposure": row.net_exposure,
                "turnover": row.turnover,
                "exposure_available": report.exposure_available,
                "turnover_available": report.turnover_available,
            }
            for row in report.rolling
        ],
        schema={
            "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
            "window": pl.Int64(),
            "return_value": pl.Float64(),
            "volatility": pl.Float64(),
            "sharpe": pl.Float64(),
            "gross_exposure": pl.Float64(),
            "net_exposure": pl.Float64(),
            "turnover": pl.Float64(),
            "exposure_available": pl.Boolean(),
            "turnover_available": pl.Boolean(),
        },
    )
    benchmark = pl.DataFrame(
        [
            {
                "ts": row.ts,
                "strategy_equity": row.strategy_equity,
                "benchmark_equity": row.benchmark_equity,
                "strategy_return": row.strategy_return,
                "benchmark_return": row.benchmark_return,
                "excess_return": row.excess_return,
                "available": report.benchmark_available,
                "benchmark_kind": benchmark_kind if report.benchmark_available else None,
                "unavailable_reason": (
                    None if report.benchmark_available else "benchmark_input_unavailable"
                ),
            }
            for row in report.benchmark
        ],
        schema={
            "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
            "strategy_equity": pl.Float64(),
            "benchmark_equity": pl.Float64(),
            "strategy_return": pl.Float64(),
            "benchmark_return": pl.Float64(),
            "excess_return": pl.Float64(),
            "available": pl.Boolean(),
            "benchmark_kind": pl.String(),
            "unavailable_reason": pl.String(),
        },
    )
    trade_statistics = pl.DataFrame(
        [
            {
                "metric": row.metric,
                "value": row.value,
                "unit": row.unit,
                "available": row.available,
                "unavailable_reason": row.unavailable_reason,
            }
            for row in report.trade_statistics
        ],
        schema={
            "metric": pl.String(),
            "value": pl.Float64(),
            "unit": pl.String(),
            "available": pl.Boolean(),
            "unavailable_reason": pl.String(),
        },
    )
    exposure_turnover = pl.DataFrame(
        [
            {
                "start_ts": row.start_ts,
                "end_ts": row.end_ts,
                "gross_exposure": row.gross_exposure,
                "net_exposure": row.net_exposure,
                "turnover": row.turnover,
                "exposure_available": report.exposure_available,
                "turnover_available": report.turnover_available,
                "exposure_unavailable_reason": (
                    None if report.exposure_available else "portfolio_state_trace_unavailable"
                ),
                "turnover_unavailable_reason": (
                    None if report.turnover_available else "fill_turnover_unavailable"
                ),
            }
            for row in report.exposure_turnover
        ],
        schema={
            "start_ts": pl.Datetime(time_unit="us", time_zone="UTC"),
            "end_ts": pl.Datetime(time_unit="us", time_zone="UTC"),
            "gross_exposure": pl.Float64(),
            "net_exposure": pl.Float64(),
            "turnover": pl.Float64(),
            "exposure_available": pl.Boolean(),
            "turnover_available": pl.Boolean(),
            "exposure_unavailable_reason": pl.String(),
            "turnover_unavailable_reason": pl.String(),
        },
    )
    return {
        "calendar_returns.parquet": calendar,
        "benchmark_comparison.parquet": benchmark,
        "exposure_turnover.parquet": exposure_turnover,
        "return_distribution.parquet": distribution,
        "rolling_metrics.parquet": rolling,
        "trade_statistics.parquet": trade_statistics,
    }


__all__ = ["native_tearsheet_frames"]
