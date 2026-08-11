"""Pure pre-hypothesis descriptive analytics: deterministic, fail-loud, engine-free."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from alpha_core import DataError
from alpha_research.descriptives import (
    autocorrelation,
    coverage_summary,
    effective_sample_size,
    return_distribution,
    seasonality_by_weekday,
    volatility_regime_tags,
)


def _sessions(count: int, *, start_hour: int = 14) -> list[datetime]:
    base = datetime(2026, 1, 5, start_hour, tzinfo=UTC)  # a Monday
    stamps: list[datetime] = []
    current = base
    while len(stamps) < count:
        if current.weekday() < 5:
            stamps.append(current)
        current += timedelta(days=1)
    return stamps


def test_coverage_summary_reports_gaps_duplicates_and_disorder_without_crashing() -> None:
    stamps = _sessions(6)
    stamps = [*stamps[:3], stamps[2], *stamps[4:]]  # one duplicate, one missing session
    stamps[4], stamps[5] = stamps[5], stamps[4]  # one disorder
    summary = coverage_summary(stamps, expected_interval_seconds=86_400.0)
    assert summary["n"] == 6
    assert summary["duplicate_count"] == 1
    assert summary["disorder_count"] == 1
    assert int(cast(int, summary["gap_count"])) >= 1
    assert float(cast(float, summary["max_gap_seconds"])) >= 2 * 86_400.0
    assert summary["start"] == stamps[0].isoformat()
    with pytest.raises(DataError, match="empty"):
        coverage_summary([], expected_interval_seconds=60.0)
    with pytest.raises(DataError, match="expected_interval_seconds"):
        coverage_summary(stamps, expected_interval_seconds=0.0)


def test_return_distribution_reports_moments_and_quantiles() -> None:
    closes = [100.0, 101.0, 99.0, 102.0, 103.0, 101.5, 104.0]
    distribution = return_distribution(closes)
    assert distribution["n"] == len(closes) - 1
    assert math.isfinite(float(distribution["mean"]))
    assert float(distribution["std"]) > 0
    assert distribution["min"] <= distribution["q05"] <= distribution["median"]
    assert distribution["median"] <= distribution["q95"] <= distribution["max"]
    assert math.isfinite(float(distribution["skewness"]))
    assert math.isfinite(float(distribution["excess_kurtosis"]))
    with pytest.raises(DataError, match="at least"):
        return_distribution([100.0])
    with pytest.raises(DataError, match="finite"):
        return_distribution([100.0, float("nan"), 101.0])
    with pytest.raises(DataError, match="positive"):
        return_distribution([100.0, -5.0, 101.0])


def test_autocorrelation_matches_known_alternating_series() -> None:
    values = [1.0, -1.0] * 20
    rows = autocorrelation(values, lags=(1, 2))
    by_lag = {row["lag"]: row["autocorrelation"] for row in rows}
    assert by_lag[1] == pytest.approx(-1.0, abs=0.06)
    assert by_lag[2] == pytest.approx(1.0, abs=0.06)
    with pytest.raises(DataError, match="lag"):
        autocorrelation(values, lags=(0,))
    with pytest.raises(DataError, match="lag"):
        autocorrelation([1.0, 2.0], lags=(5,))


def test_seasonality_by_weekday_buckets_every_return_once() -> None:
    stamps = _sessions(10)
    returns = [0.01, -0.01, 0.02, 0.0, 0.01, -0.02, 0.03, 0.0, -0.01, 0.01]
    rows = seasonality_by_weekday(stamps, returns)
    assert [row["bucket"] for row in rows] == ["Mon", "Tue", "Wed", "Thu", "Fri"]
    assert sum(int(cast(int, row["count"])) for row in rows) == len(returns)
    monday = rows[0]
    assert monday["count"] == 2
    assert float(cast(float, monday["mean"])) == pytest.approx((0.01 + (-0.02)) / 2)
    with pytest.raises(DataError, match="length"):
        seasonality_by_weekday(stamps, returns[:-1])


def test_volatility_regime_tags_are_causal_expanding_terciles() -> None:
    calm = [0.001, -0.001] * 30
    wild = [0.05, -0.05] * 30
    tags = volatility_regime_tags([*calm, *wild], window=10)
    assert len(tags) == 120
    assert set(tags[:9]) == {"warmup"}
    assert tags[59] in {"low", "mid", "high"}
    # The wild tail must eventually rank high against the expanding history.
    assert tags[-1] == "high"
    with pytest.raises(DataError, match="window"):
        volatility_regime_tags(calm, window=1)


def test_effective_sample_size_shrinks_under_positive_autocorrelation() -> None:
    assert effective_sample_size(100, 0.0) == pytest.approx(100.0)
    assert effective_sample_size(100, 0.5) == pytest.approx(100.0 / 3.0)
    assert effective_sample_size(100, -0.5) == pytest.approx(300.0)
    with pytest.raises(DataError, match="autocorrelation"):
        effective_sample_size(100, 1.5)
    with pytest.raises(DataError, match="sample"):
        effective_sample_size(0, 0.1)
