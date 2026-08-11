"""Indicators against hand-computable references, not against themselves.

An indicator test that recomputes the implementation in the test proves only that the code is
self-consistent. Every case here pins a value that can be derived by hand or from the indicator's
published definition, so a silent change in behaviour fails rather than co-varying.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    OHLCV,
    bollinger_bandwidth,
    calendar_features,
    consolidation_length,
    cross_correlation_lags,
    log_returns,
    percentile_rank,
    realized_volatility,
    rolling_correlation,
    rolling_mean,
    rolling_std,
    rsi,
    volume_ratio,
)


def _bars(closes: np.ndarray, volume: np.ndarray | None = None) -> OHLCV:
    n = closes.size
    return OHLCV(
        ts=np.arange(n, dtype=np.float64) * 86_400_000.0,
        open=closes.copy(),
        high=closes * 1.01,
        low=closes * 0.99,
        close=closes.copy(),
        volume=np.ones(n) * 100.0 if volume is None else volume,
        symbol="TEST",
    )


class TestRollingMean:
    def test_full_window_matches_hand_computation(self) -> None:
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        got = rolling_mean(x, 3)
        # Warm-up entries average what exists: 1, (1+2)/2, then full 3-bar windows.
        assert got == pytest.approx([1.0, 1.5, 2.0, 3.0, 4.0])

    def test_window_of_one_is_the_series(self) -> None:
        x = np.array([3.0, -1.0, 7.5])
        assert rolling_mean(x, 1) == pytest.approx(x)

    def test_rejects_zero_window(self) -> None:
        with pytest.raises(DataError, match="rolling_mean window"):
            rolling_mean(np.array([1.0, 2.0]), 0)


class TestRollingStd:
    def test_population_sd_of_a_known_window(self) -> None:
        x = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        # Population sd of the whole 8-point series is exactly 2.0 (the textbook example).
        assert rolling_std(x, 8)[-1] == pytest.approx(2.0)

    def test_flat_series_has_zero_sd_and_never_goes_negative(self) -> None:
        got = rolling_std(np.full(50, 1234.5678), 20)
        assert np.all(got >= 0.0)
        assert got[-1] == pytest.approx(0.0, abs=1e-9)

    def test_large_price_levels_do_not_lose_precision(self) -> None:
        # The cancellation case: a flat series at BTC-scale prices. A naive E[x^2]-E[x]^2 returns
        # a spurious sd here, which would then read as a real Bollinger bandwidth.
        assert rolling_std(np.full(60, 92_000.0), 20)[-1] == pytest.approx(0.0, abs=1e-6)

    def test_matches_numpy_on_a_known_window(self) -> None:
        rng = np.random.default_rng(17)
        x = 50_000.0 + rng.normal(0.0, 250.0, 400)
        got = rolling_std(x, 30)
        assert got[-1] == pytest.approx(float(np.std(x[-30:])), rel=1e-9)


class TestBollingerBandwidth:
    def test_equals_four_sigma_over_the_mean(self) -> None:
        rng = np.random.default_rng(3)
        closes = 100.0 + rng.normal(0.0, 5.0, 200).cumsum() * 0.01
        closes = np.abs(closes) + 1.0
        got = bollinger_bandwidth(closes, 20, sigma=2.0)
        expected = 4.0 * rolling_std(closes, 20) / rolling_mean(closes, 20)
        assert got == pytest.approx(expected)

    def test_flat_series_has_zero_bandwidth(self) -> None:
        assert bollinger_bandwidth(np.full(60, 2.0), 20)[-1] == pytest.approx(0.0, abs=1e-9)

    def test_rejects_non_positive_prices(self) -> None:
        with pytest.raises(DataError, match="strictly-positive"):
            bollinger_bandwidth(np.array([1.0, 0.0, 1.0] * 20), 20)


class TestRSI:
    def test_monotonically_rising_series_pins_at_100(self) -> None:
        # No down bars at all: by Wilder's definition average loss is zero and RSI is 100.
        assert rsi(np.arange(1.0, 60.0), 14)[-1] == pytest.approx(100.0)

    def test_monotonically_falling_series_pins_at_zero(self) -> None:
        assert rsi(np.arange(60.0, 1.0, -1.0), 14)[-1] == pytest.approx(0.0)

    def test_alternating_equal_moves_oscillate_tightly_around_fifty(self) -> None:
        # Equal average gain and loss => RS = 1 => RSI = 50. Wilder's recursion consumes one delta
        # per bar, so the value oscillates about 50 rather than settling exactly on it; the width of
        # that oscillation is the property worth pinning.
        closes = np.array([100.0 + (i % 2) for i in range(80)])
        tail = rsi(closes, 14)[-10:]
        assert np.all(np.abs(tail - 50.0) < 2.0)
        assert float(np.mean(tail)) == pytest.approx(50.0, abs=0.1)

    def test_warmup_is_neutral_not_nan(self) -> None:
        got = rsi(np.linspace(1.0, 2.0, 30), 14)
        assert np.all(np.isfinite(got))
        assert got[:14] == pytest.approx(50.0)

    def test_wilder_smoothing_reference_value(self) -> None:
        # A 15-point series whose first 14 deltas are +1 except one -1 of size 4.
        closes = np.concatenate(([100.0], 100.0 + np.arange(1, 15.0)))
        closes[7] = closes[6] - 4.0
        got = rsi(closes, 14)[14]
        gains = np.maximum(np.diff(closes), 0.0)[:14]
        losses = np.maximum(-np.diff(closes), 0.0)[:14]
        rs = gains.mean() / losses.mean()
        assert got == pytest.approx(100.0 - 100.0 / (1.0 + rs))


class TestPercentileRank:
    def test_rising_series_always_ranks_top(self) -> None:
        assert percentile_rank(np.arange(50.0), 10)[-1] == pytest.approx(1.0)

    def test_falling_series_ranks_bottom_at_one_over_window(self) -> None:
        # The current bar is included in its own window, so a fresh low ranks 1/window, not 0.
        assert percentile_rank(np.arange(50.0, 0.0, -1.0), 10)[-1] == pytest.approx(0.1)

    def test_known_window_fraction(self) -> None:
        x = np.array([5.0, 1.0, 4.0, 2.0, 3.0])
        # Final window is the whole series; 3.0 is >= three of the five values.
        assert percentile_rank(x, 5)[-1] == pytest.approx(0.6)

    def test_always_inside_the_unit_interval(self) -> None:
        rng = np.random.default_rng(11)
        got = percentile_rank(rng.normal(size=500), 60)
        assert np.all((got > 0.0) & (got <= 1.0))


class TestRollingCorrelation:
    def test_identical_series_correlate_at_one(self) -> None:
        rng = np.random.default_rng(5)
        x = rng.normal(size=200)
        assert rolling_correlation(x, x, 50)[-1] == pytest.approx(1.0)

    def test_negated_series_correlate_at_minus_one(self) -> None:
        rng = np.random.default_rng(5)
        x = rng.normal(size=200)
        assert rolling_correlation(x, -x, 50)[-1] == pytest.approx(-1.0)

    def test_flat_arm_returns_zero_not_nan(self) -> None:
        rng = np.random.default_rng(5)
        got = rolling_correlation(rng.normal(size=100), np.zeros(100), 30)
        assert np.all(np.isfinite(got))
        assert got[-1] == pytest.approx(0.0)

    def test_shape_mismatch_fails_loud(self) -> None:
        with pytest.raises(DataError, match="equal shapes"):
            rolling_correlation(np.zeros(10), np.zeros(11), 5)


class TestCrossCorrelationLags:
    def test_recovers_a_known_lead(self) -> None:
        # Build a follower that is the leader delayed by 3 bars. The peak must sit at lag -3:
        # follower[t] matches leader[t-3], i.e. the leader moved first.
        rng = np.random.default_rng(9)
        leader = rng.normal(size=600)
        follower = np.concatenate((np.zeros(3), leader[:-3]))
        got = cross_correlation_lags(follower, leader, max_lag=10)
        assert got.best_lag == -3
        assert got.best_correlation > 0.9

    def test_rejects_too_short_a_series(self) -> None:
        with pytest.raises(DataError, match="need >"):
            cross_correlation_lags(np.zeros(5), np.zeros(5), max_lag=10)


class TestCalendarFeatures:
    def test_decodes_a_known_utc_instant(self) -> None:
        # 2021-03-15 was a Monday.
        ts = np.array([np.datetime64("2021-03-15T13:00:00", "ms").astype(np.float64)])
        cal = calendar_features(ts)
        assert (cal.year[0], cal.month[0], cal.day_of_month[0]) == (2021, 3, 15)
        assert cal.day_of_week[0] == 0
        assert cal.hour[0] == 13

    def test_epoch_is_a_thursday(self) -> None:
        cal = calendar_features(np.array([0.0]))
        assert cal.day_of_week[0] == 3  # Monday=0 => Thursday=3
        assert (cal.year[0], cal.month[0], cal.day_of_month[0]) == (1970, 1, 1)

    def test_day_of_year_on_a_leap_day(self) -> None:
        ts = np.array([np.datetime64("2020-12-31", "ms").astype(np.float64)])
        assert calendar_features(ts).day_of_year[0] == 366


class TestConsolidationAndVolume:
    def test_consolidation_counts_a_known_run(self) -> None:
        # 40 flat bars then a 50% jump: the run resets once the jump enters the trailing window.
        closes = np.concatenate((np.full(40, 1.0), np.full(20, 1.5)))
        got = consolidation_length(closes, 10, threshold=0.10)
        assert got[39] == 40  # the whole flat stretch
        assert got[40] == 0  # the jump widens the range beyond 10%
        assert got[55] > 0  # once the jump leaves the window, quiet resumes

    def test_volume_ratio_of_a_constant_series_is_one(self) -> None:
        bars = _bars(np.linspace(1.0, 2.0, 100))
        assert volume_ratio(bars, 20)[-1] == pytest.approx(1.0)

    def test_volume_spike_shows_up_as_its_multiple(self) -> None:
        vol = np.full(100, 10.0)
        vol[-1] = 30.0
        bars = _bars(np.linspace(1.0, 2.0, 100), volume=vol)
        # Trailing 20-bar mean includes the spike: (19*10 + 30)/20 = 11.
        assert volume_ratio(bars, 20)[-1] == pytest.approx(30.0 / 11.0)


class TestReturnsAndVolatility:
    def test_log_returns_are_additive(self) -> None:
        closes = np.array([1.0, 2.0, 4.0, 8.0])
        got = log_returns(closes)
        assert got[0] == 0.0
        assert got[1:] == pytest.approx(np.log(2.0))
        assert got.sum() == pytest.approx(np.log(8.0))

    def test_rejects_non_positive_prices(self) -> None:
        with pytest.raises(DataError, match="strictly-positive"):
            log_returns(np.array([1.0, -1.0, 2.0]))

    def test_constant_growth_has_zero_realized_volatility(self) -> None:
        closes = 1.0 * (1.02 ** np.arange(100.0))
        assert realized_volatility(closes, 30)[-1] == pytest.approx(0.0, abs=1e-12)

    def test_annualisation_scales_by_sqrt_periods(self) -> None:
        rng = np.random.default_rng(4)
        closes = np.exp(np.cumsum(rng.normal(0.0, 0.01, 300)))
        plain = realized_volatility(closes, 60)[-1]
        annual = realized_volatility(closes, 60, periods_per_year=365.0)[-1]
        assert annual == pytest.approx(plain * np.sqrt(365.0))
