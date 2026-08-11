"""Scenario/path-risk Monte Carlo over canonical OOS account returns."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation import (
    empirical_return_paths,
    path_metric_arrays,
    regime_switching_return_paths,
    student_t_paths,
    student_t_return_paths,
    summarize_path_family,
)
from alpha_validation import path_montecarlo as path_module


def _returns() -> np.ndarray:
    return np.array([-0.02, 0.01, 0.03, -0.01, 0.02, 0.005], dtype=np.float64)


def test_empirical_paths_are_seeded_draws_with_replacement() -> None:
    returns = _returns()
    first = empirical_return_paths(returns, n_paths=100, length=12, seed=7)
    second = empirical_return_paths(returns, n_paths=100, length=12, seed=7)

    assert first.shape == (100, 12)
    assert np.array_equal(first, second)
    assert set(np.unique(first)).issubset(set(returns))
    assert float(np.mean(first)) == pytest.approx(float(np.mean(returns)), abs=0.003)


def test_regime_paths_recover_persistent_state_emissions() -> None:
    calm = np.tile(np.array([0.001, 0.002, -0.001]), 20)
    volatile = np.tile(np.array([0.04, -0.05, 0.03]), 20)
    returns = np.concatenate((calm, volatile, calm, volatile))
    states = np.concatenate(
        (
            np.zeros(calm.size, dtype=np.int8),
            np.ones(volatile.size, dtype=np.int8),
            np.zeros(calm.size, dtype=np.int8),
            np.ones(volatile.size, dtype=np.int8),
        )
    )

    result = regime_switching_return_paths(
        returns,
        states,
        n_paths=200,
        length=100,
        min_state_observations=20,
        min_state_transitions=1,
        seed=11,
    )

    assert result.paths.shape == (200, 100)
    assert result.states.shape == (200, 100)
    assert result.transition_matrix.shape == (2, 2)
    assert result.transition_matrix[0, 0] > result.transition_matrix[0, 1]
    assert result.transition_matrix[1, 1] > result.transition_matrix[1, 0]
    assert np.std(result.paths[result.states == 1]) > np.std(result.paths[result.states == 0])


def test_regime_paths_fail_loud_when_a_state_is_under_supported() -> None:
    with pytest.raises(DataError, match="state 1 needs at least 20 observations"):
        regime_switching_return_paths(
            np.resize(_returns(), 21),
            np.array([0] * 20 + [1]),
            n_paths=10,
            min_state_observations=20,
            min_state_transitions=1,
            seed=1,
        )


def test_path_summary_reports_tail_risk_and_wilson_intervals() -> None:
    paths = np.array(
        [
            [0.1, -0.6, 0.1],
            [0.01, 0.01, 0.01],
            [-0.1, -0.1, -0.1],
            [0.02, -0.01, 0.02],
        ],
        dtype=np.float64,
    )
    summary = summarize_path_family("iid_empirical", paths, ruin_drawdown=0.5)

    assert summary.family == "iid_empirical"
    assert summary.n_paths == 4
    assert summary.horizon == 3
    assert summary.ruin_probability.successes == 1
    assert summary.loss_probability.successes == 2
    assert 0.0 <= summary.ruin_probability.lower <= summary.ruin_probability.upper <= 1.0
    assert summary.maximum_drawdown_q95 >= 0.5
    assert summary.longest_loss_streak_q95 >= 2.0
    assert summary.risk_grade in {"A", "B", "C", "D", "F"}


def test_path_metrics_report_each_longest_loss_streak_exactly() -> None:
    metrics = path_metric_arrays(
        np.array(
            [
                [-0.1, -0.2, 0.1, -0.1],
                [0.1, -0.1, -0.1, -0.1],
                [0.1, 0.2, 0.3, 0.4],
            ]
        )
    )
    assert metrics.longest_loss_streak.tolist() == [2.0, 3.0, 0.0]


@pytest.mark.parametrize(
    "bad",
    [np.array([0.01]), np.array([0.01, np.nan]), np.array([[0.01, 0.02]])],
)
def test_empirical_paths_reject_invalid_returns(bad: np.ndarray) -> None:
    with pytest.raises(DataError):
        empirical_return_paths(bad, n_paths=10, seed=1)


def test_path_summary_rejects_bankruptcy_beyond_total_equity() -> None:
    with pytest.raises(DataError, match="greater than -1"):
        summarize_path_family("iid_empirical", np.array([[0.1, -1.01]]))


def test_student_t_paths_retain_heavier_tails_than_gaussian() -> None:
    source = np.array([-0.02, -0.01, 0.0, 0.01, 0.02], dtype=np.float64)
    simulated = student_t_paths(source, n_paths=20_000, df=4.5, seed=31).ravel()
    sigma = float(np.std(source, ddof=1))
    gaussian = np.random.default_rng(31).normal(0.0, sigma, simulated.size)
    assert np.quantile(np.abs(simulated), 0.999) > np.quantile(np.abs(gaussian), 0.999)


def test_student_t_account_return_paths_are_seeded_and_match_source_horizon() -> None:
    source = np.array([-0.08, -0.01, 0.0, 0.01, 0.09, 0.002] * 4, dtype=np.float64)
    first = student_t_return_paths(source, n_paths=250, seed=19)
    second = student_t_return_paths(source, n_paths=250, seed=19)

    assert first.shape == (250, source.size)
    assert np.array_equal(first, second)
    assert np.isfinite(first).all()


def test_simulation_controls_and_regime_labels_fail_closed() -> None:
    with pytest.raises(DataError, match="greater than -1"):
        empirical_return_paths(np.array([-1.0, 0.0]), seed=1)
    with pytest.raises(DataError, match="n_paths"):
        empirical_return_paths(_returns(), n_paths=0, seed=1)
    with pytest.raises(DataError, match="length"):
        empirical_return_paths(_returns(), length=0, seed=1)

    returns = np.array([0.01, 0.02, -0.01, -0.02])
    with pytest.raises(DataError, match="states shape"):
        regime_switching_return_paths(returns, np.array([0, 1]), seed=1)
    with pytest.raises(DataError, match="only 0"):
        regime_switching_return_paths(returns, np.array([0, 1, 2, 0]), seed=1)
    with pytest.raises(DataError, match="n_paths"):
        regime_switching_return_paths(
            returns,
            np.array([0, 0, 1, 1]),
            n_paths=0,
            min_state_observations=1,
            min_state_transitions=1,
            seed=1,
        )
    with pytest.raises(DataError, match="minimum state"):
        regime_switching_return_paths(
            returns,
            np.array([0, 0, 1, 1]),
            min_state_observations=0,
            seed=1,
        )
    with pytest.raises(DataError, match="length"):
        regime_switching_return_paths(
            returns,
            np.array([0, 0, 1, 1]),
            length=0,
            min_state_observations=1,
            min_state_transitions=1,
            seed=1,
        )
    with pytest.raises(DataError, match="outbound transitions"):
        regime_switching_return_paths(
            returns,
            np.array([0, 0, 1, 1]),
            min_state_observations=2,
            min_state_transitions=2,
            seed=1,
        )


def test_path_summaries_reject_every_invalid_matrix_or_ruin_boundary() -> None:
    with pytest.raises(DataError, match="non-empty 2-D"):
        summarize_path_family("iid_empirical", np.array([]))
    with pytest.raises(DataError, match="finite"):
        summarize_path_family("iid_empirical", np.array([[0.1, np.nan]]))
    with pytest.raises(DataError, match="ruin_drawdown"):
        summarize_path_family("iid_empirical", np.array([[0.1]]), ruin_drawdown=0.0)

    with pytest.raises(DataError, match="non-empty 2-D"):
        path_metric_arrays(np.array([]))
    with pytest.raises(DataError, match="finite"):
        path_metric_arrays(np.array([[np.inf]]))
    with pytest.raises(DataError, match="ruin_drawdown"):
        path_metric_arrays(np.array([[0.1]]), ruin_drawdown=1.1)


def test_student_t_wrapper_rejects_non_finite_generator_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        path_module,
        "student_t_paths",
        lambda *_args, **_kwargs: np.array([[np.inf]], dtype=np.float64),
    )
    with pytest.raises(DataError, match="non-finite"):
        student_t_return_paths(_returns(), n_paths=1, seed=1)
