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
from alpha_cli._strategies import surrogate_for
from alpha_cli._synth import full_engine_null
from alpha_core import Bar
from alpha_validation import (
    CISummary,
    ConfidenceInterval,
    CPCVSummary,
    DSRSummary,
    FloatArray,
    GauntletReport,
    NullResult,
    NullSummary,
    RunMetadata,
    Statistic,
    annualized_volatility,
    block_bootstrap_ci,
    build_outcomes,
    cagr,
    combinatorial_purged_splits,
    deflated_sharpe,
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
    dsr_threshold: float = 0.95  # deflated-Sharpe pass bar (P(true SR > deflation benchmark))
    cpcv_groups: int = 6  # CPCV partition count over the OOS stream
    cpcv_test_groups: int = 2  # groups held out per CPCV fold
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

    if not _has_variance(oos.oos_returns):
        # A flat / zero-variance OOS (e.g. a long-flat strategy whose only signals are disallowed
        # shorts) has no measurable risk-adjusted edge: the headline Sharpe is undefined and ranking
        # it against a null or bootstrapping it is meaningless. Fail gracefully — degenerate gates,
        # overall FAIL — instead of letting an undefined-Sharpe error abort the run.
        nulls = (_degenerate_null("returns_level"), _degenerate_null("full_engine"))
        cis = (
            _degenerate_ci("sharpe", params.confidence),
            _degenerate_ci("cagr", params.confidence),
        )
        dsr = _degenerate_dsr(params.dsr_threshold)
        cpcv = _degenerate_cpcv()
    else:
        safe_sharpe = _safe_sharpe(ppy)
        # Tier 1 — cheap returns-level null: the strategy's surrogate on block-resampled returns.
        price_returns = to_returns(np.array([b.close for b in bars], dtype=np.float64))
        surrogate = surrogate_for(spec)
        tier1 = randomized_price_null(
            price_returns,
            surrogate,
            statistic=safe_sharpe,
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

        # Block-bootstrap BCa CIs on the OOS returns (cagr from the resampled equity path). The
        # safe Sharpe treats a zero-variance resample as 0.0 so a sparse OOS can't abort the CI.
        sharpe_ci = block_bootstrap_ci(
            oos.oos_returns,
            safe_sharpe,
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

        # Deflated/Probabilistic Sharpe on the OOS stream (single-config: n_trials=1 → DSR=PSR) and
        # the CPCV distribution of OOS Sharpe across combinatorial time-slice folds.
        dsr = _dsr_summary(oos.oos_returns, params.dsr_threshold)
        cpcv = _cpcv_summary(oos.oos_returns, params, ppy)

    outcomes = build_outcomes(oos_metrics=oos_metrics, nulls=nulls, cis=cis, dsr=dsr, cpcv=cpcv)
    report = GauntletReport(
        metadata=_metadata(run_id, bars, spec, params, snapshot_id),
        oos_metrics=oos_metrics,
        folds=oos.folds,
        nulls=nulls,
        cis=cis,
        outcomes=outcomes,
        passed=all(o.passed for o in outcomes),
        dsr=dsr,
        cpcv=cpcv,
    )
    return GauntletOutput(report=report, oos=oos, result=result)


def _child_seeds(master: int | None, n: int) -> list[int]:
    """``n`` independent integer seeds spawned from one master — gate order can't change results."""
    return [int(s.generate_state(1)[0]) for s in np.random.SeedSequence(master).spawn(n)]


def _has_variance(returns: FloatArray) -> bool:
    """True when there are >= 2 returns with non-zero dispersion (a Sharpe is well defined)."""
    return bool(returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0)


def _safe_sharpe(periods_per_year: int) -> Statistic:
    """A Sharpe statistic that scores a zero-variance resample as 0.0 instead of raising.

    Used for the bootstrap CI + Tier-1 null so a sparse (mostly-flat) OOS — where individual block
    resamples can land all-identical — yields a finite distribution rather than aborting the run. A
    flat resample has no excess return per unit risk, so 0.0 is the natural convention here.
    """

    def stat(returns: FloatArray) -> float:
        if not _has_variance(returns):
            return 0.0
        return sharpe_ratio(returns, periods_per_year=periods_per_year)

    return stat


def _degenerate_null(tier: str) -> NullSummary:
    """A not-passed null tier for when the real OOS is flat (no statistic to rank)."""
    return NullSummary(
        tier=tier,
        observed=math.nan,
        percentile=math.nan,
        p_value=math.nan,
        threshold=math.nan,
        passed=False,
        n_paths=0,
    )


def _degenerate_ci(metric: str, confidence: float) -> CISummary:
    """A NaN confidence interval for when the OOS is flat (the bootstrap is undefined)."""
    return CISummary(
        metric=metric, point=math.nan, lower=math.nan, upper=math.nan, confidence=confidence
    )


def _dsr_summary(oos_returns: FloatArray, threshold: float) -> DSRSummary:
    """Deflated/Probabilistic Sharpe of the OOS stream (single config → n_trials=1, DSR=PSR)."""
    res = deflated_sharpe(oos_returns, threshold=threshold)
    return DSRSummary(
        sharpe=res.sharpe,
        psr=res.psr,
        dsr=res.dsr,
        expected_max_sharpe=res.expected_max_sharpe,
        n_trials=res.n_trials,
        threshold=res.threshold,
        passed=res.passed,
    )


def _degenerate_dsr(threshold: float) -> DSRSummary:
    """A not-passed DSR summary for a flat OOS (PSR/DSR undefined on zero variance)."""
    return DSRSummary(
        sharpe=math.nan,
        psr=math.nan,
        dsr=math.nan,
        expected_max_sharpe=math.nan,
        n_trials=1,
        threshold=threshold,
        passed=False,
    )


def _cpcv_summary(
    oos_returns: FloatArray, params: GauntletParams, periods_per_year: int
) -> CPCVSummary:
    """Distribution of OOS Sharpe across CPCV folds of the OOS stream (degenerate folds score 0)."""
    if oos_returns.size < params.cpcv_groups:
        return _degenerate_cpcv()  # too few OOS points to partition into groups
    splits = combinatorial_purged_splits(
        oos_returns.size,
        n_groups=params.cpcv_groups,
        n_test_groups=params.cpcv_test_groups,
        embargo=0,  # the OOS stream is already purged/embargoed at the walk-forward level
    )
    sharpes = np.array(
        [_fold_sharpe(oos_returns[sp.test], periods_per_year) for sp in splits], dtype=np.float64
    )
    mean = float(np.mean(sharpes))
    std = float(np.std(sharpes, ddof=1)) if sharpes.size >= 2 else 0.0
    return CPCVSummary(
        n_folds=int(sharpes.size),
        mean_sharpe=mean,
        std_sharpe=std,
        frac_positive=float(np.mean(sharpes > 0.0)),
        passed=mean > 0.0,
    )


def _fold_sharpe(slice_: FloatArray, periods_per_year: int) -> float:
    """Annualized Sharpe of one CPCV test slice; 0.0 for a degenerate (flat/short) slice."""
    if slice_.size >= 2 and float(np.std(slice_, ddof=1)) > 0.0:
        return sharpe_ratio(slice_, periods_per_year=periods_per_year)
    return 0.0


def _degenerate_cpcv() -> CPCVSummary:
    """A not-passed CPCV summary for when the OOS is flat or too short to partition."""
    return CPCVSummary(
        n_folds=0, mean_sharpe=math.nan, std_sharpe=math.nan, frac_positive=math.nan, passed=False
    )


def _oos_metrics(oos: OOSResult, periods_per_year: int) -> dict[str, float]:
    """Headline engine OOS metrics; NaN where a degenerate (flat) curve leaves one undefined."""
    r, eq = oos.oos_returns, oos.oos_equity
    has_var = _has_variance(r)
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
        strategy_name=spec.strategy_name,
        strategy_params=spec.strategy_params,
    )
