"""Randomized-price null (spec §8 gate 3) — the headline gate of the gauntlet.

The blueprint's own admission is that chart patterns appear with identical frequency on random
charts, so a strategy is only believable if it beats *itself run on randomised price paths*. This
module destroys the exploitable structure of the observed price returns by resampling them (an
i.i.d. bootstrap by default, or a stationary block bootstrap to retain short-range dependence as a
more conservative null), re-evaluates the strategy on each synthetic path, and reports where the
observed statistic falls in the resulting null distribution.

The strategy is supplied as a ``Callable[[price_returns], strategy_returns]`` so this package never
imports the backtest engine (the architecture DAG). Spec §7.4 describes a *two-tier* null — this
cheap returns-level tier plus a smaller set of full-engine runs on synthetic price paths as a
faithfulness check; only the returns-level tier lives here. The full-engine tier and the live
strategy evaluation are wired by the CLI in Phase 5 (which may import the engine); tests here inject
a toy strategy.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_validation.bootstrap import Statistic, stationary_bootstrap_indices
from alpha_validation.metrics import FloatArray, FloatSeq, sharpe_ratio

StrategyFn = Callable[[FloatArray], FloatArray]


@dataclass(frozen=True)
class NullResult:
    """Where the observed statistic falls in the randomized-price null distribution."""

    observed: float
    null: FloatArray
    percentile: float  # fraction of null paths strictly below the observed statistic
    p_value: float  # one-sided MC p-value, (1 + #{null >= observed}) / (1 + n_paths)
    threshold: float
    passed: bool  # percentile >= threshold
    n_paths: int


def randomized_price_null(
    price_returns: FloatSeq,
    strategy_fn: StrategyFn,
    *,
    statistic: Statistic | None = None,
    n_paths: int = 1000,
    block: float = 1.0,
    threshold: float = 0.95,
    periods_per_year: int = 252,
    seed: int | None = None,
) -> NullResult:
    """Run ``strategy_fn`` on ``n_paths`` randomized copies of ``price_returns``, ranking observed.

    By default the statistic is the annualized Sharpe of the strategy's returns and ``block=1.0``
    (i.i.d. bootstrap, destroying all serial structure). ``threshold`` is the null percentile the
    observed statistic must reach to pass. ``statistic`` must be defined and finite on every path.

    Fails loud (``DataError``) on ``n_paths < 1``, ``threshold`` outside ``(0, 1)``, fewer than 2
    price returns, or a non-finite statistic on any path.
    """
    if n_paths < 1:
        raise DataError(f"n_paths must be >= 1, got {n_paths}")
    if not 0.0 < threshold < 1.0:
        raise DataError(f"threshold must be in (0, 1), got {threshold}")
    pr = np.asarray(price_returns, dtype=np.float64)
    if pr.ndim != 1 or pr.size < 2:
        raise DataError(f"randomized_price_null needs >= 2 price returns, got shape {pr.shape}")
    if not bool(np.all(np.isfinite(pr))):
        raise DataError("randomized_price_null requires finite price returns")

    stat: Statistic = statistic or (lambda r: sharpe_ratio(r, periods_per_year=periods_per_year))
    observed = stat(strategy_fn(pr))
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(pr.size, mean_block=block, n_resamples=n_paths, rng=rng)
    null = np.array([stat(strategy_fn(pr[row])) for row in idx], dtype=np.float64)
    if not bool(np.all(np.isfinite(null))):
        raise DataError("randomized-price null produced a non-finite statistic on some path")

    percentile = float(np.mean(null < observed))
    at_least_as_good = int(np.sum(null >= observed))
    # +1 (Davison & Hinkley 1997): the valid one-sided MC p-value — never exactly 0.
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
