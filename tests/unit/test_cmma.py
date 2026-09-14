"""CMMA and the intermarket-difference signal: the formula, the honest warm-up, and the
documented threshold-entry / zero-cross-exit rule."""

from __future__ import annotations

import math

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    atr,
    cmma,
    geometric_brownian_series,
    intermarket_difference,
    rolling_mean,
    rsi,
    rsi_matrix,
    threshold_revert_signal,
)


class TestCmma:
    def test_formula_and_warmup(self) -> None:
        bars = geometric_brownian_series(300, seed=4)
        out = cmma(bars, lookback=20, atr_lookback=50)
        assert np.all(np.isnan(out[:49])) and np.all(np.isfinite(out[49:]))
        i = 120
        expected = (bars.close[i] - rolling_mean(bars.close, 20)[i]) / (
            atr(bars, 50)[i] * math.sqrt(20)
        )
        assert out[i] == pytest.approx(expected)

    def test_guards(self) -> None:
        bars = geometric_brownian_series(50, seed=1)
        with pytest.raises(DataError, match="lookback"):
            cmma(bars, lookback=1)
        with pytest.raises(DataError, match="need more than"):
            cmma(bars, lookback=10, atr_lookback=100)


class TestIntermarket:
    def test_difference_and_alignment(self) -> None:
        np.testing.assert_array_equal(
            intermarket_difference(np.array([1.0, 2.0]), np.array([0.5, 0.5])), [0.5, 1.5]
        )
        with pytest.raises(DataError, match="aligned"):
            intermarket_difference(np.ones(3), np.ones(2))

    def test_threshold_revert_signal_rule(self) -> None:
        ind = np.array([0.1, 0.6, 0.3, -0.1, -0.7, 0.2, np.nan, 0.9])
        assert list(threshold_revert_signal(ind, threshold=0.5)) == [0, 1, 1, 0, -1, 0, 0, 1]

    def test_threshold_guard(self) -> None:
        with pytest.raises(DataError, match="threshold"):
            threshold_revert_signal(np.zeros(3), threshold=0.0)


class TestRsiMatrix:
    def test_columns_are_rsi_per_period(self) -> None:
        close = geometric_brownian_series(200, seed=9).close
        m = rsi_matrix(close, [2, 5, 14])
        assert m.shape == (200, 3)
        np.testing.assert_array_equal(m[:, 1], rsi(close, 5))

    def test_guards(self) -> None:
        with pytest.raises(DataError, match="unique"):
            rsi_matrix(np.arange(50.0), [3, 3])
        with pytest.raises(DataError, match="at least one"):
            rsi_matrix(np.arange(50.0), [])
