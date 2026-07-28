"""Triple-barrier labeling against hand-constructed paths, where the answer is known by eye."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation import (
    BarrierResult,
    aggregate_outcomes,
    barrier_outcome,
    excursion_quantiles,
)


def _path(highs: list[float], lows: list[float]) -> tuple[np.ndarray, np.ndarray]:
    return np.array(highs, dtype=float), np.array(lows, dtype=float)


class TestBarrierOutcome:
    def test_target_hit_first(self) -> None:
        hi, lo = _path([101, 102, 111], [99, 98, 105])
        r = barrier_outcome(hi, lo, entry=100.0, stop=90.0, target=110.0)
        assert r.outcome == "target"
        assert r.bars_to_outcome == 3

    def test_stop_hit_first(self) -> None:
        hi, lo = _path([101, 102, 103], [99, 89, 88])
        r = barrier_outcome(hi, lo, entry=100.0, stop=90.0, target=110.0)
        assert r.outcome == "stop"
        assert r.bars_to_outcome == 2

    def test_unresolved_within_horizon(self) -> None:
        hi, lo = _path([101, 102, 103], [99, 98, 97])
        r = barrier_outcome(hi, lo, entry=100.0, stop=90.0, target=110.0)
        assert r.outcome == "unresolved"
        assert r.bars_to_outcome == -1

    def test_same_bar_collision_resolves_to_stop_by_default(self) -> None:
        """OHLC cannot order two touches inside one bar, so the default is pessimistic."""
        hi, lo = _path([115], [85])
        assert barrier_outcome(hi, lo, entry=100.0, stop=90.0, target=110.0).outcome == "stop"

    def test_optimistic_flag_brackets_the_ambiguity(self) -> None:
        hi, lo = _path([115], [85])
        r = barrier_outcome(hi, lo, entry=100.0, stop=90.0, target=110.0, optimistic=True)
        assert r.outcome == "target"

    def test_short_direction_inferred(self) -> None:
        hi, lo = _path([101, 102], [95, 89])
        r = barrier_outcome(hi, lo, entry=100.0, stop=110.0, target=90.0)
        assert not r.is_long
        assert r.outcome == "target"

    def test_excursions_are_signed_fractions_of_entry(self) -> None:
        hi, lo = _path([106, 104], [97, 95])
        r = barrier_outcome(hi, lo, entry=100.0, stop=90.0, target=200.0)
        assert r.mfe == pytest.approx(0.06)
        assert r.mae == pytest.approx(-0.05)

    def test_rejects_wrong_sided_stop(self) -> None:
        hi, lo = _path([101], [99])
        with pytest.raises(DataError):
            barrier_outcome(hi, lo, entry=100.0, stop=110.0, target=120.0)

    def test_rejects_empty_path(self) -> None:
        with pytest.raises(DataError):
            barrier_outcome(np.array([]), np.array([]), entry=100.0, stop=90.0, target=110.0)


class TestAggregate:
    def _mixed(self) -> list[BarrierResult]:
        out = []
        for hs, ls in (
            ([101, 111], [99, 105]),  # target
            ([101, 102], [99, 89]),  # stop
            ([101, 102], [99, 98]),  # unresolved
        ):
            out.append(
                barrier_outcome(
                    np.array(hs, float),
                    np.array(ls, float),
                    entry=100.0,
                    stop=90.0,
                    target=110.0,
                )
            )
        return out

    def test_counts_and_breakeven(self) -> None:
        c = aggregate_outcomes(self._mixed())
        assert (c.target_first, c.stop_first, c.unresolved, c.n) == (1, 1, 1, 3)
        assert c.reward_risk == pytest.approx(1.0)
        assert c.breakeven_rate == pytest.approx(0.5)

    def test_expectancy_scores_unresolved_flat(self) -> None:
        c = aggregate_outcomes(self._mixed())
        assert c.expectancy_r == pytest.approx((1 * 1.0 - 1) / 3)

    def test_breakeven_tracks_reward_risk(self) -> None:
        hi, lo = _path([101, 102], [99, 98])
        r = barrier_outcome(hi, lo, entry=100.0, stop=99.0, target=129.0)
        c = aggregate_outcomes([r])
        assert c.reward_risk == pytest.approx(29.0)
        assert c.breakeven_rate == pytest.approx(1 / 30)

    def test_excursion_quantiles_shape(self) -> None:
        q = excursion_quantiles(self._mixed(), quantiles=(0.5,))
        assert set(q) == {"mfe", "mae"}
        assert 0.5 in q["mfe"]

    def test_rejects_empty(self) -> None:
        with pytest.raises(DataError):
            aggregate_outcomes([])
