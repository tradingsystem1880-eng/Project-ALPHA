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
from scipy import stats

from alpha_core import DataError
from alpha_validation.bootstrap import Statistic, stationary_bootstrap_indices
from alpha_validation.metrics import FloatArray, FloatSeq, sharpe_ratio

StrategyFn = Callable[[FloatArray], FloatArray]

# bounds for the Student-t degrees of freedom inferred from sample kurtosis (df<=4 has no kurtosis;
# very large df is indistinguishable from Gaussian)
_MIN_DF = 5.0
_MAX_DF = 250.0


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

    return _rank_null(observed, null, threshold, n_paths)


def _rank_null(observed: float, null: FloatArray, threshold: float, n_paths: int) -> NullResult:
    """Assemble a ``NullResult`` from an observed statistic and its null distribution."""
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


def _infer_df(returns: FloatArray) -> float:
    """Student-t degrees of freedom implied by the sample excess kurtosis (excess = 6/(df-4))."""
    excess = float(stats.kurtosis(returns, fisher=True, bias=True))
    if excess <= 0.0:
        return _MAX_DF  # thin-tailed → effectively Gaussian
    return float(min(max(6.0 / excess + 4.0, _MIN_DF), _MAX_DF))


def _unit_variance_t(rng: np.random.Generator, df: float, size: tuple[int, ...]) -> FloatArray:
    """Standard-t draws rescaled to unit variance (a raw t has variance ``df/(df-2)``)."""
    draws = np.asarray(rng.standard_t(df, size=size), dtype=np.float64)
    scale = float(np.sqrt(df / (df - 2.0)))
    return np.asarray(draws / scale, dtype=np.float64)


def student_t_paths(
    price_returns: FloatSeq,
    *,
    n_paths: int,
    df: float | None = None,
    seed: int | None = None,
) -> FloatArray:
    """``(n_paths × n)`` i.i.d. Student-t return paths matching ``price_returns`` mean + variance.

    A fat-tailed parametric null: the marginal heavy tails of real returns survive (unlike a thin
    Gaussian null), but all temporal structure is destroyed, so a strategy that "works" here is
    exploiting tail shape, not edge. ``df`` defaults to the value implied by the sample kurtosis.
    Fails loud (``DataError``) on ``df <= 2`` (undefined variance) or fewer than 2 returns.
    """
    pr = _as_price_returns(price_returns)
    if n_paths < 1:
        raise DataError(f"n_paths must be >= 1, got {n_paths}")
    dof = _infer_df(pr) if df is None else df
    if dof <= 2.0:
        raise DataError(f"student_t df must be > 2 for finite variance, got {dof}")
    rng = np.random.default_rng(seed)
    z = _unit_variance_t(rng, dof, (n_paths, pr.size))
    return float(np.mean(pr)) + float(np.std(pr, ddof=1)) * z


def garch_paths(
    price_returns: FloatSeq,
    *,
    n_paths: int,
    alpha: float = 0.1,
    beta: float = 0.85,
    df: float | None = None,
    seed: int | None = None,
) -> FloatArray:
    """``(n_paths × n)`` GARCH(1,1) return paths with the unconditional variance of the sample.

    A volatility-clustering parametric null with conditional variance
    ``s2_t = omega + alpha*e2_{t-1} + beta*s2_{t-1}``, ``omega`` chosen so the long-run variance
    matches the sample (``omega = var*(1-alpha-beta)``). Innovations are unit-variance Student-t
    (fat tails + clustering) when ``df`` is set, else Gaussian. The most adversarial cheap null — it
    reproduces the calm/turbulent regimes that fool trend and breakout rules. Fails loud
    (``DataError``) on a non-stationary ``alpha + beta >= 1`` or bad parameters. (Full GARCH MLE
    fitting would need the ``arch`` package and is out of scope; persistence params are tunable.)
    """
    pr = _as_price_returns(price_returns)
    if n_paths < 1:
        raise DataError(f"n_paths must be >= 1, got {n_paths}")
    if alpha < 0.0 or beta < 0.0:
        raise DataError(f"alpha, beta must be >= 0, got alpha={alpha}, beta={beta}")
    if alpha + beta >= 1.0:
        raise DataError(f"GARCH non-stationary: alpha + beta = {alpha + beta} >= 1")
    mean = float(np.mean(pr))
    uncond_var = float(np.var(pr, ddof=1))
    omega = uncond_var * (1.0 - alpha - beta)
    dof = _infer_df(pr) if df is None else df
    if dof <= 2.0:
        raise DataError(f"garch df must be > 2 for finite variance, got {dof}")
    rng = np.random.default_rng(seed)
    n = pr.size
    paths = np.empty((n_paths, n), dtype=np.float64)
    for p in range(n_paths):
        sigma2 = uncond_var
        eps_prev_sq = uncond_var
        for t in range(n):
            sigma2 = omega + alpha * eps_prev_sq + beta * sigma2
            z = (
                rng.standard_normal()
                if dof >= _MAX_DF
                else float(_unit_variance_t(rng, dof, (1,))[0])
            )
            eps = np.sqrt(sigma2) * z
            paths[p, t] = eps
            eps_prev_sq = eps * eps
    return mean + paths


def parametric_price_null(
    price_returns: FloatSeq,
    strategy_fn: StrategyFn,
    *,
    model: str = "student_t",
    n_paths: int = 1000,
    df: float | None = None,
    alpha: float = 0.1,
    beta: float = 0.85,
    statistic: Statistic | None = None,
    threshold: float = 0.95,
    periods_per_year: int = 252,
    seed: int | None = None,
) -> NullResult:
    """Randomized-price null using a fat-tailed *parametric* model instead of resampling.

    ``model="student_t"`` (i.i.d. heavy tails) or ``"garch"`` (volatility clustering) generates the
    synthetic paths; otherwise identical in spirit to ``randomized_price_null`` — the observed
    statistic is ranked against the strategy run on each path. A more adversarial null than the
    bootstrap because it keeps the marginal/temporal shapes that make random charts look tradeable.
    Fails loud (``DataError``) on a bad model name, ``n_paths < 1``, a ``threshold`` outside
    ``(0, 1)``, or a non-finite statistic on any path.
    """
    if not 0.0 < threshold < 1.0:
        raise DataError(f"threshold must be in (0, 1), got {threshold}")
    pr = _as_price_returns(price_returns)
    stat: Statistic = statistic or (lambda r: sharpe_ratio(r, periods_per_year=periods_per_year))
    observed = stat(strategy_fn(pr))
    if model == "student_t":
        paths = student_t_paths(pr, n_paths=n_paths, df=df, seed=seed)
    elif model == "garch":
        paths = garch_paths(pr, n_paths=n_paths, alpha=alpha, beta=beta, df=df, seed=seed)
    else:
        raise DataError(f"unknown null model {model!r}; known: 'student_t', 'garch'")
    null = np.array([stat(strategy_fn(path)) for path in paths], dtype=np.float64)
    if not bool(np.all(np.isfinite(null))):
        raise DataError(f"parametric ({model}) null produced a non-finite statistic on some path")
    return _rank_null(observed, null, threshold, n_paths)


def _as_price_returns(price_returns: FloatSeq) -> FloatArray:
    pr = np.asarray(price_returns, dtype=np.float64)
    if pr.ndim != 1 or pr.size < 2:
        raise DataError(f"need >= 2 price returns, got shape {pr.shape}")
    if not bool(np.all(np.isfinite(pr))):
        raise DataError("price returns must be finite")
    return pr
