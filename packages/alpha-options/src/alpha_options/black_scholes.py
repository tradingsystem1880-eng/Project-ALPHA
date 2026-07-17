"""Black-Scholes-Merton European option pricing, greeks, and implied volatility.

Conventions (institutional, so the UI reads naturally): **vega** is per 1 volatility *point*
(1% = 0.01), **theta** is per calendar *day* (annual/365), and **rho** is per 1% rate move. All
inputs are fail-loud: non-finite or non-positive spot/strike/vol/time raises ``DataError`` rather
than silently returning ``nan``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq
from scipy.stats import norm

from alpha_core import DataError

_KINDS = ("call", "put")


@dataclass(frozen=True)
class Greeks:
    """Price + the first-order (and gamma) sensitivities under the stated conventions."""

    price: float
    delta: float
    gamma: float
    vega: float  # per 1 vol point (0.01)
    theta: float  # per calendar day
    rho: float  # per 1% rate move


def _check(spot: float, strike: float, rate: float, vol: float, t: float, kind: str) -> None:
    for name, value in (("spot", spot), ("strike", strike), ("vol", vol), ("t", t)):
        if not math.isfinite(value) or value <= 0.0:
            raise DataError(f"black_scholes: {name} must be finite and > 0, got {value!r}")
    if not math.isfinite(rate):
        raise DataError(f"black_scholes: rate must be finite, got {rate!r}")
    if kind not in _KINDS:
        raise DataError(f"black_scholes: kind must be one of {_KINDS}, got {kind!r}")


def _d1_d2(spot: float, strike: float, rate: float, vol: float, t: float) -> tuple[float, float]:
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    return d1, d1 - vol * math.sqrt(t)


def bs_price(spot: float, strike: float, rate: float, vol: float, t: float, kind: str) -> float:
    """The Black-Scholes price of a European ``kind`` option (``t`` in years)."""
    _check(spot, strike, rate, vol, t, kind)
    d1, d2 = _d1_d2(spot, strike, rate, vol, t)
    disc = math.exp(-rate * t)
    if kind == "call":
        return float(spot * norm.cdf(d1) - strike * disc * norm.cdf(d2))
    return float(strike * disc * norm.cdf(-d2) - spot * norm.cdf(-d1))


def bs_greeks(spot: float, strike: float, rate: float, vol: float, t: float, kind: str) -> Greeks:
    """Price + delta/gamma/vega/theta/rho for a European ``kind`` option."""
    _check(spot, strike, rate, vol, t, kind)
    d1, d2 = _d1_d2(spot, strike, rate, vol, t)
    sqrt_t = math.sqrt(t)
    pdf = float(norm.pdf(d1))
    disc = math.exp(-rate * t)
    gamma = pdf / (spot * vol * sqrt_t)
    vega = spot * pdf * sqrt_t / 100.0
    if kind == "call":
        delta = float(norm.cdf(d1))
        theta = (-(spot * pdf * vol) / (2 * sqrt_t) - rate * strike * disc * norm.cdf(d2)) / 365.0
        rho = strike * t * disc * float(norm.cdf(d2)) / 100.0
    else:
        delta = float(norm.cdf(d1)) - 1.0
        theta = (-(spot * pdf * vol) / (2 * sqrt_t) + rate * strike * disc * norm.cdf(-d2)) / 365.0
        rho = -strike * t * disc * float(norm.cdf(-d2)) / 100.0
    return Greeks(
        price=bs_price(spot, strike, rate, vol, t, kind),
        delta=delta,
        gamma=gamma,
        vega=vega,
        theta=float(theta),
        rho=rho,
    )


def implied_vol(
    price: float,
    spot: float,
    strike: float,
    rate: float,
    t: float,
    kind: str,
    *,
    tol: float = 1e-8,
) -> float:
    """The volatility that reprices a European ``kind`` option to ``price`` (Brent root-find).

    Fails loud (``DataError``) if ``price`` is below intrinsic value or the solve doesn't bracket a
    root in ``[1e-6, 10.0]`` (an implausible >1000% vol).
    """
    if not math.isfinite(price) or price <= 0.0:
        raise DataError(f"implied_vol: price must be finite and > 0, got {price!r}")
    _check(spot, strike, rate, 1.0, t, kind)  # validate the non-vol inputs
    disc = math.exp(-rate * t)
    intrinsic = max(0.0, spot - strike * disc) if kind == "call" else max(0.0, strike * disc - spot)
    if price < intrinsic - tol:
        raise DataError(f"implied_vol: price {price} is below intrinsic value {intrinsic}")

    def objective(vol: float) -> float:
        return bs_price(spot, strike, rate, vol, t, kind) - price

    try:
        return float(brentq(objective, 1e-6, 10.0, xtol=tol, maxiter=200))
    except ValueError as exc:
        raise DataError(
            f"implied_vol did not converge for price={price} (spot={spot}, strike={strike})"
        ) from exc
