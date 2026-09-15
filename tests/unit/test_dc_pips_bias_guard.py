"""Future-poison guards for directional change and PIP windows.

Same method as ``tests/bias_guards/test_oscillator_no_lookahead``: compute, replace every bar after
``CUT`` with a violently different path, recompute, and assert nothing knowable at or before
``CUT`` moved. For directional change "knowable" means ``confirmed_index <= CUT``; the extreme's own
``index`` is deliberately not enough, which a leaky twin demonstrates.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    OHLCV,
    dc_known_by,
    directional_change,
    geometric_brownian_series,
    pip_windows,
)

pytestmark = pytest.mark.bias_guard

CUT = 300


def _series(seed: int = 7, n: int = 600) -> OHLCV:
    return geometric_brownian_series(n, seed=seed, vol_per_bar=0.02, start=1.0)


def _poison(bars: OHLCV, cut: int = CUT) -> OHLCV:
    """Replace every bar strictly after ``cut``; copy everything at or before it byte for byte."""
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


@pytest.mark.parametrize("sigma", [0.02, 0.05])
def test_directional_change_known_by_is_immune_to_the_future(sigma: float) -> None:
    clean, dirty = _series(), _poison(_series())
    a = dc_known_by(directional_change(clean, sigma=sigma), CUT)
    b = dc_known_by(directional_change(dirty, sigma=sigma), CUT)
    assert a == b and len(a) > 5


def _flat(closes: list[float]) -> OHLCV:
    c = np.asarray(closes, dtype=np.float64)
    return OHLCV(np.arange(c.size, dtype=np.float64), c, c, c, c, np.ones(c.size))


def test_leaky_twin_keyed_on_extreme_index_would_fail() -> None:
    """Filtering on ``index`` instead of ``confirmed_index`` admits an extreme the future decides.

    Price peaks at bar 5 and drifts down without retracing 5% by bar 10 (the cut). If the future
    keeps falling the peak becomes a confirmed top; if the future jumps up it never does. The peak's
    own index is <= cut in both worlds, so an ``index`` filter reads the future; ``dc_known_by``
    does not.
    """
    cut = 10
    head = [1.0, 1.02, 1.04, 1.06, 1.08, 1.10, 1.09, 1.08, 1.07, 1.065, 1.06]
    falls = _flat(head + [1.05, 1.04, 1.03, 1.02, 1.08, 1.12])
    jumps = _flat(head + [2.0, 2.1, 2.2, 2.3, 2.4, 2.5])
    by_index = [
        [e for e in directional_change(b, sigma=0.05) if e.index <= cut] for b in (falls, jumps)
    ]
    assert by_index[0] != by_index[1] and by_index[0][0].index == 5
    assert dc_known_by(directional_change(falls, sigma=0.05), cut) == dc_known_by(
        directional_change(jumps, sigma=0.05), cut
    )


def test_pip_windows_rows_ending_by_cut_are_immune() -> None:
    clean, dirty = _series(), _poison(_series())
    a = pip_windows(clean.close, lookback=24, n_pips=5)
    b = pip_windows(dirty.close, lookback=24, n_pips=5)
    keep = a.end_index <= CUT
    np.testing.assert_array_equal(a.end_index, b.end_index)
    np.testing.assert_array_equal(a.matrix[keep], b.matrix[keep])
    assert not np.array_equal(a.matrix[~keep], b.matrix[~keep])
