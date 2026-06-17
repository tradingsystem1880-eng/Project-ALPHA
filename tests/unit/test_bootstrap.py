"""Stationary block bootstrap + BCa confidence intervals (spec §8 gate 4)."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.bootstrap import (
    ConfidenceInterval,
    block_bootstrap_ci,
    stationary_bootstrap_indices,
)
from alpha_validation.metrics import sharpe_ratio


def test_bootstrap_indices_shape_bounds_and_determinism() -> None:
    idx_a = stationary_bootstrap_indices(
        50, mean_block=5.0, n_resamples=200, rng=np.random.default_rng(7)
    )
    assert idx_a.shape == (200, 50)
    assert idx_a.min() >= 0 and idx_a.max() < 50  # every index is in-range
    idx_b = stationary_bootstrap_indices(
        50, mean_block=5.0, n_resamples=200, rng=np.random.default_rng(7)
    )
    assert np.array_equal(idx_a, idx_b)  # same seed -> identical resamples


def test_unit_mean_block_advances_one_step_within_a_block() -> None:
    # mean_block >> n -> restart prob ~0 -> each row is a single circular block (contiguous mod n)
    idx = stationary_bootstrap_indices(
        20, mean_block=10_000.0, n_resamples=5, rng=np.random.default_rng(1)
    )
    expected = (idx[:, :-1] + 1) % 20
    assert np.array_equal(idx[:, 1:], expected)  # purely contiguous wrap, no restarts


def test_bca_ci_brackets_point_and_is_deterministic() -> None:
    data = np.random.default_rng(0).normal(0.001, 0.01, size=250)
    ci = block_bootstrap_ci(
        data, lambda a: float(a.mean()), confidence=0.95, n_resamples=600, mean_block=5.0, seed=42
    )
    assert isinstance(ci, ConfidenceInterval)
    assert ci.confidence == 0.95
    assert ci.point == pytest.approx(float(data.mean()))
    assert ci.lower < ci.point < ci.upper  # the interval contains the point estimate
    again = block_bootstrap_ci(
        data, lambda a: float(a.mean()), confidence=0.95, n_resamples=600, mean_block=5.0, seed=42
    )
    assert (again.lower, again.upper) == (ci.lower, ci.upper)  # seeded -> reproducible


def test_bca_sharpe_ci_of_strong_signal_excludes_zero() -> None:
    # a series with a large, stable positive drift should have a Sharpe CI clear of zero
    data = np.random.default_rng(3).normal(0.0015, 0.005, size=500)
    ci = block_bootstrap_ci(
        data,
        lambda a: sharpe_ratio(a, periods_per_year=252),
        confidence=0.95,
        n_resamples=800,
        mean_block=10.0,
        seed=11,
    )
    assert ci.lower > 0.0  # the strategy's risk-adjusted edge is bounded away from zero


def test_wider_confidence_gives_wider_interval() -> None:
    data = np.random.default_rng(5).normal(0.0, 0.01, size=300)
    stat = lambda a: float(a.mean())  # noqa: E731
    narrow = block_bootstrap_ci(data, stat, confidence=0.80, n_resamples=500, seed=1)
    wide = block_bootstrap_ci(data, stat, confidence=0.99, n_resamples=500, seed=1)
    assert (wide.upper - wide.lower) > (narrow.upper - narrow.lower)


def test_fails_loud_on_bad_input() -> None:
    data = np.array([0.01, -0.02, 0.0, 0.015])
    with pytest.raises(DataError):
        block_bootstrap_ci(data, lambda a: float(a.mean()), confidence=1.5)  # not in (0, 1)
    with pytest.raises(DataError):
        block_bootstrap_ci(np.array([0.01]), lambda a: float(a.mean()))  # < 2 observations
    with pytest.raises(DataError):
        stationary_bootstrap_indices(
            50, mean_block=0.0, n_resamples=10, rng=np.random.default_rng(0)
        )  # mean_block must be > 0
