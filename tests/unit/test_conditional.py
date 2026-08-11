"""Conditional lift: the arm split, the corrections, and the failure modes it exists to prevent.

Each test here corresponds to a specific way a conditional-probability claim goes wrong in the wild:
comparing against the wrong arm, counting unresolved observations as failures, treating overlapping
windows as independent, and reading one bright cell out of forty.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation import (
    apply_fdr,
    conditional_lift,
    lift_table,
    monotonic_trend,
    two_proportion_pvalue,
)


class TestArmSplit:
    def test_compares_against_the_complement_not_the_whole_sample(self) -> None:
        # 100 bars: the condition holds on the first 50, where the outcome is always true; on the
        # other 50 the outcome never fires. The complement rate must be 0, not the pooled 0.5.
        cond = np.array([True] * 50 + [False] * 50)
        out = np.array([True] * 50 + [False] * 50)
        r = conditional_lift(cond, out)
        assert r.rate_condition == pytest.approx(1.0)
        assert r.rate_complement == pytest.approx(0.0)
        assert r.rate_overall == pytest.approx(0.5)
        assert r.difference == pytest.approx(1.0)

    def test_an_uninformative_condition_shows_no_difference(self) -> None:
        rng = np.random.default_rng(4)
        cond = rng.random(4000) < 0.3
        out = rng.random(4000) < 0.25  # independent of cond by construction
        r = conditional_lift(cond, out)
        assert abs(r.difference) < 0.05
        assert r.interval_difference.contains(0.0)
        assert not r.separated

    def test_a_real_effect_separates_from_zero(self) -> None:
        rng = np.random.default_rng(4)
        cond = rng.random(4000) < 0.3
        out = np.where(cond, rng.random(4000) < 0.60, rng.random(4000) < 0.20)
        r = conditional_lift(cond, out)
        assert r.difference > 0.3
        assert r.separated
        assert r.pvalue < 1e-6

    def test_always_or_never_firing_fails_loud(self) -> None:
        out = np.array([True, False] * 50)
        with pytest.raises(DataError, match="no comparison arm"):
            conditional_lift(np.zeros(100, dtype=bool), out)
        with pytest.raises(DataError, match="no comparison arm"):
            conditional_lift(np.ones(100, dtype=bool), out)


class TestValidMask:
    def test_unresolved_bars_are_excluded_from_both_arms(self) -> None:
        # Bars 80-99 are unresolved. Without the mask they read as outcome=False and drag the rate
        # down; with it they leave the sample entirely.
        cond = np.array([True] * 50 + [False] * 50)
        out = np.array([True] * 40 + [False] * 60)
        valid = np.array([True] * 80 + [False] * 20)
        masked = conditional_lift(cond, out, valid=valid)
        unmasked = conditional_lift(cond, out)
        assert masked.n_condition + masked.n_complement == 80
        assert unmasked.n_condition + unmasked.n_complement == 100
        assert masked.rate_complement == pytest.approx(0.0)
        assert masked.rate_condition == pytest.approx(0.8)

    def test_mask_shape_is_checked(self) -> None:
        with pytest.raises(DataError, match="expected 10"):
            conditional_lift(
                np.array([True, False] * 5), np.array([True, False] * 5), valid=np.ones(9, bool)
            )


class TestOverlapDeflation:
    def test_deflation_widens_the_interval_without_moving_the_point(self) -> None:
        rng = np.random.default_rng(8)
        cond = rng.random(3000) < 0.4
        out = np.where(cond, rng.random(3000) < 0.5, rng.random(3000) < 0.4)

        tight = conditional_lift(cond, out, overlap=1.0)
        loose = conditional_lift(cond, out, overlap=30.0)

        assert loose.difference == pytest.approx(tight.difference, abs=0.02)
        tight_width = tight.interval_difference.upper - tight.interval_difference.lower
        loose_width = loose.interval_difference.upper - loose.interval_difference.lower
        assert loose_width > tight_width * 3.0
        assert loose.n_condition_eff < tight.n_condition_eff
        assert loose.n_condition == tight.n_condition  # nominal counts stay visible

    def test_deflation_can_overturn_a_nominally_significant_result(self) -> None:
        """The whole reason the parameter exists.

        A difference that clears p < 0.05 on 3,000 overlapping daily bars routinely fails once the
        sample is reduced to the ~100 independent windows it actually contains.
        """
        rng = np.random.default_rng(21)
        cond = rng.random(3000) < 0.4
        out = np.where(cond, rng.random(3000) < 0.46, rng.random(3000) < 0.40)
        assert conditional_lift(cond, out, overlap=1.0).pvalue < 0.05
        assert conditional_lift(cond, out, overlap=30.0).pvalue > 0.05

    def test_rejects_overlap_below_one(self) -> None:
        with pytest.raises(DataError, match="overlap must be >= 1"):
            conditional_lift(np.array([True, False]), np.array([True, True]), overlap=0.5)


class TestLiftTableAndFDR:
    def _fixture(self) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        rng = np.random.default_rng(2)
        n = 2000
        conds = {f"c{i}": rng.random(n) < 0.3 for i in range(6)}
        outs = {"o1": rng.random(n) < 0.2, "o2": rng.random(n) < 0.4}
        return conds, outs

    def test_produces_every_cell(self) -> None:
        conds, outs = self._fixture()
        rows = lift_table(conds, outs, family="test")
        assert len(rows) == len(conds) * len(outs)
        assert {r.family for r in rows} == {"test"}

    def test_degenerate_cells_are_skipped_not_fatal(self) -> None:
        conds, outs = self._fixture()
        conds["never"] = np.zeros(2000, dtype=bool)
        rows = lift_table(conds, outs)
        assert len(rows) == (len(conds) - 1) * len(outs)
        with pytest.raises(DataError):
            lift_table(conds, outs, skip_degenerate=False)

    def test_fdr_only_ever_makes_results_less_significant(self) -> None:
        conds, outs = self._fixture()
        rows = apply_fdr(lift_table(conds, outs))
        assert all(r.qvalue >= r.pvalue - 1e-12 for r in rows)
        assert all(r.rejected == (r.qvalue <= 0.05) for r in rows)

    def test_pure_noise_family_survives_almost_nothing(self) -> None:
        conds, outs = self._fixture()  # every condition independent of every outcome
        rows = apply_fdr(lift_table(conds, outs), alpha=0.05)
        assert sum(r.rejected for r in rows) == 0

    def test_empty_inputs_fail_loud(self) -> None:
        with pytest.raises(DataError, match="at least one condition"):
            lift_table({}, {"o": np.array([True, False])})
        with pytest.raises(DataError, match="at least one outcome"):
            lift_table({"c": np.array([True, False])}, {})


class TestTwoProportionPvalue:
    def test_identical_proportions_give_p_of_one(self) -> None:
        assert two_proportion_pvalue(50, 100, 100, 200) == pytest.approx(1.0)

    def test_no_events_in_either_arm_is_no_evidence(self) -> None:
        assert two_proportion_pvalue(0, 100, 0, 100) == 1.0

    def test_large_separation_gives_a_tiny_p(self) -> None:
        assert two_proportion_pvalue(90, 100, 10, 100) < 1e-20

    def test_rejects_empty_arms(self) -> None:
        with pytest.raises(DataError, match="positive trial counts"):
            two_proportion_pvalue(0, 0, 1, 10)


class TestMonotonicTrend:
    def test_rising_staircase_is_positive(self) -> None:
        z = monotonic_trend([0.1, 0.2, 0.3, 0.4], [100] * 4)
        assert z > 3.0

    def test_falling_staircase_is_negative(self) -> None:
        assert monotonic_trend([0.4, 0.3, 0.2, 0.1], [100] * 4) < -3.0

    def test_flat_bins_give_zero(self) -> None:
        assert monotonic_trend([0.25] * 4, [100] * 4) == pytest.approx(0.0)

    def test_one_bright_bin_is_not_a_trend(self) -> None:
        """A single elevated bin surrounded by flat ones must not read as a staircase."""
        spike = monotonic_trend([0.2, 0.9, 0.2, 0.2, 0.2], [100] * 5)
        staircase = monotonic_trend([0.2, 0.3, 0.4, 0.5, 0.6], [100] * 5)
        assert abs(spike) < abs(staircase)

    def test_scales_with_sample_size(self) -> None:
        """z grows like sqrt(n) — which is exactly why bin counts must be deflated for overlap."""
        small = monotonic_trend([0.1, 0.2, 0.3], [10] * 3)
        large = monotonic_trend([0.1, 0.2, 0.3], [1000] * 3)
        assert large == pytest.approx(small * 10.0, rel=0.01)

    def test_rejects_too_few_bins(self) -> None:
        with pytest.raises(DataError, match=">= 3 matching bins"):
            monotonic_trend([0.1, 0.2], [10, 10])
