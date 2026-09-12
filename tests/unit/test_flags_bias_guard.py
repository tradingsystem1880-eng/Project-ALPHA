"""Future-poison guard for flags and pennants: patterns confirmed by ``CUT`` cannot change when
every later bar is replaced, under both detection variants."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    detect_flags_pips,
    detect_flags_trendline,
    flags_known_by,
    geometric_brownian_series,
)

pytestmark = pytest.mark.bias_guard

CUT = 1500


def _pair() -> tuple[np.ndarray, np.ndarray]:
    clean = np.log(geometric_brownian_series(3000, vol_per_bar=0.02, seed=7).close)
    dirty = clean.copy()
    rng = np.random.default_rng(999)
    dirty[CUT + 1 :] = clean[CUT] + np.log(10.0 + rng.random(dirty.size - CUT - 1) * 5.0)
    return clean, dirty


def test_pips_variant_known_by_cut_is_immune() -> None:
    clean, dirty = _pair()
    a = flags_known_by(detect_flags_pips(clean, order=12), CUT)
    b = flags_known_by(detect_flags_pips(dirty, order=12), CUT)
    assert a == b and len(a) > 3


def test_trendline_variant_known_by_cut_is_immune() -> None:
    clean, dirty = _pair()
    a = flags_known_by(detect_flags_trendline(clean, order=10), CUT)
    b = flags_known_by(detect_flags_trendline(dirty, order=10), CUT)
    assert a == b and len(a) > 3
