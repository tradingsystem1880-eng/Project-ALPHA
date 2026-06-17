"""The validation gauntlet orchestration — the heart of ``alpha validate``.

The CLI is the only layer the import DAG lets compose the engine with the gauntlet, so this is where
the two-tier randomized-price null, the walk-forward OOS evaluation, and the block-bootstrap BCa CIs
are wired together into a single ``GauntletReport``. Every stochastic gate draws an independent
child seed from one master seed, so the result is reproducible and order-independent (spec §11.4).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.metadata import version
from typing import TYPE_CHECKING

import numpy as np

from alpha_cli._runner import (
    OOSResult,
    RunSpec,
    run_full_backtest,
    walk_forward_oos_for_spec,
)
from alpha_cli._surrogate import make_ts_momentum_surrogate
from alpha_cli._synth import full_engine_null
from alpha_core import Bar
from alpha_validation import (
    CISummary,
    ConfidenceInterval,
    GauntletReport,
    NullResult,
    NullSummary,
    RunMetadata,
    annualized_volatility,
    block_bootstrap_ci,
    build_outcomes,
    cagr,
    max_drawdown,
    randomized_price_null,
    sharpe_ratio,
    to_returns,
)

if TYPE_CHECKING:
    from alpha_backtest.results import BacktestResult


@dataclass(frozen=True)
class GauntletParams:
    """Knobs for one gauntlet run that are not part of the backtest ``RunSpec``."""

    seed: int | None = 7
    tier1_paths: int = 1000
    tier2_paths: int = 64
    n_resamples: int = 2000
    mean_block: float = 5.0
    threshold: float = 0.95
    confidence: float = 0.95
    max_workers: int | None = None


@dataclass(frozen=True)
class GauntletOutput:
    """Everything the CLI needs to persist a run: the report + the arrays/trade log behind it."""

    report: GauntletReport
    oos: OOSResult
    result: BacktestResult


def run_gauntlet(
    bars: Sequence[Bar],
    spec: RunSpec,
    params: GauntletParams,
    *,
    run_id: str,
    snapshot_id: str | None,
) -> GauntletOutput:
    """Run the full gauntlet over ``bars`` and assemble the ``GauntletReport``."""
    ppy = spec.periods_per_year
    result = run_full_backtest(bars, spec)
    oos = walk_forward_oos_for_spec(result.equity_curve, spec)
    oos_metrics = _oos_metrics(oos, ppy)

    t1_seed, t2_seed, sharpe_seed, cagr_seed = _child_seeds(params.seed, 4)

    # Tier 1 — cheap returns-level null: the surrogate run on block-resampled price returns.
    price_returns = to_returns(np.array([b.close for b in bars], dtype=np.float64))
    surrogate = make_ts_momentum_surrogate(
        lookback=spec.lookback,
        skip=spec.skip,
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        rebalance_every=spec.rebalance_every,
        periods_per_year=ppy,
        max_leverage=spec.max_leverage,
        allow_short=spec.allow_short,
        cost_bps=spec.fee_bps + spec.slippage_bps,  # turnover-cost proxy for the cheap analogue
    )
    tier1 = randomized_price_null(
        price_returns,
        surrogate,
        n_paths=params.tier1_paths,
        block=params.mean_block,
        threshold=params.threshold,
        periods_per_year=ppy,
        seed=t1_seed,
    )
    # Tier 2 — full-engine faithfulness check, observed = the engine's walk-forward OOS Sharpe.
    tier2 = full_engine_null(
        bars,
        observed=oos_metrics["sharpe"],
        spec=spec,
        n_paths=params.tier2_paths,
        mean_block=params.mean_block,
        threshold=params.threshold,
        seed=t2_seed,
        max_workers=params.max_workers,
    )
    nulls = (_null_summary("returns_level", tier1), _null_summary("full_engine", tier2))

    # Block-bootstrap BCa CIs on the OOS returns (cagr is computed from the resampled equity path).
    sharpe_ci = block_bootstrap_ci(
        oos.oos_returns,
        lambda r: sharpe_ratio(r, periods_per_year=ppy),
        confidence=params.confidence,
        n_resamples=params.n_resamples,
        mean_block=params.mean_block,
        seed=sharpe_seed,
    )
    cagr_ci = block_bootstrap_ci(
        oos.oos_returns,
        lambda r: cagr(np.concatenate(([1.0], np.cumprod(1.0 + r))), periods_per_year=ppy),
        confidence=params.confidence,
        n_resamples=params.n_resamples,
        mean_block=params.mean_block,
        seed=cagr_seed,
    )
    cis = (_ci_summary("sharpe", sharpe_ci), _ci_summary("cagr", cagr_ci))

    outcomes = build_outcomes(oos_metrics=oos_metrics, nulls=nulls, cis=cis)
    report = GauntletReport(
        metadata=_metadata(run_id, bars, spec, params, snapshot_id),
        oos_metrics=oos_metrics,
        folds=oos.folds,
        nulls=nulls,
        cis=cis,
        outcomes=outcomes,
        passed=all(o.passed for o in outcomes),
    )
    return GauntletOutput(report=report, oos=oos, result=result)


def _child_seeds(master: int | None, n: int) -> list[int]:
    """``n`` independent integer seeds spawned from one master — gate order can't change results."""
    return [int(s.generate_state(1)[0]) for s in np.random.SeedSequence(master).spawn(n)]


def _oos_metrics(oos: OOSResult, periods_per_year: int) -> dict[str, float]:
    """Headline engine OOS metrics; NaN where a degenerate (flat) curve leaves one undefined."""
    r, eq = oos.oos_returns, oos.oos_equity
    has_var = r.size >= 2 and float(np.std(r, ddof=1)) > 0.0
    return {
        "sharpe": sharpe_ratio(r, periods_per_year=periods_per_year) if has_var else math.nan,
        "cagr": cagr(eq, periods_per_year=periods_per_year) if bool(np.all(eq > 0.0)) else math.nan,
        "annualized_vol": (
            annualized_volatility(r, periods_per_year=periods_per_year) if r.size >= 2 else math.nan
        ),
        "max_drawdown": max_drawdown(eq),
        "total_return": float(eq[-1] / eq[0] - 1.0),
    }


def _null_summary(tier: str, nr: NullResult) -> NullSummary:
    return NullSummary(
        tier=tier,
        observed=nr.observed,
        percentile=nr.percentile,
        p_value=nr.p_value,
        threshold=nr.threshold,
        passed=nr.passed,
        n_paths=nr.n_paths,
    )


def _ci_summary(metric: str, ci: ConfidenceInterval) -> CISummary:
    return CISummary(
        metric=metric, point=ci.point, lower=ci.lower, upper=ci.upper, confidence=ci.confidence
    )


def _metadata(
    run_id: str,
    bars: Sequence[Bar],
    spec: RunSpec,
    params: GauntletParams,
    snapshot_id: str | None,
) -> RunMetadata:
    return RunMetadata(
        run_id=run_id,
        symbol=bars[0].symbol,
        snapshot_id=snapshot_id,
        seed=params.seed if params.seed is not None else -1,
        periods_per_year=spec.periods_per_year,
        fee_bps=spec.fee_bps,
        slippage_bps=spec.slippage_bps,
        starting_cash=spec.starting_cash,
        lookback=spec.lookback,
        skip=spec.skip,
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        rebalance_every=spec.rebalance_every,
        max_leverage=spec.max_leverage,
        allow_short=spec.allow_short,
        train_size=spec.train_size,
        test_size=spec.test_size,
        embargo=spec.embargo,
        anchored=spec.anchored,
        n_bars=len(bars),
        first_ts=bars[0].ts.isoformat(),
        last_ts=bars[-1].ts.isoformat(),
        quantstats_version=version("quantstats-lumi"),
    )
