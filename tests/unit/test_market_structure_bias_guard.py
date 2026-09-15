"""Future-poison guards for the streaming market-structure detectors: nothing confirmed at or
before ``CUT`` at any level may change when every bar after ``CUT`` is replaced."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    OHLCV,
    atr_directional_change,
    extremes_known_by,
    geometric_brownian_series,
    hierarchical_extremes,
)

pytestmark = pytest.mark.bias_guard

CUT = 700


def _series(seed: int = 7, n: int = 1400) -> OHLCV:
    return geometric_brownian_series(n, seed=seed, vol_per_bar=0.02, start=1.0)


def _poison(bars: OHLCV, cut: int = CUT) -> OHLCV:
    rng = np.random.default_rng(999)
    n = len(bars)
    tail = n - cut - 1
    close, open_ = bars.close.copy(), bars.open.copy()
    high, low, volume = bars.high.copy(), bars.low.copy(), bars.volume.copy()
    close[cut + 1 :] = bars.close[cut] * (10.0 + rng.random(tail) * 5.0)
    open_[cut + 1 :] = np.concatenate(([bars.close[cut]], close[cut + 1 : -1]))
    high[cut + 1 :] = np.maximum(open_[cut + 1 :], close[cut + 1 :]) * 1.02
    low[cut + 1 :] = np.minimum(open_[cut + 1 :], close[cut + 1 :]) * 0.98
    volume[cut + 1 :] *= 50.0
    return OHLCV(bars.ts, open_, high, low, close, volume, bars.symbol)


def test_atr_directional_change_known_by_is_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    a = extremes_known_by(atr_directional_change(clean, atr_lookback=14), CUT)
    b = extremes_known_by(atr_directional_change(dirty, atr_lookback=14), CUT)
    assert a == b and len(a) > 20


def test_hierarchical_levels_known_by_are_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    full_a = hierarchical_extremes(clean, levels=4, atr_lookback=14)
    full_b = hierarchical_extremes(dirty, levels=4, atr_lookback=14)
    for lvl_a, lvl_b in zip(full_a, full_b, strict=True):
        assert extremes_known_by(lvl_a, CUT) == extremes_known_by(lvl_b, CUT)
    assert len(extremes_known_by(full_a[1], CUT)) > 3


def _bars(rows: list[tuple[float, float, float]]) -> OHLCV:
    """``(high, low, close)`` rows; open == close so every bar is range-consistent."""
    h, lo, c = (np.asarray(col, dtype=np.float64) for col in zip(*rows, strict=True))
    return OHLCV(np.arange(c.size, dtype=np.float64), c, h, lo, c, np.ones(c.size))


def test_leaky_twin_keyed_on_extreme_index_would_fail() -> None:
    """The future decides whether a pending base extreme is ever confirmed.

    Bars 6-10 sit just inside one ATR of the bar-5 high, so nothing is confirmed by the cut. If
    the future falls, bar 5 becomes a confirmed high; if it jumps, it never does. Its ``index`` is
    <= cut in both worlds, so an index filter reads the future; ``extremes_known_by`` does not.
    """
    cut = 10
    head = [(c + 0.02, c - 0.02, c) for c in (1.0, 1.02, 1.04, 1.06, 1.08)]
    head += [(1.12, 1.08, 1.10)] * 6  # bar 5 sets the pending high; 6-10 stay within the ATR
    falls = _bars(head + [(1.09, 1.05, 1.07)] * 4)
    jumps = _bars(head + [(2.0 + 0.1 * k, 1.9 + 0.1 * k, 1.95 + 0.1 * k) for k in range(4)])
    by_index = [
        [e for e in atr_directional_change(b, atr_lookback=3) if e.index <= cut]
        for b in (falls, jumps)
    ]
    assert by_index[0] != by_index[1] and by_index[0][0].index == 5
    assert extremes_known_by(
        atr_directional_change(falls, atr_lookback=3), cut
    ) == extremes_known_by(atr_directional_change(jumps, atr_lookback=3), cut)
