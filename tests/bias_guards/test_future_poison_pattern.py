"""The future-poison template: poisoning post-cutoff data must not change pre-cutoff outputs.
Later phases apply this same pattern to the real PIT accessor and strategy signals."""
from __future__ import annotations

import math

import pytest

pytestmark = pytest.mark.bias_guard


def causal_rolling_mean(xs: list[float], window: int) -> list[float]:
    out: list[float] = []
    for i in range(len(xs)):
        lo = max(0, i - window + 1)
        chunk = xs[lo : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def test_future_poison_does_not_change_past_outputs() -> None:
    clean = [1.0, 2.0, 3.0, 4.0, 5.0]
    cutoff = 2  # outputs at indices 0..cutoff must not depend on indices > cutoff
    poisoned = clean[: cutoff + 1] + [math.nan, math.nan]
    assert (
        causal_rolling_mean(clean, 3)[: cutoff + 1]
        == causal_rolling_mean(poisoned, 3)[: cutoff + 1]
    )
