"""Probability of Backtest Overfitting via CSCV (Bailey et al. 2017)."""

from __future__ import annotations

from math import comb

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.overfitting import probability_of_backtest_overfitting

_MEAN = lambda r: float(np.mean(r))  # noqa: E731 — terse statistic for deterministic fixtures


def test_split_count_is_n_choose_half() -> None:
    m = np.random.default_rng(0).normal(0, 1, (160, 5))
    res = probability_of_backtest_overfitting(m, n_blocks=8)
    assert res.n_splits == comb(8, 4) == 70
    assert res.n_configs == 5


def test_persistent_skill_has_low_pbo() -> None:
    # config c has a constant edge c across all blocks → IS-best is always OOS-best → not overfit
    blocks, rows = 6, 5
    cols = [np.full(blocks * rows, float(c)) for c in range(4)]
    m = np.column_stack(cols)
    res = probability_of_backtest_overfitting(m, n_blocks=blocks, statistic=_MEAN)
    assert res.pbo == 0.0
    assert res.passed is True


def test_anti_correlated_leaderboard_has_high_pbo() -> None:
    # config A wins the first half of blocks, loses the second; config B is its mirror. Whatever
    # looks best in-sample is worst out-of-sample → maximal overfitting.
    rows = 5
    a = np.concatenate(
        [np.full(rows, 1.0), np.full(rows, 1.0), np.full(rows, -1.0), np.full(rows, -1.0)]
    )
    b = -a
    m = np.column_stack([a, b])
    res = probability_of_backtest_overfitting(m, n_blocks=4, statistic=_MEAN)
    assert res.pbo == 1.0
    assert res.passed is False


def test_pure_noise_is_intermediate() -> None:
    m = np.random.default_rng(7).normal(0, 1, (320, 8))
    res = probability_of_backtest_overfitting(m, n_blocks=8)
    assert 0.1 < res.pbo < 0.9  # no real structure → neither clearly skilled nor maximally overfit


def test_deterministic() -> None:
    m = np.random.default_rng(3).normal(0, 1, (160, 5))
    a = probability_of_backtest_overfitting(m, n_blocks=8)
    b = probability_of_backtest_overfitting(m, n_blocks=8)
    assert a.pbo == b.pbo
    assert np.array_equal(a.logits, b.logits)


def test_fails_loud() -> None:
    good = np.random.default_rng(1).normal(0, 1, (160, 5))
    with pytest.raises(DataError):
        probability_of_backtest_overfitting(good, n_blocks=7)  # odd
    with pytest.raises(DataError):
        probability_of_backtest_overfitting(good[:, :1], n_blocks=8)  # < 2 configs
    with pytest.raises(DataError):
        probability_of_backtest_overfitting(good[:4], n_blocks=8)  # too few rows
    with pytest.raises(DataError):
        probability_of_backtest_overfitting(good, n_blocks=8, threshold=1.5)
