"""Black-Scholes pricing / greeks / implied vol: reference values, parity, round-trips, failloud."""

from __future__ import annotations

import math

import pytest

from alpha_core import DataError
from alpha_options import bs_greeks, bs_price, implied_vol

# canonical textbook case: S=100, K=100, r=5%, sigma=20%, T=1y
_ARGS = (100.0, 100.0, 0.05, 0.20, 1.0)


def test_reference_prices() -> None:
    assert bs_price(*_ARGS, "call") == pytest.approx(10.450583, abs=1e-5)
    assert bs_price(*_ARGS, "put") == pytest.approx(5.573526, abs=1e-5)


def test_put_call_parity() -> None:
    spot, strike, rate, vol, t = _ARGS
    call = bs_price(spot, strike, rate, vol, t, "call")
    put = bs_price(spot, strike, rate, vol, t, "put")
    assert (call - put) == pytest.approx(spot - strike * math.exp(-rate * t), abs=1e-10)


def test_reference_greeks() -> None:
    g = bs_greeks(*_ARGS, "call")
    assert g.delta == pytest.approx(0.636831, abs=1e-5)
    assert g.gamma == pytest.approx(0.018762, abs=1e-5)
    assert g.vega == pytest.approx(0.375240, abs=1e-5)  # per 1 vol point
    assert g.theta < 0  # calls decay
    assert g.rho == pytest.approx(0.532325, abs=1e-4)  # per 1% rate


def test_put_delta_is_call_delta_minus_one() -> None:
    call = bs_greeks(*_ARGS, "call")
    put = bs_greeks(*_ARGS, "put")
    assert put.delta == pytest.approx(call.delta - 1.0, abs=1e-10)
    assert put.gamma == pytest.approx(call.gamma, abs=1e-10)  # gamma is kind-independent


@pytest.mark.parametrize("kind", ["call", "put"])
@pytest.mark.parametrize("vol", [0.05, 0.2, 0.6, 1.2])
def test_implied_vol_round_trip(kind: str, vol: float) -> None:
    spot, strike, rate, _, t = _ARGS
    price = bs_price(spot, strike, rate, vol, t, kind)
    assert implied_vol(price, spot, strike, rate, t, kind) == pytest.approx(vol, abs=1e-6)


def test_bad_inputs_fail_loud() -> None:
    with pytest.raises(DataError):
        bs_price(-100.0, 100.0, 0.05, 0.2, 1.0, "call")  # negative spot
    with pytest.raises(DataError):
        bs_price(100.0, 100.0, 0.05, 0.2, 0.0, "call")  # zero time
    with pytest.raises(DataError):
        bs_price(100.0, 100.0, 0.05, 0.2, 1.0, "straddle")  # unknown kind
    with pytest.raises(DataError):
        bs_greeks(100.0, 100.0, 0.05, float("nan"), 1.0, "call")  # non-finite vol


def test_implied_vol_below_intrinsic_fails_loud() -> None:
    # a call struck deep ITM must be worth at least its (discounted) intrinsic value
    with pytest.raises(DataError):
        implied_vol(0.01, 200.0, 100.0, 0.05, 1.0, "call")
