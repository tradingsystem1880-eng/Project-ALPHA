"""Multi-asset portfolio backtest — a diversified basket of the per-symbol strategy.

The institutional form of time-series momentum is not one instrument but a *basket*: run the same
fixed-parameter strategy independently across a universe (equities, commodities, crypto, FX) and
combine the out-of-sample streams into one portfolio. Diversification across uncorrelated trends is
the edge amplifier — and because each leg reuses the fully-tested single-asset path
(``run_full_backtest`` + walk-forward OOS), this adds portfolio-level value with zero engine risk.

Streams are aligned by date; on each date the portfolio return is the weighted average over the
symbols trading that date (equal weight, or CAUSAL inverse-volatility: each leg's weight at date d
comes from the trailing window of its own OOS returns realized strictly before d — never from the
full sample, which would leak future volatility into past weights), renormalized over the symbols
present so a short-history leg never silently drags the basket. The combined stream is scored with
the same metrics + Probabilistic/Deflated Sharpe as a single run.
(Cross-sectional ranking — long winners / short losers *relative* to peers — needs a
multi-instrument engine and is future work; this is the TS-momentum-across-a-universe form.)
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from alpha_cli._runner import (
    RunSpec,
    load_bars,
    load_dividends,
    run_full_backtest,
    walk_forward_oos_for_spec,
)
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
    weight: float  # mean normalized weight across the dates the leg traded


@dataclass(frozen=True)
class PortfolioResult:
    """A diversified-basket backtest: combined OOS stream + headline metrics + per-leg summaries."""

    symbols: tuple[str, ...]
    weighting: str
    n_periods: int
    portfolio_returns: FloatArray
    portfolio_timestamps: list[datetime]
    # the basket's equity baseline: the earliest leg's first OOS equity point. Equity is 1.0 there
    # and every combined return realizes strictly after it (return i at portfolio_timestamps[i]).
    baseline_ts: datetime
    metrics: dict[str, float]  # sharpe, cagr, annualized_vol, max_drawdown, total_return
    psr: float  # probabilistic Sharpe of the basket
    dsr: float  # deflated Sharpe (single basket → equals PSR)
    sharpe_ci: ConfidenceInterval  # block-bootstrap BCa interval for the basket Sharpe
    cagr_ci: ConfidenceInterval  # block-bootstrap BCa interval for the basket CAGR
    legs: tuple[LegSummary, ...]


def _leg_series(
    spec: RunSpec, *, data_dir: Path, symbol: str
) -> tuple[datetime, dict[datetime, float]]:
    """One symbol's OOS baseline timestamp + return-by-date series (keyed by realization date)."""
    bars, _ = load_bars(symbol, data_dir=data_dir)
    dividends = load_dividends(symbol, data_dir=data_dir)
    result = run_full_backtest(bars, spec, dividends=dividends)
    oos = walk_forward_oos_for_spec(result.equity_curve, spec)
    dates = oos.oos_timestamps[1:]  # return i realizes at equity point i+1
    return oos.oos_timestamps[0], dict(zip(dates, oos.oos_returns.tolist(), strict=True))


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


def _causal_inverse_vol(
    present: Sequence[str],
    when: datetime,
    *,
    leg_dates: Mapping[str, list[datetime]],
    leg_values: Mapping[str, FloatArray],
    vol_window: int,
) -> dict[str, float]:
    """Unnormalized inverse-vol weights at ``when`` from returns realized strictly before it.

    Causal by construction: each leg's estimate is the sample std of the trailing ``vol_window``
    of its OWN OOS returns before ``when`` — never the full sample, which would let future
    volatility set past weights. A leg without >= 2 prior returns (or with zero dispersion) takes
    the mean inverse-vol of the estimated legs; while no leg has an estimate, the date is
    equal-weighted.
    """
    est: dict[str, float] = {}
    for s in present:
        k = bisect_left(leg_dates[s], when)
        hist = leg_values[s][max(0, k - vol_window) : k]
        if hist.size >= 2:
            sd = float(np.std(hist, ddof=1))
            if sd > 0.0:
                est[s] = 1.0 / sd
    if not est:
        return dict.fromkeys(present, 1.0)
    default = sum(est.values()) / len(est)
    return {s: est.get(s, default) for s in present}


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

    legs_raw = {s: _leg_series(spec, data_dir=data_dir, symbol=s) for s in symbols}
    series = {s: legs_raw[s][1] for s in symbols}
    # the basket's equity baseline: the earliest first-OOS-equity point across legs (equity 1.0
    # there; strictly before the first combined realization date by construction)
    baseline_ts = min(base for base, _ in legs_raw.values())
    leg_dates = {s: sorted(series[s]) for s in symbols}
    leg_values = {
        s: np.array([series[s][d] for d in leg_dates[s]], dtype=np.float64) for s in symbols
    }

    all_dates = sorted(set().union(*(set(s) for s in series.values())))
    port_dates: list[datetime] = []
    port_returns: list[float] = []
    weight_sums = dict.fromkeys(symbols, 0.0)
    weight_dates = dict.fromkeys(symbols, 0)
    for d in all_dates:
        present = [s for s in symbols if d in series[s]]
        if weighting == "equal":
            raw = dict.fromkeys(present, 1.0)
        else:
            raw = _causal_inverse_vol(
                present,
                d,
                leg_dates=leg_dates,
                leg_values=leg_values,
                vol_window=spec.vol_window,
            )
        norm = sum(raw.values())
        port_returns.append(sum(raw[s] * series[s][d] for s in present) / norm)
        port_dates.append(d)
        for s in present:
            weight_sums[s] += raw[s] / norm
            weight_dates[s] += 1

    returns = np.array(port_returns, dtype=np.float64)
    if returns.size < 2 or float(np.std(returns, ddof=1)) <= 0.0:
        raise DataError("portfolio OOS stream is empty or flat — nothing to evaluate")

    ppy = spec.periods_per_year
    equity = np.concatenate(([1.0], np.cumprod(1.0 + returns)))
    dsr_res = deflated_sharpe(returns, threshold=0.95)
    sharpe_ci = block_bootstrap_ci(
        returns,
        _resample_sharpe(ppy),
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
            oos_sharpe=_safe_sharpe(leg_values[s], ppy),
            weight=weight_sums[s] / weight_dates[s] if weight_dates[s] else 0.0,
        )
        for s in symbols
    )
    return PortfolioResult(
        symbols=tuple(symbols),
        weighting=weighting,
        n_periods=returns.size,
        portfolio_returns=returns,
        portfolio_timestamps=port_dates,
        baseline_ts=baseline_ts,
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
