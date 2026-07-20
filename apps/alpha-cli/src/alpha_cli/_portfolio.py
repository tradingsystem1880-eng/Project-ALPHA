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

import math
from bisect import bisect_left
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from alpha_cli._runner import (
    RunSpec,
    combine_source_fingerprints,
    fresh_oos_execution,
    load_bars,
    load_dividends,
    source_fingerprint,
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
class PortfolioAllocation:
    """One causal sleeve allocation and its contribution over an OOS return interval."""

    start_ts: datetime
    ts: datetime
    symbol: str
    weight: float
    leg_return: float
    contribution: float
    leg_gross_exposure: float
    leg_net_exposure: float
    weighted_gross_exposure: float
    weighted_net_exposure: float


@dataclass(frozen=True)
class PortfolioCorrelation:
    """One exact pairwise Pearson cell over intersecting OOS realization timestamps."""

    asset_a: str
    asset_b: str
    metric_name: str
    metric_unit: str
    correlation: float | None
    sample_count: int
    aligned_oos: bool
    frequency: str
    oos_start: str | None
    oos_end: str | None
    association_not_causation: bool


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
    allocations: tuple[PortfolioAllocation, ...]
    correlations: tuple[PortfolioCorrelation, ...]
    portfolio_gross_exposure: FloatArray
    portfolio_net_exposure: FloatArray
    source_fingerprint: str


@dataclass(frozen=True)
class _LegSeries:
    baseline_ts: datetime
    returns: dict[datetime, float]
    interval_starts: dict[datetime, datetime]
    gross_exposure: dict[datetime, float]
    net_exposure: dict[datetime, float]
    source_fingerprint: str


def _leg_series(
    spec: RunSpec,
    *,
    data_dir: Path,
    symbol: str,
    snapshot_id: str | None,
    as_of: datetime | None,
) -> _LegSeries:
    """One symbol's OOS returns plus engine-observed interval-start exposure evidence."""
    bars, _ = load_bars(symbol, data_dir=data_dir, snapshot_id=snapshot_id, as_of=as_of)
    dividends = load_dividends(symbol, data_dir=data_dir, snapshot_id=snapshot_id, as_of=as_of)
    oos, execution = fresh_oos_execution(bars, spec, dividends=dividends)
    dates = oos.oos_timestamps[1:]  # return i realizes at equity point i+1
    starts = oos.oos_timestamps[:-1]
    state_by_ts = {row.ts: row for row in execution.portfolio_state_trace}
    if len(state_by_ts) != len(execution.portfolio_state_trace):
        raise DataError(f"portfolio state trace has duplicate timestamps for {symbol!r}")
    missing = [ts for ts in starts if ts not in state_by_ts]
    if missing:
        raise DataError(
            f"portfolio state trace does not cover OOS interval starts for {symbol!r}: "
            + ", ".join(ts.isoformat() for ts in missing[:3])
        )
    return _LegSeries(
        baseline_ts=oos.oos_timestamps[0],
        returns=dict(zip(dates, oos.oos_returns.tolist(), strict=True)),
        interval_starts=dict(zip(dates, starts, strict=True)),
        gross_exposure={
            end: float(state_by_ts[start].gross_exposure)
            for start, end in zip(starts, dates, strict=True)
        },
        net_exposure={
            end: float(state_by_ts[start].net_exposure)
            for start, end in zip(starts, dates, strict=True)
        },
        source_fingerprint=source_fingerprint(bars, dividends=dividends),
    )


def _pairwise_correlations(
    symbols: Sequence[str],
    series: Mapping[str, Mapping[datetime, float]],
) -> tuple[PortfolioCorrelation, ...]:
    """Build a dense ordered matrix from exact pairwise OOS timestamp intersections."""
    values: dict[tuple[str, str], tuple[float | None, int, str | None, str | None]] = {}
    for left_index, asset_a in enumerate(symbols):
        for asset_b in symbols[left_index:]:
            common = sorted(set(series[asset_a]).intersection(series[asset_b]))
            correlation: float | None = None
            if len(common) >= 2:
                left = np.asarray([series[asset_a][ts] for ts in common], dtype=np.float64)
                right = np.asarray([series[asset_b][ts] for ts in common], dtype=np.float64)
                if float(np.std(left, ddof=1)) > 0.0 and float(np.std(right, ddof=1)) > 0.0:
                    raw = float(np.corrcoef(left, right)[0, 1])
                    if math.isfinite(raw):
                        correlation = max(-1.0, min(1.0, raw))
            cell = (
                correlation,
                len(common),
                common[0].date().isoformat() if common else None,
                common[-1].date().isoformat() if common else None,
            )
            values[(asset_a, asset_b)] = cell
            values[(asset_b, asset_a)] = cell
    return tuple(
        PortfolioCorrelation(
            asset_a=asset_a,
            asset_b=asset_b,
            metric_name="pearson_correlation",
            metric_unit="coefficient",
            correlation=values[(asset_a, asset_b)][0],
            sample_count=values[(asset_a, asset_b)][1],
            aligned_oos=True,
            frequency="1d",
            oos_start=values[(asset_a, asset_b)][2],
            oos_end=values[(asset_a, asset_b)][3],
            association_not_causation=True,
        )
        for asset_a in symbols
        for asset_b in symbols
    )


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
    snapshot_id: str | None = None,
    as_of: datetime | None = None,
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

    legs_raw = {
        s: _leg_series(
            spec,
            data_dir=data_dir,
            symbol=s,
            snapshot_id=snapshot_id,
            as_of=as_of,
        )
        for s in symbols
    }
    series = {s: legs_raw[s].returns for s in symbols}
    # the basket's equity baseline: the earliest first-OOS-equity point across legs (equity 1.0
    # there; strictly before the first combined realization date by construction)
    baseline_ts = min(leg.baseline_ts for leg in legs_raw.values())
    leg_dates = {s: sorted(series[s]) for s in symbols}
    leg_values = {
        s: np.array([series[s][d] for d in leg_dates[s]], dtype=np.float64) for s in symbols
    }

    all_dates = sorted(set().union(*(set(s) for s in series.values())))
    port_dates: list[datetime] = []
    port_returns: list[float] = []
    allocations: list[PortfolioAllocation] = []
    portfolio_gross_exposure: list[float] = []
    portfolio_net_exposure: list[float] = []
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
        weights = {s: raw[s] / norm for s in present}
        port_returns.append(sum(weights[s] * series[s][d] for s in present))
        port_dates.append(d)
        gross = 0.0
        net = 0.0
        for s in present:
            weight = weights[s]
            leg = legs_raw[s]
            weighted_gross = weight * leg.gross_exposure[d]
            weighted_net = weight * leg.net_exposure[d]
            allocations.append(
                PortfolioAllocation(
                    start_ts=leg.interval_starts[d],
                    ts=d,
                    symbol=s,
                    weight=weight,
                    leg_return=series[s][d],
                    contribution=weight * series[s][d],
                    leg_gross_exposure=leg.gross_exposure[d],
                    leg_net_exposure=leg.net_exposure[d],
                    weighted_gross_exposure=weighted_gross,
                    weighted_net_exposure=weighted_net,
                )
            )
            gross += weighted_gross
            net += weighted_net
            weight_sums[s] += weight
            weight_dates[s] += 1
        portfolio_gross_exposure.append(gross)
        portfolio_net_exposure.append(net)

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
        allocations=tuple(allocations),
        correlations=_pairwise_correlations(symbols, series),
        portfolio_gross_exposure=np.asarray(portfolio_gross_exposure, dtype=np.float64),
        portfolio_net_exposure=np.asarray(portfolio_net_exposure, dtype=np.float64),
        source_fingerprint=combine_source_fingerprints(
            {symbol: legs_raw[symbol].source_fingerprint for symbol in symbols}
        ),
    )


def _safe_sharpe(returns: FloatArray, periods_per_year: int) -> float:
    if returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0:
        return sharpe_ratio(returns, periods_per_year=periods_per_year)
    return float("nan")
