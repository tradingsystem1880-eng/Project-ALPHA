"""``alpha_validation.forecast_eval``: sample-CRPS, pinball, coverage, baselines, summary."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.forecast_eval import (
    OriginScore,
    bootstrap_end_returns,
    central_coverage,
    crps_sample,
    pinball_loss,
    rw_drift_end_returns,
    score_origin,
    summarize_scores,
)


def test_crps_two_point_closed_form() -> None:
    # samples {0, 2}, y = 1: E|X-y| = 1, (1/2S^2)ΣΣ|xi-xj| = (0+2+2+0)/8 = 0.5 -> CRPS 0.5
    assert crps_sample(np.array([0.0, 2.0]), 1.0) == pytest.approx(0.5)


def test_crps_zero_when_degenerate_at_truth() -> None:
    assert crps_sample(np.array([1.0, 1.0, 1.0]), 1.0) == pytest.approx(0.0)


def test_crps_fails_loud() -> None:
    with pytest.raises(DataError, match="samples"):
        crps_sample(np.array([1.0]), 1.0)
    with pytest.raises(DataError, match="finite"):
        crps_sample(np.array([1.0, np.nan]), 1.0)


def test_pinball_asymmetry() -> None:
    samples = np.linspace(0.0, 10.0, 101)  # empirical q-quantile ~= 10q
    over = pinball_loss(samples, 10.0, 0.9)  # forecast q90 ~= 9, y above -> under-forecast
    under = pinball_loss(samples, 10.0, 0.1)  # forecast q10 ~= 1, y far above
    # q=0.9 weights under-forecast by 0.9; q=0.1 weights it by 0.1
    assert over == pytest.approx(0.9 * (10.0 - 9.0), abs=0.05)
    assert under == pytest.approx(0.1 * (10.0 - 1.0), abs=0.05)


def test_central_coverage_levels() -> None:
    samples = np.linspace(0.0, 100.0, 1001)
    assert central_coverage(samples, 50.0, 0.5) is True  # inside q25..q75
    assert central_coverage(samples, 99.0, 0.5) is False  # outside q25..q75
    assert central_coverage(samples, 99.0, 0.99) is True  # inside q005..q995


def test_baselines_deterministic_and_shaped() -> None:
    returns = np.array([0.01, -0.02, 0.015, 0.005, -0.01, 0.02])
    rw_a = rw_drift_end_returns(returns, horizon=5, n_samples=64, rng=np.random.default_rng(1))
    rw_b = rw_drift_end_returns(returns, horizon=5, n_samples=64, rng=np.random.default_rng(1))
    assert rw_a.shape == (64,) and np.array_equal(rw_a, rw_b)
    assert bool(np.all(rw_a > -1.0))

    bt_a = bootstrap_end_returns(
        returns, horizon=5, n_samples=64, mean_block=3.0, rng=np.random.default_rng(2)
    )
    bt_b = bootstrap_end_returns(
        returns, horizon=5, n_samples=64, mean_block=3.0, rng=np.random.default_rng(2)
    )
    assert bt_a.shape == (64,) and np.array_equal(bt_a, bt_b)
    assert bool(np.all(np.isfinite(bt_a)))


def test_baselines_fail_loud_on_degenerate_input() -> None:
    with pytest.raises(DataError):
        rw_drift_end_returns(np.array([0.01]), horizon=3, n_samples=8, rng=np.random.default_rng())
    with pytest.raises(DataError):
        rw_drift_end_returns(
            np.array([0.01, -1.5]), horizon=3, n_samples=8, rng=np.random.default_rng()
        )


def test_score_origin_and_summarize() -> None:
    rng = np.random.default_rng(7)
    model = rng.normal(0.02, 0.05, 200)
    rw = rng.normal(0.0, 0.05, 200)
    boot = rng.normal(0.0, 0.05, 200)
    score = score_origin(model, 0.03, rw_end_returns=rw, bootstrap_end_returns_=boot)
    assert isinstance(score, OriginScore)
    assert score.crps > 0.0 and score.crps_rw > 0.0
    assert score.hit is True  # median model > 0 and realized > 0

    summary = summarize_scores([score, score])
    assert summary.n_origins == 2
    assert summary.hit_rate == 1.0
    assert summary.skill_vs_rw == pytest.approx(1.0 - score.crps / score.crps_rw)
    assert 0.0 <= summary.coverage80 <= 1.0


def test_summarize_fails_loud_on_empty() -> None:
    with pytest.raises(DataError, match="origin"):
        summarize_scores([])
