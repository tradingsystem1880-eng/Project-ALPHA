"""Bias guard: each signal reads ONLY its trailing window — bars before it can't change the result.

A common look-ahead/leak bug is averaging or scanning the whole series instead of the intended
trailing window. These guards corrupt every bar *older* than the window with an extreme value and
assert the signal is unchanged; if the boundary were wrong, the corruption would leak in and flip
it. (Causality of the decide-on-close / fill-next-open execution is guarded at the engine level in
``tests/integration/test_nautilus_engine.py``.)
"""

from __future__ import annotations

import pytest

from alpha_strategies.signals import (
    breakout_signal,
    ma_crossover_signal,
    zscore_reversion_signal,
)

_SPIKE = 1.0e9  # finite, positive (so _check_prices never trips) but ruinous if it leaked in


@pytest.mark.bias_guard
def test_ma_crossover_ignores_bars_before_the_slow_window() -> None:
    slow, fast = 4, 2
    base = [float(i) for i in range(1, 9)]  # rising → long
    clean = ma_crossover_signal(base, fast=fast, slow=slow)
    poisoned = [_SPIKE] * (len(base) - slow) + base[-slow:]
    assert ma_crossover_signal(poisoned, fast=fast, slow=slow) == clean == 1


@pytest.mark.bias_guard
def test_zscore_reversion_ignores_bars_before_the_window() -> None:
    window = 5
    base = [10.0, 10.0, 10.0, 10.0, 20.0]  # overbought → short
    clean = zscore_reversion_signal(base, window=window, entry_z=1.5)
    poisoned = [_SPIKE] * 4 + base
    assert zscore_reversion_signal(poisoned, window=window, entry_z=1.5) == clean == -1


@pytest.mark.bias_guard
def test_breakout_ignores_bars_before_the_channel() -> None:
    window = 3
    base = [10.0, 11.0, 12.0, 13.0, 20.0]  # new high → long
    clean = breakout_signal(base, base, base, window=window)
    poisoned = [_SPIKE] * 4 + base
    assert breakout_signal(poisoned, poisoned, poisoned, window=window) == clean == 1
