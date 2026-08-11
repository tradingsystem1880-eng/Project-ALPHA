"""Fail-loud guards on the new indicator, wedge and conditional-lift surfaces.

Project ALPHA's rule is that bad input raises a typed error with context rather than producing a
plausible number. That rule is only worth having if the guards are exercised — an unreached
``raise`` is indistinguishable from a missing one, and both let a malformed series through.

This file also covers the linear-scale and degenerate branches that the ground-truth tests never
reach, because those tests deliberately run the primary (log-scale, well-formed) path.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    OHLCV,
    Wedge,
    WedgeConfig,
    calendar_features,
    consolidation_length,
    cross_correlation_lags,
    detect_wedges,
    geometric_brownian_series,
    inject_wedge,
    log_returns,
    realized_volatility,
    rolling_mean,
    rsi,
    wedge_lines,
    wedge_panel,
)
from alpha_validation import (
    apply_fdr,
    conditional_lift,
    monotonic_trend,
    two_proportion_pvalue,
)


class TestIndicatorGuards:
    def test_empty_series_is_rejected(self) -> None:
        with pytest.raises(DataError, match="non-empty"):
            rolling_mean(np.array([]), 5)

    def test_single_close_cannot_produce_returns(self) -> None:
        with pytest.raises(DataError, match=">= 2 closes"):
            log_returns(np.array([1.0]))

    def test_non_positive_annualisation_is_rejected(self) -> None:
        with pytest.raises(DataError, match="periods_per_year"):
            realized_volatility(np.linspace(1.0, 2.0, 50), 10, periods_per_year=0.0)

    def test_non_positive_bollinger_sigma_is_rejected(self) -> None:
        from alpha_patterns import bollinger_bandwidth

        with pytest.raises(DataError, match="sigma must be > 0"):
            bollinger_bandwidth(np.linspace(1.0, 2.0, 50), 20, sigma=0.0)

    def test_rsi_on_a_series_shorter_than_its_window_stays_neutral(self) -> None:
        got = rsi(np.linspace(1.0, 2.0, 10), 14)
        assert got.size == 10
        assert np.all(got == 50.0)

    def test_consolidation_rejects_a_non_positive_threshold(self) -> None:
        with pytest.raises(DataError, match="threshold must be > 0"):
            consolidation_length(np.linspace(1.0, 2.0, 50), 10, threshold=0.0)

    def test_calendar_features_rejects_empty_and_non_finite(self) -> None:
        with pytest.raises(DataError, match="non-empty"):
            calendar_features(np.array([]))
        with pytest.raises(DataError, match="finite"):
            calendar_features(np.array([0.0, np.nan]))


class TestCrossCorrelationBranches:
    def test_positive_lag_side_is_populated(self) -> None:
        """A follower that *leads* must peak on the positive side — the folklore-backwards case."""
        rng = np.random.default_rng(13)
        leader = rng.normal(size=500)
        # Here "leader" is actually the delayed one, so the relationship runs the other way.
        follower = leader.copy()
        leader = np.concatenate((np.zeros(4), follower[:-4]))
        got = cross_correlation_lags(follower, leader, max_lag=8)
        assert got.best_lag == 4
        assert got.correlations.size == 17
        assert got.n_observations == 500

    def test_zero_lag_is_included_and_perfect_for_identical_series(self) -> None:
        rng = np.random.default_rng(2)
        x = rng.normal(size=400)
        got = cross_correlation_lags(x, x, max_lag=5)
        assert got.best_lag == 0
        assert got.best_correlation == pytest.approx(1.0)

    def test_rejects_mismatched_shapes(self) -> None:
        with pytest.raises(DataError, match="equal shapes"):
            cross_correlation_lags(np.zeros(100), np.zeros(99), max_lag=5)

    def test_rejects_a_non_positive_max_lag(self) -> None:
        with pytest.raises(DataError, match="max_lag must be >= 1"):
            cross_correlation_lags(np.zeros(100), np.zeros(100), max_lag=0)


class TestWedgeGuards:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"lookback": 0}, "lookback must be >= 1"),
            ({"min_span": 2}, "min_span must be >= 4"),
            ({"max_apex_bars": 0}, "max_apex_bars must be >= 1"),
            ({"track_bars": 0}, "track_bars must be >= 1"),
            ({"min_convergence": 0.0}, "min_convergence"),
        ],
    )
    def test_config_validation(self, kwargs: dict[str, int | float], match: str) -> None:
        with pytest.raises(DataError, match=match):
            WedgeConfig(**kwargs)  # type: ignore[arg-type]

    def test_too_few_swings_yields_no_wedges(self) -> None:
        # A strictly monotonic ramp has no interior fractal pivots at all.
        n = 60
        closes = np.linspace(1.0, 2.0, n)
        bars = OHLCV(
            ts=np.arange(n, dtype=np.float64) * 86_400_000.0,
            open=closes,
            high=closes * 1.001,
            low=closes * 0.999,
            close=closes,
            volume=np.ones(n),
            symbol="RAMP",
        )
        assert detect_wedges(bars, WedgeConfig()) == []

    def test_linear_scale_produces_wedges_too(self) -> None:
        """The non-default fitting scale. A straight line in price is a different object from a
        straight line in log price, and which the market respects is empirical, not assumed."""
        bars, _ = inject_wedge(kind="falling")
        linear = detect_wedges(bars, WedgeConfig(scale="linear"))
        assert linear, "linear-scale fitting found nothing in a series built to contain a wedge"
        assert all(w.scale == "linear" for w in linear)
        for w in linear:
            upper, lower = wedge_lines(w, len(bars))
            assert np.all(
                upper[w.start_index : w.end_index + 1] > lower[w.start_index : w.end_index + 1]
            )

    def test_bars_to_apex_is_the_gap_from_confirmation(self) -> None:
        bars, _ = inject_wedge()
        for w in detect_wedges(bars, WedgeConfig()):
            assert w.bars_to_apex == pytest.approx(w.apex_index - w.confirmed_index)

    def test_coincident_anchors_are_rejected(self) -> None:
        w = Wedge(
            kind="falling",
            symbol="X",
            config_label="test",
            scale="log",
            upper_indices=(10, 10),
            upper_prices=(2.0, 1.5),
            lower_indices=(5, 30),
            lower_prices=(1.0, 1.2),
            start_index=5,
            end_index=30,
            confirmed_index=35,
            apex_index=60.0,
            width_start=1.0,
            width_confirm=0.5,
            convergence=0.5,
            upper_slope=-0.01,
            lower_slope=0.01,
            break_index=-1,
            break_direction=0,
            break_price=float("nan"),
            break_volume_ratio=float("nan"),
            bars_past_apex=0,
            apex_passed_unbroken=False,
        )
        with pytest.raises(DataError, match="distinct bars"):
            wedge_lines(w, 100)

    def test_panel_over_no_wedges_is_entirely_inactive(self) -> None:
        bars = geometric_brownian_series(200, seed=1)
        panel = wedge_panel(bars, [])
        assert not panel.active.any()
        assert np.all(np.isnan(panel.width))
        assert np.all(panel.kind_code == 0)


class TestInjectWedgeGuards:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"kind": "spiral"}, "kind must be"),
            ({"start_lower": 2.0, "start_upper": 1.0}, "start_lower < start_upper"),
            ({"break_direction": 0}, "break_direction must be"),
            ({"n_pivots": 3}, ">= 4 pivots"),
            ({"break_bar": 10}, "must fit inside"),
            ({"apex_bar": 100}, "apex_bar must lie beyond"),
        ],
    )
    def test_validation(self, kwargs: dict[str, object], match: str) -> None:
        with pytest.raises(DataError, match=match):
            inject_wedge(**kwargs)  # type: ignore[arg-type]


class TestConditionalGuards:
    def test_accepts_integer_zero_one_arrays(self) -> None:
        cond = np.array([1, 0] * 100, dtype=np.int64)
        out = np.array([1, 1, 0, 0] * 50, dtype=np.int64)
        r = conditional_lift(cond, out)
        assert r.n_condition + r.n_complement == 200

    def test_rejects_a_non_binary_numeric_array(self) -> None:
        with pytest.raises(DataError, match="boolean or 0/1"):
            conditional_lift(np.array([0, 1, 2, 0]), np.array([True, False, True, False]))

    def test_rejects_a_two_dimensional_condition(self) -> None:
        with pytest.raises(DataError, match="must be 1-D"):
            conditional_lift(np.zeros((4, 2), dtype=bool), np.zeros(8, dtype=bool))

    def test_result_line_renders_before_and_after_correction(self) -> None:
        rng = np.random.default_rng(6)
        cond = rng.random(1000) < 0.4
        out = np.where(cond, rng.random(1000) < 0.7, rng.random(1000) < 0.2)
        raw = conditional_lift(cond, out, label="c", outcome_label="o", family="f")
        assert math.isnan(raw.qvalue)
        assert raw.line().endswith(" ")  # uncorrected rows carry a blank marker

        corrected = apply_fdr([raw])[0]
        assert not math.isnan(corrected.qvalue)
        assert corrected.line().rstrip().endswith("*")
        assert corrected.lift > 1.0

    def test_apply_fdr_on_an_empty_family_is_empty(self) -> None:
        assert apply_fdr([]) == []

    def test_lift_is_infinite_when_the_complement_never_fires(self) -> None:
        cond = np.array([True] * 50 + [False] * 50)
        out = np.array([True] * 25 + [False] * 75)
        assert math.isinf(conditional_lift(cond, out).lift)

    def test_pooled_extremes_carry_no_evidence(self) -> None:
        assert two_proportion_pvalue(100, 100, 100, 100) == 1.0


class TestMonotonicTrendGuards:
    def test_rejects_empty_bins(self) -> None:
        with pytest.raises(DataError, match="positive counts"):
            monotonic_trend([0.1, 0.2, 0.3], [10, 0, 10])

    def test_all_or_nothing_outcomes_give_no_trend(self) -> None:
        # A pooled proportion of exactly 0 or 1 has no variance to test against.
        assert monotonic_trend([0.0, 0.0, 0.0], [10, 10, 10]) == 0.0
        assert monotonic_trend([1.0, 1.0, 1.0], [10, 10, 10]) == 0.0

    def test_a_single_populated_bin_gives_no_trend(self) -> None:
        # Zero score-variance across bins: the statistic is undefined and returns 0 rather than
        # dividing by zero.
        assert monotonic_trend([0.5, 0.5, 0.5], [1, 1, 1_000_000]) == pytest.approx(0.0)
