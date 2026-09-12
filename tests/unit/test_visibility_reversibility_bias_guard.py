"""Future-poison guards for the rolling visibility-graph and irreversibility indicators."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    geometric_brownian_series,
    rolling_perm_reversibility,
    rolling_relative_async_index,
    rolling_vg_shortest_path,
)

pytestmark = pytest.mark.bias_guard

CUT = 300


def _pair() -> tuple[np.ndarray, np.ndarray]:
    clean = geometric_brownian_series(500, vol_per_bar=0.02, seed=7).close
    dirty = clean.copy()
    dirty[CUT + 1 :] = clean[CUT] * (
        10.0 + np.random.default_rng(999).random(dirty.size - CUT - 1) * 5.0
    )
    return clean, dirty


def _same(a: np.ndarray, b: np.ndarray) -> None:
    np.testing.assert_array_equal(a[: CUT + 1], b[: CUT + 1])
    assert not np.array_equal(a[CUT + 1 :], b[CUT + 1 :])


def test_rolling_shortest_paths_are_immune() -> None:
    clean, dirty = _pair()
    pa, na = rolling_vg_shortest_path(clean, lookback=12)
    pb, nb = rolling_vg_shortest_path(dirty, lookback=12)
    _same(pa, pb)
    _same(na, nb)


def test_rolling_reversibility_is_immune() -> None:
    clean, dirty = _pair()
    _same(
        rolling_relative_async_index(clean, window=40),
        rolling_relative_async_index(dirty, window=40),
    )
    a, b = (
        rolling_perm_reversibility(clean, window=60),
        rolling_perm_reversibility(dirty, window=60),
    )
    np.testing.assert_array_equal(a[: CUT + 1], b[: CUT + 1])
