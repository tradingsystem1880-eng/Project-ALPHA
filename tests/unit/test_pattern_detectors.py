"""Detectors must recover patterns injected at known indices — verified before any statistic.

A pattern study has two independent failure modes and only one is statistical. If the detector does
not find what the analyst believes it finds, no downstream rigour repairs it. These tests inject
triple taps and trendlines at chosen bars and require exact recovery, then measure what the same
detector reports on pattern-free noise (its false-positive base rate).
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    OHLCV,
    TrendlineConfig,
    TripleTapConfig,
    atr,
    build_trendlines,
    detect_triple_taps,
    find_breaks,
    find_order_blocks,
    find_swings,
    geometric_brownian_series,
    inject_descending_trendline,
    inject_triple_tap,
    rolling_vwap,
    swings_known_by,
)

STRICT = TripleTapConfig(
    lookback=5, tolerance=0.02, band_reference="mean", gap_min=12, gap_max=250, population="strict"
)


class TestTripleTapRecovery:
    @pytest.mark.parametrize("taps", [(60, 160, 260), (50, 120, 190), (80, 200, 320)])
    @pytest.mark.parametrize("seed", [1, 7, 13])
    def test_exact_recovery(self, taps: tuple[int, int, int], seed: int) -> None:
        bars, injected = inject_triple_tap(
            n_bars=400, tap_bars=taps, level=1.0, noise=0.001, seed=seed
        )
        events = detect_triple_taps(bars, STRICT)
        assert [e.tap_indices for e in events] == [injected]

    def test_level_matches_injection(self) -> None:
        bars, _ = inject_triple_tap(n_bars=400, level=1.0, noise=0.001)
        assert detect_triple_taps(bars, STRICT)[0].level == pytest.approx(1.0, abs=0.01)

    def test_gap_max_excludes_distant_taps(self) -> None:
        bars, _ = inject_triple_tap(n_bars=400, tap_bars=(40, 180, 330), noise=0.001)
        tight = TripleTapConfig(**{**STRICT.__dict__, "gap_max": 100})
        assert detect_triple_taps(bars, tight) == []

    def test_gap_min_excludes_adjacent_taps(self) -> None:
        bars, _ = inject_triple_tap(n_bars=400, tap_bars=(60, 160, 260), noise=0.001)
        wide = TripleTapConfig(**{**STRICT.__dict__, "gap_min": 150})
        assert detect_triple_taps(bars, wide) == []

    def test_ascending_population_admits_rising_taps(self) -> None:
        bars, injected = inject_triple_tap(n_bars=400, tap_jitter=0.012, noise=0.001)
        asc = TripleTapConfig(**{**STRICT.__dict__, "population": "ascending"})
        assert injected in [e.tap_indices for e in detect_triple_taps(bars, asc)]

    def test_tolerance_too_tight_rejects_ascending_taps(self) -> None:
        bars, _ = inject_triple_tap(n_bars=400, tap_jitter=0.05, noise=0.001)
        tight = TripleTapConfig(**{**STRICT.__dict__, "tolerance": 0.005})
        assert detect_triple_taps(bars, tight) == []

    def test_one_event_per_third_tap(self) -> None:
        bars, _ = inject_triple_tap(n_bars=400, noise=0.001)
        events = detect_triple_taps(bars, STRICT)
        thirds = [e.tap_indices[2] for e in events]
        assert len(thirds) == len(set(thirds))

    def test_config_rejects_invalid_parameters(self) -> None:
        with pytest.raises(DataError):
            TripleTapConfig(gap_min=50, gap_max=10)
        with pytest.raises(DataError):
            TripleTapConfig(tolerance=0.0)


class TestNullCalibration:
    def test_detector_reports_a_measurable_base_rate_on_noise(self) -> None:
        """Anything found in a pattern-free walk is a false positive by construction."""
        counts = [
            len(detect_triple_taps(geometric_brownian_series(400, seed=s), STRICT))
            for s in range(10)
        ]
        assert min(counts) >= 0
        assert np.mean(counts) > 0  # the base rate is NOT zero; real counts must be read against it

    def test_tighter_tolerance_lowers_the_base_rate(self) -> None:
        def rate(tol: float) -> float:
            cfg = TripleTapConfig(**{**STRICT.__dict__, "tolerance": tol})
            return float(
                np.mean(
                    [
                        len(detect_triple_taps(geometric_brownian_series(400, seed=s), cfg))
                        for s in range(8)
                    ]
                )
            )

        assert rate(0.005) < rate(0.03)


class TestTrendlines:
    def test_recovers_injected_break(self) -> None:
        bars, _peaks, brk = inject_descending_trendline(
            n_bars=300, peak_bars=(40, 120, 200), break_bar=250, noise=0.001
        )
        lines = build_trendlines(bars, TrendlineConfig(lookback=5, scale="linear"))
        assert lines
        breaks = find_breaks(bars, lines, rules=("any_close",))
        assert {b.break_index for b in breaks} == {brk}

    def test_log_and_linear_both_find_it(self) -> None:
        bars, _p, brk = inject_descending_trendline(n_bars=300, break_bar=250, noise=0.001)
        for scale in ("linear", "log"):
            lines = build_trendlines(bars, TrendlineConfig(lookback=5, scale=scale))
            breaks = find_breaks(bars, lines, rules=("any_close",))
            assert brk in {b.break_index for b in breaks}

    def test_lines_are_descending_only(self) -> None:
        bars, _p, _b = inject_descending_trendline(n_bars=300, noise=0.001)
        for ln in build_trendlines(bars, TrendlineConfig(lookback=5)):
            assert ln.anchor_prices[1] < ln.anchor_prices[0]

    def test_atr_rule_is_stricter_than_any_close(self) -> None:
        bars = geometric_brownian_series(1200, vol_per_bar=0.02, seed=3)
        lines = build_trendlines(bars, TrendlineConfig(lookback=5, max_age=200))
        breaks = find_breaks(bars, lines, rules=("any_close", "atr_full"))
        n_any = sum(1 for b in breaks if b.rule == "any_close")
        n_atr = sum(1 for b in breaks if b.rule == "atr_full")
        assert n_atr <= n_any

    def test_max_age_retires_lines(self) -> None:
        bars = geometric_brownian_series(1500, vol_per_bar=0.02, seed=5)
        short = build_trendlines(bars, TrendlineConfig(lookback=5, max_age=50))
        for ln in short:
            assert ln.retire_at - ln.active_from <= 50


class TestSupportingPrimitives:
    def test_atr_is_causal(self) -> None:
        bars = geometric_brownian_series(300, seed=11)
        full = atr(bars, 14)
        cut = 150
        assert atr(bars.slice(0, cut), 14)[-1] == pytest.approx(full[cut - 1])

    def test_rolling_vwap_is_causal(self) -> None:
        bars = geometric_brownian_series(300, seed=11)
        full = rolling_vwap(bars, 50)
        cut = 200
        assert rolling_vwap(bars.slice(0, cut), 50)[-1] == pytest.approx(full[cut - 1])

    def test_swing_confirmation_lag(self) -> None:
        bars = geometric_brownian_series(400, seed=2)
        for s in find_swings(bars, lookback=5, kind="low"):
            assert s.confirmed_index == s.index + 5

    def test_swings_known_by_filters_the_future(self) -> None:
        bars = geometric_brownian_series(400, seed=2)
        swings = find_swings(bars, lookback=5, kind="low")
        known = swings_known_by(swings, 200)
        assert all(s.confirmed_index <= 200 for s in known)

    def test_order_blocks_track_mitigation(self) -> None:
        bars = geometric_brownian_series(1000, vol_per_bar=0.03, seed=4)
        obs = find_order_blocks(bars)
        for ob in obs:
            assert ob.top >= ob.bottom
            assert ob.is_unmitigated == (ob.mitigated_index < 0)

    def test_ohlcv_rejects_inconsistent_bars(self) -> None:
        n = 10
        with pytest.raises(DataError):
            OHLCV(
                ts=np.arange(n, dtype=float),
                open=np.ones(n),
                high=np.full(n, 0.5),  # high below low
                low=np.ones(n),
                close=np.ones(n),
                volume=np.ones(n),
            )

    def test_ohlcv_rejects_unordered_timestamps(self) -> None:
        n = 10
        with pytest.raises(DataError):
            OHLCV(
                ts=np.zeros(n),
                open=np.ones(n),
                high=np.ones(n),
                low=np.ones(n),
                close=np.ones(n),
                volume=np.ones(n),
            )
