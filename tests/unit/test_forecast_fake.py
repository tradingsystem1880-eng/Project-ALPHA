"""``FakeForecaster``: the offline, deterministic test double for the Forecaster protocol."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_forecast import FakeForecaster, Forecaster
from tests.fixtures.forecast_fixtures import daily_bars


def test_satisfies_forecaster_protocol() -> None:
    assert isinstance(FakeForecaster(), Forecaster)


def test_shapes_and_metadata() -> None:
    bars = daily_bars(20)
    r = FakeForecaster().forecast(bars, horizon=5, sample_count=7, seed=3)
    assert r.symbol == "SPY"
    assert r.origin_ts == bars[-1].ts
    assert r.horizon == 5
    assert len(r.samples) == 7
    assert all(len(p.close) == 5 for p in r.samples)
    # weekday-only history -> weekday cadence, first step strictly after the origin
    assert all(t.weekday() < 5 for t in r.step_ts)
    assert r.step_ts[0] > r.origin_ts


def test_deterministic_per_seed() -> None:
    bars = daily_bars(20)
    a = FakeForecaster().forecast(bars, horizon=4, sample_count=5, seed=11)
    b = FakeForecaster().forecast(bars, horizon=4, sample_count=5, seed=11)
    c = FakeForecaster().forecast(bars, horizon=4, sample_count=5, seed=12)
    assert a == b
    assert a != c


def test_samples_are_distinct_paths() -> None:
    bars = daily_bars(20)
    r = FakeForecaster().forecast(bars, horizon=4, sample_count=6, seed=0)
    assert len({p.close for p in r.samples}) > 1


def test_exact_step_timestamps_override_inferred_calendar() -> None:
    bars = daily_bars(20)
    exact = tuple(bars[-1].ts + timedelta(days=offset) for offset in (1, 4, 8))
    result = FakeForecaster().forecast(bars, horizon=3, sample_count=2, step_ts=exact, seed=4)
    assert result.step_ts == exact


def test_fails_loud_on_bad_input() -> None:
    bars = daily_bars(20)
    with pytest.raises(DataError, match="bars"):
        FakeForecaster().forecast([], horizon=3, sample_count=2)
    with pytest.raises(DataError, match="bars"):
        FakeForecaster().forecast(bars[:1], horizon=3, sample_count=2)
    with pytest.raises(DataError, match="horizon"):
        FakeForecaster().forecast(bars, horizon=0, sample_count=2)
    with pytest.raises(DataError, match="sample_count"):
        FakeForecaster().forecast(bars, horizon=3, sample_count=0)
    with pytest.raises(DataError, match="step_ts"):
        FakeForecaster().forecast(bars, horizon=3, sample_count=2, step_ts=(bars[-1].ts,))
    with pytest.raises(DataError, match="tz-aware"):
        FakeForecaster().forecast(
            bars,
            horizon=2,
            sample_count=2,
            step_ts=(datetime(2030, 1, 1), datetime(2030, 1, 2)),
        )
    with pytest.raises(DataError, match="strictly ascending"):
        FakeForecaster().forecast(
            bars,
            horizon=2,
            sample_count=2,
            step_ts=(bars[-1].ts + timedelta(days=2), bars[-1].ts + timedelta(days=1)),
        )
    with pytest.raises(DataError, match="after the forecast origin"):
        FakeForecaster().forecast(
            bars,
            horizon=2,
            sample_count=2,
            step_ts=(bars[-1].ts, bars[-1].ts + timedelta(days=1)),
        )
