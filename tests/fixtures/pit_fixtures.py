"""Deterministic builders for PIT tests — no network, no randomness."""

from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl

from alpha_core import ActionType, CorporateAction


def linear_bars(symbol: str, start: date, n: int, first_close: float = 100.0) -> pl.DataFrame:
    """n daily bars, close increasing by 1.0/day; OHLC kept consistent around close."""
    rows = []
    for i in range(n):
        d = date.fromordinal(start.toordinal() + i)
        c = first_close + i
        rows.append(
            {
                "ts": datetime(d.year, d.month, d.day, tzinfo=UTC),
                "open": c - 0.5,
                "high": c + 0.5,
                "low": c - 1.0,
                "close": c,
                "volume": 1000.0,
            }
        )
    return pl.DataFrame(rows)


def aapl_4for1_split() -> CorporateAction:
    return CorporateAction(
        symbol="AAPL",
        action_type=ActionType.SPLIT,
        ex_date=date(2020, 8, 31),
        announce_date=date(2020, 7, 30),
        ratio=4.0,
    )
