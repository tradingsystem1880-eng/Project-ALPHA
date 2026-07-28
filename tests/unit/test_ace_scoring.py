"""Call-scoring arithmetic, on hand-built series where the right answer is known by construction.

The verdict on a trader's record is a sign. A short scored with a long's arithmetic inverts it, and
nothing downstream would catch that — the intervals would be just as tight around the wrong number.
So the direction handling, the pessimistic stop convention and the unresolved-horizon refusal are
each pinned against a series whose forward path was written by hand.

These use synthetic `Series` objects rather than the cached mirrors, so they run in CI where the
market-data cache is gitignored and absent.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.ace_calls.prices import Series, canonical
from research.ace_calls.score import (
    Call,
    Score,
    _excursions,
    _target_first,
    aggregate,
    score_call,
)

_DAY = 86_400_000.0


def _series(
    closes: list[float],
    *,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    tier: str = "ohlcv",
) -> Series:
    c = np.array(closes, dtype=np.float64)
    return Series(
        asset="TEST",
        tier=tier,  # type: ignore[arg-type]
        ts=np.arange(c.size, dtype=np.float64) * _DAY,
        close=c,
        high=c.copy() if highs is None else np.array(highs, dtype=np.float64),
        low=c.copy() if lows is None else np.array(lows, dtype=np.float64),
        source="synthetic",
    )


class TestCanonical:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("XRP", "XRP"),
            ("xrp", "XRP"),
            ("XRPUSDT", "XRP"),
            ("XRP/USDT", "XRP"),
            ("XRP-USD", "XRP"),
            ("  btcusd ", "BTC"),
            ("XBT", "BTC"),
            ("MATIC", "POL"),
        ],
    )
    def test_ticker_normalisation(self, raw: str, expected: str) -> None:
        assert canonical(raw) == expected

    def test_does_not_strip_a_suffix_that_is_the_whole_ticker(self) -> None:
        # "USD" must survive: stripping it would leave an empty string.
        assert canonical("USD") == "USD"


class TestExcursions:
    def test_long_reads_the_high_as_best_and_the_low_as_worst(self) -> None:
        s = _series([100, 101, 102], highs=[100, 110, 105], lows=[100, 95, 90])
        best, worst, end = _excursions(s, 0, 2, sign=1)
        assert best == pytest.approx(0.10)  # high of 110 from a base of 100
        assert worst == pytest.approx(-0.10)  # low of 90
        assert end == pytest.approx(0.02)  # close of 102

    def test_short_inverts_both_ends(self) -> None:
        """The case that would silently invert a verdict. A short profits from the LOW."""
        s = _series([100, 101, 102], highs=[100, 110, 105], lows=[100, 95, 90])
        best, worst, end = _excursions(s, 0, 2, sign=-1)
        assert best == pytest.approx(0.10)  # price fell to 90 => +10% for a short
        assert worst == pytest.approx(-0.10)  # price rose to 110 => -10% for a short
        assert end == pytest.approx(-0.02)  # closed at 102 => -2% for a short

    def test_horizon_truncates_at_the_end_of_the_series(self) -> None:
        s = _series([100, 120, 130])
        best, _, _ = _excursions(s, 0, 99, sign=1)
        assert best == pytest.approx(0.30)

    def test_a_flat_series_produces_zero_excursion(self) -> None:
        s = _series([50.0] * 10)
        assert _excursions(s, 0, 5, sign=1) == pytest.approx((0.0, 0.0, 0.0))


class TestTargetFirst:
    def test_target_reached_before_stop_is_a_win(self) -> None:
        s = _series([100, 105, 112], highs=[100, 106, 112], lows=[100, 104, 108])
        call = Call(
            file="t",
            date="1970-01-01",
            asset="TEST",
            direction="long",
            horizon_days=2,
            target=110.0,
            stop=95.0,
        )
        assert _target_first(s, call, 0, 2) is True

    def test_stop_reached_before_target_is_a_loss(self) -> None:
        s = _series([100, 94, 115], highs=[100, 99, 115], lows=[100, 93, 100])
        call = Call(
            file="t",
            date="1970-01-01",
            asset="TEST",
            direction="long",
            horizon_days=2,
            target=110.0,
            stop=95.0,
        )
        assert _target_first(s, call, 0, 2) is False

    def test_same_bar_collision_resolves_to_the_stop(self) -> None:
        """The pessimistic convention. A bar touching both cannot be known to have hit target
        first, and the adverse assumption is the one that cannot flatter the record."""
        s = _series([100, 100], highs=[100, 115], lows=[100, 90])
        call = Call(
            file="t",
            date="1970-01-01",
            asset="TEST",
            direction="long",
            horizon_days=1,
            target=110.0,
            stop=95.0,
        )
        assert _target_first(s, call, 0, 1) is False

    def test_short_direction_uses_the_mirrored_levels(self) -> None:
        # Short from 100: target 90 below, stop 105 above. Price falls to 89 without touching 105.
        s = _series([100, 92, 89], highs=[100, 96, 93], lows=[100, 91, 89])
        call = Call(
            file="t",
            date="1970-01-01",
            asset="TEST",
            direction="short",
            horizon_days=2,
            target=90.0,
            stop=105.0,
        )
        assert _target_first(s, call, 0, 2) is True

    def test_short_stop_triggers_on_a_rise(self) -> None:
        s = _series([100, 106, 85], highs=[100, 107, 100], lows=[100, 99, 85])
        call = Call(
            file="t",
            date="1970-01-01",
            asset="TEST",
            direction="short",
            horizon_days=2,
            target=90.0,
            stop=105.0,
        )
        assert _target_first(s, call, 0, 2) is False

    def test_neither_touched_inside_the_horizon_is_not_a_win(self) -> None:
        s = _series([100, 101, 102], highs=[100, 102, 103], lows=[100, 99, 100])
        call = Call(
            file="t",
            date="1970-01-01",
            asset="TEST",
            direction="long",
            horizon_days=2,
            target=110.0,
            stop=95.0,
        )
        assert _target_first(s, call, 0, 2) is False

    def test_no_levels_returns_none_not_false(self) -> None:
        """None and False mean different things: 'not a levelled call' vs 'the trade lost'."""
        s = _series([100, 120])
        call = Call(file="t", date="1970-01-01", asset="TEST", direction="long", horizon_days=1)
        assert _target_first(s, call, 0, 1) is None


class TestTrendMask:
    """Regression guard for a bug that made every call silently unscoreable.

    ``trend_state_vwap`` returns a Python ``list[str]``, not an array. Comparing that list against
    one of its own elements yields the scalar ``False``, numpy broadcasts it to an all-False mask,
    and the matched-control step then finds zero eligible bars — so every call came back
    "unresolved: only 0 matched control bars" with no error anywhere. mypy caught it; nothing at
    runtime would have. The fix is one ``np.asarray``, which is exactly the kind of thing that gets
    refactored away later, so it is pinned here.
    """

    def test_list_comparison_is_the_trap(self) -> None:
        states = ["uptrend", "uptrend", "downtrend"]
        # Spelled through `object` so mypy does not reject the very comparison being demonstrated —
        # which is itself the point: the type checker rejects this shape on sight, and did.
        as_object: object = states
        assert (as_object == states[0]) is False  # the bug: a scalar, not an elementwise mask
        mask = np.asarray(states) == np.asarray(states)[0]
        assert mask.tolist() == [True, True, False]  # the fix

    def test_score_call_finds_matched_controls_on_a_real_series(self) -> None:
        """End-to-end: a scoreable call must actually come back scored, with controls drawn."""
        from research.ace_calls.prices import tier_for

        if tier_for("BTC") != "ohlcv":
            pytest.skip("BTC price mirror not present in this environment")
        call = Call(file="t", date="2026-03-01", asset="BTC", direction="long", horizon_days=30)
        got = score_call(call, np.random.default_rng(7))
        assert got.status == "resolved", got.reason
        assert got.control_n >= 20
        assert 0.0 <= got.control_rate <= 1.0


class TestScoreCallRefusals:
    def test_unknown_asset_is_no_data_not_a_crash(self) -> None:
        call = Call(file="t", date="2026-01-01", asset="NOTATICKER", direction="long")
        got = score_call(call, np.random.default_rng(7))
        assert got.status == "no_data"
        assert not got.scoreable
        assert "NOTATICKER" in got.reason

    def test_direction_must_be_long_or_short(self) -> None:
        from alpha_core import DataError

        with pytest.raises(DataError, match="direction must be"):
            _ = Call(file="t", date="2026-01-01", asset="XRP", direction="sideways").sign


class TestAggregate:
    def _score(self, hit: bool, best: float = 0.2) -> Score:
        call = Call(file="t", date="2026-01-01", asset="XRP", direction="long")
        return Score(
            call=call,
            status="resolved",
            tier="ohlcv",
            best=best,
            worst=-0.05,
            end=0.1,
            hit=hit,
            control_rate=0.25,
            control_n=300,
        )

    def test_empty_record_yields_no_verdict_rather_than_a_crash(self) -> None:
        agg = aggregate([])
        assert agg.n_resolved == 0
        assert "Nothing is scoreable" in agg.report()

    def test_all_unresolved_still_reports_the_breakdown(self) -> None:
        call = Call(file="t", date="2026-07-25", asset="XRP", direction="long")
        agg = aggregate([Score(call, "unresolved", "ohlcv", reason="horizon incomplete")])
        assert agg.n_calls == 1
        assert agg.n_resolved == 0
        assert agg.by_status == {"unresolved": 1}

    def test_hit_rate_and_control_difference(self) -> None:
        scores = [self._score(True) for _ in range(6)] + [self._score(False) for _ in range(4)]
        agg = aggregate(scores)
        assert agg.n_resolved == 10
        assert agg.hit_rate == pytest.approx(0.6)
        assert agg.control_rate == pytest.approx(0.25)
        assert agg.difference.point == pytest.approx(0.35, abs=0.01)

    def test_small_sample_warning_fires_below_twenty(self) -> None:
        agg = aggregate([self._score(True) for _ in range(5)])
        assert "cannot establish anything" in agg.report()

    def test_no_warning_once_the_record_is_large_enough(self) -> None:
        agg = aggregate([self._score(i % 2 == 0) for i in range(30)])
        assert "cannot establish anything" not in agg.report()
