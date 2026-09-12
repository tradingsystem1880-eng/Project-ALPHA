"""Directional-change extremes: recovered on a synthetic zigzag, knowable only after the retrace,
and byte-for-byte equal to the pinned upstream implementation on the shared fixture series.

The rolling-window equivalence class pins the provenance doc's "not ported" entry: upstream
``rw_extremes(order=k)`` is ``find_swings(lookback=k)`` with ``confirmed_index = index + k``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    OHLCV,
    DCExtreme,
    dc_known_by,
    directional_change,
    find_swings,
    geometric_brownian_series,
)
from alpha_patterns.swings import SwingKind

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


def _fixture_bars(spec: dict[str, Any]) -> OHLCV:
    return geometric_brownian_series(
        int(spec["n_bars"]),
        vol_per_bar=float(spec["vol_per_bar"]),
        seed=int(spec["seed"]),
        start=float(spec["start"]),
    )


def _flat_bars(closes: list[float]) -> OHLCV:
    c = np.asarray(closes, dtype=np.float64)
    return OHLCV(np.arange(c.size, dtype=np.float64), c, c, c, c, np.ones(c.size))


class TestZigzagRecovery:
    # Up 2% a bar for five bars, down 2% for five, repeat: extremes at 5, 10, 15, ...
    CLOSES = [1.02**k for k in range(6)] + [(1.02**5) * (0.98**k) for k in range(1, 6)]

    def test_top_then_bottom_with_confirmation_lag(self) -> None:
        closes = self.CLOSES + [self.CLOSES[-1] * (1.02**k) for k in range(1, 6)]
        events = directional_change(_flat_bars(closes), sigma=0.05)
        assert [e.kind for e in events] == ["high", "low"]
        top, bottom = events
        assert top.index == 5 and top.price == pytest.approx(1.02**5)
        # first bar whose close is 5% below the top: 0.98**k < 0.95 -> k = 3 -> bar 8
        assert top.confirmed_index == 8
        assert bottom.index == 10 and bottom.confirmed_index == 13

    def test_confirmation_never_precedes_extreme(self) -> None:
        bars = geometric_brownian_series(600, vol_per_bar=0.02, seed=3)
        for e in directional_change(bars, sigma=0.03):
            assert e.confirmed_index > e.index

    def test_kinds_alternate(self) -> None:
        bars = geometric_brownian_series(600, vol_per_bar=0.02, seed=5)
        kinds = [e.kind for e in directional_change(bars, sigma=0.02)]
        assert len(kinds) > 10
        assert all(a != b for a, b in zip(kinds, kinds[1:], strict=False))

    def test_no_retrace_no_events(self) -> None:
        assert directional_change(_flat_bars([1.0, 1.01, 1.02, 1.03]), sigma=0.05) == []

    @pytest.mark.parametrize("sigma", [0.0, 1.0, -0.1, 1.5])
    def test_sigma_must_be_a_fraction(self, sigma: float) -> None:
        with pytest.raises(DataError, match="sigma"):
            directional_change(_flat_bars([1.0, 1.1, 1.0]), sigma=sigma)


class TestKnownBy:
    def test_filters_on_confirmation_not_extreme(self) -> None:
        events = [DCExtreme(5, 8, 1.1, "high"), DCExtreme(10, 13, 0.9, "low")]
        assert dc_known_by(events, 7) == []
        assert dc_known_by(events, 8) == events[:1]
        assert dc_known_by(events, 13) == events


class TestUpstreamParity:
    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "directional_change.json").read_text())
        bars = _fixture_bars(fx["series"])
        for case in fx["cases"]:
            events = directional_change(bars, sigma=float(case["sigma"]))
            tops = [[e.confirmed_index, e.index, e.price] for e in events if e.kind == "high"]
            bottoms = [[e.confirmed_index, e.index, e.price] for e in events if e.kind == "low"]
            assert [t[:2] for t in tops] == [t[:2] for t in case["tops"]]
            assert [b[:2] for b in bottoms] == [b[:2] for b in case["bottoms"]]
            for ours, theirs in ((tops, case["tops"]), (bottoms, case["bottoms"])):
                np.testing.assert_allclose([o[2] for o in ours], [x[2] for x in theirs], rtol=1e-12)


class TestRollingWindowEquivalence:
    """Upstream ``rw_extremes`` is not ported; ``find_swings`` already is that detector."""

    def test_find_swings_reproduces_rw_extremes(self) -> None:
        fx = json.loads((FIXTURES / "rolling_window.json").read_text())
        close = _fixture_bars(fx["series"]).close
        bars = _flat_bars(list(close))
        for case in fx["cases"]:
            order = int(case["order"])
            kinds: list[tuple[SwingKind, str]] = [("high", "tops"), ("low", "bottoms")]
            for kind, key in kinds:
                swings = find_swings(bars, lookback=order, kind=kind)
                # upstream starts scanning at curr_index = 2*order + 1, so it can never report
                # an extreme at index <= order; ALPHA can. Compare on the shared domain.
                ours = {s.index: s.confirmed_index for s in swings if s.index > order}
                theirs = {int(i): int(c) for c, i, _ in case[key] if int(i) > order}
                assert ours == theirs
