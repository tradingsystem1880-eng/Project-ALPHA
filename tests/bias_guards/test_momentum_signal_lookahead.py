"""The momentum signal must provably ignore the most recent `skip` bars (spec §7).

Those bars are the ones closest to "now" and most prone to leaking near-future information into
the decision; the skip-adjusted encoding excludes them, and this guard pins that property.
"""

from __future__ import annotations

import pytest

from alpha_strategies.signals import ts_momentum_signal

pytestmark = pytest.mark.bias_guard


def test_recent_skipped_bars_never_change_the_signal() -> None:
    lookback, skip = 5, 2
    base = [100.0 + i for i in range(10)]  # uptrend -> long
    assert ts_momentum_signal(base, lookback, skip) == 1

    # crash the most recent `skip` bars; if the signal read them it would flip to short.
    poisoned = base[:-skip] + [0.01] * skip
    assert ts_momentum_signal(poisoned, lookback, skip) == 1  # unchanged: skipped bars excluded
