"""Future-poison guards for the trailing D1 rolling statistics (ADR-0025)."""

from __future__ import annotations

import pytest

from alpha_research.ic import rolling_rank_ic
from alpha_research.stability import rolling_effect_size


@pytest.mark.bias_guard
def test_rolling_rank_ic_ignores_poisoned_future_observations() -> None:
    """Series[i] may read pairs [..i] only: rewriting the future must not rewrite the past."""
    signal = [float(i % 7) for i in range(60)]
    outcome = [float((i * 3) % 11) for i in range(60)]
    clean = rolling_rank_ic(signal, outcome, window=10)
    poisoned_signal = [*signal[:40], *([999.0] * 20)]
    poisoned_outcome = [*outcome[:40], *([-999.0] * 20)]
    poisoned = rolling_rank_ic(poisoned_signal, poisoned_outcome, window=10)
    assert poisoned[:40] == clean[:40]


@pytest.mark.bias_guard
def test_rolling_effect_size_ignores_poisoned_future_outcomes() -> None:
    outcomes = [0.01, -0.005, 0.02, 0.0, 0.015, -0.01] * 10
    clean = rolling_effect_size(outcomes, window=10)
    poisoned = rolling_effect_size([*outcomes[:45], *([9.9] * 15)], window=10)
    assert poisoned[:45] == clean[:45]
