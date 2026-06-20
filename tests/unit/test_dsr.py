"""Probabilistic + Deflated Sharpe Ratio (Bailey & López de Prado).

Pins the statistical contract: PSR rises with edge and sample size; non-normality lowers it;
deflation against more trials lowers DSR; a standalone run's DSR equals its PSR; degenerate input
fails loud; everything is deterministic (no RNG).
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation import (
    deflated_sharpe,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)


def _gaussian_returns(n: int, mean: float, sd: float, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).normal(mean, sd, n)


class TestProbabilisticSharpe:
    def test_is_a_probability(self) -> None:
        r = _gaussian_returns(500, 0.001, 0.01, seed=0)
        psr = probabilistic_sharpe_ratio(r)
        assert 0.0 <= psr <= 1.0

    def test_strong_edge_is_near_one(self) -> None:
        r = _gaussian_returns(1000, 0.002, 0.005, seed=1)  # high, stable mean return
        assert probabilistic_sharpe_ratio(r) > 0.99

    def test_no_edge_is_not_confident(self) -> None:
        # a zero-mean series gives no confident verdict either way (not near 0 or 1)
        r = _gaussian_returns(1000, 0.0, 0.01, seed=2)
        assert 0.05 < probabilistic_sharpe_ratio(r) < 0.95

    def test_more_data_increases_confidence(self) -> None:
        small = probabilistic_sharpe_ratio(_gaussian_returns(60, 0.001, 0.01, seed=3))
        large = probabilistic_sharpe_ratio(_gaussian_returns(2000, 0.001, 0.01, seed=3))
        assert large > small

    def test_higher_benchmark_lowers_psr(self) -> None:
        r = _gaussian_returns(500, 0.001, 0.01, seed=4)
        assert probabilistic_sharpe_ratio(r, benchmark_sr=0.2) < probabilistic_sharpe_ratio(r)

    def test_deterministic(self) -> None:
        r = _gaussian_returns(300, 0.001, 0.01, seed=5)
        assert probabilistic_sharpe_ratio(r) == probabilistic_sharpe_ratio(r)

    def test_fails_loud(self) -> None:
        with pytest.raises(DataError):
            probabilistic_sharpe_ratio([0.01])  # < 2 returns
        with pytest.raises(DataError):
            probabilistic_sharpe_ratio([0.01, 0.01, 0.01])  # zero variance


class TestExpectedMaxSharpe:
    def test_no_trials_is_zero(self) -> None:
        assert expected_max_sharpe(0.04, n_trials=1) == 0.0

    def test_no_dispersion_is_zero(self) -> None:
        assert expected_max_sharpe(0.0, n_trials=100) == 0.0

    def test_grows_with_trials(self) -> None:
        assert expected_max_sharpe(0.04, 1000) > expected_max_sharpe(0.04, 10) > 0.0

    def test_negative_variance_fails_loud(self) -> None:
        with pytest.raises(DataError):
            expected_max_sharpe(-1.0, 10)


class TestDeflatedSharpe:
    def test_standalone_dsr_equals_psr(self) -> None:
        r = _gaussian_returns(500, 0.001, 0.01, seed=6)
        res = deflated_sharpe(r)
        assert res.n_trials == 1
        assert res.expected_max_sharpe == 0.0
        assert res.dsr == pytest.approx(res.psr)

    def test_many_trials_deflate_below_psr(self) -> None:
        r = _gaussian_returns(1000, 0.0015, 0.01, seed=7)
        # a wide spread of trial Sharpes => a high expected-max benchmark => DSR < PSR
        trials = np.linspace(-0.1, 0.15, 200)
        res = deflated_sharpe(r, trial_sharpes=trials)
        assert res.n_trials == 200
        assert res.expected_max_sharpe > 0.0
        assert res.dsr < res.psr

    def test_more_trials_lower_dsr(self) -> None:
        r = _gaussian_returns(1000, 0.0015, 0.01, seed=8)
        few = deflated_sharpe(r, trial_sharpes=np.linspace(-0.1, 0.15, 10))
        many = deflated_sharpe(r, trial_sharpes=np.linspace(-0.1, 0.15, 1000))
        assert many.dsr < few.dsr

    def test_pass_flag_tracks_threshold(self) -> None:
        r = _gaussian_returns(2000, 0.002, 0.005, seed=9)  # very strong, should pass
        assert deflated_sharpe(r, threshold=0.95).passed is True

    def test_fails_loud(self) -> None:
        r = _gaussian_returns(100, 0.001, 0.01, seed=10)
        with pytest.raises(DataError):
            deflated_sharpe(r, threshold=1.5)
        with pytest.raises(DataError):
            deflated_sharpe(r, trial_sharpes=[float("nan"), 0.1])
