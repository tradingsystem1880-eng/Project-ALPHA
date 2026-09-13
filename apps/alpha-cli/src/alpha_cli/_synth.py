"""Synthetic price paths for the engine-backed randomized-price nulls (spec §7.4).

The cheap Tier-1 null resamples *returns*; the faithfulness check (Tier 2) resamples whole OHLCV
bars and re-runs the real engine on each synthetic path. ``synthetic_bar_paths`` generates those
paths; the full-engine orchestration that runs them through ``run_backtest`` is added alongside.
Tier 3 (``bar_permutation_null``) is the walk-forward Monte Carlo permutation test: every bar
after the last decision bar before the OOS window is permuted (``alpha_validation.bar_permutation``,
Masters 2018 ch. 7 / neurotrader888/mcpt) and the same fixed-parameter engine replay scores it.
"""

from __future__ import annotations

import multiprocessing
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np

from alpha_cli._runner import RunSpec, fresh_oos_execution
from alpha_core import Bar, CorporateAction, DataError
from alpha_validation import NullResult, sharpe_ratio, stationary_bootstrap_indices
from alpha_validation.bar_permutation import OHLC, permute_bars

# below this path count the pool's spin-up costs more than it saves; run in-process
_SERIAL_THRESHOLD = 8


def synthetic_bar_paths(
    bars: Sequence[Bar], *, n_paths: int, mean_block: float, seed: int | None
) -> list[list[Bar]]:
    """Block-bootstrap whole OHLCV rows into ``n_paths`` level-continuous synthetic series.

    Resampling whole bars (not close-to-close returns) preserves each bar's intrabar OHLC shape
    and the realistic close(t)->open(t+1) gap the fill model consumes; only the *ordering* of
    blocks is randomized, which is what destroys the exploitable trend. Each picked row is applied
    RELATIVELY — its own overnight gap ``O_j/C_{j-1}`` moves the running level, then its intrabar
    ratios ``H/O``, ``L/O``, ``C/O`` shape the bar — so the reconstructed path is level-continuous.
    (Copying raw price rows would splice, say, a 380-level block onto a 110-level block on a
    trending series: a fictitious ~70% overnight move at every block seam that pollutes the null's
    volatility and signal structure.) Within a continued block the reconstruction is an exact
    scaled copy of the original block; volumes ride along per row; bars are re-stamped onto the
    original (strictly-monotone) session axis so the feed stays chronological, and ``Bar``
    invariants hold by construction. Fails loud (``DataError``) on fewer than 2 bars or
    ``n_paths < 1``.
    """
    n = len(bars)
    if n < 2:
        raise DataError(f"synthetic_bar_paths needs >= 2 bars, got {n}")
    if n_paths < 1:
        raise DataError(f"n_paths must be >= 1, got {n_paths}")
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(n, mean_block=mean_block, n_resamples=n_paths, rng=rng)
    timeline = [b.ts for b in bars]
    # per-row relative decomposition: overnight gap (row 0 has no prior close -> no gap) + intrabar
    gap = np.ones(n, dtype=np.float64)
    for j in range(1, n):
        gap[j] = bars[j].open / bars[j - 1].close
    h_rel = np.array([b.high / b.open for b in bars], dtype=np.float64)
    l_rel = np.array([b.low / b.open for b in bars], dtype=np.float64)
    c_rel = np.array([b.close / b.open for b in bars], dtype=np.float64)

    paths: list[list[Bar]] = []
    for row in idx:
        path: list[Bar] = []
        prev_close: float | None = None
        for i, j_ in enumerate(row):
            j = int(j_)
            o = bars[j].open if prev_close is None else prev_close * gap[j]
            close = o * c_rel[j]
            path.append(
                Bar(
                    symbol=bars[j].symbol,
                    ts=timeline[i],
                    open=o,
                    high=o * h_rel[j],
                    low=o * l_rel[j],
                    close=close,
                    volume=bars[j].volume,
                )
            )
            prev_close = close
        paths.append(path)
    return paths


def permuted_bar_paths(
    bars: Sequence[Bar], *, start_index: int, n_paths: int, seed: int | None
) -> list[list[Bar]]:
    """Bar-permutation paths: bars ``0..start_index`` verbatim, every later bar permuted.

    Each path draws one ``permute_bars`` permutation (log gaps and intrabar shapes shuffled as
    two independent multisets, final close preserved) from one seeded generator, so the paths
    are deterministic and distinct. Bars are re-stamped onto the original session axis with the
    original symbol; volume stays at its session (upstream drops volume altogether, so no
    permuted-volume convention exists to follow). Fails loud on ``n_paths < 1``; ``permute_bars``
    rejects fewer than two bars or a ``start_index`` that leaves nothing to permute.
    """
    if n_paths < 1:
        raise DataError(f"n_paths must be >= 1, got {n_paths}")
    ohlc = OHLC(
        open=np.array([b.open for b in bars], dtype=np.float64),
        high=np.array([b.high for b in bars], dtype=np.float64),
        low=np.array([b.low for b in bars], dtype=np.float64),
        close=np.array([b.close for b in bars], dtype=np.float64),
    )
    rng = np.random.default_rng(seed)
    paths: list[list[Bar]] = []
    for _ in range(n_paths):
        permuted = permute_bars(ohlc, start_index=start_index, rng=rng)
        paths.append(
            [
                Bar(
                    symbol=b.symbol,
                    ts=b.ts,
                    open=float(permuted.open[i]),
                    high=float(permuted.high[i]),
                    low=float(permuted.low[i]),
                    close=float(permuted.close[i]),
                    volume=b.volume,
                )
                for i, b in enumerate(bars)
            ]
        )
    return paths


@dataclass(frozen=True)
class _SynthTask:
    """One picklable unit of full-engine work: a synthetic path + the run spec.

    ``dividends`` are the observed run's cash events, applied identically to every synthetic
    path (same amounts, same dates, each path's own positions) so the null and the observed are
    scored under one cash-crediting convention.
    """

    bars: list[Bar]
    spec: RunSpec
    dividends: tuple[CorporateAction, ...] = ()


def _oos_sharpe_for_path(task: _SynthTask) -> float:
    """Run the real engine on one synthetic path; return its walk-forward OOS Sharpe.

    A flat (zero-variance) OOS — common when the strategy finds no trend in a trendless path —
    has no risk-adjusted edge, so it scores 0.0 rather than raising. Top-level and picklable so a
    process pool can dispatch it.
    """
    oos, _ = fresh_oos_execution(task.bars, task.spec, dividends=task.dividends)
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
    dividends: Sequence[CorporateAction] = (),
    spec_for_path: Callable[[list[Bar]], RunSpec] | None = None,
) -> NullResult:
    """Tier-2 faithfulness check: the OOS Sharpe null from re-running the engine on synthetic paths.

    Each of ``n_paths`` block-bootstrapped price paths is run through the *real* engine and scored
    by the same walk-forward OOS Sharpe as the observed run, then ``observed`` is ranked against the
    resulting distribution. Percentile and the one-sided MC p-value use the same formula as the
    cheap Tier-1 ``randomized_price_null`` so the tiers are directly comparable. Determinism comes
    from deterministic path generation (seeded) and a deterministic engine — order-preserving
    ``map`` makes the result independent of whether it ran serially or in a (spawn) process pool.
    Fails loud on a bad ``threshold``, a non-finite ``observed`` (a flat/zero-variance real OOS —
    ranking it against the null would be meaningless), or a non-finite null statistic.
    """
    if not 0.0 < threshold < 1.0:
        raise DataError(f"threshold must be in (0, 1), got {threshold}")
    if not bool(np.isfinite(observed)):
        raise DataError(
            f"full-engine null needs a finite observed statistic, got {observed!r} "
            "(the real OOS Sharpe is undefined — a flat/zero-variance OOS)"
        )
    paths = synthetic_bar_paths(bars, n_paths=n_paths, mean_block=mean_block, seed=seed)
    return _engine_null(
        paths,
        observed=observed,
        spec=spec,
        threshold=threshold,
        max_workers=max_workers,
        dividends=dividends,
        spec_for_path=spec_for_path,
        label="full-engine",
    )


def bar_permutation_null(
    bars: Sequence[Bar],
    *,
    observed: float,
    spec: RunSpec,
    n_paths: int,
    start_index: int,
    threshold: float = 0.95,
    seed: int | None = None,
    max_workers: int | None = None,
    dividends: Sequence[CorporateAction] = (),
    spec_for_path: Callable[[list[Bar]], RunSpec] | None = None,
) -> NullResult:
    """Tier-3 walk-forward permutation null: the OOS Sharpe over bar-permuted OOS windows.

    ``start_index`` is the last bar left untouched (the decision bar before the first scored OOS
    bar), so the history the fixed rules were primed on is byte-identical on every path and only
    the scored window is shuffled; ``observed`` is the same engine OOS Sharpe Tier 2 ranks, and
    the ranking is the same ``(1 + c) / (1 + N)``. Same fail-loud contract as ``full_engine_null``.
    """
    if not 0.0 < threshold < 1.0:
        raise DataError(f"threshold must be in (0, 1), got {threshold}")
    if not bool(np.isfinite(observed)):
        raise DataError(
            f"bar-permutation null needs a finite observed statistic, got {observed!r} "
            "(the real OOS Sharpe is undefined — a flat/zero-variance OOS)"
        )
    paths = permuted_bar_paths(bars, start_index=start_index, n_paths=n_paths, seed=seed)
    return _engine_null(
        paths,
        observed=observed,
        spec=spec,
        threshold=threshold,
        max_workers=max_workers,
        dividends=dividends,
        spec_for_path=spec_for_path,
        label="bar-permutation",
    )


def _engine_null(
    paths: Sequence[list[Bar]],
    *,
    observed: float,
    spec: RunSpec,
    threshold: float,
    max_workers: int | None,
    dividends: Sequence[CorporateAction],
    spec_for_path: Callable[[list[Bar]], RunSpec] | None,
    label: str,
) -> NullResult:
    """Score every path with the real engine (serially or in a spawn pool) and rank ``observed``."""
    n_paths = len(paths)
    # spec_for_path lets model-backed strategies re-derive per-path state (e.g. a kronos
    # signal cache computed IN THE PARENT for each synthetic path) while workers stay
    # torch-free; None keeps the default one-spec-for-all behavior byte-identically.
    tasks = [
        _SynthTask(
            bars=p,
            spec=spec if spec_for_path is None else spec_for_path(p),
            dividends=tuple(dividends),
        )
        for p in paths
    ]

    if max_workers is not None and max_workers > 1 and n_paths > _SERIAL_THRESHOLD:
        # spawn (not fork): the engine pulls in nautilus/Cython, and forking such a process is a
        # known deadlock hazard; spawn re-imports cleanly in each worker.
        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as pool:
            null = np.array(list(pool.map(_oos_sharpe_for_path, tasks)), dtype=np.float64)
    else:
        null = np.array([_oos_sharpe_for_path(t) for t in tasks], dtype=np.float64)

    if not bool(np.all(np.isfinite(null))):
        raise DataError(f"{label} null produced a non-finite Sharpe on some path")
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
