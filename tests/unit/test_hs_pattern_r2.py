"""``HSEvent.pattern_r2``: an exact piecewise-linear structure scores 1, an injected pattern scores
high, and the value is knowable at the right shoulder (poison after it changes nothing)."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import OHLCV, HSConfig, detect_head_shoulders, inject_head_shoulders
from alpha_patterns.head_shoulders import _pattern_r2

pytestmark = pytest.mark.bias_guard


def test_exact_polyline_scores_one_and_flat_is_nan() -> None:
    close = np.interp(np.arange(50), [0, 10, 25, 35, 49], [1.0, 1.2, 0.8, 1.2, 1.0])
    assert _pattern_r2(close, (0, 10, 25, 35, 49)) == pytest.approx(1.0)
    assert np.isnan(_pattern_r2(np.ones(50), (0, 10, 25, 35, 49)))


def test_injected_pattern_fits_well_and_is_point_in_time() -> None:
    bars, _ = inject_head_shoulders(n_bars=520, head_depth=0.10, noise=0.001)
    cfg = HSConfig(direction="bullish", lookback=5)
    events = detect_head_shoulders(bars, cfg)
    assert events and 0.5 < events[0].pattern_r2 <= 1.0
    ev = events[0]
    cut = ev.confirmed_index
    rng = np.random.default_rng(999)
    tail = len(bars) - cut - 1
    close, open_ = bars.close.copy(), bars.open.copy()
    high, low = bars.high.copy(), bars.low.copy()
    close[cut + 1 :] = bars.close[cut] * (10.0 + rng.random(tail) * 5.0)
    open_[cut + 1 :] = np.concatenate(([bars.close[cut]], close[cut + 1 : -1]))
    high[cut + 1 :] = np.maximum(open_[cut + 1 :], close[cut + 1 :]) * 1.02
    low[cut + 1 :] = np.minimum(open_[cut + 1 :], close[cut + 1 :]) * 0.98
    dirty = OHLCV(bars.ts, open_, high, low, close, bars.volume, bars.symbol)
    again = [e for e in detect_head_shoulders(dirty, cfg) if e.confirmed_index <= cut]
    assert again and again[0].pattern_r2 == ev.pattern_r2
