"""Future-poison guard for harmonic patterns: patterns whose D bar printed by ``CUT`` and the
position series up to ``CUT`` cannot change when every later bar is replaced."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    OHLCV,
    detect_harmonics,
    directional_change,
    geometric_brownian_series,
    harmonics_known_by,
)

pytestmark = pytest.mark.bias_guard

CUT = 1500


def _series(seed: int = 7, n: int = 3000) -> OHLCV:
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


def test_patterns_and_signal_known_by_cut_are_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    a = detect_harmonics(clean, directional_change(clean, sigma=0.02), error_threshold=0.5)
    b = detect_harmonics(dirty, directional_change(dirty, sigma=0.02), error_threshold=0.5)
    assert harmonics_known_by(a.patterns, CUT) == harmonics_known_by(b.patterns, CUT)
    assert len(harmonics_known_by(a.patterns, CUT)) > 10
    np.testing.assert_array_equal(a.signal[: CUT + 1], b.signal[: CUT + 1])
