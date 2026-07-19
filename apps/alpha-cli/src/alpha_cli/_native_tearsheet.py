"""Serialize Python-authoritative native tear-sheet analytics into stable Parquet frames."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import polars as pl

from alpha_validation.native_tearsheet import build_native_tearsheet


def native_tearsheet_frames(
    equity: Sequence[tuple[datetime, float]], *, periods_per_year: int
) -> dict[str, pl.DataFrame]:
    """Build the three additive v3 analytics sidecars without writing any files."""

    report = build_native_tearsheet(
        [ts for ts, _ in equity],
        [value for _, value in equity],
        periods_per_year=periods_per_year,
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
            }
            for row in report.rolling
        ],
        schema={
            "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
            "window": pl.Int64(),
            "return_value": pl.Float64(),
            "volatility": pl.Float64(),
            "sharpe": pl.Float64(),
        },
    )
    return {
        "calendar_returns.parquet": calendar,
        "return_distribution.parquet": distribution,
        "rolling_metrics.parquet": rolling,
    }


__all__ = ["native_tearsheet_frames"]
