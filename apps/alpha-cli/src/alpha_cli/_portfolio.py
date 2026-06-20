"""Multi-asset portfolio backtest — a diversified basket of the per-symbol strategy.

The institutional form of time-series momentum is not one instrument but a *basket*: run the same
fixed-parameter strategy independently across a universe (equities, commodities, crypto, FX) and
combine the out-of-sample streams into one portfolio. Diversification across uncorrelated trends is
the edge amplifier — and because each leg reuses the fully-tested single-asset path
(``run_full_backtest`` + walk-forward OOS), this adds portfolio-level value with zero engine risk.

Streams are aligned by date; on each date the portfolio return is the weighted average over the
symbols trading that date (equal weight, or inverse-volatility from each leg's own OOS vol),
renormalized over the symbols present so a short-history leg never silently drags the basket. The
combined stream is scored with the same metrics + Probabilistic/Deflated Sharpe as a single run.
(Cross-sectional ranking — long winners / short losers *relative* to peers — needs a
multi-instrument engine and is future work; this is the TS-momentum-across-a-universe form.)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from alpha_cli._runner import RunSpec, load_bars, run_full_backtest, walk_forward_oos_for_spec
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

_WEIGHTINGS = ("equal", "inverse_vol")


@dataclass(frozen=True)
class LegSummary:
    """One symbol's contribution to the basket."""

    symbol: str
    n_oos: int
    oos_sharpe: float
    weight: float  # nominal portfolio weight (pre per-date renormalization)


@dataclass(frozen=True)
class PortfolioResult:
    """A diversified-basket backtest: combined OOS stream + headline metrics + per-leg summaries."""

    symbols: tuple[str, ...]
    weighting: str
    n_periods: int
    portfolio_returns: FloatArray
    portfolio_timestamps: list[datetime]
    metrics: dict[str, float]  # sharpe, cagr, annualized_vol, max_drawdown, total_return
    psr: float  # probabilistic Sharpe of the basket
    dsr: float  # deflated Sharpe (single basket → equals PSR)
    sharpe_ci: ConfidenceInterval  # block-bootstrap BCa interval for the basket Sharpe
    cagr_ci: ConfidenceInterval  # block-bootstrap BCa interval for the basket CAGR
    legs: tuple[LegSummary, ...]


def _leg_series(spec: RunSpec, *, data_dir: Path, symbol: str) -> dict[datetime, float]:
    """One symbol's OOS return-by-date series (returns[i] keyed by the date it realizes)."""
    bars, _ = load_bars(symbol, data_dir=data_dir)
    result = run_full_backtest(bars, spec)
    oos = walk_forward_oos_for_spec(result.equity_curve, spec)
    dates = oos.oos_timestamps[1:]  # return i realizes at equity point i+1
    return dict(zip(dates, oos.oos_returns.tolist(), strict=True))


def _leg_weights(
    series: Mapping[str, Mapping[datetime, float]], weighting: str
) -> dict[str, float]:
    """Nominal weights per symbol: equal, or inverse-volatility from each leg's own OOS returns."""
    symbols = list(series)
    if weighting == "equal":
        return {s: 1.0 / len(symbols) for s in symbols}
    inv = {}
    for s in symbols:
        rets = np.array(list(series[s].values()), dtype=np.float64)
        vol = float(np.std(rets, ddof=1)) if rets.size >= 2 else 0.0
        inv[s] = 1.0 / vol if vol > 0.0 else 0.0
    total = sum(inv.values())
    if total <= 0.0:
        raise DataError("inverse-vol weighting undefined: every leg has zero volatility")
    return {s: w / total for s, w in inv.items()}


def run_portfolio(
    symbols: Sequence[str],
    spec: RunSpec,
    *,
    data_dir: Path,
    weighting: str = "equal",
    n_resamples: int = 2000,
    mean_block: float = 5.0,
    confidence: float = 0.95,
    seed: int | None = 7,
) -> PortfolioResult:
    """Backtest a basket of ``symbols`` under ``spec`` and combine their OOS streams.

    Reports the basket's headline metrics, Probabilistic/Deflated Sharpe, and block-bootstrap BCa
    confidence intervals for its Sharpe and CAGR (the uncertainty band on what you'd trade).
    Fails loud (``DataError``) on an unknown ``weighting``, fewer than 2 symbols, a degenerate
    (flat) combined stream, or any leg whose data won't load / clear the warmup floor.
    """
    if weighting not in _WEIGHTINGS:
        raise DataError(f"unknown weighting {weighting!r}; known: {_WEIGHTINGS}")
    if len(symbols) < 2:
        raise DataError(f"a portfolio needs >= 2 symbols, got {len(symbols)}")
    if len(set(symbols)) != len(symbols):
        raise DataError(f"duplicate symbols in portfolio: {symbols}")

    series = {s: _leg_series(spec, data_dir=data_dir, symbol=s) for s in symbols}
    weights = _leg_weights(series, weighting)

    all_dates = sorted(set().union(*(set(s) for s in series.values())))
    port_dates: list[datetime] = []
    port_returns: list[float] = []
    for d in all_dates:
        present = [(s, series[s][d]) for s in symbols if d in series[s]]
        norm = sum(weights[s] for s, _ in present)
        if norm <= 0.0:
            continue  # only zero-weight legs trade this date
        port_returns.append(sum(weights[s] * r for s, r in present) / norm)
        port_dates.append(d)

    returns = np.array(port_returns, dtype=np.float64)
    if returns.size < 2 or float(np.std(returns, ddof=1)) <= 0.0:
        raise DataError("portfolio OOS stream is empty or flat — nothing to evaluate")

    ppy = spec.periods_per_year
    equity = np.concatenate(([1.0], np.cumprod(1.0 + returns)))
    dsr_res = deflated_sharpe(returns, threshold=0.95)
    sharpe_ci = block_bootstrap_ci(
        returns,
        lambda r: sharpe_ratio(r, periods_per_year=ppy),
        confidence=confidence,
        n_resamples=n_resamples,
        mean_block=mean_block,
        seed=seed,
    )
    cagr_ci = block_bootstrap_ci(
        returns,
        lambda r: cagr(np.concatenate(([1.0], np.cumprod(1.0 + r))), periods_per_year=ppy),
        confidence=confidence,
        n_resamples=n_resamples,
        mean_block=mean_block,
        seed=seed,
    )
    legs = tuple(
        LegSummary(
            symbol=s,
            n_oos=len(series[s]),
            oos_sharpe=_safe_sharpe(np.array(list(series[s].values()), dtype=np.float64), ppy),
            weight=weights[s],
        )
        for s in symbols
    )
    return PortfolioResult(
        symbols=tuple(symbols),
        weighting=weighting,
        n_periods=returns.size,
        portfolio_returns=returns,
        portfolio_timestamps=port_dates,
        metrics={
            "sharpe": sharpe_ratio(returns, periods_per_year=ppy),
            "cagr": cagr(equity, periods_per_year=ppy),
            "annualized_vol": annualized_volatility(returns, periods_per_year=ppy),
            "max_drawdown": max_drawdown(equity),
            "total_return": float(equity[-1] / equity[0] - 1.0),
        },
        psr=dsr_res.psr,
        dsr=dsr_res.dsr,
        sharpe_ci=sharpe_ci,
        cagr_ci=cagr_ci,
        legs=legs,
    )


def _safe_sharpe(returns: FloatArray, periods_per_year: int) -> float:
    if returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0:
        return sharpe_ratio(returns, periods_per_year=periods_per_year)
    return float("nan")
