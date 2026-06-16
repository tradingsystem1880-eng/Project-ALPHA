"""Volatility-targeted position sizing (spec §7). Pure functions, fail loud on bad inputs."""

from __future__ import annotations

import math
from collections.abc import Sequence

from alpha_core import DataError


def realized_volatility(closes: Sequence[float], *, periods_per_year: int = 252) -> float:
    """Annualized realized volatility: sample std (ddof=1) of simple returns × √periods_per_year.

    Requires >= 3 positive, finite closes (>= 2 returns); fails loud (``DataError``) otherwise.
    """
    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    if len(closes) < 3:
        raise DataError(f"realized_volatility needs >= 3 closes, got {len(closes)}")
    for c in closes:
        if not math.isfinite(c) or c <= 0:
            raise DataError(f"realized_volatility requires finite > 0 prices, got {c!r}")
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    mean = sum(rets) / len(rets)
    variance = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(variance) * math.sqrt(periods_per_year)


def vol_target_size(
    signal: int,
    price: float,
    annualized_vol: float,
    *,
    target_vol: float,
    capital: float,
    max_leverage: float = 1.0,
) -> float:
    """Signed position size (units) scaling notional to ``target_vol``.

    ``notional = min(capital · target_vol / annualized_vol, capital · max_leverage)``;
    ``units = signal · notional / price``. Returns ``0.0`` for a flat (``0``) signal. Fails loud
    (``DataError``) on a signal outside ``{-1, 0, 1}`` or non-positive ``price`` / ``target_vol`` /
    ``capital`` / ``max_leverage`` / ``annualized_vol`` (for a non-flat signal).
    """
    if signal not in (-1, 0, 1):
        raise DataError(f"signal must be one of -1/0/1, got {signal}")
    if signal == 0:
        return 0.0
    for label, value in (
        ("price", price),
        ("target_vol", target_vol),
        ("capital", capital),
        ("max_leverage", max_leverage),
        ("annualized_vol", annualized_vol),
    ):
        if not math.isfinite(value) or value <= 0:
            raise DataError(f"vol_target_size {label} must be finite > 0, got {value!r}")
    notional = min(capital * (target_vol / annualized_vol), capital * max_leverage)
    return signal * notional / price
