"""FakeForecaster is a pure function of (window, seed): bars outside the window can never
leak in, and any in-window change must change the output (discriminating power). True
PIT causality of the *glue* (only past bars reach the window) is guarded at the CLI layer."""

from __future__ import annotations

import pytest

from alpha_core import Bar
from alpha_forecast import FakeForecaster
from tests.fixtures.forecast_fixtures import daily_bars

pytestmark = pytest.mark.bias_guard


def _poison_last(bars: list[Bar]) -> list[Bar]:
    last = bars[-1]
    spiked = last.close * 7.7
    return bars[:-1] + [
        Bar(
            symbol=last.symbol,
            ts=last.ts,
            open=last.open,
            high=max(last.high, spiked),
            low=last.low,
            close=spiked,
            volume=last.volume,
        )
    ]


def test_future_bars_beyond_window_cannot_change_forecast() -> None:
    series_a = daily_bars(30)
    series_b = _poison_last(daily_bars(30))  # differs only at index 29
    window = 20
    fake = FakeForecaster()
    a = fake.forecast(series_a[:window], horizon=5, sample_count=4, seed=7)
    b = fake.forecast(series_b[:window], horizon=5, sample_count=4, seed=7)
    assert a == b  # identical windows -> identical forecasts, whatever came later


def test_in_window_poison_changes_forecast() -> None:
    clean = daily_bars(20)
    poisoned = _poison_last(daily_bars(20))  # differs at the window's last bar
    fake = FakeForecaster()
    a = fake.forecast(clean, horizon=5, sample_count=4, seed=7)
    b = fake.forecast(poisoned, horizon=5, sample_count=4, seed=7)
    assert a != b  # otherwise this guard has no discriminating power
