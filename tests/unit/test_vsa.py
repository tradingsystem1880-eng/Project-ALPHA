"""Volume spread analysis: an exact linear relation leaves no residual, a rejected fit reads zero,
the rolling OLS reproduces the pinned upstream regression loop, and the indicator warms up
honestly."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import geometric_brownian_series, rolling_ols_residual, vsa_indicator

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


class TestRollingOls:
    def test_exact_relation_has_zero_residual(self) -> None:
        x = np.linspace(1.0, 5.0, 60)
        y = 2.0 + 3.0 * x
        out = rolling_ols_residual(x, y, window=10)
        assert np.all(np.isnan(out[:9]))
        np.testing.assert_allclose(out[9:], 0.0, atol=1e-10)

    def test_negative_or_weak_relation_is_gated_to_zero(self) -> None:
        x = np.linspace(1.0, 5.0, 60)
        assert np.all(rolling_ols_residual(x, -x, window=10)[9:] == 0.0)
        rng = np.random.default_rng(0)
        noise = rng.normal(size=60)
        assert np.all(rolling_ols_residual(x, noise, window=10, min_r=0.999)[9:] == 0.0)

    def test_constant_x_is_nan_not_a_guess(self) -> None:
        out = rolling_ols_residual(np.ones(20), np.arange(20.0), window=5)
        assert np.all(np.isnan(out))

    def test_guards(self) -> None:
        with pytest.raises(DataError, match="window"):
            rolling_ols_residual(np.ones(5), np.ones(5), window=2)
        with pytest.raises(DataError, match="start"):
            rolling_ols_residual(np.ones(9), np.ones(9), window=5, start=2)

    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "vsa.json").read_text())
        x = np.array([np.nan if v is None else v for v in fx["norm_volume"]])
        y = np.array([np.nan if v is None else v for v in fx["norm_range"]])
        lb = int(fx["norm_lookback"])
        out = rolling_ols_residual(x, y, window=lb, start=2 * lb)
        expected = np.array([np.nan if v is None else v for v in fx["dev"]])
        np.testing.assert_allclose(out, expected, rtol=1e-9, atol=1e-12, equal_nan=True)
        assert np.sum(expected == 0.0) > 100 and np.sum(expected != 0.0) > 1000


class TestIndicator:
    def test_warmup_and_shape(self) -> None:
        bars = geometric_brownian_series(700, vol_per_bar=0.02, seed=8)
        out = vsa_indicator(bars, norm_lookback=100)
        assert out.shape == (700,)
        assert np.all(np.isnan(out[:200])) and np.all(np.isfinite(out[200:]))

    def test_guard(self) -> None:
        with pytest.raises(DataError, match="norm_lookback"):
            vsa_indicator(geometric_brownian_series(100, seed=1), norm_lookback=60)
