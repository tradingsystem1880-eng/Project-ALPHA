"""Metamorphic relations for ``alpha_validation.metrics``.

Each relation is a property the textbook definition guarantees; a sign, scale or
annualisation bug in the implementation breaks at least one of them.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from alpha_core import DataError
from alpha_validation.metrics import (
    annualized_volatility,
    cagr,
    max_drawdown,
    sharpe_ratio,
    to_returns,
)
from tests.oracles._reference.tolerances import FLOAT64_REL

pytestmark = pytest.mark.oracle

_RETURNS = st.lists(
    st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False),
    min_size=3,
    max_size=200,
).filter(lambda r: np.std(r, ddof=1) > 1e-9)


@given(_RETURNS, st.floats(min_value=0.01, max_value=100.0))
@settings(max_examples=100, deadline=None)
def test_sharpe_is_scale_invariant(returns: list[float], k: float) -> None:
    """SR(k·r) == SR(r) for k > 0 (mean and std scale together)."""
    r = np.asarray(returns)
    assert sharpe_ratio(k * r) == pytest.approx(sharpe_ratio(r), rel=FLOAT64_REL, abs=1e-9)


@given(_RETURNS)
@settings(max_examples=100, deadline=None)
def test_sharpe_flips_sign_under_negation(returns: list[float]) -> None:
    r = np.asarray(returns)
    assert sharpe_ratio(-r) == pytest.approx(-sharpe_ratio(r), rel=FLOAT64_REL, abs=1e-12)


@given(_RETURNS, st.integers(min_value=1, max_value=365))
@settings(max_examples=100, deadline=None)
def test_sharpe_annualises_by_sqrt_periods(returns: list[float], periods: int) -> None:
    """SR(P) / SR(1) == sqrt(P): annualisation is a pure sqrt(P) rescaling."""
    r = np.asarray(returns)
    base = sharpe_ratio(r, periods_per_year=1)
    assert sharpe_ratio(r, periods_per_year=periods) == pytest.approx(
        base * math.sqrt(periods), rel=FLOAT64_REL, abs=1e-12
    )
    assert annualized_volatility(r, periods_per_year=periods) == pytest.approx(
        annualized_volatility(r, periods_per_year=1) * math.sqrt(periods), rel=FLOAT64_REL
    )


@given(_RETURNS, st.floats(min_value=-0.05, max_value=0.05))
@settings(max_examples=100, deadline=None)
def test_sharpe_risk_free_shifts_the_mean_only(returns: list[float], rf: float) -> None:
    """SR(r, rf) == SR(r - rf/P, 0): the risk-free rate is a per-period mean shift, not a scale."""
    r = np.asarray(returns)
    shifted = r - rf / 252
    assert sharpe_ratio(r, risk_free=rf) == pytest.approx(sharpe_ratio(shifted), rel=FLOAT64_REL)


def test_sharpe_of_constant_series_fails_loud() -> None:
    with pytest.raises(DataError, match="zero-variance"):
        sharpe_ratio([0.01, 0.01, 0.01, 0.01])


def _compound(returns: list[float]) -> list[float]:
    return list(np.cumprod([100.0, *[1.0 + r for r in returns]]))


# Equity curves built from bounded per-step returns, so a 252-period annualisation cannot
# overflow (cagr fails loud on inf by design — that is a separate, deliberate behaviour).
_EQUITY = st.lists(
    st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=200,
).map(_compound)


@given(_EQUITY, st.floats(min_value=0.01, max_value=100.0))
@settings(max_examples=100, deadline=None)
def test_returns_drawdown_and_cagr_are_scale_invariant(equity: list[float], k: float) -> None:
    e = np.asarray(equity)
    assert np.allclose(to_returns(k * e), to_returns(e), rtol=FLOAT64_REL, atol=1e-12)
    assert max_drawdown(k * e) == pytest.approx(max_drawdown(e), abs=1e-12)
    assert cagr(k * e) == pytest.approx(cagr(e), rel=FLOAT64_REL, abs=1e-12)


@given(_EQUITY)
@settings(max_examples=100, deadline=None)
def test_max_drawdown_is_bounded_and_zero_iff_monotone(equity: list[float]) -> None:
    e = np.asarray(equity)
    dd = max_drawdown(e)
    assert -1.0 < dd <= 0.0
    monotone = bool(np.all(np.diff(e) >= 0))
    assert (dd == 0.0) == monotone


@given(_EQUITY)
@settings(max_examples=100, deadline=None)
def test_returns_compound_back_to_the_terminal_ratio(equity: list[float]) -> None:
    """prod(1 + r_t) == E_last / E_first: to_returns loses nothing."""
    e = np.asarray(equity)
    assert float(np.prod(1.0 + to_returns(e))) == pytest.approx(e[-1] / e[0], rel=FLOAT64_REL)


def test_cagr_of_a_pure_annual_double_is_one() -> None:
    """A curve that exactly doubles over one year of periods has CAGR == 1.0."""
    equity = np.geomspace(1.0, 2.0, 253)  # 252 return periods
    assert cagr(equity, periods_per_year=252) == pytest.approx(1.0, rel=FLOAT64_REL)
