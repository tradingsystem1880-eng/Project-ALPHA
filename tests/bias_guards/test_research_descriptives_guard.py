"""Future-poison guards for the windowed descriptive statistics."""

from __future__ import annotations

import pytest

from alpha_research.descriptives import volatility_regime_tags


@pytest.mark.bias_guard
def test_volatility_regime_tags_ignore_poisoned_future_returns() -> None:
    """Tag[i] may read returns[..i] only: rewriting the future must not rewrite the past."""
    calm = [0.002, -0.002] * 40
    clean = volatility_regime_tags(calm, window=10)
    poisoned_input = [*calm[:50], *([9.9, -9.9] * 15)]
    poisoned = volatility_regime_tags(poisoned_input, window=10)
    assert poisoned[:50] == clean[:50]
