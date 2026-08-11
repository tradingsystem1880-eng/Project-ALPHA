"""Wedge detection against injected ground truth, plus its false-positive rate on noise.

The generator in ``alpha_patterns.synthetic`` builds its boundaries in log space — the same space
:class:`~alpha_patterns.wedge.WedgeConfig` fits in by default — so a correct detector recovers the
injected anchors *exactly* and lands the apex on the generated bar rather than near it. That
exactness is what makes these assertions worth writing: "found something wedge-shaped" would pass
for a detector that was substantially wrong.

The noise test is the other half. Converging trendlines are trivially common in random data, and a
detector's own false-positive rate is the base rate every real-data count has to be read against.
It is asserted as a band rather than a maximum, because a detector that found *nothing* in noise
would be one whose thresholds had quietly become impossible to satisfy.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    WedgeConfig,
    detect_wedges,
    geometric_brownian_series,
    inject_wedge,
    wedge_lines,
    wedge_panel,
)


class TestExactRecovery:
    @pytest.mark.parametrize(
        ("kind", "break_direction"),
        [("falling", 1), ("rising", -1), ("symmetrical", 1), ("falling", -1)],
    )
    def test_recovers_injected_anchors_and_apex(self, kind: str, break_direction: int) -> None:
        bars, truth = inject_wedge(kind=kind, break_direction=break_direction)
        wedges = detect_wedges(bars, WedgeConfig())
        assert wedges, f"no {kind} wedge detected in a series built to contain one"

        highs, lows = truth.highs, truth.lows
        # The formation completed by the last injected pivot: its anchors are the final two of each
        # kind, and its apex is the bar the generator converged on.
        complete = [
            w
            for w in wedges
            if w.upper_indices == (highs[-2], highs[-1]) and w.lower_indices == (lows[-2], lows[-1])
        ]
        assert complete, (
            f"expected a wedge anchored on highs {highs[-2:]} and lows {lows[-2:]}; "
            f"got {[(w.upper_indices, w.lower_indices) for w in wedges]}"
        )
        w = complete[0]
        assert w.kind == kind
        assert w.apex_index == pytest.approx(float(truth.apex), abs=0.5)

    def test_classifies_all_three_shapes(self) -> None:
        seen: set[str] = set()
        for kind in ("falling", "rising", "symmetrical"):
            bars, _ = inject_wedge(kind=kind)
            seen.update(w.kind for w in detect_wedges(bars, WedgeConfig()))
        assert seen == {"falling", "rising", "symmetrical"}

    def test_finds_the_injected_break_with_the_right_direction(self) -> None:
        for direction in (1, -1):
            bars, truth = inject_wedge(kind="falling", break_direction=direction)
            wedges = [w for w in detect_wedges(bars, WedgeConfig()) if w.break_index >= 0]
            assert wedges
            first = min(wedges, key=lambda w: w.break_index)
            assert first.break_direction == direction
            assert first.break_index == pytest.approx(truth.break_bar, abs=3)

    def test_confirmation_never_precedes_the_final_anchor(self) -> None:
        bars, _ = inject_wedge()
        for w in detect_wedges(bars, WedgeConfig()):
            assert w.confirmed_index >= w.end_index
            assert w.apex_index >= w.end_index


class TestValidityRules:
    def test_rejects_diverging_lines(self) -> None:
        # A broadening formation: the generator's own boundaries run backwards in time.
        bars, _ = inject_wedge(kind="falling")
        reversed_bars = type(bars)(
            ts=bars.ts,
            open=bars.open[::-1].copy(),
            high=bars.high[::-1].copy(),
            low=bars.low[::-1].copy(),
            close=bars.close[::-1].copy(),
            volume=bars.volume[::-1].copy(),
            symbol="REVERSED",
        )
        # Whatever it finds, nothing may be a *diverging* pair: the gap slope is negative by
        # construction in every emitted Wedge.
        for w in detect_wedges(reversed_bars, WedgeConfig()):
            assert w.width_confirm <= w.width_start

    def test_convergence_floor_is_enforced(self) -> None:
        bars, _ = inject_wedge()
        strict = detect_wedges(bars, WedgeConfig(min_convergence=0.9))
        loose = detect_wedges(bars, WedgeConfig(min_convergence=0.05))
        assert len(strict) <= len(loose)
        assert all(w.convergence >= 0.9 for w in strict)

    def test_apex_horizon_is_enforced(self) -> None:
        bars, _ = inject_wedge()
        for w in detect_wedges(bars, WedgeConfig(max_apex_bars=40)):
            assert w.apex_index - w.end_index <= 40

    def test_config_rejects_nonsense(self) -> None:
        with pytest.raises(DataError, match="min_convergence"):
            WedgeConfig(min_convergence=1.5)
        with pytest.raises(DataError, match="max_span"):
            WedgeConfig(min_span=100, max_span=50)


class TestNoiseBaseRate:
    def test_fires_on_noise_at_a_measured_rate(self) -> None:
        """Converging lines are common in random walks — the count is the detector's own base rate.

        Asserted as a band. Too high would mean the detector reports noise as structure; zero would
        mean the thresholds had become unsatisfiable, which is the failure mode that makes a real
        study silently report "no events found".
        """
        total = sum(
            len(detect_wedges(geometric_brownian_series(1500, seed=s, vol_per_bar=0.012)))
            for s in range(8)
        )
        per_1000 = total / (8 * 1500) * 1000
        assert 2.0 < per_1000 < 80.0, f"{per_1000:.1f} wedges per 1000 noise bars"


class TestPanelProjection:
    def test_apex_distance_advances_one_bar_at_a_time_within_a_formation(self) -> None:
        bars, _ = inject_wedge()
        panel = wedge_panel(bars, detect_wedges(bars, WedgeConfig()))
        assert panel.active.shape == (len(bars),)
        assert panel.active.any()

        # Where several wedges overlap the most recently confirmed one wins, so the apex distance
        # jumps at a handover. Within one formation — identified by its own convergence value — the
        # distance must advance by exactly one bar per bar.
        same_wedge = (
            panel.active[:-1] & panel.active[1:] & (panel.convergence[:-1] == panel.convergence[1:])
        )
        steps = np.diff(panel.bars_past_apex)[same_wedge]
        assert steps.size > 0
        assert np.all(steps == 1)

    def test_inactive_bars_carry_no_width(self) -> None:
        bars, _ = inject_wedge()
        panel = wedge_panel(bars, detect_wedges(bars, WedgeConfig()))
        assert np.all(np.isnan(panel.width[~panel.active]))
        assert np.all(np.isfinite(panel.width[panel.active]))

    def test_lines_bracket_the_closes_inside_the_formation(self) -> None:
        bars, _ = inject_wedge()
        for w in detect_wedges(bars, WedgeConfig()):
            upper, lower = wedge_lines(w, len(bars))
            seg = slice(w.start_index, w.end_index + 1)
            assert np.all(bars.close[seg] <= upper[seg] + 1e-9)
            assert np.all(bars.close[seg] >= lower[seg] - 1e-9)
