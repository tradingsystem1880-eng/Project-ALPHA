"""Future-poison guards for the runs indicator, permutation entropy, CMMA and the RSI matrix."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    OHLCV,
    cmma,
    geometric_brownian_series,
    permutation_entropy,
    rolling_runs_z,
    rsi_matrix,
)

pytestmark = pytest.mark.bias_guard

CUT = 600


def _series(seed: int = 7, n: int = 1000) -> OHLCV:
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


def _same(a: np.ndarray, b: np.ndarray) -> None:
    np.testing.assert_array_equal(a[: CUT + 1], b[: CUT + 1])
    assert not np.array_equal(a[CUT + 1 :], b[CUT + 1 :])


def test_rolling_runs_z_is_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    _same(rolling_runs_z(clean.close, lookback=24), rolling_runs_z(dirty.close, lookback=24))


def test_permutation_entropy_is_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    _same(
        permutation_entropy(clean.close, d=3, mult=10),
        permutation_entropy(dirty.close, d=3, mult=10),
    )


def test_cmma_and_rsi_matrix_are_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    _same(cmma(clean, lookback=20, atr_lookback=50), cmma(dirty, lookback=20, atr_lookback=50))
    a, b = rsi_matrix(clean.close, [5, 14]), rsi_matrix(dirty.close, [5, 14])
    np.testing.assert_array_equal(a[: CUT + 1], b[: CUT + 1])
