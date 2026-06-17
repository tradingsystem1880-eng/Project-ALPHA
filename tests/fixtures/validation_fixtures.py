"""Toy strategies and price processes for exercising the validation gauntlet offline."""

from __future__ import annotations

import numpy as np

from alpha_validation.metrics import FloatArray


def causal_momentum(price_returns: FloatArray) -> FloatArray:
    """A look-ahead-free momentum strategy: yesterday's return sign is today's position.

    Profits only when returns are positively autocorrelated, so it earns a real edge on a trending
    series and ~0 on i.i.d. noise — exactly the signal the randomized-price null should detect.
    """
    position = np.sign(price_returns[:-1])
    return position * price_returns[1:]


def ar1_returns(n: int, phi: float, *, seed: int, sigma: float = 0.01) -> FloatArray:
    """An AR(1) return series with autocorrelation ``phi`` — the exploitable structure to detect."""
    rng = np.random.default_rng(seed)
    eps = rng.normal(0.0, sigma, size=n)
    out = np.empty(n, dtype=np.float64)
    out[0] = eps[0]
    for t in range(1, n):
        out[t] = phi * out[t - 1] + eps[t]
    return out
