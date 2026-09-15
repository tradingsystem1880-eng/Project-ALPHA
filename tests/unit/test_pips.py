"""Perceptually important points: hand-checkable selections for all three distance measures,
fail-loud bounds, z-scored trailing windows, and parity with the pinned upstream implementation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import find_pips, geometric_brownian_series, pip_windows

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"

# Endpoints are 0 and 0, so the first pip is the spike at 2 under every measure; the second pip
# then depends on the measure (worked by hand in the test names).
SHAPE = np.array([0.0, 1.0, 5.0, 1.0, 0.0, 2.0, 0.0])


class TestSelection:
    def test_endpoints_always_included_and_sorted(self) -> None:
        idx, prices = find_pips(SHAPE, 3)
        assert idx[0] == 0 and idx[-1] == SHAPE.size - 1
        assert list(idx) == sorted(idx)
        np.testing.assert_array_equal(prices, SHAPE[idx])

    def test_vertical_picks_largest_gap_to_polyline(self) -> None:
        idx, _ = find_pips(SHAPE, 4, distance="vertical")
        assert list(idx) == [0, 2, 3, 6]

    def test_perpendicular_agrees_on_this_shape(self) -> None:
        idx, _ = find_pips(SHAPE, 4, distance="perpendicular")
        assert list(idx) == [0, 2, 3, 6]

    def test_euclidean_prefers_the_bar_far_from_both_anchors(self) -> None:
        idx, _ = find_pips(SHAPE, 4, distance="euclidean")
        assert list(idx) == [0, 2, 4, 6]

    def test_all_points_when_n_pips_equals_length(self) -> None:
        idx, _ = find_pips(SHAPE, SHAPE.size)
        assert list(idx) == list(range(SHAPE.size))

    def test_collinear_interior_still_selects_a_bar(self) -> None:
        idx, _ = find_pips(np.array([1.0, 1.0, 1.0, 1.0]), 3)
        assert list(idx) == [0, 1, 3]


class TestGuards:
    @pytest.mark.parametrize("n_pips", [0, 1])
    def test_too_few_pips(self, n_pips: int) -> None:
        with pytest.raises(DataError, match="n_pips"):
            find_pips(SHAPE, n_pips)

    def test_more_pips_than_bars(self) -> None:
        with pytest.raises(DataError, match="exceeds"):
            find_pips(SHAPE, SHAPE.size + 1)

    def test_non_finite_rejected(self) -> None:
        with pytest.raises(DataError, match="non-finite"):
            find_pips(np.array([0.0, np.nan, 1.0]), 2)

    def test_unknown_distance_rejected(self) -> None:
        with pytest.raises(DataError, match="distance"):
            find_pips(SHAPE, 3, distance="manhattan")  # type: ignore[arg-type]


class TestWindows:
    def test_rows_are_zscored_and_end_indexed(self) -> None:
        close = geometric_brownian_series(120, vol_per_bar=0.02, seed=11).close
        win = pip_windows(close, lookback=24, n_pips=5)
        assert win.matrix.shape == (120 - 24 + 1, 5)
        assert list(win.end_index[:3]) == [23, 24, 25] and win.end_index[-1] == 119
        np.testing.assert_allclose(win.matrix.mean(axis=1), 0.0, atol=1e-12)
        np.testing.assert_allclose(win.matrix.std(axis=1), 1.0, rtol=1e-12)

    def test_stride_thins_the_window_ends(self) -> None:
        close = geometric_brownian_series(100, seed=2).close
        win = pip_windows(close, lookback=10, n_pips=3, stride=7)
        assert list(win.end_index) == list(range(9, 100, 7))

    def test_row_matches_direct_find_pips(self) -> None:
        close = geometric_brownian_series(80, vol_per_bar=0.03, seed=9).close
        win = pip_windows(close, lookback=30, n_pips=4)
        end = int(win.end_index[10])
        _, prices = find_pips(close[end - 29 : end + 1], 4)
        expected = (prices - prices.mean()) / prices.std()
        np.testing.assert_allclose(win.matrix[10], expected, rtol=1e-12)

    def test_flat_window_fails_loud(self) -> None:
        with pytest.raises(DataError, match="flat"):
            pip_windows(np.ones(20), lookback=10, n_pips=3)

    @pytest.mark.parametrize("lookback", [1, 500])
    def test_lookback_bounds(self, lookback: int) -> None:
        with pytest.raises(DataError, match="lookback"):
            pip_windows(np.arange(50, dtype=np.float64), lookback=lookback, n_pips=3)


class TestUpstreamParity:
    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "pips.json").read_text())
        s = fx["series"]
        bars = geometric_brownian_series(
            int(s["n_bars"]), vol_per_bar=float(s["vol_per_bar"]), seed=int(s["seed"])
        )
        lo, hi = fx["window"]
        x = bars.close[lo:hi]
        for case in fx["cases"]:
            idx, prices = find_pips(x, int(fx["n_pips"]), distance=case["distance"])
            assert list(idx) == case["pips_x"]
            np.testing.assert_allclose(prices, case["pips_y"], rtol=1e-12)
