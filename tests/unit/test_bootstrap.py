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


def test_bootstrap_indices_respects_explicit_length() -> None:
    # an explicit output length decouples the path length from the index range (samples in [0, n))
    idx = stationary_bootstrap_indices(
        20, mean_block=5.0, n_resamples=10, rng=np.random.default_rng(7), length=50
    )
    assert idx.shape == (10, 50)
    assert idx.min() >= 0 and idx.max() < 20  # indices still drawn from the 20-long source
    # length=n reproduces the no-length call byte-for-byte (existing callers stay unchanged)
    a = stationary_bootstrap_indices(
        20, mean_block=5.0, n_resamples=8, rng=np.random.default_rng(3)
    )
    b = stationary_bootstrap_indices(
        20, mean_block=5.0, n_resamples=8, rng=np.random.default_rng(3), length=20
    )
    assert np.array_equal(a, b)


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


def test_default_mean_block_produces_a_valid_interval() -> None:
    # omitting mean_block exercises the n**(1/3) default heuristic (216 -> 6)
    data = np.random.default_rng(9).normal(0.0, 0.01, size=216)
    ci = block_bootstrap_ci(data, lambda a: float(a.mean()), n_resamples=400, seed=1)
    assert ci.lower < ci.point < ci.upper


def test_bca_collapses_to_point_on_constant_data() -> None:
    # constant data -> zero jackknife variation (the accel denom==0 early return) and degenerate
    # replicates -> the interval collapses onto the point estimate without crashing
    ci = block_bootstrap_ci(
        np.full(20, 5.0), lambda a: float(a.mean()), n_resamples=200, mean_block=4.0, seed=0
    )
    assert ci.lower == pytest.approx(5.0) and ci.upper == pytest.approx(5.0)


def test_bca_is_asymmetric_under_skew() -> None:
    # the point of BCa over a plain percentile interval: skew shifts the two tails differently
    data = np.random.default_rng(4).exponential(0.01, size=400)  # right-skewed
    ci = block_bootstrap_ci(
        data, lambda a: float(a.mean()), n_resamples=1000, mean_block=1.0, seed=2
    )
    assert abs((ci.upper - ci.point) - (ci.point - ci.lower)) > 1e-5


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


def test_degenerate_statistic_fails_loud() -> None:
    # a constant series makes every Sharpe resample zero-variance -> fail loud, never a silent NaN
    with pytest.raises(DataError):
        block_bootstrap_ci(np.full(50, 0.01), sharpe_ratio, n_resamples=100, mean_block=5.0, seed=0)
