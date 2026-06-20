"""White's Reality Check + Hansen's SPA data-snooping tests."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.reality_check import reality_check, spa_test


def _noise(n: int, s: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, 0.01, (n, s))


def test_strong_strategy_among_noise_is_detected() -> None:
    m = _noise(250, 20, seed=0)
    m[:, 5] += 0.01  # one strategy with a large, persistent edge
    rc = reality_check(m, n_resamples=500, seed=1)
    spa = spa_test(m, n_resamples=500, seed=1)
    assert rc.passed is True and rc.p_value < 0.05
    assert spa.passed is True and spa.p_value < 0.05


def test_pure_noise_is_not_significant() -> None:
    m = _noise(250, 30, seed=2)  # 30 strategies, none with real edge
    rc = reality_check(m, n_resamples=500, seed=3)
    spa = spa_test(m, n_resamples=500, seed=3)
    assert rc.passed is False and rc.p_value > 0.05
    assert spa.passed is False and spa.p_value > 0.05


def test_spa_is_at_least_as_powerful_as_rc() -> None:
    # one marginal strategy plus many clearly-bad ones: SPA drops the bad ones from the null, so its
    # p-value is no larger than RC's (which is dragged up by every bad candidate).
    m = _noise(150, 1, seed=4) + 0.0018  # marginal positive edge
    bad = _noise(150, 40, seed=5) - 0.003  # many losers
    full = np.column_stack([m, bad])
    rc = reality_check(full, n_resamples=800, seed=6)
    spa = spa_test(full, n_resamples=800, seed=6)
    assert spa.p_value <= rc.p_value + 1e-9


def test_deterministic() -> None:
    m = _noise(120, 10, seed=7)
    assert (
        reality_check(m, n_resamples=300, seed=9).p_value
        == reality_check(m, n_resamples=300, seed=9).p_value
    )
    assert (
        spa_test(m, n_resamples=300, seed=9).p_value == spa_test(m, n_resamples=300, seed=9).p_value
    )


def test_fails_loud() -> None:
    m = _noise(100, 5, seed=8)
    with pytest.raises(DataError):
        reality_check(m, n_resamples=0)
    with pytest.raises(DataError):
        spa_test(m, mean_block=0.0)
    with pytest.raises(DataError):
        reality_check(m, alpha=1.5)
    with pytest.raises(DataError):
        spa_test(m[:1])  # < 2 observations
