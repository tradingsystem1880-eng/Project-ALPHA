"""Deterministic bar builders + store writers for alpha_forecast tests (no RNG, no network)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl

from alpha_core import Bar


def store_bars(data_dir: Path, bars: list[Bar]) -> None:
    """Write ``bars`` into the CLI store (``data_dir/store``) for one symbol."""
    from alpha_data.store import ParquetStore

    frame = pl.DataFrame(
        [
            {
                "ts": b.ts,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ]
    )
    ParquetStore(data_dir / "store").write_bars(bars[0].symbol, frame)


def daily_bars(
    n: int,
    *,
    symbol: str = "SPY",
    start: date = date(2026, 1, 5),  # a Monday
    calendar: bool = False,
    price0: float = 100.0,
    drift: float = 0.001,
) -> list[Bar]:
    """``n`` ascending daily bars: weekday cadence by default, calendar cadence (crypto) if
    ``calendar``. Prices follow a deterministic drift so tests can assert exact values."""
    bars: list[Bar] = []
    d = start
    close = price0
    while len(bars) < n:
        if calendar or d.weekday() < 5:
            prev = close
            close = close * (1.0 + drift)
            high = max(prev, close) * 1.001
            low = min(prev, close) * 0.999
            bars.append(
                Bar(
                    symbol=symbol,
                    ts=datetime(d.year, d.month, d.day, tzinfo=UTC),
                    open=prev,
                    high=high,
                    low=low,
                    close=close,
                    volume=1_000.0,
                )
            )
        d = d + timedelta(days=1)
    return bars
