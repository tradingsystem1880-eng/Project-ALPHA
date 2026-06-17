"""Volatility-target sizing (spec §7): scale notional to a constant annualized vol."""

from __future__ import annotations

import math

import pytest

from alpha_core import DataError
from alpha_strategies.sizing import realized_volatility, vol_target_size


def test_realized_volatility_zero_for_constant_returns() -> None:
    # constant +1%/bar -> zero dispersion -> zero realized vol
    closes = [100.0 * (1.01**i) for i in range(10)]
    assert realized_volatility(closes) == pytest.approx(0.0, abs=1e-9)


def test_realized_volatility_annualizes_sample_std() -> None:
    closes = [100.0, 110.0, 99.0]  # returns: +0.10, -0.10
    rets = [0.10, -0.10]
    mean = sum(rets) / 2
    var = sum((r - mean) ** 2 for r in rets) / 1  # ddof=1
    expected = math.sqrt(var) * math.sqrt(252)
    assert realized_volatility(closes) == pytest.approx(expected)


def test_realized_volatility_fails_loud() -> None:
    with pytest.raises(DataError):
        realized_volatility([100.0, 101.0])  # too few
    with pytest.raises(DataError):
        realized_volatility([100.0, -1.0, 102.0])  # non-positive price


def test_vol_target_scales_notional_and_signs() -> None:
    # target 10% vs realized 20% -> half-capital notional; long -> positive units
    units = vol_target_size(1, price=50.0, annualized_vol=0.20, target_vol=0.10, capital=100_000.0)
    assert units == pytest.approx(0.5 * 100_000.0 / 50.0)  # notional 50k / price 50
    short = vol_target_size(-1, price=50.0, annualized_vol=0.20, target_vol=0.10, capital=100_000.0)
    assert short == pytest.approx(-units)


def test_vol_target_caps_leverage() -> None:
    # realized 5% vs target 10% would imply 2x; max_leverage=1.0 caps notional at capital
    units = vol_target_size(
        1, price=10.0, annualized_vol=0.05, target_vol=0.10, capital=100_000.0, max_leverage=1.0
    )
    assert units == pytest.approx(100_000.0 / 10.0)  # capped at 1x capital


def test_flat_signal_is_zero() -> None:
    assert (
        vol_target_size(0, price=10.0, annualized_vol=0.2, target_vol=0.1, capital=1_000.0) == 0.0
    )


def test_vol_target_fails_loud() -> None:
    with pytest.raises(DataError):
        vol_target_size(1, price=0.0, annualized_vol=0.2, target_vol=0.1, capital=1_000.0)
    with pytest.raises(DataError):
        vol_target_size(1, price=10.0, annualized_vol=0.0, target_vol=0.1, capital=1_000.0)
    with pytest.raises(DataError):
        vol_target_size(
            2, price=10.0, annualized_vol=0.2, target_vol=0.1, capital=1_000.0
        )  # bad signal


def test_non_finite_inputs_fail_loud() -> None:
    with pytest.raises(DataError):
        realized_volatility([100.0, float("nan"), 102.0])
    with pytest.raises(DataError):
        vol_target_size(1, price=float("inf"), annualized_vol=0.2, target_vol=0.1, capital=1_000.0)
