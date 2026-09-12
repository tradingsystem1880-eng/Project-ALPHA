"""Future-poison guards for window trendline breakouts and their meta-label trades: a value or a
settled trade at or before ``CUT`` cannot change when every later bar is replaced, and a twin that
fits on a window including the decision bar is shown to leak."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    OHLCV,
    breakout_features,
    fit_trendlines_single,
    geometric_brownian_series,
    trendline_breakout,
)

pytestmark = pytest.mark.bias_guard

CUT = 300


def _series(seed: int = 7, n: int = 600) -> OHLCV:
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


def test_breakout_series_is_immune_before_the_cut() -> None:
    clean, dirty = _series(), _poison(_series())
    a = trendline_breakout(np.log(clean.close), lookback=30)
    b = trendline_breakout(np.log(dirty.close), lookback=30)
    k = CUT + 1
    np.testing.assert_array_equal(a.support[:k], b.support[:k])
    np.testing.assert_array_equal(a.resistance[:k], b.resistance[:k])
    np.testing.assert_array_equal(a.signal[:k], b.signal[:k])
    assert not np.array_equal(a.signal[k:], b.signal[k:])


def test_leaky_twin_including_the_decision_bar_would_fail() -> None:
    """Fitting on ``close[i-lookback+1 : i+1]`` lets bar ``i`` shape the line it is compared to."""
    clean, dirty = _series(), _poison(_series())
    lookback, i = 30, CUT + 1  # first poisoned bar
    honest = [
        fit_trendlines_single(np.log(b.close[i - lookback : i])).resistance for b in (clean, dirty)
    ]
    leaky = [
        fit_trendlines_single(np.log(b.close[i - lookback + 1 : i + 1])).resistance
        for b in (clean, dirty)
    ]
    assert honest[0] == honest[1]
    assert leaky[0] != leaky[1]


def test_settled_trades_before_the_cut_are_immune() -> None:
    clean, dirty = _series(seed=21, n=900), _poison(_series(seed=21, n=900))
    a = [
        t
        for t in breakout_features(clean, lookback=24, hold_period=12, atr_lookback=48)
        if t.exit_index <= CUT
    ]
    b = [
        t
        for t in breakout_features(dirty, lookback=24, hold_period=12, atr_lookback=48)
        if t.exit_index <= CUT
    ]
    assert a == b and len(a) > 1
