"""The optimizer and CSCV share one historical tolerant selection-score convention."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_cli._optim import _safe_period_sharpe
from alpha_core import DataError
from alpha_validation.metrics import sharpe_ratio
from alpha_validation.overfitting import probability_of_backtest_overfitting, selection_sharpe


@pytest.mark.parametrize("values", [[], [0.1], [0.0, 0.0], [0.2, 0.2]])
def test_degenerate_selection_score_stays_zero_while_strict_sharpe_rejects(
    values: list[float],
) -> None:
    returns = np.asarray(values, dtype=np.float64)
    assert selection_sharpe(returns) == pytest.approx(0.0)
    assert _safe_period_sharpe(returns) == pytest.approx(0.0)
    with pytest.raises(DataError):
        sharpe_ratio(returns, periods_per_year=1)


def test_one_owner_preserves_sample_std_units_and_cscv_result() -> None:
    returns = np.array([0.0, 0.1, 0.2], dtype=np.float64)
    assert _safe_period_sharpe is selection_sharpe
    assert selection_sharpe(returns) == pytest.approx(1.0)
    assert selection_sharpe(returns) == pytest.approx(sharpe_ratio(returns, periods_per_year=1))
    assert selection_sharpe(-returns) == pytest.approx(-1.0)
    matrix = np.array(
        [
            [0.01, -0.02],
            [0.03, -0.01],
            [-0.02, 0.01],
            [0.02, 0.03],
            [-0.01, 0.04],
            [0.02, -0.01],
            [0.03, 0.01],
            [-0.01, 0.02],
        ]
    )
    default = probability_of_backtest_overfitting(matrix, n_blocks=4)
    explicit = probability_of_backtest_overfitting(matrix, n_blocks=4, statistic=selection_sharpe)
    np.testing.assert_allclose(default.logits, explicit.logits, rtol=1e-14, atol=1e-14)
    assert default.pbo == pytest.approx(explicit.pbo)
