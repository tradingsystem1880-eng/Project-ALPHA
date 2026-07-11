"""forecast_signal: deadband edges + fail-loud cases."""

from __future__ import annotations

import math

import pytest

from alpha_core import DataError
from alpha_strategies.signals import forecast_signal


def test_above_deadband_long() -> None:
    # +100 bps horizon-end log-return vs a 25 bps deadband
    assert forecast_signal(100.0, [100.0, 100.0 * math.exp(0.01)], 25.0) == 1


def test_below_deadband_short() -> None:
    assert forecast_signal(100.0, [100.0 * math.exp(-0.01)], 25.0) == -1


def test_inside_deadband_flat_both_sides() -> None:
    assert forecast_signal(100.0, [100.0 * math.exp(0.001)], 25.0) == 0  # +10 bps < 25
    assert forecast_signal(100.0, [100.0 * math.exp(-0.001)], 25.0) == 0


def test_just_inside_deadband_is_flat() -> None:
    # r_bps a hair under the deadband -> not strictly greater -> flat (the exact-equality
    # boundary is FP-unstable by nature; the contract is strict inequality)
    assert forecast_signal(100.0, [100.0 * math.exp(24.999 / 1e4)], 25.0) == 0
    assert forecast_signal(100.0, [100.0 * math.exp(-24.999 / 1e4)], 25.0) == 0


def test_only_horizon_end_matters() -> None:
    # a wild path that ends where it started is flat
    assert forecast_signal(100.0, [150.0, 50.0, 100.0], 25.0) == 0


def test_zero_deadband_trades_any_drift() -> None:
    assert forecast_signal(100.0, [100.01], 0.0) == 1
    assert forecast_signal(100.0, [99.99], 0.0) == -1
    assert forecast_signal(100.0, [100.0], 0.0) == 0


def test_fail_loud_cases() -> None:
    with pytest.raises(DataError, match="deadband_bps"):
        forecast_signal(100.0, [101.0], -1.0)
    with pytest.raises(DataError, match="empty"):
        forecast_signal(100.0, [], 25.0)
    with pytest.raises(DataError, match="finite"):
        forecast_signal(0.0, [101.0], 25.0)
    with pytest.raises(DataError, match="finite"):
        forecast_signal(100.0, [float("nan")], 25.0)
    with pytest.raises(DataError, match="finite"):
        forecast_signal(100.0, [-5.0], 25.0)
