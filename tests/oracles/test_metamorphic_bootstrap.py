"""Metamorphic relations for the stationary bootstrap and BCa interval.

Primary sources: Politis & Romano, "The Stationary Bootstrap" (JASA 1994) — geometric block
lengths with continuation probability 1 − 1/mean_block and circular wrap-around; Efron,
"Better Bootstrap Confidence Intervals" (JASA 1987) — BCa collapses to the percentile
interval when z0 = a = 0.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.bootstrap import (
    _bca_percentile,
    block_bootstrap_ci,
    stationary_bootstrap_indices,
)

pytestmark = pytest.mark.oracle


def _indices(n: int, mean_block: float, *, seed: int = 3, n_resamples: int = 200) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return stationary_bootstrap_indices(n, mean_block=mean_block, n_resamples=n_resamples, rng=rng)


def test_indices_have_the_declared_shape_and_stay_in_range() -> None:
    idx = _indices(50, 5.0)
    assert idx.shape == (200, 50)
    assert idx.min() >= 0 and idx.max() < 50
    short = stationary_bootstrap_indices(
        50, mean_block=5.0, n_resamples=7, rng=np.random.default_rng(1), length=12
    )
    assert short.shape == (7, 12)


def test_huge_mean_block_yields_contiguous_circular_runs() -> None:
    """Continuation probability → 1 ⇒ one circular run per resample: idx[t] = idx[t-1]+1 mod n."""
    idx = _indices(40, 1e12)
    expected = (idx[:, :-1] + 1) % 40
    assert np.array_equal(idx[:, 1:], expected)


def test_mean_block_one_is_iid_resampling() -> None:
    """mean_block=1 ⇒ continuation probability 0 ⇒ each index is drawn fresh; the chance that
    idx[t] happens to equal idx[t-1]+1 mod n is then 1/n (a contiguous-run frequency near 1
    would betray a block bug)."""
    n = 20
    idx = _indices(n, 1.0, n_resamples=2000)
    continued = float(np.mean(idx[:, 1:] == (idx[:, :-1] + 1) % n))
    # 2000*19 = 38,000 Bernoulli(1/20) draws: sd ≈ 0.0011; ±0.01 is a > 9-sigma band.
    assert abs(continued - 1.0 / n) < 0.01


def test_indices_are_seed_deterministic_and_seed_sensitive() -> None:
    assert np.array_equal(_indices(30, 4.0, seed=9), _indices(30, 4.0, seed=9))
    assert not np.array_equal(_indices(30, 4.0, seed=9), _indices(30, 4.0, seed=10))


def test_bca_with_no_bias_and_no_acceleration_is_the_percentile_interval() -> None:
    reps = np.random.default_rng(5).normal(size=5000)
    for prob in (0.025, 0.5, 0.975):
        assert _bca_percentile(reps, 0.0, 0.0, prob) == pytest.approx(
            float(np.quantile(reps, prob)), rel=1e-12
        )


def test_block_bootstrap_ci_is_seed_deterministic_and_brackets_the_point_estimate() -> None:
    data = np.random.default_rng(2).normal(0.01, 0.02, size=200)
    a = block_bootstrap_ci(data, np.mean, confidence=0.9, n_resamples=500, mean_block=5.0, seed=7)
    b = block_bootstrap_ci(data, np.mean, confidence=0.9, n_resamples=500, mean_block=5.0, seed=7)
    assert (a.lower, a.upper) == (b.lower, b.upper)
    assert a.lower <= a.point <= a.upper
    assert a.point == pytest.approx(float(np.mean(data)))


def test_parameter_guards_fail_loud() -> None:
    rng = np.random.default_rng(0)
    with pytest.raises(DataError):
        stationary_bootstrap_indices(0, mean_block=2.0, n_resamples=3, rng=rng)
    with pytest.raises(DataError):
        stationary_bootstrap_indices(10, mean_block=0.0, n_resamples=3, rng=rng)
    with pytest.raises(DataError):
        stationary_bootstrap_indices(10, mean_block=2.0, n_resamples=0, rng=rng)
    with pytest.raises(DataError):
        block_bootstrap_ci([1.0, 2.0, 3.0], np.mean, confidence=1.0, n_resamples=10, seed=1)
