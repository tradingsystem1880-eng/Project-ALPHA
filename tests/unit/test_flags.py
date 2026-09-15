"""Flags and pennants: an injected bull flag is confirmed after its pole and consolidation,
every reported pattern satisfies the width/height bounds and confirmation geometry, and both
variants reproduce the pinned upstream implementation exactly."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    FlagPattern,
    detect_flags_pips,
    detect_flags_trendline,
    flags_known_by,
    geometric_brownian_series,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


def _injected_bull_flag() -> np.ndarray:
    down = [1.06, 1.04, 1.02, 1.01, 1.005, 1.0]  # base at bar 5
    pole = [1.0 + 0.01 * k for k in range(1, 21)]  # tip 1.20 at bar 25
    flag = [1.17, 1.19, 1.16, 1.18, 1.15, 1.17, 1.14, 1.16]  # descending channel, bars 26-33
    breakout = [1.25, 1.27, 1.26, 1.28, 1.30, 1.29, 1.31, 1.33]
    return np.asarray(down + pole + flag + breakout, dtype=np.float64)


def _check_geometry(pat: FlagPattern) -> None:
    assert pat.base_index < pat.tip_index < pat.confirmed_index
    assert pat.flag_width == pat.confirmed_index - pat.tip_index
    assert pat.pole_width == pat.tip_index - pat.base_index
    assert pat.flag_width <= pat.pole_width * 0.5
    assert pat.pole_height > 0.0 and pat.flag_height >= 0.0
    if pat.bullish:
        assert pat.tip_price > pat.base_price
    else:
        assert pat.tip_price < pat.base_price


class TestInjectedFlag:
    def test_trendline_variant_confirms_the_bull_flag(self) -> None:
        found = [p for p in detect_flags_trendline(_injected_bull_flag(), order=3) if p.bullish]
        assert found, "injected flag not detected"
        pat = found[0]
        assert (pat.base_index, pat.tip_index) == (5, 25)
        assert 28 <= pat.confirmed_index <= 34
        assert pat.confirmed_price > pat.resist_intercept + pat.resist_slope * (pat.flag_width + 1)
        _check_geometry(pat)

    def test_flat_series_has_no_patterns(self) -> None:
        assert detect_flags_pips(np.ones(200), order=5) == []
        assert detect_flags_trendline(np.ones(200), order=5) == []


class TestInvariantsOnNoise:
    @pytest.mark.parametrize("variant", ["pips", "trendline"])
    def test_geometry_bounds(self, variant: str) -> None:
        data = np.log(geometric_brownian_series(3000, vol_per_bar=0.02, seed=7).close)
        found = (
            detect_flags_pips(data, order=12)
            if variant == "pips"
            else detect_flags_trendline(data, order=10)
        )
        assert len(found) > 5
        for pat in found:
            _check_geometry(pat)
            assert pat.confirmed_price == pytest.approx(data[pat.confirmed_index])
            assert pat.tip_price == pytest.approx(data[pat.tip_index])
        assert [p.confirmed_index for p in found] == sorted(p.confirmed_index for p in found)

    def test_known_by(self) -> None:
        data = np.log(geometric_brownian_series(3000, vol_per_bar=0.02, seed=7).close)
        found = detect_flags_trendline(data, order=10)
        mid = found[len(found) // 2].confirmed_index
        assert flags_known_by(found, mid) == [p for p in found if p.confirmed_index <= mid]

    def test_guards(self) -> None:
        with pytest.raises(DataError, match="order"):
            detect_flags_pips(np.arange(50, dtype=np.float64), order=2)
        with pytest.raises(DataError, match="non-finite"):
            detect_flags_trendline(np.array([1.0, np.nan, 2.0]), order=3)


class TestUpstreamParity:
    @staticmethod
    def _rows(found: list[FlagPattern]) -> list[tuple[object, ...]]:
        return sorted(
            (
                (
                    p.bullish,
                    p.pennant,
                    p.base_index,
                    p.tip_index,
                    p.confirmed_index,
                    p.flag_width,
                    p.pole_width,
                )
                for p in found
            ),
            key=lambda r: (r[4], r[0]),
        )

    @pytest.mark.parametrize("variant", ["pips", "trendline"])
    def test_matches_pinned_upstream(self, variant: str) -> None:
        fx = json.loads((FIXTURES / "flags.json").read_text())
        s = fx["series"]
        data = np.log(
            geometric_brownian_series(
                int(s["n_bars"]),
                vol_per_bar=float(s["vol_per_bar"]),
                seed=int(s["seed"]),
                start=float(s["start"]),
            ).close
        )
        case = fx[variant]
        found = (
            detect_flags_pips(data, order=int(case["order"]))
            if variant == "pips"
            else detect_flags_trendline(data, order=int(case["order"]))
        )
        theirs = sorted(
            (
                (
                    r["bull"],
                    r["pennant"],
                    r["base_x"],
                    r["tip_x"],
                    r["conf_x"],
                    r["flag_width"],
                    r["pole_width"],
                )
                for r in case["patterns"]
            ),
            key=lambda r: (r[4], r[0]),
        )
        assert self._rows(found) == theirs
        ours_sorted = sorted(found, key=lambda p: (p.confirmed_index, p.bullish))
        theirs_sorted = sorted(case["patterns"], key=lambda r: (r["conf_x"], r["bull"]))
        for p, r in zip(ours_sorted, theirs_sorted, strict=True):
            for ours, key in (
                (p.flag_height, "flag_height"),
                (p.pole_height, "pole_height"),
                (p.support_slope, "support_slope"),
                (p.support_intercept, "support_intercept"),
                (p.resist_slope, "resist_slope"),
                (p.resist_intercept, "resist_intercept"),
            ):
                assert ours == pytest.approx(r[key], rel=1e-12, abs=1e-12), key
