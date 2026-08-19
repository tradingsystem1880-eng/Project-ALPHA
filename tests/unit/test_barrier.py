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


class TestBarrierFailsLoud:
    """A rejected setup is a study that would otherwise produce a confident wrong number."""

    @pytest.mark.parametrize(
        ("highs", "lows", "message"),
        [
            ([[1.0]], [[1.0]], "1-D highs/lows"),
            ([101.0, 102.0], [99.0], "matching highs/lows"),
            ([], [], "at least one forward bar"),
            ([101.0, float("nan")], [99.0, 98.0], "finite highs/lows"),
            ([101.0, 97.0], [99.0, 98.0], "high is below its low"),
        ],
    )
    def test_rejects_a_malformed_path(
        self, highs: list[object], lows: list[object], message: str
    ) -> None:
        with pytest.raises(DataError, match=message):
            barrier_outcome(highs, lows, entry=100.0, stop=90.0, target=110.0)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("entry", "stop", "target", "message"),
        [
            (100.0, 90.0, float("inf"), "finite entry/stop/target"),
            (0.0, -10.0, 10.0, "positive entry price"),
            (100.0, 90.0, 100.0, "differ from entry"),
            (100.0, 100.0, 110.0, "differ from entry"),
            (100.0, 110.0, 120.0, "long setup needs stop < entry"),
            (100.0, 90.0, 80.0, "short setup needs stop > entry"),
        ],
    )
    def test_rejects_an_incoherent_setup(
        self, entry: float, stop: float, target: float, message: str
    ) -> None:
        hi, lo = _path([101, 102], [99, 98])
        with pytest.raises(DataError, match=message):
            barrier_outcome(hi, lo, entry=entry, stop=stop, target=target)

    def test_aggregate_and_quantiles_reject_an_empty_or_degenerate_family(self) -> None:
        with pytest.raises(DataError, match="at least one result"):
            aggregate_outcomes([])
        with pytest.raises(DataError, match="at least one result"):
            excursion_quantiles([])

        hi, lo = _path([101, 111], [99, 105])
        result = barrier_outcome(hi, lo, entry=100.0, stop=90.0, target=110.0)
        with pytest.raises(DataError, match=r"quantiles must lie in \[0, 1\]"):
            excursion_quantiles([result], quantiles=(0.5, 1.5))

    def test_a_zero_risk_leg_is_refused_rather_than_dividing_by_zero(self) -> None:
        degenerate = BarrierResult(
            outcome="target",
            bars_to_outcome=1,
            mfe=0.1,
            mae=0.0,
            entry=100.0,
            stop=100.0,
            target=110.0,
            is_long=True,
        )
        with pytest.raises(DataError, match="non-zero risk leg"):
            aggregate_outcomes([degenerate])


class TestBarrierCountsOnAnEmptyFamily:
    def test_rates_are_zero_not_undefined(self) -> None:
        from alpha_validation.barrier import BarrierCounts

        empty = BarrierCounts(
            target_first=0,
            stop_first=0,
            unresolved=0,
            n=0,
            breakeven_rate=0.5,
            reward_risk=1.0,
        )
        assert empty.target_rate == 0.0
        assert empty.expectancy_r == 0.0
