"""Synthetic price paths for the full-engine randomized-price null (Tier 2, spec §7.4).

The cheap Tier-1 null resamples *returns*; the faithfulness check (Tier 2) resamples whole OHLCV
bars and re-runs the real engine on each synthetic path. ``synthetic_bar_paths`` generates those
paths; the full-engine orchestration that runs them through ``run_backtest`` is added alongside.
"""

from __future__ import annotations

import multiprocessing
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np

from alpha_cli._runner import RunSpec, run_full_backtest, walk_forward_oos_for_spec
from alpha_core import Bar, DataError
from alpha_validation import NullResult, sharpe_ratio, stationary_bootstrap_indices

# below this path count the pool's spin-up costs more than it saves; run in-process
_SERIAL_THRESHOLD = 8


def synthetic_bar_paths(
    bars: Sequence[Bar], *, n_paths: int, mean_block: float, seed: int | None
) -> list[list[Bar]]:
    """Block-bootstrap whole OHLCV rows into ``n_paths`` synthetic series of the same length.

    Resampling whole bars (not close-to-close returns) preserves each bar's intrabar OHLC
    consistency and the realistic close(t)->open(t+1) gap the fill model consumes; only the
    *ordering* of blocks is randomized, which is what destroys the exploitable trend. Each picked
    row keeps its own prices but is re-stamped onto the original (strictly-monotone) session axis,
    so the synthetic feed stays chronological and ``Bar`` invariants hold by construction. Fails
    loud (``DataError``) on fewer than 2 bars or ``n_paths < 1``.
    """
    n = len(bars)
    if n < 2:
        raise DataError(f"synthetic_bar_paths needs >= 2 bars, got {n}")
    if n_paths < 1:
        raise DataError(f"n_paths must be >= 1, got {n_paths}")
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(n, mean_block=mean_block, n_resamples=n_paths, rng=rng)
    timeline = [b.ts for b in bars]
    paths: list[list[Bar]] = []
    for row in idx:
        path = [
            Bar(
                symbol=bars[int(j)].symbol,
                ts=timeline[i],
                open=bars[int(j)].open,
                high=bars[int(j)].high,
                low=bars[int(j)].low,
                close=bars[int(j)].close,
                volume=bars[int(j)].volume,
            )
            for i, j in enumerate(row)
        ]
        paths.append(path)
    return paths


@dataclass(frozen=True)
class _SynthTask:
    """One picklable unit of full-engine work: a synthetic path + the run spec."""

    bars: list[Bar]
    spec: RunSpec


def _oos_sharpe_for_path(task: _SynthTask) -> float:
    """Run the real engine on one synthetic path; return its walk-forward OOS Sharpe.

    A flat (zero-variance) OOS — common when the strategy finds no trend in a trendless path —
    has no risk-adjusted edge, so it scores 0.0 rather than raising. Top-level and picklable so a
    process pool can dispatch it.
    """
    result = run_full_backtest(task.bars, task.spec)
    oos = walk_forward_oos_for_spec(result.equity_curve, task.spec)
    returns = oos.oos_returns
    if returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0:
        return sharpe_ratio(returns, periods_per_year=task.spec.periods_per_year)
    return 0.0


def full_engine_null(
    bars: Sequence[Bar],
    *,
    observed: float,
    spec: RunSpec,
    n_paths: int,
    mean_block: float,
    threshold: float = 0.95,
    seed: int | None = None,
    max_workers: int | None = None,
) -> NullResult:
    """Tier-2 faithfulness check: the OOS Sharpe null from re-running the engine on synthetic paths.

    Each of ``n_paths`` block-bootstrapped price paths is run through the *real* engine and scored
    by the same walk-forward OOS Sharpe as the observed run, then ``observed`` is ranked against the
    resulting distribution. Percentile and the one-sided MC p-value use the same formula as the
    cheap Tier-1 ``randomized_price_null`` so the tiers are directly comparable. Determinism comes
    from deterministic path generation (seeded) and a deterministic engine — order-preserving
    ``map`` makes the result independent of whether it ran serially or in a (spawn) process pool.
    Fails loud on a bad ``threshold`` or a non-finite null statistic.
    """
    if not 0.0 < threshold < 1.0:
        raise DataError(f"threshold must be in (0, 1), got {threshold}")
    paths = synthetic_bar_paths(bars, n_paths=n_paths, mean_block=mean_block, seed=seed)
    tasks = [_SynthTask(bars=p, spec=spec) for p in paths]

    if max_workers is not None and max_workers > 1 and n_paths > _SERIAL_THRESHOLD:
        # spawn (not fork): the engine pulls in nautilus/Cython, and forking such a process is a
        # known deadlock hazard; spawn re-imports cleanly in each worker.
        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as pool:
            null = np.array(list(pool.map(_oos_sharpe_for_path, tasks)), dtype=np.float64)
    else:
        null = np.array([_oos_sharpe_for_path(t) for t in tasks], dtype=np.float64)

    if not bool(np.all(np.isfinite(null))):
        raise DataError("full-engine null produced a non-finite Sharpe on some path")
    percentile = float(np.mean(null < observed))
    at_least_as_good = int(np.sum(null >= observed))
    p_value = (1 + at_least_as_good) / (1 + n_paths)
    return NullResult(
        observed=observed,
        null=null,
        percentile=percentile,
        p_value=p_value,
        threshold=threshold,
        passed=percentile >= threshold,
        n_paths=n_paths,
    )
