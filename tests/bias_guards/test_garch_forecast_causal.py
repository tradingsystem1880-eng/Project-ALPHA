"""The GARCH vol forecast must be a pure function of its window — future returns cannot leak in."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_validation.volatility import garch_volatility_forecast

pytestmark = pytest.mark.bias_guard


def test_forecast_unchanged_by_future_poison() -> None:
    rng = np.random.default_rng(3)
    series = rng.normal(0.0, 0.01, 500)
    window = series[:300]

    baseline = garch_volatility_forecast(window)
    # poison everything after the window with absurd values; the forecast never sees them
    poisoned_tail = series.copy()
    poisoned_tail[300:] = 9.9e3
    after = garch_volatility_forecast(poisoned_tail[:300])

    assert baseline == after
