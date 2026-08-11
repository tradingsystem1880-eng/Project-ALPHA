"""Pattern detection must be point-in-time: nothing after bar *t* may change what is known at *t*.

This is the guard the whole trendline study rests on. A line fitted with hindsight can be placed to
touch whatever the analyst wants, and a swing "detected" at its own bar is a bar of free
information. Both studies are only meaningful if:

1. a fractal swing is confirmed no earlier than ``lookback`` bars after it prints;
2. corrupting every bar after *t* leaves detections on ``[0, t)`` byte-identical (future poison);
3. entries are taken at the confirmation bar, never at the swing itself.

The one deliberate exception is ``TripleTap.entry_tap_close``, which the brief requested and which
is unknowable live. It is flagged ``entry_tap_close_is_lookahead`` and asserted here so the flag can
never quietly become False.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    OHLCV,
    TrendlineConfig,
    TripleTapConfig,
    build_trendlines,
    detect_triple_taps,
    distance_from_low,
    find_swings,
    geometric_brownian_series,
    inject_triple_tap,
    trend_state_vwap,
)

pytestmark = pytest.mark.bias_guard

CFG = TripleTapConfig(
    lookback=5, tolerance=0.02, band_reference="mean", gap_min=12, gap_max=250, population="strict"
)


def _poison(bars: OHLCV, cut: int, factor: float = 5.0) -> OHLCV:
    """Multiply every bar from ``cut`` onward — a violent, unmissable future perturbation."""
    o, h, low, c, v = (
        bars.open.copy(),
        bars.high.copy(),
        bars.low.copy(),
        bars.close.copy(),
        bars.volume.copy(),
    )
    for arr in (o, h, low, c):
        arr[cut:] *= factor
    v[cut:] *= factor
    return OHLCV(ts=bars.ts, open=o, high=h, low=low, close=c, volume=v, symbol=bars.symbol)


class TestSwingConfirmation:
    def test_swing_is_never_confirmed_before_its_lookback_elapses(self) -> None:
        bars = geometric_brownian_series(600, seed=3)
        for lookback in (3, 5, 8):
            for s in find_swings(bars, lookback=lookback, kind="low"):
                assert s.confirmed_index == s.index + lookback
                assert s.confirmed_index > s.index

    def test_swing_detection_on_a_prefix_matches_the_full_series(self) -> None:
        """Swings confirmed by bar t must be identical whether or not later bars exist."""
        bars = geometric_brownian_series(800, seed=9)
        cut = 500
        full = [
            s.index for s in find_swings(bars, lookback=5, kind="low") if s.confirmed_index < cut
        ]
        prefix = [
            s.index
            for s in find_swings(bars.slice(0, cut), lookback=5, kind="low")
            if s.confirmed_index < cut
        ]
        assert full == prefix


class TestFuturePoison:
    def test_triple_tap_detection_ignores_poisoned_future(self) -> None:
        bars, _ = inject_triple_tap(n_bars=500, tap_bars=(60, 160, 260), noise=0.001)
        cut = 300
        clean = detect_triple_taps(bars.slice(0, cut), CFG)
        dirty = detect_triple_taps(_poison(bars, cut).slice(0, cut), CFG)
        assert [e.tap_indices for e in clean] == [e.tap_indices for e in dirty]
        assert [e.level for e in clean] == [e.level for e in dirty]

    @pytest.mark.parametrize("seed", [1, 4, 21])
    def test_detection_stable_across_poisoned_noise(self, seed: int) -> None:
        bars = geometric_brownian_series(900, vol_per_bar=0.02, seed=seed)
        cut = 600
        clean = detect_triple_taps(bars.slice(0, cut), CFG)
        dirty = detect_triple_taps(_poison(bars, cut).slice(0, cut), CFG)
        assert [e.tap_indices for e in clean] == [e.tap_indices for e in dirty]

    def test_trendlines_ignore_poisoned_future(self) -> None:
        bars = geometric_brownian_series(900, vol_per_bar=0.02, seed=6)
        cut = 600
        cfg = TrendlineConfig(lookback=5, max_age=300)
        clean = build_trendlines(bars.slice(0, cut), cfg)
        dirty = build_trendlines(_poison(bars, cut).slice(0, cut), cfg)
        assert [ln.anchor_indices for ln in clean] == [ln.anchor_indices for ln in dirty]
        assert [ln.anchor_prices for ln in clean] == [ln.anchor_prices for ln in dirty]

    def test_context_measures_are_causal(self) -> None:
        bars = geometric_brownian_series(900, vol_per_bar=0.02, seed=8)
        cut = 600
        assert trend_state_vwap(bars, window=200)[:cut] == trend_state_vwap(
            bars.slice(0, cut), window=200
        )
        np.testing.assert_allclose(
            distance_from_low(bars, window=200)[:cut],
            distance_from_low(bars.slice(0, cut), window=200),
        )


class TestEntryHonesty:
    def test_confirmation_entry_is_at_or_after_the_third_tap_confirmation(self) -> None:
        bars, _ = inject_triple_tap(n_bars=500, noise=0.001)
        for e in detect_triple_taps(bars, CFG):
            assert e.entry_confirm_index >= e.tap_indices[2] + CFG.lookback - 1
            assert e.entry_confirm_index == e.confirmed_index

    def test_breakout_entry_never_precedes_confirmation(self) -> None:
        bars = geometric_brownian_series(1500, vol_per_bar=0.02, seed=12)
        for e in detect_triple_taps(bars, CFG):
            if e.entry_breakout_index >= 0:
                assert e.entry_breakout_index > e.confirmed_index

    def test_tap_close_entry_is_declared_lookahead(self) -> None:
        """This entry variant was requested but is unknowable live; the flag must stay True."""
        bars, _ = inject_triple_tap(n_bars=500, noise=0.001)
        for e in detect_triple_taps(bars, CFG):
            assert e.entry_tap_close_is_lookahead is True
            assert e.entry_tap_close_index < e.entry_confirm_index

    def test_trendline_is_inactive_before_its_second_anchor_confirms(self) -> None:
        bars = geometric_brownian_series(1200, vol_per_bar=0.02, seed=15)
        for ln in build_trendlines(bars, TrendlineConfig(lookback=5)):
            assert ln.active_from >= ln.anchor_indices[1]
