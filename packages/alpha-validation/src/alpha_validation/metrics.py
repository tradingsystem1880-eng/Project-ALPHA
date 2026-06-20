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
FloatSeq = Sequence[float] | FloatArray  # public functions accept a plain sequence or a numpy array


def _as_equity(equity: FloatSeq, name: str) -> FloatArray:
    arr = np.asarray(equity, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise DataError(f"{name} needs >= 2 equity points, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{name} requires finite equity values")
    if bool(np.any(arr <= 0.0)):
        raise DataError(f"{name} requires strictly-positive equity (net-liq must stay > 0)")
    return arr


def _as_returns(returns: FloatSeq, name: str) -> FloatArray:
    arr = np.asarray(returns, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise DataError(f"{name} needs >= 2 returns, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{name} requires finite returns")
    return arr


def to_returns(equity: FloatSeq) -> FloatArray:
    """Simple per-period returns ``r_t = E_t / E_{t-1} - 1`` from an equity curve.

    Requires >= 2 finite, strictly-positive equity points; fails loud otherwise.
    """
    arr = _as_equity(equity, "to_returns")
    return arr[1:] / arr[:-1] - 1.0


def sharpe_ratio(
    returns: FloatSeq, *, periods_per_year: int = 252, risk_free: float = 0.0
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


def annualized_volatility(returns: FloatSeq, *, periods_per_year: int = 252) -> float:
    """Annualized volatility: sample std (ddof=1) of per-period returns × sqrt(periods_per_year)."""
    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    r = _as_returns(returns, "annualized_volatility")
    return float(np.std(r, ddof=1)) * math.sqrt(periods_per_year)


def cagr(equity: FloatSeq, *, periods_per_year: int = 252) -> float:
    """Compound annual growth rate: ``(E_last / E_first) ** (periods_per_year / n_steps) - 1``.

    ``n_steps`` is the number of return periods (``len(equity) - 1``).
    """
    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    arr = _as_equity(equity, "cagr")
    n_steps = arr.size - 1
    with np.errstate(over="ignore"):  # an extreme ratio may overflow; caught loudly just below
        result = float((arr[-1] / arr[0]) ** (periods_per_year / n_steps) - 1.0)
    if not math.isfinite(result):
        raise DataError(f"cagr overflowed to a non-finite value: {result!r}")
    return result


def max_drawdown(equity: FloatSeq) -> float:
    """Worst peak-to-trough decline as a non-positive fraction (``0.0`` if monotonically rising).

    ``-0.25`` means the deepest trough sat 25% below its prior running peak.
    """
    arr = _as_equity(equity, "max_drawdown")
    running_peak = np.maximum.accumulate(arr)
    return float((arr / running_peak - 1.0).min())


def value_at_risk(returns: FloatSeq, *, confidence: float = 0.95) -> float:
    """Historical Value-at-Risk as a non-negative per-period loss fraction.

    The ``1 - confidence`` quantile of the return distribution, sign-flipped so a worse tail reads
    as a larger positive loss (``0.03`` ≈ "5%-of-the-time the period loses at least 3%"). A
    non-negative profit at that quantile clamps to ``0.0`` (no loss). Fails loud on < 2 returns,
    non-finite values, or ``confidence`` outside ``(0, 1)``.
    """
    if not 0.0 < confidence < 1.0:
        raise DataError(f"confidence must be in (0, 1), got {confidence}")
    r = _as_returns(returns, "value_at_risk")
    quantile = float(np.quantile(r, 1.0 - confidence))
    return max(0.0, -quantile)


def expected_shortfall(returns: FloatSeq, *, confidence: float = 0.95) -> float:
    """Expected shortfall (CVaR) as a non-negative per-period loss fraction.

    The mean of the returns at or below the ``1 - confidence`` quantile — the average loss *given*
    that the VaR threshold was breached. Always at least as heavy as :func:`value_at_risk` because
    it averages the worst tail (which includes the VaR point). Same fail-loud contract as VaR.
    """
    if not 0.0 < confidence < 1.0:
        raise DataError(f"confidence must be in (0, 1), got {confidence}")
    r = _as_returns(returns, "expected_shortfall")
    quantile = float(np.quantile(r, 1.0 - confidence))
    tail = r[r <= quantile]  # min return always satisfies r <= quantile, so tail is never empty
    return max(0.0, -float(np.mean(tail)))
