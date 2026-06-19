"""GARCH conditional-volatility wrappers: shape, clustering response, and fail-loud guards."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.volatility import (
    garch_conditional_volatility,
    garch_volatility_forecast,
)


def _two_regime_returns(n: int = 600, *, seed: int = 7) -> np.ndarray:
    """Low-vol first half, high-vol second half — deterministic."""
    rng = np.random.default_rng(seed)
    lo = rng.normal(0.0, 0.005, n // 2)
    hi = rng.normal(0.0, 0.02, n - n // 2)
    return np.concatenate([lo, hi])


def test_conditional_volatility_shape_and_positive() -> None:
    r = _two_regime_returns()
    cv = garch_conditional_volatility(r)
    assert cv.shape == r.shape
    assert np.all(np.isfinite(cv)) and np.all(cv > 0.0)


def test_conditional_volatility_tracks_clustering() -> None:
    r = _two_regime_returns()
    cv = garch_conditional_volatility(r)
    first_half = cv[: len(cv) // 2].mean()
    second_half = cv[len(cv) // 2 :].mean()
    assert second_half > first_half  # the high-vol regime must read as higher conditional vol


def test_forecast_is_positive_and_scales_with_volatility() -> None:
    rng = np.random.default_rng(11)
    calm = rng.normal(0.0, 0.004, 400)
    wild = rng.normal(0.0, 0.03, 400)
    f_calm = garch_volatility_forecast(calm)
    f_wild = garch_volatility_forecast(wild)
    assert f_calm > 0.0 and f_wild > 0.0
    assert f_wild > f_calm


@pytest.mark.parametrize("fn", [garch_conditional_volatility, garch_volatility_forecast])
def test_too_few_returns_fails_loud(fn: object) -> None:
    with pytest.raises(DataError):
        fn(np.array([0.01, -0.01, 0.0]))  # type: ignore[operator]


def test_non_finite_fails_loud() -> None:
    r = _two_regime_returns()
    r[5] = np.nan
    with pytest.raises(DataError):
        garch_conditional_volatility(r)


def test_zero_variance_fails_loud() -> None:
    with pytest.raises(DataError):
        garch_volatility_forecast(np.zeros(50))


def test_invalid_order_fails_loud() -> None:
    with pytest.raises(DataError):
        garch_conditional_volatility(_two_regime_returns(), p=0)
