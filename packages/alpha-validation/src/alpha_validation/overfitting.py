"""Probability of Backtest Overfitting via CSCV (Bailey, Borwein, López de Prado & Zhu, 2017).

When a parameter sweep reports the *best* configuration, the question is whether that choice
generalizes or just won the in-sample lottery. CSCV (Combinatorially Symmetric Cross-Validation)
answers it directly: split the timeline into ``n_blocks`` blocks; for every way to use half the
blocks in-sample and half out-of-sample, pick the config that looks best in-sample and record where
it ranks out-of-sample. PBO is the fraction of those splits where the in-sample winner lands below
the OOS median — i.e. the probability that "the best backtest" is overfit. Low PBO = the selection
generalizes; PBO near or above 0.5 = the search is mostly fitting noise.

Operates on a ``(T observations × S configs)`` performance matrix (each column one config's return
series over the same observations). Pure ``numpy``/``scipy``, deterministic (no RNG), fail-loud.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

from alpha_core import DataError
from alpha_validation.bootstrap import Statistic
from alpha_validation.metrics import FloatArray


@dataclass(frozen=True)
class PBOResult:
    """The CSCV overfitting verdict for a sweep's performance matrix."""

    pbo: float  # P(in-sample-best config is below the OOS median) over all CSCV splits
    logits: FloatArray  # per-split logit of the OOS relative rank (negative = overfit)
    n_splits: int  # C(n_blocks, n_blocks/2)
    n_configs: int
    threshold: float
    passed: bool  # pbo <= threshold


def _safe_sharpe(returns: FloatArray) -> float:
    sd = float(np.std(returns, ddof=1)) if returns.size >= 2 else 0.0
    return float(np.mean(returns)) / sd if sd > 0.0 else 0.0


def probability_of_backtest_overfitting(
    perf_matrix: FloatArray,
    *,
    n_blocks: int = 16,
    statistic: Statistic | None = None,
    threshold: float = 0.5,
) -> PBOResult:
    """CSCV probability of backtest overfitting over a ``(T × S)`` performance matrix.

    Each column is one configuration's per-observation return series. The timeline is cut into
    ``n_blocks`` equal blocks (trailing remainder dropped); for each combination of ``n_blocks/2``
    blocks used in-sample, the in-sample-best config's out-of-sample relative rank gives a logit
    (negative ⇒ it fell below the OOS median). ``statistic`` scores a config on a row subset
    (default: per-observation Sharpe, zero-variance → 0). Passes when ``pbo <= threshold``.

    Fails loud (``DataError``) on a non-2-D matrix, ``< 2`` configs, an odd or ``< 2`` ``n_blocks``,
    too few rows to fill the blocks, a non-finite matrix, or a bad ``threshold``.
    """
    if not 0.0 < threshold < 1.0:
        raise DataError(f"threshold must be in (0, 1), got {threshold}")
    m = np.asarray(perf_matrix, dtype=np.float64)
    if m.ndim != 2:
        raise DataError(f"perf_matrix must be 2-D (T observations × S configs), got {m.shape}")
    n_obs, n_configs = m.shape
    if n_configs < 2:
        raise DataError(f"PBO needs >= 2 configurations, got {n_configs}")
    if n_blocks < 2 or n_blocks % 2 != 0:
        raise DataError(f"n_blocks must be an even integer >= 2, got {n_blocks}")
    if n_obs < n_blocks:
        raise DataError(f"perf_matrix has {n_obs} rows < n_blocks {n_blocks}")
    if not bool(np.all(np.isfinite(m))):
        raise DataError("perf_matrix must be finite")

    stat = statistic if statistic is not None else _safe_sharpe
    rows_per_block = n_obs // n_blocks
    blocks = [
        np.arange(b * rows_per_block, (b + 1) * rows_per_block, dtype=np.intp)
        for b in range(n_blocks)
    ]

    logits: list[float] = []
    half = n_blocks // 2
    for is_blocks in itertools.combinations(range(n_blocks), half):
        is_set = set(is_blocks)
        is_rows = np.concatenate([blocks[b] for b in is_blocks])
        oos_rows = np.concatenate([blocks[b] for b in range(n_blocks) if b not in is_set])

        is_perf = np.array([stat(m[is_rows, c]) for c in range(n_configs)], dtype=np.float64)
        oos_perf = np.array([stat(m[oos_rows, c]) for c in range(n_configs)], dtype=np.float64)
        n_star = int(np.argmax(is_perf))  # config selected in-sample
        ranks = stats.rankdata(oos_perf)  # 1..S, average ties
        omega = float(ranks[n_star]) / (n_configs + 1)  # relative OOS rank in (0, 1)
        logits.append(math.log(omega / (1.0 - omega)))

    logit_arr = np.array(logits, dtype=np.float64)
    pbo = float(np.mean(logit_arr <= 0.0))  # share of splits where the IS-best is below OOS median
    return PBOResult(
        pbo=pbo,
        logits=logit_arr,
        n_splits=int(logit_arr.size),
        n_configs=n_configs,
        threshold=threshold,
        passed=pbo <= threshold,
    )
