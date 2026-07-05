"""Cross-sectional momentum — a dollar-neutral relative-strength book over a universe.

Distinct from time-series momentum (which trades each asset on its *own* trend), cross-sectional
momentum ranks the universe each rebalance and goes long the winners / short the losers *relative*
to peers — a separate, well-documented institutional alpha source. This is a vectorized,
look-ahead-safe panel backtest (consistent with the project's returns-level analogues like the
Tier-1 surrogate): weights decided from closes up to date ``t`` earn the ``t -> t+1`` move, ranks
use only past returns, and the book is vol-targeted from its own trailing realized volatility. The
resulting OOS stream is scored with the same metrics + Probabilistic/Deflated Sharpe + BCa intervals
as a single run. (A full-engine cross-sectional path — per-instrument t+1-open fills and frictions —
needs a multi-instrument engine and is future work.)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from alpha_cli._runner import load_bars
from alpha_core import DataError
from alpha_validation import (
    ConfidenceInterval,
    FloatArray,
    annualized_volatility,
    block_bootstrap_ci,
    cagr,
    deflated_sharpe,
    max_drawdown,
    sharpe_ratio,
)


@dataclass(frozen=True)
class CrossSectionalResult:
    """A cross-sectional momentum backtest: the OOS stream + headline metrics + uncertainty."""

    symbols: tuple[str, ...]
    long_short: bool
    n_long: int  # names per leg
    n_periods: int
    returns: FloatArray
    timestamps: list[datetime]
    metrics: dict[str, float]
    psr: float
    dsr: float
    sharpe_ci: ConfidenceInterval
    cagr_ci: ConfidenceInterval


def _close_panel(symbols: Sequence[str], *, data_dir: Path) -> tuple[list[datetime], FloatArray]:
    """Align every symbol's closes on their common dates → ``(dates, T×N close matrix)``."""
    by_symbol: dict[str, dict[datetime, float]] = {}
    for sym in symbols:
        bars, _ = load_bars(sym, data_dir=data_dir)
        by_symbol[sym] = {b.ts: b.close for b in bars}
    common = sorted(set.intersection(*(set(d) for d in by_symbol.values())))
    if len(common) < 3:
        raise DataError(f"cross-sectional needs >= 3 common dates, got {len(common)}")
    panel = np.array([[by_symbol[s][d] for s in symbols] for d in common], dtype=np.float64)
    return common, panel


def _resample_sharpe(periods_per_year: int) -> Callable[[FloatArray], float]:
    """Sharpe for bootstrap resamples: a zero-variance block resample scores 0.0, not a crash.

    Mirrors the gauntlet's convention - a sparse/flat resample has no excess return per unit risk,
    and one degenerate draw must not abort the whole CI.
    """

    def stat(r: FloatArray) -> float:
        if r.size >= 2 and float(np.std(r, ddof=1)) > 0.0:
            return sharpe_ratio(r, periods_per_year=periods_per_year)
        return 0.0

    return stat


def run_cross_sectional(
    symbols: Sequence[str],
    *,
    data_dir: Path,
    lookback: int = 252,
    skip: int = 21,
    vol_window: int = 63,
    target_vol: float = 0.15,
    rebalance_every: int = 21,
    top_quantile: float = 0.3,
    long_short: bool = True,
    max_leverage: float = 2.0,
    fee_bps: float = 1.0,
    slippage_bps: float = 2.0,
    periods_per_year: int = 252,
    n_resamples: int = 2000,
    mean_block: float = 5.0,
    confidence: float = 0.95,
    seed: int | None = 7,
) -> CrossSectionalResult:
    """Backtest a cross-sectional momentum book over ``symbols`` and score the OOS stream.

    Each rebalance ranks the universe by trailing (``lookback``, skipping ``skip``) return; the top
    ``top_quantile`` go long and (if ``long_short``) the bottom go short, equal-weighted and
    dollar-neutral, then the whole book is scaled toward ``target_vol`` by its own trailing realized
    vol (capped at ``max_leverage``). Fails loud (``DataError``) on too few symbols/dates or a
    degenerate stream.
    """
    if len(symbols) < 2:
        raise DataError(f"cross-sectional needs >= 2 symbols, got {len(symbols)}")
    if len(set(symbols)) != len(symbols):
        raise DataError(f"duplicate symbols: {symbols}")
    if not 0.0 < top_quantile <= 0.5:
        raise DataError(f"top_quantile must be in (0, 0.5], got {top_quantile}")
    n_symbols = len(symbols)
    k = max(1, round(top_quantile * n_symbols))
    if long_short and 2 * k > n_symbols:
        k = n_symbols // 2
    if k < 1:
        raise DataError(f"too few symbols ({n_symbols}) to form a leg at quantile {top_quantile}")

    dates, panel = _close_panel(symbols, data_dir=data_dir)
    warmup = skip + lookback  # first decision index with a full score window
    n_dates = len(dates)
    if warmup + 1 >= n_dates:
        raise DataError(f"not enough history ({n_dates} dates) for lookback+skip={warmup}")

    cost_rate = (fee_bps + slippage_bps) / 10_000.0
    weights = np.zeros(n_symbols, dtype=np.float64)
    out_returns: list[float] = []
    out_dates: list[datetime] = []
    realized: list[float] = []  # portfolio returns so far, for trailing-vol scaling
    for step, t in enumerate(range(warmup, n_dates - 1)):  # decide at t, earn the t -> t+1 move
        cost = 0.0
        if step % rebalance_every == 0:
            new_weights = _target_weights(
                panel[t], panel[t - skip], panel[t - skip - lookback], k=k, long_short=long_short
            )
            new_weights *= _vol_scale(
                realized, target_vol, vol_window, max_leverage, periods_per_year
            )
            cost = cost_rate * float(np.abs(new_weights - weights).sum())  # turnover frictions
            weights = new_weights
        asset_returns = panel[t + 1] / panel[t] - 1.0
        r = float(np.dot(weights, asset_returns)) - cost
        realized.append(r)
        out_returns.append(r)
        out_dates.append(dates[t + 1])

    returns = np.array(out_returns, dtype=np.float64)
    if returns.size < 2 or float(np.std(returns, ddof=1)) <= 0.0:
        raise DataError("cross-sectional OOS stream is empty or flat — nothing to evaluate")

    equity = np.concatenate(([1.0], np.cumprod(1.0 + returns)))
    dsr_res = deflated_sharpe(returns, threshold=0.95)
    sharpe_ci = block_bootstrap_ci(
        returns,
        _resample_sharpe(periods_per_year),
        confidence=confidence,
        n_resamples=n_resamples,
        mean_block=mean_block,
        seed=seed,
    )
    cagr_ci = block_bootstrap_ci(
        returns,
        lambda x: cagr(
            np.concatenate(([1.0], np.cumprod(1.0 + x))), periods_per_year=periods_per_year
        ),
        confidence=confidence,
        n_resamples=n_resamples,
        mean_block=mean_block,
        seed=seed,
    )
    return CrossSectionalResult(
        symbols=tuple(symbols),
        long_short=long_short,
        n_long=k,
        n_periods=returns.size,
        returns=returns,
        timestamps=out_dates,
        metrics={
            "sharpe": sharpe_ratio(returns, periods_per_year=periods_per_year),
            "cagr": cagr(equity, periods_per_year=periods_per_year),
            "annualized_vol": annualized_volatility(returns, periods_per_year=periods_per_year),
            "max_drawdown": max_drawdown(equity),
            "total_return": float(equity[-1] / equity[0] - 1.0),
        },
        psr=dsr_res.psr,
        dsr=dsr_res.dsr,
        sharpe_ci=sharpe_ci,
        cagr_ci=cagr_ci,
    )


def _target_weights(
    now: FloatArray, recent: FloatArray, past: FloatArray, *, k: int, long_short: bool
) -> FloatArray:
    """Dollar-neutral (or long-only) equal-weight book from the cross-sectional momentum ranking."""
    scores = recent / past - 1.0  # trailing return, skipping the most recent ``skip`` bars
    order = np.argsort(scores)  # ascending: losers first, winners last
    w = np.zeros(now.size, dtype=np.float64)
    winners = order[-k:]
    if long_short:
        losers = order[:k]
        w[winners] = 0.5 / k  # +0.5 gross long
        w[losers] = -0.5 / k  # -0.5 gross short → dollar-neutral, gross 1.0
    else:
        w[winners] = 1.0 / k  # long-only, gross 1.0
    return w


def _vol_scale(
    realized: list[float],
    target_vol: float,
    vol_window: int,
    max_leverage: float,
    periods_per_year: int,
) -> float:
    """Scale the book toward ``target_vol`` using its own trailing realized vol (causal, capped)."""
    if len(realized) < vol_window:
        return 1.0  # not enough history yet — run at base gross
    recent = np.array(realized[-vol_window:], dtype=np.float64)
    if float(np.std(recent, ddof=1)) <= 0.0:
        return 1.0
    vol = annualized_volatility(recent, periods_per_year=periods_per_year)
    return float(min(target_vol / vol, max_leverage)) if vol > 0.0 else 1.0
