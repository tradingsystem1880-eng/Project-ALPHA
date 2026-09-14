"""Market profile: the numpy KDE and peak finder match SciPy, window levels match the pinned
upstream implementation when the ATR is supplied, per-bar levels stay inside their window, and
the penetration signal follows the documented crossing rule."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import scipy.signal
import scipy.stats

from alpha_core import DataError
from alpha_patterns import (
    geometric_brownian_series,
    log_atr,
    market_profile,
    sr_penetration_signal,
    support_resistance_levels,
)
from alpha_patterns._kde import prominent_peaks, weighted_gaussian_kde

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


class TestKdeMatchesScipy:
    @pytest.mark.parametrize("seed", [1, 2, 3])
    @pytest.mark.parametrize("factor", [0.05, 0.3, 1.5])
    def test_weighted_density(self, seed: int, factor: float) -> None:
        rng = np.random.default_rng(seed)
        x = rng.normal(size=150)
        w = np.asarray(0.05 + np.arange(150) * (0.95 / 150), dtype=np.float64)
        grid = np.linspace(x.min(), x.max(), 97)
        ours = weighted_gaussian_kde(x, grid, bandwidth_factor=factor, weights=w)
        theirs = scipy.stats.gaussian_kde(x, bw_method=factor, weights=w)(grid)
        np.testing.assert_allclose(ours, theirs, rtol=1e-9, atol=1e-12)

    def test_guards(self) -> None:
        g = np.linspace(0.0, 1.0, 5)
        with pytest.raises(DataError, match="zero weighted variance"):
            weighted_gaussian_kde(np.ones(10), g, bandwidth_factor=1.0, weights=np.ones(10))
        with pytest.raises(DataError, match="non-negative"):
            weighted_gaussian_kde(np.arange(5.0), g, bandwidth_factor=1.0, weights=-np.ones(5))
        with pytest.raises(DataError, match="bandwidth_factor"):
            weighted_gaussian_kde(np.arange(5.0), g, bandwidth_factor=0.0, weights=np.ones(5))


class TestPeaksMatchScipy:
    @pytest.mark.parametrize("seed", [4, 5, 6])
    def test_prominent_peaks(self, seed: int) -> None:
        rng = np.random.default_rng(seed)
        t = np.linspace(0.0, 10.0, 400)
        y = np.zeros_like(t)
        for centre, height, width in rng.uniform([0, 0.2, 0.1], [10, 1.0, 0.8], size=(8, 3)):
            y += height * np.exp(-0.5 * ((t - centre) / width) ** 2)
        y += rng.normal(0.0, 0.01, t.size)
        for pmin in (0.02, 0.1, 0.3):
            ours = prominent_peaks(y, min_prominence=pmin)
            theirs, _ = scipy.signal.find_peaks(y, prominence=pmin)
            np.testing.assert_array_equal(ours, theirs)

    def test_plateau_reports_midpoint_like_scipy(self) -> None:
        y = np.array([0.0, 1.0, 3.0, 3.0, 3.0, 1.0, 0.0, 2.0, 0.0])
        theirs, _ = scipy.signal.find_peaks(y, prominence=0.5)
        np.testing.assert_array_equal(prominent_peaks(y, min_prominence=0.5), theirs)


class TestWindowProfile:
    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "market_profile.json").read_text())
        s = fx["series"]
        bars = geometric_brownian_series(
            int(s["n_bars"]),
            vol_per_bar=float(s["vol_per_bar"]),
            seed=int(s["seed"]),
            start=float(s["start"]),
        )
        lc = np.log(bars.close)
        lb = int(fx["lookback"])
        for case in fx["cases"]:
            end = int(case["end"])
            prof = market_profile(
                lc[end - lb + 1 : end + 1],
                atr=float(case["atr"]),
                first_w=float(case["first_w"]),
                atr_mult=float(case["atr_mult"]),
                prom_thresh=float(case["prom_thresh"]),
            )
            assert prof.grid.size == case["grid_len"]
            assert list(prof.peaks) == case["peaks"]
            np.testing.assert_allclose(prof.levels, case["levels"], rtol=1e-9)
            sample = [prof.density[k] for k in (0, 50, 100, 150, prof.density.size - 1)]
            np.testing.assert_allclose(sample, case["pdf_sample"], rtol=1e-9)

    def test_flat_window_fails_loud(self) -> None:
        with pytest.raises(DataError, match="flat"):
            market_profile(np.zeros(50), atr=0.01)

    def test_levels_stay_inside_the_window(self) -> None:
        bars = geometric_brownian_series(800, vol_per_bar=0.02, seed=3)
        levels = support_resistance_levels(bars, lookback=120)
        assert all(v is None for v in levels[:120]) and all(v is not None for v in levels[120:])
        for i in range(120, 800):
            lv = levels[i]
            assert lv is not None
            window = bars.close[i - 119 : i + 1]
            assert np.all(lv >= window.min() * (1 - 1e-12)) and np.all(
                lv <= window.max() * (1 + 1e-12)
            )
        assert log_atr(bars, 120).shape == (800,)


class TestPenetrationSignal:
    def test_crossing_rule_persists(self) -> None:
        close = np.array([1.0, 2.0, 3.0, 2.0, 1.0, 1.5])
        levels: list[np.ndarray | None] = [None] + [np.array([2.5])] * 5
        assert list(sr_penetration_signal(close, levels)) == [0, 0, 1, -1, -1, -1]

    def test_length_mismatch(self) -> None:
        with pytest.raises(DataError, match="length"):
            sr_penetration_signal(np.ones(3), [None, None])
