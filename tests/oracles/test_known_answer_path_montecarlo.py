"""Known-answer and differential oracle for the path-risk Monte Carlo summaries.

``path_metric_arrays`` and ``summarize_path_family`` (``alpha_validation.path_montecarlo``) are
checked on hand-computed paths, then against a plain-Python recomputation of every per-path
outcome and every summary quantile on random paths. Wilson intervals are already checked against
published values in ``tests/unit/test_proportion.py``; here only their counts are checked.

Sources: maximum drawdown as the largest peak-to-trough fall of compounded wealth, Magdon-Ismail
and Atiya (2004), "Maximum drawdown", Risk 17(10); sample quantiles are numpy's default (Hyndman
and Fan 1996, definition 7, DOI 10.2307/2684934), the definition the summaries document.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_validation import path_metric_arrays, summarize_path_family
from tests.oracles._reference.tolerances import DIFFERENTIAL_ABS

pytestmark = pytest.mark.oracle


def test_hand_computed_paths() -> None:
    paths = np.array([[0.1, -0.5, 0.2], [-0.1, -0.1, 0.3], [0.0, 0.0, 0.0]])
    metrics = path_metric_arrays(paths)
    # wealth 1.1, 0.55, 0.66 / 0.9, 0.81, 1.053 / flat
    np.testing.assert_allclose(metrics.terminal_return, [-0.34, 0.053, 0.0], atol=DIFFERENTIAL_ABS)
    np.testing.assert_allclose(metrics.maximum_drawdown, [0.5, 0.19, 0.0], atol=DIFFERENTIAL_ABS)
    np.testing.assert_array_equal(metrics.longest_loss_streak, [1, 2, 0])
    np.testing.assert_array_equal(metrics.loss, [True, False, False])
    np.testing.assert_array_equal(metrics.ruined, [True, False, False])  # 50% is ruin


def test_a_first_day_loss_counts_against_the_starting_capital() -> None:
    metrics = path_metric_arrays(np.array([[-0.2, 0.1]]))
    assert metrics.maximum_drawdown[0] == pytest.approx(0.2, abs=DIFFERENTIAL_ABS)


def _plain(path: np.ndarray) -> tuple[float, float, int]:
    wealth, peak, worst, streak, longest = 1.0, 1.0, 0.0, 0, 0
    for value in path:
        wealth *= 1.0 + float(value)
        peak = max(peak, wealth)
        worst = max(worst, 1.0 - wealth / peak)
        streak = streak + 1 if value < 0.0 else 0
        longest = max(longest, streak)
    return wealth - 1.0, worst, longest


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_summary_matches_a_plain_python_recomputation(seed: int) -> None:
    rng = np.random.default_rng(seed)
    paths = rng.standard_t(4, size=(257, 60)) * 0.03
    paths[rng.random(paths.shape) < 0.2] = 0.0  # flat days, as an out-of-market strategy has
    summary = summarize_path_family("oracle", paths, confidence=0.9)
    rows = np.array([_plain(path) for path in paths])
    terminal, drawdown, streak = rows[:, 0], rows[:, 1], rows[:, 2]
    metrics = path_metric_arrays(paths)
    np.testing.assert_allclose(metrics.terminal_return, terminal, atol=DIFFERENTIAL_ABS)
    np.testing.assert_allclose(metrics.maximum_drawdown, drawdown, atol=DIFFERENTIAL_ABS)
    np.testing.assert_array_equal(metrics.longest_loss_streak, streak)
    expected = {
        "terminal_return_q05": np.quantile(terminal, 0.05),
        "terminal_return_q50": np.quantile(terminal, 0.50),
        "terminal_return_q95": np.quantile(terminal, 0.95),
        "maximum_drawdown_q50": np.quantile(drawdown, 0.50),
        "maximum_drawdown_q95": np.quantile(drawdown, 0.95),
        "longest_loss_streak_q95": np.quantile(streak, 0.95),
    }
    for field, value in expected.items():
        assert getattr(summary, field) == pytest.approx(float(value), abs=DIFFERENTIAL_ABS), field
    assert summary.loss_probability.successes == int(np.sum(terminal < 0.0))
    assert summary.ruin_probability.successes == int(np.sum(drawdown >= 0.5))
    assert summary.loss_probability.trials == summary.ruin_probability.trials == 257
    assert summary.loss_probability.confidence == pytest.approx(0.9, abs=DIFFERENTIAL_ABS)


def test_summary_is_invariant_to_path_order() -> None:
    rng = np.random.default_rng(7)
    paths = rng.normal(0.0005, 0.02, size=(101, 40))
    first = summarize_path_family("a", paths)
    second = summarize_path_family("a", paths[rng.permutation(101)])
    for field in (
        "terminal_return_q05", "terminal_return_q50", "terminal_return_q95",
        "maximum_drawdown_q50", "maximum_drawdown_q95", "longest_loss_streak_q95",
    ):  # fmt: skip
        assert getattr(second, field) == pytest.approx(getattr(first, field), abs=DIFFERENTIAL_ABS)
    assert second.loss_probability.successes == first.loss_probability.successes
    assert second.ruin_probability.successes == first.ruin_probability.successes
    assert (second.risk_grade, second.status) == (first.risk_grade, first.status)
