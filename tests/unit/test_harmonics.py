"""Harmonic XABCD detection: the ratio error behaves as specified, an ideal bullish Gartley built by
hand is recovered at the bar that prints D with the upstream position rule, invariants hold on
noise, and the scan reproduces the pinned upstream implementation exactly."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    HARMONIC_RATIOS,
    OHLCV,
    DCExtreme,
    detect_harmonics,
    directional_change,
    geometric_brownian_series,
    harmonics_known_by,
    ratio_error,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


def _flat(closes: list[float]) -> OHLCV:
    c = np.asarray(closes, dtype=np.float64)
    return OHLCV(np.arange(c.size, dtype=np.float64), c, c, c, c, np.ones(c.size))


class TestRatioError:
    def test_no_requirement_costs_nothing(self) -> None:
        assert ratio_error(3.0, None) == 0.0

    def test_point_target_is_log_distance(self) -> None:
        assert ratio_error(0.618, 0.618) == pytest.approx(0.0)
        assert ratio_error(1.236, 0.618) == pytest.approx(np.log(2.0))

    def test_range_is_free_inside_and_doubled_outside(self) -> None:
        assert ratio_error(0.5, (0.382, 0.886)) == 0.0
        assert ratio_error(1.0, (0.382, 0.886)) == pytest.approx(
            2.0 * (np.log(1.0) - np.log(0.886))
        )

    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    def test_non_positive_ratio_rejected(self, bad: float) -> None:
        with pytest.raises(DataError, match="finite and positive"):
            ratio_error(bad, 0.618)

    def test_table_has_the_seven_named_patterns(self) -> None:
        assert [p.name for p in HARMONIC_RATIOS] == [
            "Gartley",
            "Bat",
            "Butterfly",
            "Crab",
            "Deep Crab",
            "Cypher",
            "Shark",
        ]


class TestIdealGartley:
    # top0=1.05 -> X=1.00 (bar 2) -> A=1.10 (bar 5) -> B=A-0.618*XA (bar 7) -> C=B+0.5*AB (bar 9)
    # -> D=A-0.786*XA (bar 11); then the D bottom is confirmed on bar 13.
    CLOSES = [
        1.05,
        1.02,
        1.00,
        1.03,
        1.06,
        1.10,
        1.07,
        1.0382,
        1.055,
        1.0691,
        1.045,
        1.0214,
        1.03,
        1.04,
        1.05,
    ]

    def test_recovered_on_the_bar_that_prints_d(self) -> None:
        bars = _flat(self.CLOSES)
        exts = directional_change(bars, sigma=0.01)
        assert [(e.kind, e.index) for e in exts] == [
            ("high", 0),
            ("low", 2),
            ("high", 5),
            ("low", 7),
            ("high", 9),
            ("low", 11),
        ]
        scan = detect_harmonics(bars, exts, error_threshold=0.2)
        assert len(scan.patterns) == 1
        pat = scan.patterns[0]
        assert (pat.name, pat.bullish) == ("Gartley", True)
        assert (pat.x, pat.a, pat.b, pat.c, pat.d) == (2, 5, 7, 9, 11)
        assert pat.confirmed_index == 11 and pat.error < 0.05
        # long from D until the next extreme (the D bottom) is confirmed on bar 13
        assert list(scan.signal) == [0] * 11 + [1, 1, 0, 0]

    def test_ideal_ratios_fit_exactly(self) -> None:
        bars = _flat(self.CLOSES)
        exts = directional_change(bars, sigma=0.01)
        scan = detect_harmonics(bars, exts, error_threshold=1e-9)
        assert [p.name for p in scan.patterns] == ["Gartley"] and scan.patterns[0].error < 1e-9


class TestInvariants:
    def test_noise_patterns_are_ordered_and_signed(self) -> None:
        bars = geometric_brownian_series(3000, vol_per_bar=0.02, seed=7)
        exts = directional_change(bars, sigma=0.02)
        scan = detect_harmonics(bars, exts, error_threshold=0.5)
        assert scan.patterns
        for p in scan.patterns:
            assert p.x < p.a < p.b < p.c < p.d == p.confirmed_index
            assert 0.0 <= p.error <= 0.5
            assert scan.signal[p.d] == (1 if p.bullish else -1)

    def test_known_by_filters_on_d(self) -> None:
        bars = geometric_brownian_series(3000, vol_per_bar=0.02, seed=7)
        scan = detect_harmonics(bars, directional_change(bars, sigma=0.02), error_threshold=0.5)
        mid = scan.patterns[len(scan.patterns) // 2].d
        assert harmonics_known_by(scan.patterns, mid) == [p for p in scan.patterns if p.d <= mid]

    def test_guards(self) -> None:
        bars = geometric_brownian_series(100, seed=1)
        with pytest.raises(DataError, match="error_threshold"):
            detect_harmonics(bars, [], error_threshold=0.0)
        assert detect_harmonics(bars, [DCExtreme(3, 5, 1.0, "high")]).patterns == []
        with pytest.raises(DataError, match="confirmation order"):
            detect_harmonics(bars, [DCExtreme(3, 9, 1.0, "high"), DCExtreme(6, 8, 0.9, "low")])


class TestUpstreamParity:
    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "harmonics.json").read_text())
        s = fx["series"]
        bars = geometric_brownian_series(
            int(s["n_bars"]),
            vol_per_bar=float(s["vol_per_bar"]),
            seed=int(s["seed"]),
            start=float(s["start"]),
        )
        exts = directional_change(bars, sigma=float(fx["sigma"]))
        scan = detect_harmonics(bars, exts, error_threshold=float(fx["error_threshold"]))
        ours = sorted(
            [(p.name, p.bullish, p.x, p.a, p.b, p.c, p.d) for p in scan.patterns],
            key=lambda r: r[6],
        )
        theirs = [
            (p["name"], p["bull"], p["X"], p["A"], p["B"], p["C"], p["D"]) for p in fx["patterns"]
        ]
        assert ours == theirs
        np.testing.assert_allclose(
            [p.error for p in sorted(scan.patterns, key=lambda p: p.d)],
            [p["error"] for p in fx["patterns"]],
            rtol=1e-12,
        )
        assert list(scan.signal) == fx["signal"]
