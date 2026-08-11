"""Wilson / Newcombe / Benjamini-Hochberg / effective-n, checked against published values.

These four are the load-bearing statistics of any pattern-edge study, so they are pinned to
independently-known answers rather than to whatever the implementation happens to produce.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation import (
    autocorrelation_effective_size,
    benjamini_hochberg,
    effective_sample_size,
    newcombe_diff_interval,
    overlap_factor,
    wilson_interval,
)


class TestWilson:
    def test_matches_published_value(self) -> None:
        # Textbook worked example: 9 successes in 181 trials, 95% -> approx [2.6%, 9.2%].
        ci = wilson_interval(9, 181)
        assert ci.lower == pytest.approx(0.0264, abs=5e-4)
        assert ci.upper == pytest.approx(0.0918, abs=5e-4)
        assert ci.point == pytest.approx(9 / 181)

    def test_beats_normal_approximation_at_small_p(self) -> None:
        """The normal interval sinks below zero at small p; Wilson never leaves [0, 1]."""
        ci = wilson_interval(1, 200)
        assert ci.lower >= 0.0
        normal_lower = 1 / 200 - 1.96 * np.sqrt((1 / 200) * (199 / 200) / 200)
        assert normal_lower < 0.0 < ci.lower

    def test_zero_and_full_successes_stay_in_bounds(self) -> None:
        assert wilson_interval(0, 50).lower == 0.0
        assert wilson_interval(50, 50).upper == 1.0

    def test_interval_narrows_as_n_grows(self) -> None:
        widths = [
            wilson_interval(round(0.33 * n), n).upper - wilson_interval(round(0.33 * n), n).lower
            for n in (50, 200, 800, 3200)
        ]
        assert widths == sorted(widths, reverse=True)

    def test_contains_and_beats_helpers(self) -> None:
        ci = wilson_interval(9, 181)
        assert ci.contains(0.0336)  # breakeven inside -> no edge established
        assert not ci.beats(0.0336)
        assert wilson_interval(60, 100).beats(0.40)

    @pytest.mark.parametrize(("k", "n"), [(-1, 10), (11, 10), (0, 0)])
    def test_rejects_bad_counts(self, k: int, n: int) -> None:
        with pytest.raises(DataError):
            wilson_interval(k, n)


class TestNewcombe:
    def test_symmetric_arms_centre_on_zero(self) -> None:
        d = newcombe_diff_interval(30, 100, 30, 100)
        assert d.point == pytest.approx(0.0)
        assert d.lower < 0.0 < d.upper

    def test_detects_a_real_difference(self) -> None:
        d = newcombe_diff_interval(80, 100, 20, 100)
        assert d.point == pytest.approx(0.6)
        assert d.lower > 0.0  # whole interval above zero

    def test_wide_interval_straddles_zero_on_small_samples(self) -> None:
        d = newcombe_diff_interval(6, 10, 4, 10)
        assert d.lower < 0.0 < d.upper

    def test_bounds_stay_within_minus_one_to_one(self) -> None:
        d = newcombe_diff_interval(10, 10, 0, 10)
        assert -1.0 <= d.lower <= d.upper <= 1.0


class TestBenjaminiHochberg:
    def test_known_worked_example(self) -> None:
        """Hand-checked: reject up to the largest i with p_(i) <= alpha*i/m.

        m=8, alpha=0.05 -> thresholds 0.00625, 0.0125, 0.01875, 0.025, ...
        i=1: 0.001 <= 0.00625 yes; i=2: 0.008 <= 0.0125 yes; i=3: 0.039 > 0.01875 no.
        Largest passing i is 2, so exactly two hypotheses are rejected.
        """
        p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205])
        r = benjamini_hochberg(p, alpha=0.05)
        assert r.n_rejected == 2
        assert bool(r.rejected[0]) and bool(r.rejected[1])
        assert not bool(r.rejected[2])
        # q-values are p_(i) * m / i, made monotone: 0.001*8/1 and 0.008*8/2.
        assert r.qvalues[0] == pytest.approx(0.008)
        assert r.qvalues[1] == pytest.approx(0.032)

    def test_step_up_rejects_a_whole_prefix(self) -> None:
        """A borderline p-value carries the ones below it: BH is step-*up*, not per-hypothesis."""
        p = np.array([0.04, 0.03, 0.02, 0.01])  # every p_(i) <= 0.05*i/4
        r = benjamini_hochberg(p, alpha=0.05)
        assert r.n_rejected == 4

    def test_qvalues_are_monotone_in_pvalue_order(self) -> None:
        p = np.array([0.02, 0.001, 0.3, 0.04])
        q = benjamini_hochberg(p).qvalues
        order = np.argsort(p)
        assert list(q[order]) == sorted(q[order])

    def test_only_ever_raises_pvalues(self) -> None:
        """BH cannot rescue a family with no raw significance — q >= p always."""
        p = np.array([0.2, 0.4, 0.6, 0.8])
        r = benjamini_hochberg(p)
        assert bool(np.all(r.qvalues >= p - 1e-12))
        assert r.n_rejected == 0

    def test_large_family_needs_extreme_pvalue(self) -> None:
        p = np.concatenate(([1e-3], np.full(9999, 0.5)))
        assert benjamini_hochberg(p).n_rejected == 0

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(DataError):
            benjamini_hochberg(np.array([0.5, 1.5]))


class TestEffectiveSampleSize:
    def test_non_overlapping_windows_keep_full_n(self) -> None:
        # 100 events over 10,000 bars with a 10-bar horizon: spacing 100 >> horizon.
        assert effective_sample_size(100, span_bars=10_000, horizon_bars=10) == 100.0
        assert overlap_factor(100, span_bars=10_000, horizon_bars=10) == 1.0

    def test_overlapping_windows_collapse_n(self) -> None:
        """The live-trade case: 181 events, 20,866 bars, 540-bar (90-day) horizon."""
        n_eff = effective_sample_size(181, span_bars=20_866, horizon_bars=540)
        assert n_eff == pytest.approx(38.6, abs=0.5)
        ov = overlap_factor(181, span_bars=20_866, horizon_bars=540)
        assert ov == pytest.approx(4.7, abs=0.1)

    def test_never_exceeds_event_count(self) -> None:
        assert effective_sample_size(5, span_bars=10_000, horizon_bars=1) == 5.0

    def test_zero_events(self) -> None:
        assert effective_sample_size(0, span_bars=100, horizon_bars=10) == 0.0

    def test_autocorrelated_series_loses_independence(self) -> None:
        rng = np.random.default_rng(7)
        white = rng.normal(size=2000)
        # AR(1) with strong persistence carries far less information per observation.
        ar = np.zeros(2000)
        for i in range(1, 2000):
            ar[i] = 0.9 * ar[i - 1] + rng.normal()
        assert autocorrelation_effective_size(ar) < autocorrelation_effective_size(white) / 3

    def test_rejects_degenerate_input(self) -> None:
        with pytest.raises(DataError):
            autocorrelation_effective_size(np.ones(50))
