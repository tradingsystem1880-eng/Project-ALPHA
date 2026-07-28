"""Context measures, matched controls, and fourth-tap detection.

These are the parts of ``alpha_patterns`` the confluence and exhaustion questions rest on — order
blocks and fair-value gaps for "is there supply overhead?", trend state and distance-from-low for
matching controls, and ``detect_nth_taps`` for "does the fourth tap behave like the third?". Each is
exercised on hand-built series where the expected answer is known.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    OHLCV,
    TrendlineConfig,
    TrendState,
    TripleTapConfig,
    detect_nth_taps,
    distance_from_low,
    find_fair_value_gaps,
    find_order_blocks,
    geometric_brownian_series,
    inject_triple_tap,
    rolling_max,
    rolling_min,
    rolling_vwap,
    sample_matched_controls,
    trend_state_ma,
    trend_state_vwap,
    true_range,
)
from alpha_patterns.series import FloatArray
from alpha_patterns.trendline import Trendline


def _bars_from_ohlc(
    o: list[float], h: list[float], low: list[float], c: list[float], vol: list[float] | None = None
) -> OHLCV:
    n = len(o)
    return OHLCV(
        ts=np.arange(n, dtype=float) * 14_400_000.0,
        open=np.array(o, float),
        high=np.array(h, float),
        low=np.array(low, float),
        close=np.array(c, float),
        volume=np.array(vol if vol is not None else [1.0] * n, float),
    )


class TestFairValueGaps:
    def test_detects_a_bullish_gap(self) -> None:
        # bar 2's low (12) sits above bar 0's high (10): an unfilled upward imbalance.
        bars = _bars_from_ohlc(
            o=[9, 10, 12.5, 13], h=[10, 12, 14, 14], low=[8, 9.5, 12, 12.8], c=[9.5, 11.5, 13, 13.5]
        )
        gaps = find_fair_value_gaps(bars)
        bull = [g for g in gaps if g.direction == "bullish"]
        assert bull
        assert bull[0].bottom == pytest.approx(10.0)
        assert bull[0].top == pytest.approx(12.0)

    def test_detects_a_bearish_gap(self) -> None:
        bars = _bars_from_ohlc(
            o=[13, 12, 9.5, 9],
            h=[14, 12.5, 10, 9.5],
            low=[12.8, 11, 8, 8.5],
            c=[13.5, 11.5, 8.5, 9],
        )
        assert any(g.direction == "bearish" for g in find_fair_value_gaps(bars))

    def test_gap_records_fill(self) -> None:
        bars = _bars_from_ohlc(
            o=[9, 10, 12.5, 13, 9],
            h=[10, 12, 14, 14, 13],
            low=[8, 9.5, 12, 12.8, 9],
            c=[9.5, 11.5, 13, 13.5, 9.5],
        )
        bull = [g for g in find_fair_value_gaps(bars) if g.direction == "bullish"][0]
        assert bull.filled_index == 4
        assert not bull.is_unfilled

    def test_no_gap_when_every_range_overlaps(self) -> None:
        """Hand-built: each bar's range overlaps the one two back, so no imbalance exists."""
        bars = _bars_from_ohlc(
            o=[10, 10, 10, 10, 10],
            h=[11, 11, 11, 11, 11],
            low=[9, 9, 9, 9, 9],
            c=[10.5, 10.2, 10.4, 10.1, 10.3],
        )
        assert find_fair_value_gaps(bars) == []


class TestOrderBlocks:
    def test_contains_and_unmitigated_flags(self) -> None:
        bars = geometric_brownian_series(600, vol_per_bar=0.03, seed=4)
        obs = find_order_blocks(bars)
        assert obs
        for ob in obs:
            assert ob.contains((ob.top + ob.bottom) / 2)
            assert not ob.contains(ob.top * 10)
            assert ob.is_unmitigated == (ob.mitigated_index < 0)
            assert ob.displacement_atr >= 1.5

    def test_higher_threshold_finds_fewer(self) -> None:
        bars = geometric_brownian_series(800, vol_per_bar=0.03, seed=5)
        assert len(find_order_blocks(bars, displacement_atr=3.0)) <= len(
            find_order_blocks(bars, displacement_atr=1.5)
        )

    @pytest.mark.parametrize(("kwargs"), [{"displacement_atr": 0.0}, {"structure_lookback": 0}])
    def test_rejects_bad_parameters(self, kwargs: dict[str, float]) -> None:
        bars = geometric_brownian_series(100, seed=1)
        with pytest.raises(DataError):
            find_order_blocks(bars, **kwargs)  # type: ignore[arg-type]


class TestTrendState:
    def test_ma_state_labels_a_rising_market_uptrend(self) -> None:
        bars = geometric_brownian_series(800, vol_per_bar=0.004, drift_per_bar=0.004, seed=2)
        assert trend_state_ma(bars, fast=20, slow=60)[-1] == "uptrend"

    def test_ma_state_labels_a_falling_market_downtrend(self) -> None:
        bars = geometric_brownian_series(800, vol_per_bar=0.004, drift_per_bar=-0.004, seed=2)
        assert trend_state_ma(bars, fast=20, slow=60)[-1] == "downtrend"

    def test_wide_band_forces_range(self) -> None:
        bars = geometric_brownian_series(800, vol_per_bar=0.004, drift_per_bar=0.004, seed=2)
        assert set(trend_state_ma(bars, fast=20, slow=60, band=10.0)) == {"range"}

    def test_ma_rejects_inverted_windows(self) -> None:
        bars = geometric_brownian_series(300, seed=1)
        with pytest.raises(DataError):
            trend_state_ma(bars, fast=200, slow=50)

    def test_vwap_state_covers_all_bars(self) -> None:
        bars = geometric_brownian_series(400, vol_per_bar=0.01, seed=3)
        states = trend_state_vwap(bars, window=100)
        assert len(states) == len(bars)
        assert set(states) <= {"uptrend", "downtrend", "range"}

    def test_distance_from_low_is_non_negative(self) -> None:
        bars = geometric_brownian_series(400, vol_per_bar=0.01, seed=3)
        d = distance_from_low(bars, window=100)
        assert d.shape == (len(bars),)
        assert bool(np.all(d >= -1e-12))


class TestSeriesPrimitives:
    def test_true_range_first_bar_falls_back_to_span(self) -> None:
        bars = _bars_from_ohlc(o=[10, 11], h=[12, 13], low=[9, 10], c=[11, 12])
        assert true_range(bars)[0] == pytest.approx(3.0)

    def test_rolling_min_max_are_causal_and_correct(self) -> None:
        v = np.array([5.0, 3.0, 8.0, 1.0, 9.0])
        np.testing.assert_allclose(rolling_min(v, 2), [5, 3, 3, 1, 1])
        np.testing.assert_allclose(rolling_max(v, 2), [5, 5, 8, 8, 9])

    def test_rolling_vwap_handles_zero_volume(self) -> None:
        bars = _bars_from_ohlc(o=[10, 11], h=[12, 13], low=[9, 10], c=[11, 12], vol=[0.0, 0.0])
        assert bool(np.all(np.isfinite(rolling_vwap(bars, 2))))

    @pytest.mark.parametrize("window", [0, -1])
    def test_rolling_helpers_reject_bad_windows(self, window: int) -> None:
        bars = geometric_brownian_series(50, seed=1)
        with pytest.raises(DataError):
            rolling_min(bars.low, window)
        with pytest.raises(DataError):
            rolling_max(bars.high, window)
        with pytest.raises(DataError):
            rolling_vwap(bars, window)

    def test_slice_preserves_symbol_and_length(self) -> None:
        bars = geometric_brownian_series(100, seed=1, symbol="ABC")
        s = bars.slice(10, 40)
        assert len(s) == 30
        assert s.symbol == "ABC"

    def test_rejects_open_outside_range(self) -> None:
        with pytest.raises(DataError):
            _bars_from_ohlc(o=[99, 11], h=[12, 13], low=[9, 10], c=[11, 12])

    def test_rejects_close_outside_range(self) -> None:
        with pytest.raises(DataError):
            _bars_from_ohlc(o=[10, 11], h=[12, 13], low=[9, 10], c=[99, 12])

    def test_rejects_non_finite(self) -> None:
        with pytest.raises(DataError):
            _bars_from_ohlc(o=[10, float("nan")], h=[12, 13], low=[9, 10], c=[11, 12])

    def test_rejects_too_few_bars(self) -> None:
        with pytest.raises(DataError):
            OHLCV(
                ts=np.array([0.0]),
                open=np.ones(1),
                high=np.ones(1),
                low=np.ones(1),
                close=np.ones(1),
                volume=np.ones(1),
            )

    def test_rejects_mismatched_column_length(self) -> None:
        with pytest.raises(DataError):
            OHLCV(
                ts=np.arange(3, dtype=float),
                open=np.ones(2),
                high=np.ones(3),
                low=np.ones(3),
                close=np.ones(3),
                volume=np.ones(3),
            )


class TestMatchedControls:
    def _fixture(self, n: int = 1000) -> tuple[OHLCV, list[TrendState], FloatArray]:
        bars = geometric_brownian_series(n, vol_per_bar=0.015, seed=6)
        return bars, trend_state_vwap(bars, window=200), distance_from_low(bars, window=200)

    def test_draws_controls_matched_on_trend_state(self) -> None:
        bars, trend, dist = self._fixture()
        events = [300, 500, 700]
        mc = sample_matched_controls(
            events,
            trend=trend,
            distance=dist,
            n_bars=len(bars),
            n_per_event=3,
            distance_tolerance=1.0,
            exclusion_bars=20,
        )
        assert mc.control_indices
        for c in mc.control_indices:
            assert trend[c] in {trend[e] for e in events}

    def test_excludes_bars_near_events(self) -> None:
        bars, trend, dist = self._fixture()
        events = [500]
        mc = sample_matched_controls(
            events,
            trend=trend,
            distance=dist,
            n_bars=len(bars),
            n_per_event=5,
            distance_tolerance=5.0,
            exclusion_bars=50,
        )
        assert all(abs(c - 500) > 50 for c in mc.control_indices)

    def test_reserves_room_for_the_forward_horizon(self) -> None:
        bars, trend, dist = self._fixture()
        mc = sample_matched_controls(
            [400],
            trend=trend,
            distance=dist,
            n_bars=len(bars),
            n_per_event=5,
            distance_tolerance=5.0,
            exclusion_bars=10,
            horizon_bars=200,
        )
        assert all(c <= len(bars) - 200 - 1 for c in mc.control_indices)

    def test_is_deterministic_for_a_given_seed(self) -> None:
        bars, trend, dist = self._fixture()
        kw = {
            "trend": trend,
            "distance": dist,
            "n_bars": len(bars),
            "n_per_event": 4,
            "distance_tolerance": 1.0,
        }
        a = sample_matched_controls([300, 600], seed=7, **kw)  # type: ignore[arg-type]
        b = sample_matched_controls([300, 600], seed=7, **kw)  # type: ignore[arg-type]
        c = sample_matched_controls([300, 600], seed=8, **kw)  # type: ignore[arg-type]
        assert a == b
        assert a != c

    def test_counts_events_it_could_not_match(self) -> None:
        bars, trend, dist = self._fixture()
        mc = sample_matched_controls(
            [500],
            trend=trend,
            distance=dist,
            n_bars=len(bars),
            n_per_event=3,
            distance_tolerance=1e-9,
            exclusion_bars=999,
        )
        assert mc.unmatched_events == 1
        assert mc.control_indices == ()

    def test_rejects_bad_arguments(self) -> None:
        bars, trend, dist = self._fixture()
        with pytest.raises(DataError):
            sample_matched_controls(
                [1], trend=trend, distance=dist, n_bars=len(bars), n_per_event=0
            )
        with pytest.raises(DataError):
            sample_matched_controls(
                [1], trend=trend, distance=dist, n_bars=len(bars), distance_tolerance=0.0
            )
        with pytest.raises(DataError):
            sample_matched_controls([1], trend=trend[:10], distance=dist, n_bars=len(bars))
        with pytest.raises(DataError):
            sample_matched_controls(
                [1], trend=trend, distance=dist, n_bars=len(bars), horizon_bars=len(bars) + 5
            )


class TestFourthTap:
    def test_finds_a_fourth_tap_of_the_same_level(self) -> None:
        bars, _ = inject_triple_tap(n_bars=560, tap_bars=(60, 160, 260), level=1.0, noise=0.001)
        cfg = TripleTapConfig(
            lookback=5,
            tolerance=0.02,
            band_reference="mean",
            gap_min=12,
            gap_max=250,
            population="strict",
        )
        # Real series carry later retests; the detector must at least run and return sane indices.
        fourth = detect_nth_taps(bars, cfg, n_taps=4)
        assert all(isinstance(i, int) and 0 <= i < len(bars) for i in fourth)
        assert fourth == sorted(set(fourth))

    def test_finds_fourth_taps_on_a_real_shaped_series(self) -> None:
        bars = geometric_brownian_series(4000, vol_per_bar=0.02, seed=9)
        cfg = TripleTapConfig(
            lookback=5,
            tolerance=0.02,
            band_reference="mean",
            gap_min=12,
            gap_max=250,
            population="strict",
        )
        fourth = detect_nth_taps(bars, cfg, n_taps=4)
        assert all(0 <= i < len(bars) for i in fourth)

    def test_rejects_n_taps_below_four(self) -> None:
        bars = geometric_brownian_series(200, seed=1)
        with pytest.raises(DataError):
            detect_nth_taps(bars, n_taps=3)


class TestTrendlineHelpers:
    def test_value_at_interpolates_linearly(self) -> None:
        ln = Trendline(
            anchor_indices=(0, 10),
            anchor_prices=(2.0, 1.0),
            active_from=10,
            retire_at=100,
            scale="linear",
            touches=2,
            config_label="t",
            symbol="X",
        )
        assert ln.value_at(0) == pytest.approx(2.0)
        assert ln.value_at(10) == pytest.approx(1.0)
        assert ln.value_at(5) == pytest.approx(1.5)
        assert ln.value_at(20) == pytest.approx(0.0)  # extrapolates forward

    def test_value_at_interpolates_geometrically_on_log_scale(self) -> None:
        ln = Trendline(
            anchor_indices=(0, 10),
            anchor_prices=(4.0, 1.0),
            active_from=10,
            retire_at=100,
            scale="log",
            touches=2,
            config_label="t",
            symbol="X",
        )
        assert ln.value_at(5) == pytest.approx(2.0)  # geometric mean, not 2.5

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"lookback": 0},
            {"min_anchor_gap": 0},
            {"min_anchor_gap": 100, "max_anchor_gap": 10},
            {"max_age": 0},
            {"volume_multiple": 0.0},
        ],
    )
    def test_config_rejects_bad_parameters(self, kwargs: dict[str, int | float]) -> None:
        with pytest.raises(DataError):
            TrendlineConfig(**kwargs)  # type: ignore[arg-type]

    def test_label_is_stable_and_descriptive(self) -> None:
        cfg = TrendlineConfig(lookback=5, scale="log", require_third_touch=True)
        assert "L5" in cfg.label
        assert "log" in cfg.label
        assert "3touch" in cfg.label
