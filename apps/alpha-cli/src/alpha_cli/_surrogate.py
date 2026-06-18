"""Cheap, engine-free TS-momentum surrogate for the Tier-1 randomized-price null.

The full-engine null (Tier 2) is faithful but expensive; the bulk null distribution (Tier 1) is
built from this vectorized analogue of ``alpha_strategies.TimeSeriesMomentum`` run directly on a
returns path. It reuses the strategy's *own* pure decision functions (``ts_momentum_signal`` /
``realized_volatility`` / ``vol_target_size``) so the surrogate cannot silently drift from the real
signal and sizing logic — only the nautilus event loop, order fills and mark-to-market are dropped.

Look-ahead-free by construction: the weight that earns ``pr[t]`` (the close-t → close-(t+1) move) is
decided from closes up to and including close ``t`` only. The one modelled simplification vs the
engine is that the surrogate credits the full close-to-close move to the freshly-decided weight,
whereas the engine fills at the t+1 open (the overnight gap goes to the prior position); the Tier-2
full-engine null exists precisely to catch any material divergence this introduces.
"""

from __future__ import annotations

import numpy as np

from alpha_core import DataError
from alpha_strategies.signals import ts_momentum_signal
from alpha_strategies.sizing import realized_volatility, vol_target_size
from alpha_validation import FloatArray, StrategyFn


def make_ts_momentum_surrogate(
    *,
    lookback: int,
    skip: int,
    vol_window: int,
    target_vol: float,
    rebalance_every: int,
    periods_per_year: int = 252,
    max_leverage: float = 1.0,
    allow_short: bool = True,
    cost_bps: float = 0.0,
) -> StrategyFn:
    """Build ``f(price_returns) -> strategy_returns`` modelling vol-targeted TS momentum.

    On each rebalance bar (once warmed up) the signal and realized vol are recomputed from the
    reconstructed close path and turned into a target notional weight via ``vol_target_size``
    (``capital=price=1`` makes the returned units the weight). The weight is held between
    rebalances; ``cost_bps`` is charged on turnover ``|Δweight|`` the bar a rebalance changes it.
    Returns an array the same length as ``price_returns``. Fails loud (``DataError``) on
    ``rebalance_every < 1`` or ``vol_window < 3``.
    """
    if rebalance_every < 1:
        raise DataError(f"rebalance_every must be >= 1, got {rebalance_every}")
    if vol_window < 3:
        raise DataError(f"vol_window must be >= 3 for a realized-vol estimate, got {vol_window}")
    # first close index with enough history for BOTH a signal and a vol estimate; matches the
    # engine's _min_history = max(skip+lookback+1, vol_window+1) closes (here in 0-based bar terms)
    warm = max(skip + lookback, vol_window)
    cost_rate = cost_bps / 10_000.0

    def surrogate(price_returns: FloatArray) -> FloatArray:
        pr = np.asarray(price_returns, dtype=np.float64)
        n = pr.size
        # reconstruct a synthetic close path: closes[0]=1, closes[t]=prod(1+pr[:t]); length n+1.
        # pr[t] == closes[t+1]/closes[t] - 1, so a weight decided from closes[:t+1] never peeks.
        closes = np.empty(n + 1, dtype=np.float64)
        closes[0] = 1.0
        np.cumprod(1.0 + pr, out=closes[1:])

        weights = np.zeros(n, dtype=np.float64)
        costs = np.zeros(n, dtype=np.float64)
        weight = 0.0
        for t in range(n):  # decision at close t applies to pr[t] (close t -> close t+1)
            if t >= warm and (t - warm) % rebalance_every == 0:
                target = _target_weight(
                    closes[: t + 1],
                    lookback=lookback,
                    skip=skip,
                    vol_window=vol_window,
                    target_vol=target_vol,
                    periods_per_year=periods_per_year,
                    max_leverage=max_leverage,
                    allow_short=allow_short,
                )
                if target != weight:
                    costs[t] = cost_rate * abs(target - weight)
                weight = target
            weights[t] = weight
        return weights * pr - costs

    return surrogate


def _target_weight(
    closes_prefix: FloatArray,
    *,
    lookback: int,
    skip: int,
    vol_window: int,
    target_vol: float,
    periods_per_year: int,
    max_leverage: float,
    allow_short: bool,
) -> float:
    """Target notional weight at this close: 0 when flat/short-disallowed or vol is degenerate.

    Hands the pure strategy functions exactly the trailing windows the *engine* reads (as
    ``list[float]``, their declared input type): the signal needs the last ``skip + lookback + 1``
    closes, the vol estimate the last ``vol_window + 1`` closes (i.e. ``vol_window`` returns —
    matching ``TimeSeriesMomentum``). ``closes_prefix`` is guaranteed long enough (caller warms up).
    """
    signal = ts_momentum_signal(closes_prefix[-(skip + lookback + 1) :].tolist(), lookback, skip)
    if signal == 0 or (signal < 0 and not allow_short):
        return 0.0
    vol_closes = closes_prefix[-(vol_window + 1) :].tolist()
    vol = realized_volatility(vol_closes, periods_per_year=periods_per_year)
    if vol <= 0.0:
        return 0.0  # no dispersion to target -> hold flat (not an error)
    # capital=price=1 -> vol_target_size returns the signed notional weight directly
    return vol_target_size(
        signal, 1.0, vol, target_vol=target_vol, capital=1.0, max_leverage=max_leverage
    )
