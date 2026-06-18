"""Property-based tests for the pure paper-trading cost functions (Phase 4i)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from pytest import approx

from alpha_paper.funding import estimate_short_funding_cost
from alpha_paper.reconcile import realized_slippage_bps

_prices = st.floats(min_value=0.01, max_value=1e7, allow_nan=False, allow_infinity=False)
_rate = st.floats(min_value=0.0, max_value=1e5, allow_nan=False, allow_infinity=False)
_days = st.floats(min_value=0.0, max_value=3650.0, allow_nan=False, allow_infinity=False)
_notional = st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False)


@given(fill=_prices, ref=_prices)
def test_buy_and_sell_slippage_are_sign_opposites(fill: float, ref: float) -> None:
    # The same fill vs reference is an equal-and-opposite signed cost for the two sides.
    buy = realized_slippage_bps("BUY", fill, ref)
    sell = realized_slippage_bps("SELL", fill, ref)
    assert buy == -sell


@given(fill=_prices, ref=_prices)
def test_a_fill_at_the_reference_has_zero_slippage(fill: float, ref: float) -> None:
    assert realized_slippage_bps("BUY", ref, ref) == 0.0


@given(notional=_notional, rate=_rate, days=_days)
def test_funding_cost_is_non_negative_and_doubles_with_notional(
    notional: float, rate: float, days: float
) -> None:
    cost = estimate_short_funding_cost(notional, rate, days)
    assert cost >= 0.0
    assert estimate_short_funding_cost(2.0 * notional, rate, days) == approx(2.0 * cost)
