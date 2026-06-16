"""Time-series momentum signal (spec §7): sign of the skip-adjusted trailing return."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_strategies.signals import ts_momentum_signal


def test_uptrend_is_long() -> None:
    closes = [100.0 + i for i in range(12)]  # strictly increasing
    assert ts_momentum_signal(closes, lookback=5, skip=2) == 1


def test_downtrend_is_short() -> None:
    closes = [100.0 - i for i in range(12)]  # strictly decreasing
    assert ts_momentum_signal(closes, lookback=5, skip=2) == -1


def test_flat_window_is_zero() -> None:
    closes = [100.0] * 12
    assert ts_momentum_signal(closes, lookback=5, skip=2) == 0


def test_insufficient_history_is_zero() -> None:
    # needs skip + lookback + 1 = 8 closes; 7 is too few
    assert ts_momentum_signal([100.0] * 7, lookback=5, skip=2) == 0


def test_skip_uses_correct_reference_points() -> None:
    # recent = closes[-1-skip], past = closes[-1-skip-lookback]; only these drive the sign.
    closes = [10.0] * 13
    closes[-1 - 2] = 20.0  # recent (skip=2) up vs past (10.0) -> long
    assert ts_momentum_signal(closes, lookback=5, skip=2) == 1


def test_bad_params_fail_loud() -> None:
    with pytest.raises(DataError):
        ts_momentum_signal([1.0] * 10, lookback=0, skip=2)
    with pytest.raises(DataError):
        ts_momentum_signal([1.0] * 10, lookback=5, skip=-1)


def test_non_positive_reference_price_fails_loud() -> None:
    closes = [100.0] * 12
    closes[-1 - 2] = 0.0  # the recent reference price is invalid
    with pytest.raises(DataError):
        ts_momentum_signal(closes, lookback=5, skip=2)
