"""Reference transcriptions of Bailey & López de Prado estimators (test-only, loop-based).

Sources:
- PSR: Bailey & López de Prado, "The Sharpe Ratio Efficient Frontier", J. Risk 15(2), 2012,
  eq. (11): PSR(SR*) = Z[(SR − SR*)·sqrt(n−1) / sqrt(1 − γ3·SR + (γ4−1)/4·SR²)].
- DSR: Bailey & López de Prado, "The Deflated Sharpe Ratio", J. Portfolio Mgmt 40(5), 2014,
  eq. (7): SR0 = sqrt(V[SR_n]) · [(1−γ)·Z⁻¹(1−1/N) + γ·Z⁻¹(1−1/(N·e))]; DSR = PSR(SR0).
- PBO: Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting",
  J. Computational Finance 20(4), 2016, §4 (CSCV algorithm).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Sequence

from scipy import stats

_EULER_GAMMA = 0.57721566490153286061


def _moments(x: Sequence[float]) -> tuple[float, float, float, float, int]:
    n = len(x)
    mean = sum(x) / n
    dev = [v - mean for v in x]
    var_unbiased = sum(d * d for d in dev) / (n - 1)
    sd = math.sqrt(var_unbiased)
    m2 = sum(d * d for d in dev) / n  # biased second moment (for skew/kurt as in the paper)
    m3 = sum(d**3 for d in dev) / n
    m4 = sum(d**4 for d in dev) / n
    skew = m3 / m2**1.5
    kurt = m4 / m2**2  # non-excess (Gaussian = 3)
    return mean, sd, skew, kurt, n


def sharpe(x: Sequence[float]) -> float:
    mean, sd, _, _, _ = _moments(x)
    return mean / sd


def psr(x: Sequence[float], sr_star: float = 0.0) -> float:
    """Eq. (11) of Bailey & LdP (2012) with the biased sample skew/kurtosis of the paper."""
    mean, sd, skew, kurt, n = _moments(x)
    sr = mean / sd
    denom = math.sqrt(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr)
    return float(stats.norm.cdf((sr - sr_star) * math.sqrt(n - 1) / denom))


def sr0(trial_variance: float, n_trials: int) -> float:
    """Eq. (7) of Bailey & LdP (2014): expected max Sharpe of N zero-skill trials."""
    if n_trials <= 1 or trial_variance <= 0.0:
        return 0.0
    z = stats.norm.ppf
    return math.sqrt(trial_variance) * float(
        (1.0 - _EULER_GAMMA) * z(1.0 - 1.0 / n_trials)
        + _EULER_GAMMA * z(1.0 - 1.0 / (n_trials * math.e))
    )


def dsr(x: Sequence[float], trial_sharpes: Sequence[float]) -> float:
    """DSR = PSR evaluated at SR0(Var of the trial Sharpes, N)."""
    n = len(trial_sharpes)
    if n < 2:
        return psr(x, 0.0)
    mean = sum(trial_sharpes) / n
    var = sum((s - mean) ** 2 for s in trial_sharpes) / (n - 1)
    return psr(x, sr0(var, n))


def _avg_rank(values: Sequence[float], i: int) -> float:
    """1-based average rank (ties averaged) of values[i]."""
    below = sum(1 for v in values if v < values[i])
    ties = sum(1 for v in values if v == values[i])
    return below + (ties + 1) / 2.0


def pbo(
    matrix: Sequence[Sequence[float]],
    n_blocks: int,
    statistic: Callable[[Sequence[float]], float] = sharpe,
) -> tuple[float, list[float]]:
    """CSCV (Bailey et al. 2016 §4): returns (PBO, logits) for a T×S performance matrix.

    Steps: cut T rows into S=n_blocks equal blocks; for each of C(S, S/2) in-sample block
    sets, pick the IS-best column, compute its OOS relative rank ω = rank/(S_cols+1) and
    logit λ = ln(ω/(1−ω)); PBO = share of λ ≤ 0.
    """
    t = len(matrix)
    n_cols = len(matrix[0])
    rows_per_block = t // n_blocks
    blocks = [list(range(b * rows_per_block, (b + 1) * rows_per_block)) for b in range(n_blocks)]
    logits: list[float] = []
    for is_blocks in itertools.combinations(range(n_blocks), n_blocks // 2):
        is_rows = [r for b in is_blocks for r in blocks[b]]
        oos_rows = [r for b in range(n_blocks) if b not in is_blocks for r in blocks[b]]
        is_perf = [statistic([matrix[r][c] for r in is_rows]) for c in range(n_cols)]
        oos_perf = [statistic([matrix[r][c] for r in oos_rows]) for c in range(n_cols)]
        best = max(range(n_cols), key=lambda c: (is_perf[c], -c))  # first max on ties
        omega = _avg_rank(oos_perf, best) / (n_cols + 1)
        logits.append(math.log(omega / (1.0 - omega)))
    return sum(1 for lam in logits if lam <= 0.0) / len(logits), logits
