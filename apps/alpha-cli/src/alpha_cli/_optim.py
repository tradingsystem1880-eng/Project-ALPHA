"""Parameter optimization wired to the overfitting-aware gates (spec §8 note on PBO/DSR).

A sweep that just reports the best Sharpe is the textbook way to overfit. This module runs a grid of
configurations through the *same* engine + walk-forward OOS the gauntlet uses, assembles their OOS
return streams into a ``(T × S)`` performance matrix, and judges the selection with the gates that
only become meaningful once you have many trials:

- **Deflated Sharpe** of the selected config, deflated against the variance of *all* trial Sharpes;
- **PBO** (CSCV) — the probability the in-sample winner is below the OOS median;
- **White's Reality Check / Hansen's SPA** — does the best config beat the data-snooping null?

Because every config shares the same ``train_size``/``test_size``/``embargo`` and bar series, their
walk-forward test windows tile identically, so the OOS streams align column-for-column (a well
defined matrix). Configs whose warmup floor exceeds ``train_size`` would misalign, so the sweep
fails loud up front rather than silently comparing different windows. Engine work is parallelized
over a spawn pool (nautilus is fork-unsafe), order-preserving and deterministic.
"""

from __future__ import annotations

import multiprocessing
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from itertools import product
from typing import Any

import numpy as np

from alpha_cli._runner import RunSpec, run_full_backtest, walk_forward_oos_for_spec
from alpha_core import Bar, DataError
from alpha_validation import (
    DataSnoopingResult,
    DeflatedSharpeResult,
    FloatArray,
    PBOResult,
    deflated_sharpe,
    probability_of_backtest_overfitting,
    reality_check,
    sharpe_ratio,
    spa_test,
)

_SERIAL_THRESHOLD = 8  # below this many configs the pool's spin-up costs more than it saves
_INT_FIELDS = frozenset({"lookback", "skip", "vol_window", "rebalance_every"})
_FLOAT_FIELDS = frozenset({"target_vol", "max_leverage"})

Config = tuple[tuple[str, float], ...]  # sorted (name, value) pairs — one swept configuration


@dataclass(frozen=True)
class OptimResult:
    """The overfitting-aware verdict for a parameter sweep."""

    best_config: Config
    best_sharpe: float  # annualized OOS Sharpe of the selected config
    n_configs: int
    n_oos: int
    dsr: DeflatedSharpeResult  # deflated Sharpe of the best config vs all trials
    pbo: PBOResult
    reality_check: DataSnoopingResult
    spa: DataSnoopingResult
    configs: tuple[Config, ...]
    sharpes: FloatArray  # annualized OOS Sharpe per config (aligned with ``configs``)
    passed: bool  # DSR, PBO and SPA all pass — the selection is not just snooping


def expand_grid(grid: Mapping[str, Sequence[float]]) -> list[Config]:
    """Cartesian product of a parameter grid into sorted ``(name, value)`` configurations."""
    if not grid:
        raise DataError("optimization grid is empty")
    names = sorted(grid)
    for name in names:
        if len(grid[name]) == 0:
            raise DataError(f"grid axis {name!r} has no values")
    return [
        tuple(zip(names, (float(v) for v in combo), strict=True))
        for combo in product(*(grid[name] for name in names))
    ]


def _spec_for(base: RunSpec, config: Config) -> RunSpec:
    """Apply one configuration to the base ``RunSpec`` (first-class fields or strategy_params)."""
    overrides: dict[str, Any] = {}
    extra = dict(base.strategy_params)
    for name, value in config:
        if name in _INT_FIELDS:
            overrides[name] = int(value)
        elif name in _FLOAT_FIELDS:
            overrides[name] = float(value)
        else:
            extra[name] = float(value)
    return replace(base, strategy_params=tuple(sorted(extra.items())), **overrides)


@dataclass(frozen=True)
class _ConfigTask:
    """One picklable unit of sweep work: a bar series + a fully-resolved spec."""

    bars: list[Bar]
    spec: RunSpec


def _oos_returns_for(task: _ConfigTask) -> FloatArray:
    """Run one config through the engine + walk-forward and return its OOS return stream."""
    result = run_full_backtest(task.bars, task.spec)
    return walk_forward_oos_for_spec(result.equity_curve, task.spec).oos_returns


def _safe_period_sharpe(returns: FloatArray) -> float:
    sd = float(np.std(returns, ddof=1)) if returns.size >= 2 else 0.0
    return float(np.mean(returns)) / sd if sd > 0.0 else 0.0


def _annualized_sharpe(returns: FloatArray, periods_per_year: int) -> float:
    if returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0:
        return sharpe_ratio(returns, periods_per_year=periods_per_year)
    return 0.0


def run_optimization(
    bars: Sequence[Bar],
    base_spec: RunSpec,
    grid: Mapping[str, Sequence[float]],
    *,
    pbo_blocks: int = 10,
    n_resamples: int = 2000,
    mean_block: float = 5.0,
    dsr_threshold: float = 0.95,
    alpha: float = 0.05,
    seed: int | None = 7,
    max_workers: int | None = None,
) -> OptimResult:
    """Run the sweep and return its overfitting-aware verdict (DSR + PBO + Reality Check + SPA)."""
    configs = expand_grid(grid)
    if len(configs) < 2:
        raise DataError(
            f"optimization needs >= 2 configs to test for overfitting, got {len(configs)}"
        )
    specs = [_spec_for(base_spec, c) for c in configs]

    floors = [s.min_train for s in specs]
    if base_spec.train_size < max(floors):
        raise DataError(
            f"train_size {base_spec.train_size} < warmup floor {max(floors)} for some config; "
            "raise --train-size or shrink the grid so every config's OOS window aligns"
        )

    oos_list = _run_configs([_ConfigTask(bars=list(bars), spec=s) for s in specs], max_workers)
    lengths = {r.size for r in oos_list}
    if len(lengths) != 1:
        raise DataError(f"OOS streams misaligned across configs: lengths {sorted(lengths)}")
    n_oos = lengths.pop()
    if n_oos < 2:
        raise DataError(f"OOS stream too short ({n_oos}) to evaluate the sweep")

    ppy = base_spec.periods_per_year
    matrix = np.column_stack(oos_list)  # (n_oos × n_configs)
    ann = np.array([_annualized_sharpe(r, ppy) for r in oos_list], dtype=np.float64)
    per_period = np.array([_safe_period_sharpe(r) for r in oos_list], dtype=np.float64)
    best_idx = int(np.argmax(ann))
    best_returns = oos_list[best_idx]
    if float(np.std(best_returns, ddof=1)) <= 0.0:
        raise DataError("the best config produced a flat OOS — no edge to optimize")

    dsr = deflated_sharpe(best_returns, trial_sharpes=per_period, threshold=dsr_threshold)
    pbo = probability_of_backtest_overfitting(matrix, n_blocks=_even_blocks(pbo_blocks, n_oos))
    rc = reality_check(
        matrix, n_resamples=n_resamples, mean_block=mean_block, alpha=alpha, seed=seed
    )
    spa = spa_test(matrix, n_resamples=n_resamples, mean_block=mean_block, alpha=alpha, seed=seed)

    return OptimResult(
        best_config=configs[best_idx],
        best_sharpe=float(ann[best_idx]),
        n_configs=len(configs),
        n_oos=n_oos,
        dsr=dsr,
        pbo=pbo,
        reality_check=rc,
        spa=spa,
        configs=tuple(configs),
        sharpes=ann,
        passed=dsr.passed and pbo.passed and spa.passed,
    )


def _run_configs(tasks: list[_ConfigTask], max_workers: int | None) -> list[FloatArray]:
    """Evaluate each config's OOS stream: a spawn pool when it's worth it, else serial."""
    if max_workers is not None and max_workers > 1 and len(tasks) > _SERIAL_THRESHOLD:
        ctx = multiprocessing.get_context("spawn")  # nautilus/Cython is fork-unsafe
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as pool:
            return list(pool.map(_oos_returns_for, tasks))
    return [_oos_returns_for(t) for t in tasks]


def _even_blocks(requested: int, n_oos: int) -> int:
    """Largest even block count <= ``requested`` that fits ``n_oos`` (CSCV needs even >= 2)."""
    blocks = min(requested, n_oos)
    if blocks % 2 != 0:
        blocks -= 1
    if blocks < 2:
        raise DataError(f"too few OOS points ({n_oos}) for PBO blocks")
    return blocks
