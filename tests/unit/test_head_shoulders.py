"""Head & shoulders / Quasimodo detection, verified against injected ground truth.

The detector must recover all five anchors of a pattern injected at known bars, must distinguish a
Quasimodo from a plain head-and-shoulders by the presence of a break of structure, and must behave
identically under mirroring. Mirror-symmetry is the sharpest available check on a directional
detector: a bearish series is a bullish one turned upside down, so any asymmetry in the results is a
bug in the sign handling rather than a property of markets.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    HSConfig,
    HSEvent,
    break_of_structure,
    detect_head_shoulders,
    extreme_between,
    find_swings,
    geometric_brownian_series,
    inject_head_shoulders,
    last_pivot_before,
    swing_sequence,
)

BASE = HSConfig(
    lookback=5,
    head_prominence=0.03,
    shoulder_tol=0.6,
    time_symmetry_tol=0.25,
    max_neckline_slope=0.25,
    gap_min=20,
    gap_max=250,
)


def _cfg(**kw: object) -> HSConfig:
    return HSConfig(**{**BASE.__dict__, **kw})


def _anchors(e: HSEvent) -> tuple[int, int, int, int, int]:
    return (e.ls_index, e.n1_index, e.head_index, e.n2_index, e.rs_index)


class TestExactRecovery:
    @pytest.mark.parametrize("direction", ["bullish", "bearish"])
    @pytest.mark.parametrize("bars_at", [(80, 220, 360), (60, 180, 300), (100, 250, 400)])
    @pytest.mark.parametrize("seed", [1, 7])
    def test_recovers_all_five_anchors(
        self, direction: str, bars_at: tuple[int, int, int], seed: int
    ) -> None:
        bars, inj = inject_head_shoulders(
            n_bars=520, direction=direction, anchor_bars=bars_at, noise=0.001, seed=seed
        )
        events = detect_head_shoulders(bars, _cfg(direction=direction))
        assert [_anchors(e) for e in events] == [
            (inj["ls"], inj["n1"], inj["head"], inj["n2"], inj["rs"])
        ]

    def test_head_depth_matches_injection(self) -> None:
        bars, _ = inject_head_shoulders(n_bars=520, head_depth=0.10, noise=0.001)
        assert detect_head_shoulders(bars, _cfg())[0].head_depth == pytest.approx(0.10, abs=0.01)

    def test_symmetric_injection_has_near_zero_asymmetry(self) -> None:
        bars, _ = inject_head_shoulders(n_bars=520, shoulder_tilt=0.0, noise=0.001)
        ev = detect_head_shoulders(bars, _cfg())[0]
        assert ev.shoulder_asymmetry < 0.05
        assert ev.time_asymmetry == pytest.approx(1.0, abs=0.05)

    def test_one_event_per_head(self) -> None:
        bars = geometric_brownian_series(3000, vol_per_bar=0.02, seed=4)
        events = detect_head_shoulders(bars, _cfg())
        heads = [e.head_index for e in events]
        assert len(heads) == len(set(heads))


class TestBreakOfStructure:
    """The single feature separating a Quasimodo from a plain head-and-shoulders."""

    @pytest.mark.parametrize("direction", ["bullish", "bearish"])
    def test_no_overshoot_gives_no_bos(self, direction: str) -> None:
        bars, _ = inject_head_shoulders(
            n_bars=520, direction=direction, bos_overshoot=0.0, noise=0.001
        )
        ev = detect_head_shoulders(bars, _cfg(direction=direction))[0]
        assert not ev.has_bos
        assert ev.bos_index == -1
        assert ev.variant == (
            "inverse_head_shoulders" if direction == "bullish" else "head_shoulders"
        )

    @pytest.mark.parametrize("direction", ["bullish", "bearish"])
    def test_overshoot_produces_a_quasimodo(self, direction: str) -> None:
        bars, _ = inject_head_shoulders(
            n_bars=520, direction=direction, bos_overshoot=0.08, noise=0.001
        )
        ev = detect_head_shoulders(bars, _cfg(direction=direction))[0]
        assert ev.has_bos
        assert ev.is_quasimodo
        assert ev.variant.endswith("quasimodo")

    def test_bos_occurs_after_the_head_and_before_the_right_shoulder(self) -> None:
        bars, inj = inject_head_shoulders(n_bars=520, bos_overshoot=0.08, noise=0.001)
        ev = detect_head_shoulders(bars, _cfg())[0]
        assert inj["head"] < ev.bos_index < ev.rs_index

    @pytest.mark.parametrize("overshoot", [0.0, 0.08])
    def test_require_bos_filters_the_population(self, overshoot: float) -> None:
        bars, _ = inject_head_shoulders(n_bars=520, bos_overshoot=overshoot, noise=0.001)
        found = len(detect_head_shoulders(bars, _cfg(require_bos=True)))
        assert found == (1 if overshoot > 0 else 0)


class TestShapeConstraints:
    def test_insufficient_head_prominence_rejects(self) -> None:
        bars, _ = inject_head_shoulders(n_bars=520, head_depth=0.04, noise=0.001)
        assert detect_head_shoulders(bars, _cfg(head_prominence=0.20)) == []

    def test_shoulder_asymmetry_limit_rejects_a_tilted_shoulder(self) -> None:
        bars, _ = inject_head_shoulders(n_bars=520, shoulder_tilt=0.09, noise=0.001)
        assert detect_head_shoulders(bars, _cfg(shoulder_tol=0.05)) == []

    def test_time_symmetry_limit_rejects_a_lopsided_pattern(self) -> None:
        bars, _ = inject_head_shoulders(n_bars=620, anchor_bars=(60, 100, 500), noise=0.001)
        assert detect_head_shoulders(bars, _cfg(time_symmetry_tol=0.9)) == []

    def test_gap_max_rejects_an_overlong_pattern(self) -> None:
        bars, _ = inject_head_shoulders(n_bars=620, anchor_bars=(60, 260, 460), noise=0.001)
        assert detect_head_shoulders(bars, _cfg(gap_max=100)) == []

    @pytest.mark.parametrize(
        ("rule", "expected"), [("any", 1), ("higher", 1), ("lower", 0), ("within_tol", 0)]
    )
    def test_shoulder_rule_discriminates_an_ascending_right_shoulder(
        self, rule: str, expected: int
    ) -> None:
        """The user's own chart shape: right shoulder above the left."""
        bars, _ = inject_head_shoulders(n_bars=520, shoulder_tilt=0.05, noise=0.001)
        found = detect_head_shoulders(bars, _cfg(shoulder_tol=1.5, shoulder_rule=rule))
        assert len(found) == expected


class TestMirrorSymmetry:
    def test_bullish_and_bearish_recover_the_same_anchor_bars(self) -> None:
        up, inj_up = inject_head_shoulders(
            n_bars=520, direction="bullish", anchor_bars=(80, 220, 360), noise=0.001, seed=3
        )
        dn, inj_dn = inject_head_shoulders(
            n_bars=520, direction="bearish", anchor_bars=(80, 220, 360), noise=0.001, seed=3
        )
        assert inj_up == inj_dn
        a_up = _anchors(detect_head_shoulders(up, _cfg(direction="bullish"))[0])
        a_dn = _anchors(detect_head_shoulders(dn, _cfg(direction="bearish"))[0])
        assert a_up == a_dn

    def test_target_sits_beyond_the_neckline_in_the_trade_direction(self) -> None:
        up, _ = inject_head_shoulders(n_bars=520, direction="bullish", noise=0.001)
        dn, _ = inject_head_shoulders(n_bars=520, direction="bearish", noise=0.001)
        e_up = detect_head_shoulders(up, _cfg(direction="bullish"))[0]
        e_dn = detect_head_shoulders(dn, _cfg(direction="bearish"))[0]
        assert e_up.target_measured > e_up.n1_price
        assert e_dn.target_measured < e_dn.n1_price

    def test_stops_sit_beyond_head_and_shoulder_correctly(self) -> None:
        up, _ = inject_head_shoulders(n_bars=520, direction="bullish", noise=0.001)
        e = detect_head_shoulders(up, _cfg(direction="bullish"))[0]
        assert e.stop_head == e.head_price
        assert e.stop_rs == e.rs_price
        assert e.stop_head < e.stop_rs  # head is deeper than the right shoulder on a bottom


class TestMeasuredMove:
    def test_measured_move_is_neckline_plus_head_distance(self) -> None:
        bars, _ = inject_head_shoulders(n_bars=520, noise=0.001)
        e = detect_head_shoulders(bars, _cfg())[0]
        reference = e.neckline_at_break if np.isfinite(e.neckline_at_break) else e.n1_price
        assert e.target_measured == pytest.approx(reference + (reference - e.head_price), rel=1e-9)

    def test_reward_risk_is_computable_and_positive(self) -> None:
        bars, _ = inject_head_shoulders(n_bars=520, noise=0.001)
        e = detect_head_shoulders(bars, _cfg())[0]
        assert e.reward_risk(entry=e.n1_price, stop=e.head_price) > 0.0

    def test_reward_risk_rejects_a_zero_risk_leg(self) -> None:
        bars, _ = inject_head_shoulders(n_bars=520, noise=0.001)
        e = detect_head_shoulders(bars, _cfg())[0]
        with pytest.raises(DataError):
            e.reward_risk(entry=1.0, stop=1.0)


class TestNullCalibration:
    def test_detector_has_a_measurable_false_positive_rate_on_noise(self) -> None:
        counts = [
            len(
                detect_head_shoulders(
                    geometric_brownian_series(1500, vol_per_bar=0.02, seed=s), _cfg()
                )
            )
            for s in range(8)
        ]
        assert all(c >= 0 for c in counts)

    def test_stricter_prominence_lowers_the_base_rate(self) -> None:
        def rate(prom: float) -> float:
            return float(
                np.mean(
                    [
                        len(
                            detect_head_shoulders(
                                geometric_brownian_series(1500, vol_per_bar=0.02, seed=s),
                                _cfg(head_prominence=prom),
                            )
                        )
                        for s in range(6)
                    ]
                )
            )

        assert rate(0.15) <= rate(0.02)


class TestConfigValidation:
    @pytest.mark.parametrize(
        "kw",
        [
            {"direction": "sideways"},
            {"lookback": 0},
            {"head_prominence": 0.0},
            {"shoulder_tol": 0.0},
            {"time_symmetry_tol": 1.5},
            {"max_neckline_slope": -0.1},
            {"gap_min": 0},
            {"gap_min": 300, "gap_max": 10},
        ],
    )
    def test_rejects_bad_parameters(self, kw: dict[str, object]) -> None:
        with pytest.raises(DataError):
            _cfg(**kw)

    def test_anchor_and_neckline_kinds_are_opposite(self) -> None:
        assert HSConfig(direction="bullish").anchor_kind == "low"
        assert HSConfig(direction="bullish").neckline_kind == "high"
        assert HSConfig(direction="bearish").anchor_kind == "high"
        assert HSConfig(direction="bearish").neckline_kind == "low"

    def test_label_encodes_the_variant(self) -> None:
        assert "bos" in _cfg(require_bos=True).label
        assert "bos" not in _cfg(require_bos=False).label


class TestStructurePrimitives:
    def test_swing_sequence_strictly_alternates(self) -> None:
        bars = geometric_brownian_series(2000, vol_per_bar=0.02, seed=5)
        seq = swing_sequence(bars, lookback=5)
        assert seq
        assert all(a.kind != b.kind for a, b in zip(seq, seq[1:], strict=False))
        assert [s.index for s in seq] == sorted(s.index for s in seq)

    def test_swing_sequence_rejects_bad_lookback(self) -> None:
        bars = geometric_brownian_series(200, seed=1)
        with pytest.raises(DataError):
            swing_sequence(bars, lookback=0)

    def test_break_of_structure_finds_the_first_close_beyond(self) -> None:
        bars = geometric_brownian_series(500, vol_per_bar=0.02, drift_per_bar=0.004, seed=2)
        level = float(bars.close[50])
        b = break_of_structure(bars, level=level, level_index=50, search_from=51, upward=True)
        assert b.occurred
        assert bars.close[b.index] > level
        assert not np.any(bars.close[51 : b.index] > level)

    def test_break_of_structure_respects_the_search_window(self) -> None:
        bars = geometric_brownian_series(500, vol_per_bar=0.02, drift_per_bar=0.004, seed=2)
        level = float(np.max(bars.close)) * 2.0
        assert not break_of_structure(
            bars, level=level, level_index=0, search_from=1, upward=True
        ).occurred

    def test_break_of_structure_rejects_bad_input(self) -> None:
        bars = geometric_brownian_series(200, seed=1)
        with pytest.raises(DataError):
            break_of_structure(bars, level=1.0, level_index=0, search_from=-1, upward=True)
        with pytest.raises(DataError):
            break_of_structure(bars, level=float("nan"), level_index=0, search_from=1, upward=True)

    def test_extreme_between_picks_the_right_extreme(self) -> None:
        bars = geometric_brownian_series(1000, vol_per_bar=0.02, seed=6)
        seq = find_swings(bars, lookback=5, kind="high")
        top = extreme_between(seq, 100, 500, "high")
        assert top is not None
        inside = [s.price for s in seq if 100 < s.index < 500]
        assert top.price == max(inside)

    def test_extreme_between_returns_none_when_empty(self) -> None:
        bars = geometric_brownian_series(1000, vol_per_bar=0.02, seed=6)
        seq = find_swings(bars, lookback=5, kind="high")
        assert extreme_between(seq, 10, 11, "high") is None

    def test_last_pivot_before_respects_knowledge_cutoff(self) -> None:
        bars = geometric_brownian_series(1000, vol_per_bar=0.02, seed=6)
        seq = find_swings(bars, lookback=5, kind="low")
        p = last_pivot_before(seq, 500, "low", known_by=400)
        assert p is not None
        assert p.confirmed_index <= 400
        assert p.index < 500
