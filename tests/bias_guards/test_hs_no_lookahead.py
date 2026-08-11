"""Head & shoulders / Quasimodo detection must be point-in-time.

A five-point pattern carries **five** confirmation lags, and it is the *latest* of them that decides
when a trader could have acted. Getting this wrong is the single easiest way to manufacture a fake
edge in this pattern family: the right shoulder is by definition the last thing to form, so an
entry priced at the head — or a neckline break searched from the head's bar — quietly buys several
weeks of hindsight.

The Quasimodo break of structure adds a second trap. It must be searched only *after the head is
confirmed*, never from the head's own bar, and it must land before the right shoulder prints.

Guards here: the confirmation contract, future poisoning, and the ordering of every entry index.
"""

from __future__ import annotations

import pytest

from alpha_patterns import (
    OHLCV,
    HSConfig,
    HSEvent,
    detect_head_shoulders,
    geometric_brownian_series,
    inject_head_shoulders,
)

pytestmark = pytest.mark.bias_guard

CFG = HSConfig(
    lookback=5,
    head_prominence=0.03,
    shoulder_tol=0.6,
    time_symmetry_tol=0.25,
    max_neckline_slope=0.25,
    gap_min=20,
    gap_max=250,
)


def _anchors(events: list[HSEvent]) -> list[tuple[int, int, int, int, int]]:
    return [(e.ls_index, e.n1_index, e.head_index, e.n2_index, e.rs_index) for e in events]


def _poison(bars: OHLCV, cut: int, factor: float = 5.0) -> OHLCV:
    """Multiply every bar from ``cut`` onward — an unmissable future perturbation."""
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


class TestConfirmationContract:
    def test_confirmed_index_is_the_latest_of_all_five_pivots(self) -> None:
        bars = geometric_brownian_series(4000, vol_per_bar=0.02, seed=3)
        for e in detect_head_shoulders(bars, CFG):
            latest_pivot = max(e.ls_index, e.n1_index, e.head_index, e.n2_index, e.rs_index)
            assert e.confirmed_index >= latest_pivot + CFG.lookback - 1
            assert e.confirmed_index >= e.rs_index

    def test_confirmation_never_precedes_the_right_shoulder(self) -> None:
        """The right shoulder forms last, so nothing can be known before it prints."""
        bars = geometric_brownian_series(4000, vol_per_bar=0.02, seed=11)
        for e in detect_head_shoulders(bars, CFG):
            assert e.confirmed_index > e.rs_index or e.confirmed_index == len(bars) - 1

    def test_anchor_ordering_is_strict(self) -> None:
        bars = geometric_brownian_series(4000, vol_per_bar=0.02, seed=8)
        for e in detect_head_shoulders(bars, CFG):
            assert e.ls_index < e.n1_index < e.head_index < e.n2_index < e.rs_index


class TestEntryOrdering:
    @pytest.mark.parametrize("direction", ["bullish", "bearish"])
    def test_every_entry_index_is_at_or_after_confirmation(self, direction: str) -> None:
        bars = geometric_brownian_series(4000, vol_per_bar=0.02, seed=5)
        cfg = HSConfig(**{**CFG.__dict__, "direction": direction})
        for e in detect_head_shoulders(bars, cfg):
            for idx in (e.neckline_break_index, e.qm_entry_index, e.retest_index):
                if idx >= 0:
                    assert idx > e.confirmed_index, (
                        f"entry at {idx} precedes confirmation {e.confirmed_index}"
                    )

    def test_retest_never_precedes_the_break_it_retests(self) -> None:
        bars = geometric_brownian_series(4000, vol_per_bar=0.02, seed=9)
        for e in detect_head_shoulders(bars, CFG):
            if e.retest_index >= 0:
                assert e.neckline_break_index >= 0
                assert e.retest_index > e.neckline_break_index

    def test_bos_is_searched_only_after_the_head_is_confirmed(self) -> None:
        bars = geometric_brownian_series(4000, vol_per_bar=0.02, seed=7)
        for e in detect_head_shoulders(bars, CFG):
            if e.has_bos:
                assert e.bos_index >= e.head_index + CFG.lookback
                assert e.bos_index <= e.rs_index


class TestFuturePoison:
    @pytest.mark.parametrize("direction", ["bullish", "bearish"])
    def test_detection_ignores_a_poisoned_future(self, direction: str) -> None:
        bars, _ = inject_head_shoulders(
            n_bars=700, direction=direction, anchor_bars=(80, 220, 360), noise=0.001
        )
        cut = 400
        cfg = HSConfig(**{**CFG.__dict__, "direction": direction})
        clean = detect_head_shoulders(bars.slice(0, cut), cfg)
        dirty = detect_head_shoulders(_poison(bars, cut).slice(0, cut), cfg)
        assert _anchors(clean) == _anchors(dirty)

    @pytest.mark.parametrize("seed", [2, 14, 23])
    def test_detection_stable_on_poisoned_noise(self, seed: int) -> None:
        bars = geometric_brownian_series(2000, vol_per_bar=0.02, seed=seed)
        cut = 1400
        clean = detect_head_shoulders(bars.slice(0, cut), CFG)
        dirty = detect_head_shoulders(_poison(bars, cut).slice(0, cut), CFG)
        assert [e.head_index for e in clean] == [e.head_index for e in dirty]
        assert [e.has_bos for e in clean] == [e.has_bos for e in dirty]

    def test_geometry_is_identical_under_poisoning(self) -> None:
        """Not just the anchors — prices, depth and the neckline must be byte-identical too."""
        bars = geometric_brownian_series(2000, vol_per_bar=0.02, seed=17)
        cut = 1200
        clean = detect_head_shoulders(bars.slice(0, cut), CFG)
        dirty = detect_head_shoulders(_poison(bars, cut).slice(0, cut), CFG)
        assert [e.head_price for e in clean] == [e.head_price for e in dirty]
        assert [e.head_depth for e in clean] == [e.head_depth for e in dirty]
        assert [e.neckline_slope for e in clean] == [e.neckline_slope for e in dirty]

    def test_prefix_detection_matches_the_full_series(self) -> None:
        """Events confirmed by bar t must be identical whether or not later bars exist."""
        bars = geometric_brownian_series(2500, vol_per_bar=0.02, seed=13)
        cut = 1500
        full = [
            (e.ls_index, e.head_index, e.rs_index)
            for e in detect_head_shoulders(bars, CFG)
            if e.confirmed_index < cut
        ]
        prefix = [
            (e.ls_index, e.head_index, e.rs_index)
            for e in detect_head_shoulders(bars.slice(0, cut), CFG)
            if e.confirmed_index < cut
        ]
        assert full == prefix
