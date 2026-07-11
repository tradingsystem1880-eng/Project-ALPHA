"""Deterministic forecast fixtures: bar factories + a window-recording stub forecaster."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from alpha_core import Bar


def daily_bars(
    *, symbol: str = "TEST", n: int = 30, start_price: float = 100.0, drift: float = 0.001
) -> list[Bar]:
    """Weekday-stamped daily bars with a deterministic geometric drift."""
    out: list[Bar] = []
    ts = datetime(2026, 1, 2, tzinfo=UTC)  # a Friday
    price = start_price
    while len(out) < n:
        if ts.weekday() < 5:
            price *= 1.0 + drift
            out.append(
                Bar(
                    symbol=symbol,
                    ts=ts,
                    open=price / (1.0 + drift),
                    high=price * 1.01,
                    low=price * 0.985 / (1.0 + drift),
                    close=price,
                    volume=1_000_000.0,
                )
            )
        ts += timedelta(days=1)
    return out


class StubForecaster:
    """BarForecaster stub: extends the last close at a fixed per-bar drift.

    Records every window it is handed (as tuples of Bars) so bias guards can assert the
    strategy never fed it anything beyond the decision bar.
    """

    def __init__(self, *, drift: float = 0.01) -> None:
        self.drift = drift
        self.received_windows: list[tuple[Bar, ...]] = []

    def forecast(self, bars: Sequence[Bar], horizon: int) -> list[Bar]:
        self.received_windows.append(tuple(bars))
        last = bars[-1]
        spacing = bars[-1].ts - bars[-2].ts if len(bars) >= 2 else timedelta(days=1)
        out: list[Bar] = []
        price = last.close
        ts = last.ts
        for _ in range(horizon):
            price *= 1.0 + self.drift
            ts = ts + spacing
            out.append(
                Bar(
                    symbol=last.symbol,
                    ts=ts,
                    open=price / (1.0 + self.drift),
                    high=max(price, price / (1.0 + self.drift)) * 1.001,
                    low=min(price, price / (1.0 + self.drift)) * 0.999,
                    close=price,
                    volume=last.volume,
                )
            )
        return out
