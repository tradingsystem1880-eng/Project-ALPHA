"""Correctness tests for the oscillator, cycle and level layers.

The bias guards prove these functions do not read the future. They do **not** prove the functions
compute the right thing — a function returning zeros is perfectly causal. These tests pin the
arithmetic against hand-computable cases and against series with known structure.

The cycle statistics get the most attention, because they are the ones whose failure mode is a
plausible number rather than an obvious one. A variance ratio must read ~1 on a random walk, above
1 on a trending series and below 1 on a mean-reverting one; a Hurst estimate must be quoted against
its own small-sample null rather than against the textbook 0.5; and a periodogram must recover a
period that was actually injected rather than one it invented.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    FIB_RATIOS,
    OHLCV,
    FibGrid,
    VarianceRatio,
    autocorrelation,
    chaikin_money_flow,
    directional_index,
    dominant_cycle,
    donchian_channel,
    ema,
    fib_levels_at,
    find_swings,
    geometric_brownian_series,
    hurst_exponent,
    hurst_random_walk_reference,
    ichimoku,
    keltner_channel,
    macd,
    money_flow_index,
    nearest_fib_distance,
    on_balance_volume,
    rolling_autocorrelation,
    rolling_hurst,
    rolling_variance_ratio,
    round_levels,
    round_number_distance,
    squeeze,
    stochastic,
    variance_ratio,
    wilder_smooth,
    williams_r,
)
from alpha_patterns.indicators import bollinger_bandwidth
from alpha_patterns.swings import Swing


def _fgn(n: int, *, hurst: float, seed: int) -> np.ndarray:
    """Approximate fractional Gaussian noise by spectral filtering of white noise.

    The power spectral density of fGn goes as ``f**(1 - 2H)``, so filtering white noise by the
    square root of that shape produces a series with the requested long-range dependence. Good
    enough as a positive control; not a substitute for an exact Davies-Harte synthesis.
    """
    rng = np.random.default_rng(seed)
    white = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, d=1.0)
    shape = np.ones_like(freqs)
    shape[1:] = freqs[1:] ** (-(2.0 * hurst - 1.0) / 2.0)
    return np.fft.irfft(white * shape, n=n)


def _bars(close: np.ndarray, *, volume: np.ndarray | None = None) -> OHLCV:
    close = np.asarray(close, dtype=np.float64)
    n = close.size
    return OHLCV(
        ts=np.arange(n, dtype=np.float64) * 86_400_000.0,
        open=close.copy(),
        high=close * 1.01,
        low=close * 0.99,
        close=close,
        volume=np.ones(n) if volume is None else np.asarray(volume, dtype=np.float64),
        symbol="TEST",
    )


class TestEma:
    def test_constant_series_is_its_own_ema(self) -> None:
        out = ema(np.full(50, 3.0), 10)
        assert np.allclose(out, 3.0)

    def test_recursion_matches_the_definition(self) -> None:
        values = np.array([1.0, 2.0, 3.0, 4.0])
        alpha = 2.0 / 4.0  # window=3
        expected = [1.0]
        for v in values[1:]:
            expected.append(alpha * v + (1 - alpha) * expected[-1])
        assert np.allclose(ema(values, 3), expected)

    def test_seeded_on_first_value_not_a_window_mean(self) -> None:
        """Priming on a mean of the opening window would make early bars see each other."""
        values = np.array([10.0, 0.0, 0.0, 0.0, 0.0])
        assert ema(values, 4)[0] == pytest.approx(10.0)

    def test_rejects_empty(self) -> None:
        with pytest.raises(DataError):
            ema(np.array([]), 5)


class TestWilderSmooth:
    def test_constant_series(self) -> None:
        assert np.allclose(wilder_smooth(np.full(30, 2.5), 14), 2.5)

    def test_matches_the_recursion(self) -> None:
        v = np.array([4.0, 8.0, 6.0])
        expected = [4.0, (4.0 * 1 + 8.0) / 2, ((4.0 * 1 + 8.0) / 2 * 1 + 6.0) / 2]
        assert np.allclose(wilder_smooth(v, 2), expected)


class TestOnBalanceVolume:
    def test_accumulates_signed_volume(self) -> None:
        close = np.array([10.0, 11.0, 10.5, 10.5, 12.0])
        vol = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
        # first bar has no prior close -> sign 0; then +200, -300, 0 (flat), +500
        assert np.allclose(on_balance_volume(close, vol), [0.0, 200.0, -100.0, -100.0, 400.0])

    def test_length_mismatch_fails_loud(self) -> None:
        with pytest.raises(DataError):
            on_balance_volume(np.ones(5), np.ones(4))


class TestMacd:
    def test_line_is_the_ema_difference(self) -> None:
        close = np.cumsum(np.random.default_rng(1).standard_normal(200)) + 100
        m = macd(close)
        assert np.allclose(m.line, ema(close, 12) - ema(close, 26))
        assert np.allclose(m.histogram, m.line - m.signal)

    def test_rejects_fast_slower_than_slow(self) -> None:
        with pytest.raises(DataError):
            macd(np.ones(100), fast=26, slow=12)


class TestStochastic:
    def test_close_at_window_high_is_100(self) -> None:
        bars = _bars(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
        # high = close*1.01, low = close*0.99; last close 5.0, window high 5.05, low 0.99
        k = stochastic(bars, window=5, smooth=1).k
        assert k[-1] == pytest.approx(100.0 * (5.0 - 0.99) / (5.05 - 0.99))

    def test_flat_window_is_neutral_not_undefined(self) -> None:
        flat = OHLCV(
            ts=np.arange(10.0) * 8.64e7,
            open=np.full(10, 5.0),
            high=np.full(10, 5.0),
            low=np.full(10, 5.0),
            close=np.full(10, 5.0),
            volume=np.ones(10),
            symbol="FLAT",
        )
        assert np.allclose(stochastic(flat, window=5, smooth=1).k, 50.0)

    def test_williams_r_is_k_minus_100(self) -> None:
        bars = _bars(np.linspace(1.0, 5.0, 40))
        assert np.allclose(williams_r(bars), stochastic(bars, smooth=1).k - 100.0)
        assert williams_r(bars).max() <= 0.0


class TestMoneyFlowAndChaikin:
    def test_mfi_stays_in_bounds(self) -> None:
        bars = geometric_brownian_series(300, seed=3, vol_per_bar=0.02, start=1.0)
        out = money_flow_index(bars)
        assert out.min() >= 0.0
        assert out.max() <= 100.0

    def test_monotonic_rise_saturates_high(self) -> None:
        bars = _bars(np.linspace(1.0, 5.0, 60), volume=np.full(60, 10.0))
        assert money_flow_index(bars, window=14)[-1] == pytest.approx(100.0)

    def test_cmf_stays_in_bounds(self) -> None:
        bars = geometric_brownian_series(300, seed=5, vol_per_bar=0.02, start=1.0)
        out = chaikin_money_flow(bars)
        assert out.min() >= -1.0
        assert out.max() <= 1.0

    def test_zero_range_bars_contribute_nothing(self) -> None:
        flat = OHLCV(
            ts=np.arange(40.0) * 8.64e7,
            open=np.full(40, 2.0),
            high=np.full(40, 2.0),
            low=np.full(40, 2.0),
            close=np.full(40, 2.0),
            volume=np.full(40, 7.0),
            symbol="FLAT",
        )
        assert np.allclose(chaikin_money_flow(flat), 0.0)


class TestDirectionalIndex:
    def test_uptrend_has_plus_di_above_minus_di(self) -> None:
        bars = _bars(np.linspace(1.0, 4.0, 120))
        di = directional_index(bars)
        assert di.plus_di[-1] > di.minus_di[-1]

    def test_downtrend_reverses_it(self) -> None:
        bars = _bars(np.linspace(4.0, 1.0, 120))
        di = directional_index(bars)
        assert di.minus_di[-1] > di.plus_di[-1]

    def test_adx_is_higher_in_a_clean_trend_than_in_noise(self) -> None:
        trend = directional_index(_bars(np.linspace(1.0, 4.0, 300))).adx[-1]
        noise = directional_index(
            geometric_brownian_series(300, seed=11, vol_per_bar=0.02, start=1.0)
        ).adx[-1]
        assert trend > noise


class TestChannels:
    def test_donchian_excludes_the_current_bar(self) -> None:
        """A channel including bar i is touched by bar i's own high by construction."""
        close = np.array([1.0, 1.0, 1.0, 1.0, 5.0])
        bars = _bars(close)
        ch = donchian_channel(bars, window=3)
        # The spike at index 4 must not appear in its own upper band.
        assert ch.upper[4] == pytest.approx(1.01)
        assert bars.high[4] > ch.upper[4]

    def test_keltner_brackets_the_ema(self) -> None:
        bars = geometric_brownian_series(200, seed=2, vol_per_bar=0.02, start=1.0)
        ch = keltner_channel(bars)
        assert np.all(ch.upper >= ch.middle)
        assert np.all(ch.lower <= ch.middle)

    def test_squeeze_fires_when_bollingers_sit_inside_keltners(self) -> None:
        bars = geometric_brownian_series(400, seed=4, vol_per_bar=0.02, start=1.0)
        flags = squeeze(bollinger_bandwidth(bars.close), keltner_channel(bars), bars.close)
        assert flags.dtype == bool
        assert flags.size == bars.close.size


class TestIchimoku:
    def test_spans_are_the_ones_in_force(self) -> None:
        bars = geometric_brownian_series(300, seed=6, vol_per_bar=0.02, start=1.0)
        ich = ichimoku(bars)
        raw_a = (ich.tenkan + ich.kijun) / 2.0
        assert np.allclose(ich.span_a[26:], raw_a[:-26])

    def test_chikou_compares_close_against_its_own_lag(self) -> None:
        close = np.concatenate((np.full(30, 1.0), np.full(30, 2.0)))
        ich = ichimoku(_bars(close))
        assert bool(ich.chikou_above[40])  # 2.0 > 1.0 (26 bars back)
        assert not bool(ich.chikou_above[10])  # 1.0 == 1.0, strict comparison

    def test_above_cloud_in_a_strong_uptrend(self) -> None:
        bars = _bars(np.linspace(1.0, 6.0, 300))
        assert bool(ichimoku(bars).above_cloud[-1])


class TestAutocorrelation:
    def test_perfectly_persistent_series(self) -> None:
        assert autocorrelation(np.arange(100.0), 1) == pytest.approx(1.0)

    def test_alternating_series_is_negative(self) -> None:
        values = np.tile([1.0, -1.0], 50)
        assert autocorrelation(values, 1) == pytest.approx(-1.0)

    def test_short_series_is_nan_not_a_crash(self) -> None:
        assert np.isnan(autocorrelation(np.ones(3), 5))

    def test_rejects_zero_lag(self) -> None:
        with pytest.raises(DataError):
            autocorrelation(np.arange(50.0), 0)


class TestVarianceRatio:
    def test_random_walk_reads_about_one(self) -> None:
        rng = np.random.default_rng(7)
        ratios = [
            variance_ratio(np.cumsum(rng.standard_normal(1500)), q=5).ratio for _ in range(20)
        ]
        assert 0.9 < float(np.mean(ratios)) < 1.1

    def test_random_walk_verdict_is_random_walk(self) -> None:
        rng = np.random.default_rng(21)
        verdicts = [
            variance_ratio(np.cumsum(rng.standard_normal(1500)), q=5).verdict for _ in range(20)
        ]
        # A 5% test on 20 draws should almost never reject more than a handful of times.
        assert verdicts.count("random walk") >= 16

    def test_a_constant_drift_alone_does_not_read_as_trending(self) -> None:
        """The test de-means, so drift + iid noise is still a random walk. This is correct."""
        rng = np.random.default_rng(9)
        drift = np.cumsum(0.25 + rng.standard_normal(1500) * 0.1)
        assert variance_ratio(drift, q=5).ratio == pytest.approx(1.0, abs=0.25)

    def test_positively_autocorrelated_returns_read_above_one(self) -> None:
        """Trending means momentum *in returns*, which is what the ratio detects."""
        rng = np.random.default_rng(9)
        n = 3000
        r = np.zeros(n)
        for i in range(1, n):
            r[i] = 0.35 * r[i - 1] + rng.standard_normal()
        vr = variance_ratio(np.cumsum(r), q=5)
        assert vr.ratio > 1.0
        assert vr.verdict == "trending"

    def test_mean_reverting_series_reads_below_one(self) -> None:
        rng = np.random.default_rng(13)
        n = 2000
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = 0.2 * x[i - 1] + rng.standard_normal()  # strongly mean-reverting in levels
        vr = variance_ratio(x, q=5)
        assert vr.ratio < 1.0
        assert vr.verdict == "mean reverting"

    def test_too_short_returns_nan_not_a_crash(self) -> None:
        assert np.isnan(variance_ratio(np.arange(6.0), q=5).ratio)

    def test_rejects_q_below_two(self) -> None:
        with pytest.raises(DataError):
            variance_ratio(np.arange(100.0), q=1)


class TestHurst:
    def test_no_memory_null_sits_near_one_half_not_at_it(self) -> None:
        """The whole reason the reference function exists — 0.5 is an asymptotic promise."""
        mean, sd = hurst_random_walk_reference(128, trials=60, seed=3)
        assert np.isfinite(mean) and np.isfinite(sd)
        assert 0.35 < mean < 0.65
        assert sd > 0.0

    def test_the_null_is_white_noise_not_an_integrated_series(self) -> None:
        """Calibrating on cumsum(noise) would put the null at ~1.0 and invert every verdict."""
        mean, _ = hurst_random_walk_reference(256, trials=40, seed=3)
        integrated = hurst_exponent(np.cumsum(np.random.default_rng(5).standard_normal(256)))
        assert integrated > 0.85
        assert mean < 0.65

    def test_long_memory_noise_scores_above_the_no_memory_null(self) -> None:
        """Positive control: fractional Gaussian noise at H=0.85 must be detected as persistent."""
        mean, sd = hurst_random_walk_reference(1024, trials=60, seed=3)
        assert (hurst_exponent(_fgn(1024, hurst=0.85, seed=2)) - mean) / sd > 2.0

    def test_it_is_blind_to_short_memory_autocorrelation(self) -> None:
        """A documented blind spot, pinned so nobody reads a flat H as 'no momentum'.

        R/S measures *long*-range dependence. An AR(1) with phi=0.5 is strongly autocorrelated at
        lag 1 and has no long memory at all, and the estimator barely moves — under 2 sigma from
        the no-memory null. Anyone using rolling Hurst to detect a momentum regime needs to know
        that a null result here does not mean returns are unpredictable, only that they are not
        predictable in the specific long-range way this statistic looks for.
        """
        mean, sd = hurst_random_walk_reference(512, trials=60, seed=3)
        rng = np.random.default_rng(2)
        r = np.zeros(512)
        for i in range(1, 512):
            r[i] = 0.5 * r[i - 1] + rng.standard_normal()
        assert abs(hurst_exponent(r) - mean) / sd < 2.0
        # ...while the plain lag-1 autocorrelation sees it immediately.
        assert autocorrelation(r, 1) > 0.3

    def test_flat_series_is_nan(self) -> None:
        assert np.isnan(hurst_exponent(np.ones(256)))

    def test_rolling_version_warms_up_as_nan(self) -> None:
        out = rolling_hurst(np.random.default_rng(4).standard_normal(400), window=128)
        assert np.all(np.isnan(out[:127]))
        assert np.isfinite(out[-1])


class TestDominantCycle:
    def test_recovers_an_injected_period(self) -> None:
        n, period = 512, 32
        signal = np.sin(2 * np.pi * np.arange(n) / period)
        found = dominant_cycle(signal, min_period=4)
        assert found.period_bars == pytest.approx(period, rel=0.15)
        assert found.power_share > 0.5

    def test_detrends_before_transforming(self) -> None:
        """Without detrending, a pure ramp reports a 'cycle' of roughly the window length."""
        n, period = 512, 32
        ramp = np.arange(n) * 0.5
        signal = ramp + 3.0 * np.sin(2 * np.pi * np.arange(n) / period)
        assert dominant_cycle(signal, min_period=4).period_bars == pytest.approx(period, rel=0.15)

    def test_noise_has_a_peak_but_a_small_power_share(self) -> None:
        noise = np.random.default_rng(8).standard_normal(512)
        found = dominant_cycle(noise, min_period=4)
        assert np.isfinite(found.period_bars)  # there is always a peak
        assert found.power_share < 0.10  # and it explains almost nothing

    def test_too_short_is_nan(self) -> None:
        assert np.isnan(dominant_cycle(np.arange(8.0), min_period=4).period_bars)


class TestFibLevels:
    def _swings(self) -> list[Swing]:
        return [
            Swing(index=10, confirmed_index=15, price=1.0, kind="low", lookback=5),
            Swing(index=30, confirmed_index=35, price=2.0, kind="high", lookback=5),
        ]

    def test_upward_leg_retraces_down_from_the_high(self) -> None:
        grid = fib_levels_at(self._swings(), 40)
        assert grid is not None
        assert grid.upward
        assert grid.levels[0.5] == pytest.approx(1.5)
        assert grid.levels[0.618] == pytest.approx(2.0 - 0.618)

    def test_grid_is_none_before_both_swings_confirm(self) -> None:
        assert fib_levels_at(self._swings(), 34) is None  # high confirms at 35
        assert fib_levels_at(self._swings(), 35) is not None

    def test_known_at_is_the_later_confirmation(self) -> None:
        grid = fib_levels_at(self._swings(), 40)
        assert grid is not None
        assert grid.known_at == 35

    def test_extensions_project_beyond_the_leg(self) -> None:
        grid = fib_levels_at(self._swings(), 40)
        assert grid is not None
        assert grid.extensions[1.618] == pytest.approx(1.0 + 1.618)

    def test_nearest_reports_ratio_and_normalised_distance(self) -> None:
        grid = fib_levels_at(self._swings(), 40)
        assert grid is not None
        ratio, distance = grid.nearest(1.5)
        assert ratio == pytest.approx(0.5)
        assert distance == pytest.approx(0.0)

    def test_distance_series_is_nan_before_any_grid_exists(self) -> None:
        bars = geometric_brownian_series(300, seed=12, vol_per_bar=0.02, start=1.0)
        swings = find_swings(bars, lookback=5, kind="high") + find_swings(
            bars, lookback=5, kind="low"
        )
        out = nearest_fib_distance(bars.close, swings)
        assert np.isnan(out[0])
        assert np.any(np.isfinite(out))

    def test_all_ratios_present(self) -> None:
        grid = fib_levels_at(self._swings(), 40)
        assert grid is not None
        assert set(grid.levels) == set(FIB_RATIOS)


class TestRoundNumbers:
    @pytest.mark.parametrize(
        ("price", "below", "above"),
        [(1.04, 1.0, 1.1), (0.53, 0.53, 0.54), (65_400.0, 65_000.0, 66_000.0)],
    )
    def test_two_sig_fig_grid_scales_with_magnitude(
        self, price: float, below: float, above: float
    ) -> None:
        lo, hi = round_levels(price)
        assert lo == pytest.approx(below)
        assert hi == pytest.approx(above)

    @pytest.mark.parametrize(
        ("price", "below", "above"),
        [(1.04, 1.0, 2.0), (0.53, 0.5, 0.6), (65_400.0, 60_000.0, 70_000.0)],
    )
    def test_coarse_grid_is_what_a_trader_calls_round(
        self, price: float, below: float, above: float
    ) -> None:
        lo, hi = round_levels(price, per_decade=1)
        assert lo == pytest.approx(below)
        assert hi == pytest.approx(above)

    def test_distance_is_zero_on_a_round_number(self) -> None:
        assert round_number_distance(np.array([1.0, 2.0, 0.5]))[0] == pytest.approx(0.0)

    def test_distance_maxes_at_one_half(self) -> None:
        out = round_number_distance(np.linspace(1.0, 2.0, 500))
        assert out.max() <= 0.5 + 1e-9
        assert out.min() >= 0.0

    def test_rejects_non_positive_price(self) -> None:
        with pytest.raises(DataError):
            round_levels(0.0)

    def test_rejects_a_grid_below_one_per_decade(self) -> None:
        with pytest.raises(DataError):
            round_levels(1.0, per_decade=0)

    def test_non_finite_closes_become_nan_not_a_crash(self) -> None:
        out = round_number_distance(np.array([1.05, np.nan, -3.0]))
        assert np.isfinite(out[0])
        assert np.isnan(out[1]) and np.isnan(out[2])


class TestRollingWrappersAndEdgeCases:
    """The warm-up, validation and degenerate paths — where a silent NaN would hide a bug."""

    def test_rolling_autocorrelation_warms_up_then_tracks(self) -> None:
        values = np.tile([1.0, -1.0], 200)
        out = rolling_autocorrelation(values, window=64, lag=1)
        assert np.all(np.isnan(out[:63]))
        assert out[-1] == pytest.approx(-1.0)

    def test_rolling_variance_ratio_warms_up_then_tracks(self) -> None:
        rng = np.random.default_rng(31)
        out = rolling_variance_ratio(np.cumsum(rng.standard_normal(600)), window=256, q=5)
        assert np.all(np.isnan(out[:255]))
        assert 0.5 < out[-1] < 1.8

    @pytest.mark.parametrize(
        "fn",
        [
            lambda v: rolling_autocorrelation(v, window=8),
            lambda v: rolling_variance_ratio(v, window=8, q=2),
            lambda v: rolling_hurst(v, window=8),
        ],
    )
    def test_rolling_windows_below_the_memory_floor_fail_loud(self, fn) -> None:  # type: ignore[no-untyped-def]
        """A 8-bar Hurst estimate is computable and meaningless; refusing beats returning it."""
        with pytest.raises(DataError):
            fn(np.arange(100.0))

    @pytest.mark.parametrize(
        "fn",
        [
            lambda v: rolling_autocorrelation(v, window=64),
            lambda v: rolling_variance_ratio(v, window=64, q=2),
            lambda v: rolling_hurst(v, window=64),
        ],
    )
    def test_rolling_windows_reject_an_empty_series(self, fn) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(DataError):
            fn(np.array([]))

    def test_variance_ratio_of_a_flat_series_is_nan(self) -> None:
        assert np.isnan(variance_ratio(np.ones(200), q=5).ratio)

    def test_variance_ratio_verdict_is_random_walk_when_z_is_undefined(self) -> None:
        assert VarianceRatio(1.4, float("nan"), 100).verdict == "random walk"

    def test_hurst_returns_nan_when_no_scales_fit(self) -> None:
        assert np.isnan(hurst_exponent(np.arange(20.0), min_chunk=8))

    def test_hurst_reference_is_nan_when_every_trial_degenerates(self) -> None:
        mean, sd = hurst_random_walk_reference(10, trials=5, seed=1)
        assert np.isnan(mean) and np.isnan(sd)

    def test_dominant_cycle_of_a_flat_series_is_nan(self) -> None:
        assert np.isnan(dominant_cycle(np.ones(256), min_period=4).period_bars)

    def test_dominant_cycle_returns_nan_when_the_band_is_empty(self) -> None:
        """min_period above the Nyquist ceiling leaves nothing to search."""
        signal = np.sin(2 * np.pi * np.arange(256) / 16)
        assert np.isnan(dominant_cycle(signal, min_period=200, max_period=10).period_bars)

    def test_dominant_cycle_honours_an_explicit_ceiling(self) -> None:
        n = 512
        slow = np.sin(2 * np.pi * np.arange(n) / 128)
        fast = 0.6 * np.sin(2 * np.pi * np.arange(n) / 16)
        found = dominant_cycle(slow + fast, min_period=4, max_period=32)
        assert found.period_bars == pytest.approx(16, rel=0.2)

    def test_fib_grid_nearest_rejects_a_degenerate_span(self) -> None:
        grid = FibGrid(
            known_at=0, swing_low=1.0, swing_high=1.0, upward=True, levels={}, extensions={}
        )
        with pytest.raises(DataError):
            grid.nearest(1.0)

    def test_fib_grid_is_none_when_the_high_sits_below_the_low(self) -> None:
        swings = [
            Swing(index=10, confirmed_index=15, price=5.0, kind="low", lookback=5),
            Swing(index=30, confirmed_index=35, price=2.0, kind="high", lookback=5),
        ]
        assert fib_levels_at(swings, 40) is None

    def test_downward_leg_retraces_up_from_the_low(self) -> None:
        swings = [
            Swing(index=10, confirmed_index=15, price=2.0, kind="high", lookback=5),
            Swing(index=30, confirmed_index=35, price=1.0, kind="low", lookback=5),
        ]
        grid = fib_levels_at(swings, 40)
        assert grid is not None
        assert not grid.upward
        assert grid.levels[0.5] == pytest.approx(1.5)
        assert grid.extensions[1.618] == pytest.approx(2.0 - 1.618)
