"""Market structure: streaming ATR directional change and hierarchical extremes recover a synthetic
zigzag, satisfy the structural invariants at every level, answer level queries in confirmation
order, and reproduce the pinned upstream implementation exactly on the shared fixture series."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    OHLCV,
    ATRDirectionalChange,
    HierarchicalExtremes,
    LocalExtreme,
    atr_directional_change,
    extremes_known_by,
    extremes_sanity_checks,
    geometric_brownian_series,
    hierarchical_extremes,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


def _ext(kind: str, index: int, price: float, conf: int = 0) -> LocalExtreme:
    return LocalExtreme(kind, index, price, conf or index + 1, price)  # type: ignore[arg-type]


def _flat(closes: list[float]) -> OHLCV:
    c = np.asarray(closes, dtype=np.float64)
    return OHLCV(np.arange(c.size, dtype=np.float64), c, c, c, c, np.ones(c.size))


def _fixture() -> tuple[dict[str, Any], OHLCV]:
    fx = json.loads((FIXTURES / "market_structure.json").read_text())
    s = fx["series"]
    bars = geometric_brownian_series(
        int(s["n_bars"]),
        vol_per_bar=float(s["vol_per_bar"]),
        seed=int(s["seed"]),
        start=float(s["start"]),
    )
    return fx, bars


def _rows(exts: list[LocalExtreme]) -> list[list[float]]:
    return [
        [1 if e.kind == "high" else -1, e.index, e.price, e.confirmed_index, e.confirmed_price]
        for e in exts
    ]


class TestSanityChecks:
    def test_alternating_sequence_passes(self) -> None:
        extremes_sanity_checks([_ext("low", 1, 1.0), _ext("high", 5, 1.2), _ext("low", 9, 1.1)])

    def test_short_sequences_pass(self) -> None:
        extremes_sanity_checks([])
        extremes_sanity_checks([_ext("high", 3, 1.0)])

    def test_two_highs_in_a_row(self) -> None:
        with pytest.raises(DataError, match="alternate"):
            extremes_sanity_checks([_ext("high", 1, 1.0), _ext("high", 2, 1.1)])

    def test_index_must_not_decrease(self) -> None:
        with pytest.raises(DataError, match="non-decreasing"):
            extremes_sanity_checks([_ext("high", 5, 1.2), _ext("low", 4, 1.0)])

    def test_high_must_exceed_prior_low(self) -> None:
        with pytest.raises(DataError, match="exceed the prior low"):
            extremes_sanity_checks([_ext("low", 1, 1.0), _ext("high", 3, 0.9)])

    def test_low_must_be_below_prior_high(self) -> None:
        with pytest.raises(DataError, match="below the prior high"):
            extremes_sanity_checks([_ext("high", 1, 1.0), _ext("low", 3, 1.1)])


class TestATRDirectionalChange:
    ZIGZAG = (
        [1.0 + 0.02 * k for k in range(6)]
        + [1.10 - 0.02 * k for k in range(1, 6)]
        + [1.0 + 0.02 * k for k in range(1, 6)]
    )

    def test_zigzag_turning_points(self) -> None:
        # flat bars: true range == |close - prev close| == 0.02 everywhere, so ATR == 0.02 and
        # a reversal is confirmed on the second bar past each turn.
        exts = atr_directional_change(_flat(self.ZIGZAG), atr_lookback=3)
        assert [(e.kind, e.index, e.confirmed_index) for e in exts] == [
            ("high", 5, 7),
            ("low", 10, 12),
        ]
        extremes_sanity_checks(exts)

    def test_invariants_on_noise(self) -> None:
        exts = atr_directional_change(geometric_brownian_series(800, seed=3), atr_lookback=14)
        assert len(exts) > 20
        extremes_sanity_checks(exts)
        # an extreme may be confirmed on its own bar when that bar's range exceeds the ATR
        assert all(e.confirmed_index >= e.index for e in exts)

    def test_streaming_returns_the_confirmed_extreme(self) -> None:
        bars = geometric_brownian_series(300, seed=5)
        dc = ATRDirectionalChange(10)
        returned = [e for i in range(len(bars)) if (e := dc.update(i, bars)) is not None]
        assert returned == dc.extremes
        assert all(e.confirmed_index == i for i, e in ((e.confirmed_index, e) for e in returned))

    def test_prefix_run_equals_known_by(self) -> None:
        """Streaming is point-in-time: feeding only bars <= cut yields exactly known_by(cut)."""
        bars = geometric_brownian_series(500, seed=11)
        cut = 260
        full = atr_directional_change(bars, atr_lookback=12)
        prefix = atr_directional_change(bars.slice(0, cut + 1), atr_lookback=12)
        assert prefix == extremes_known_by(full, cut)

    def test_update_out_of_order_fails(self) -> None:
        bars = geometric_brownian_series(50, seed=1)
        dc = ATRDirectionalChange(5)
        dc.update(0, bars)
        with pytest.raises(DataError, match="in order"):
            dc.update(2, bars)

    def test_lookback_guard(self) -> None:
        with pytest.raises(DataError, match="atr_lookback"):
            ATRDirectionalChange(0)

    def test_matches_pinned_upstream(self) -> None:
        fx, bars = _fixture()
        exts = atr_directional_change(bars, atr_lookback=int(fx["atr_lookback"]))
        ours, theirs = _rows(exts), fx["atr_dc"]
        assert [r[:2] + [r[3]] for r in ours] == [r[:2] + [r[3]] for r in theirs]
        np.testing.assert_allclose([r[2] for r in ours], [r[2] for r in theirs], rtol=1e-12)
        np.testing.assert_allclose([r[4] for r in ours], [r[4] for r in theirs], rtol=1e-12)


class TestHierarchicalExtremes:
    def test_every_level_is_sane_and_nested(self) -> None:
        levels = hierarchical_extremes(
            geometric_brownian_series(1500, seed=4), levels=4, atr_lookback=14
        )
        counts = [len(lvl) for lvl in levels]
        assert counts[0] > counts[1] > counts[2] > 0
        for lower, upper in zip(levels, levels[1:], strict=False):
            extremes_sanity_checks(upper)
            lower_keys = {(e.kind, e.index, e.price) for e in lower}
            assert all((e.kind, e.index, e.price) in lower_keys for e in upper)
            assert all(e.confirmed_index >= e.index for e in upper)

    def test_promotion_confirms_no_earlier_than_the_base(self) -> None:
        levels = hierarchical_extremes(
            geometric_brownian_series(1500, seed=6), levels=3, atr_lookback=14
        )
        base_conf = {(e.kind, e.index): e.confirmed_index for e in levels[0]}
        for e in levels[1]:
            assert e.confirmed_index >= base_conf[(e.kind, e.index)]

    def test_level_queries(self) -> None:
        bars = geometric_brownian_series(1500, seed=8)
        he = HierarchicalExtremes(levels=3, atr_lookback=14)
        for i in range(len(bars)):
            he.update(i, bars)
        seq = he.extremes[1]
        highs = [e for e in seq if e.kind == "high"]
        lows = [e for e in seq if e.kind == "low"]
        assert he.get_level_high(1) == highs[-1]
        assert he.get_level_high(1, lag=1) == highs[-2]
        assert he.get_level_low(1) == lows[-1]
        assert he.get_level_low(1, lag=len(lows)) is None
        assert he.get_level_high(2, lag=50) is None

    def test_query_guards(self) -> None:
        he = HierarchicalExtremes(levels=2, atr_lookback=5)
        assert he.get_level_high(0) is None
        with pytest.raises(DataError, match="level"):
            he.get_level_high(2)
        with pytest.raises(DataError, match="lag"):
            he.get_level_low(0, lag=-1)
        with pytest.raises(DataError, match="levels"):
            HierarchicalExtremes(levels=0, atr_lookback=5)

    def test_prefix_run_equals_known_by_at_every_level(self) -> None:
        bars = geometric_brownian_series(1200, seed=13)
        cut = 700
        full = hierarchical_extremes(bars, levels=4, atr_lookback=14)
        prefix = hierarchical_extremes(bars.slice(0, cut + 1), levels=4, atr_lookback=14)
        for lvl_full, lvl_prefix in zip(full, prefix, strict=True):
            assert lvl_prefix == extremes_known_by(lvl_full, cut)

    def test_matches_pinned_upstream(self) -> None:
        fx, bars = _fixture()
        levels = hierarchical_extremes(
            bars, levels=int(fx["levels"]), atr_lookback=int(fx["atr_lookback"])
        )
        assert [len(lvl) for lvl in levels] == [len(lvl) for lvl in fx["hierarchical"]]
        for ours_lvl, theirs_lvl in zip(levels, fx["hierarchical"], strict=True):
            ours = _rows(ours_lvl)
            assert [r[:2] + [r[3]] for r in ours] == [r[:2] + [r[3]] for r in theirs_lvl]
            np.testing.assert_allclose([r[2] for r in ours], [r[2] for r in theirs_lvl], rtol=1e-12)
