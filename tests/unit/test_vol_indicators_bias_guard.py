"""Future-poison guards for the market-profile levels and signal, the Hawkes volatility process
and signal, and the VSA indicator: nothing at or before ``CUT`` changes when later bars are
replaced."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    OHLCV,
    geometric_brownian_series,
    hawkes_process,
    hawkes_vol_signal,
    log_atr,
    sr_penetration_signal,
    support_resistance_levels,
    vsa_indicator,
)

pytestmark = pytest.mark.bias_guard

CUT = 800


def _series(seed: int = 7, n: int = 1200) -> OHLCV:
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


def test_market_profile_levels_and_signal_are_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    a = support_resistance_levels(clean, lookback=120)
    b = support_resistance_levels(dirty, lookback=120)
    for i in range(CUT + 1):
        if a[i] is None:
            assert b[i] is None
        else:
            np.testing.assert_array_equal(a[i], b[i])
    sa, sb = sr_penetration_signal(clean.close, a), sr_penetration_signal(dirty.close, b)
    np.testing.assert_array_equal(sa[: CUT + 1], sb[: CUT + 1])


def test_hawkes_process_and_signal_are_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    out = []
    for bars in (clean, dirty):
        norm_range = (np.log(bars.high) - np.log(bars.low)) / log_atr(bars, 168)
        h = hawkes_process(norm_range, kappa=0.1)
        out.append((h, hawkes_vol_signal(bars.close, h, lookback=96)))
    np.testing.assert_array_equal(out[0][0][: CUT + 1], out[1][0][: CUT + 1])
    np.testing.assert_array_equal(out[0][1][: CUT + 1], out[1][1][: CUT + 1])
    assert np.any(out[0][1][: CUT + 1] != 0)


def test_vsa_indicator_is_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    a, b = vsa_indicator(clean, norm_lookback=168), vsa_indicator(dirty, norm_lookback=168)
    np.testing.assert_array_equal(a[: CUT + 1], b[: CUT + 1])
    assert np.isfinite(a[CUT])
