"""Portfolio optimizers: long-only fully-invested weights, sensible allocation, fail-loud guards."""

from __future__ import annotations

import numpy as np
import pytest
from alpha_portfolio import (
    hierarchical_risk_parity_weights,
    min_variance_weights,
)

from alpha_core import DataError

_OPTIMIZERS = [min_variance_weights, hierarchical_risk_parity_weights]


def _returns(n_obs: int = 400, n_assets: int = 4, *, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0005, 0.01, (n_obs, n_assets))


@pytest.mark.parametrize("optimizer", _OPTIMIZERS)
def test_weights_are_long_only_and_fully_invested(optimizer: object) -> None:
    w = optimizer(_returns())  # type: ignore[operator]
    assert w.shape == (4,)
    assert np.all(np.isfinite(w))
    assert np.all(w >= -1e-9)  # long-only
    assert abs(float(w.sum()) - 1.0) < 1e-6  # fully invested


def test_min_variance_underweights_the_volatile_asset() -> None:
    rng = np.random.default_rng(3)
    calm = rng.normal(0.0005, 0.005, (500, 1))
    mid = rng.normal(0.0005, 0.01, (500, 1))
    wild = rng.normal(0.0005, 0.04, (500, 1))
    returns = np.hstack([calm, mid, wild])
    w = min_variance_weights(returns)
    assert w[0] > w[2]  # the calm asset gets more weight than the volatile one


@pytest.mark.parametrize("optimizer", _OPTIMIZERS)
def test_non_2d_input_fails_loud(optimizer: object) -> None:
    with pytest.raises(DataError):
        optimizer(np.array([0.01, -0.01, 0.02]))  # type: ignore[operator]


@pytest.mark.parametrize("optimizer", _OPTIMIZERS)
def test_single_asset_fails_loud(optimizer: object) -> None:
    with pytest.raises(DataError):
        optimizer(_returns(n_assets=1))  # type: ignore[operator]


@pytest.mark.parametrize("optimizer", _OPTIMIZERS)
def test_non_finite_fails_loud(optimizer: object) -> None:
    bad = _returns()
    bad[10, 1] = np.inf
    with pytest.raises(DataError):
        optimizer(bad)  # type: ignore[operator]


@pytest.mark.parametrize("optimizer", _OPTIMIZERS)
def test_deterministic(optimizer: object) -> None:
    r = _returns()
    assert np.array_equal(optimizer(r), optimizer(r))  # type: ignore[operator]
