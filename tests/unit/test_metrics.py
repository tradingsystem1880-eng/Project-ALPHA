"""Return/risk metrics consumed by the validation gates (spec §8, §11)."""

from __future__ import annotations

import math

import pytest

from alpha_core import DataError
from alpha_validation.metrics import (
    annualized_volatility,
    cagr,
    max_drawdown,
    sharpe_ratio,
    to_returns,
)


def test_to_returns_simple_period_returns() -> None:
    rets = to_returns([100.0, 110.0, 99.0])  # +0.10 then -0.10
    assert rets == pytest.approx([0.10, -0.10])


def test_to_returns_fails_loud() -> None:
    with pytest.raises(DataError):
        to_returns([100.0])  # need >= 2 points
    with pytest.raises(DataError):
        to_returns([100.0, 0.0])  # net-liq must stay > 0
    with pytest.raises(DataError):
        to_returns([100.0, float("nan")])  # non-finite


def test_sharpe_ratio_matches_manual_annualization() -> None:
    rets = [0.01, -0.005, 0.02, 0.0, 0.015]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)  # ddof=1
    expected = mean / math.sqrt(var) * math.sqrt(252)
    assert sharpe_ratio(rets) == pytest.approx(expected)


def test_sharpe_ratio_subtracts_risk_free() -> None:
    rets = [0.01, 0.02, 0.015, 0.005]
    # a positive risk-free rate lowers the Sharpe
    assert sharpe_ratio(rets, risk_free=0.05) < sharpe_ratio(rets, risk_free=0.0)


def test_sharpe_ratio_zero_variance_fails_loud() -> None:
    with pytest.raises(DataError):
        sharpe_ratio([0.01, 0.01, 0.01])  # undefined: no dispersion


def test_annualized_volatility_scales_with_root_time() -> None:
    rets = [0.02, -0.01, 0.03, -0.02, 0.01]
    var = sum((r - sum(rets) / len(rets)) ** 2 for r in rets) / (len(rets) - 1)
    assert annualized_volatility(rets) == pytest.approx(math.sqrt(var) * math.sqrt(252))
    # quarterly (ppy=4) annualizes by sqrt(4)=2 of the daily-style estimate at ppy=1
    assert annualized_volatility(rets, periods_per_year=4) == pytest.approx(
        2.0 * annualized_volatility(rets, periods_per_year=1)
    )


def test_cagr_compounds_to_horizon() -> None:
    # doubling over exactly one year (ppy == n_periods) -> +100%
    assert cagr([100.0, 200.0], periods_per_year=1) == pytest.approx(1.0)
    # doubling over half a year (ppy=2, 1 period) -> (2)^2 - 1 = 300%
    assert cagr([100.0, 200.0], periods_per_year=2) == pytest.approx(3.0)


def test_max_drawdown_is_worst_peak_to_trough() -> None:
    # peak 120 then trough 60 -> -50% is the worst; a later partial recovery doesn't beat it
    assert max_drawdown([100.0, 120.0, 60.0, 90.0]) == pytest.approx(-0.5)
    assert max_drawdown([100.0, 110.0, 120.0]) == pytest.approx(0.0)  # monotone up -> no drawdown


def test_metrics_fail_loud_on_degenerate_input() -> None:
    with pytest.raises(DataError):
        sharpe_ratio([0.01])  # < 2 returns
    with pytest.raises(DataError):
        cagr([100.0])  # < 2 equity points
    with pytest.raises(DataError):
        max_drawdown([float("inf"), 1.0])  # non-finite
