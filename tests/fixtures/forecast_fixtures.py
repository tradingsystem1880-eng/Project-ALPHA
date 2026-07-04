"""Deterministic bar builders for alpha_forecast tests (no RNG, no network)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from alpha_core import Bar


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
