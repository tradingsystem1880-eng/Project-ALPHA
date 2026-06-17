"""Return/risk metrics for the validation gauntlet (spec §8, §11).

Pure ``numpy`` functions that fail loud (``DataError``) on degenerate input. They consume either
an *equity curve* — net-liquidation values sampled once per session, as produced by
``alpha_backtest.BacktestResult.equity_curve`` — or the simple per-period returns derived from it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from alpha_core import DataError

FloatArray = npt.NDArray[np.float64]


def _as_equity(equity: Sequence[float], name: str) -> FloatArray:
    arr = np.asarray(equity, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise DataError(f"{name} needs >= 2 equity points, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{name} requires finite equity values")
    if bool(np.any(arr <= 0.0)):
        raise DataError(f"{name} requires strictly-positive equity (net-liq must stay > 0)")
    return arr


def _as_returns(returns: Sequence[float], name: str) -> FloatArray:
    arr = np.asarray(returns, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise DataError(f"{name} needs >= 2 returns, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{name} requires finite returns")
    return arr


def to_returns(equity: Sequence[float]) -> FloatArray:
    """Simple per-period returns ``r_t = E_t / E_{t-1} - 1`` from an equity curve.

    Requires >= 2 finite, strictly-positive equity points; fails loud otherwise.
    """
    arr = _as_equity(equity, "to_returns")
    return arr[1:] / arr[:-1] - 1.0


def sharpe_ratio(
    returns: Sequence[float], *, periods_per_year: int = 252, risk_free: float = 0.0
) -> float:
    """Annualized Sharpe ratio of a per-period return series.

    ``mean(excess) / std(excess, ddof=1) · sqrt(periods_per_year)`` where
    ``excess = returns - risk_free / periods_per_year``. Fails loud on < 2 returns or a
    degenerate (zero-variance) series, for which the ratio is undefined.
    """
    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    excess = _as_returns(returns, "sharpe_ratio") - risk_free / periods_per_year
    std = float(np.std(excess, ddof=1))
    if std <= 0.0:
        raise DataError("sharpe_ratio undefined for a zero-variance return series")
    return float(np.mean(excess)) / std * math.sqrt(periods_per_year)


def annualized_volatility(returns: Sequence[float], *, periods_per_year: int = 252) -> float:
    """Annualized volatility: sample std (ddof=1) of per-period returns × sqrt(periods_per_year)."""
    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    r = _as_returns(returns, "annualized_volatility")
    return float(np.std(r, ddof=1)) * math.sqrt(periods_per_year)


def cagr(equity: Sequence[float], *, periods_per_year: int = 252) -> float:
    """Compound annual growth rate: ``(E_last / E_first) ** (periods_per_year / n_steps) - 1``.

    ``n_steps`` is the number of return periods (``len(equity) - 1``).
    """
    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    arr = _as_equity(equity, "cagr")
    n_steps = arr.size - 1
    return float((arr[-1] / arr[0]) ** (periods_per_year / n_steps) - 1.0)


def max_drawdown(equity: Sequence[float]) -> float:
    """Worst peak-to-trough decline as a non-positive fraction (``0.0`` if monotonically rising).

    ``-0.25`` means the deepest trough sat 25% below its prior running peak.
    """
    arr = _as_equity(equity, "max_drawdown")
    running_peak = np.maximum.accumulate(arr)
    return float((arr / running_peak - 1.0).min())
