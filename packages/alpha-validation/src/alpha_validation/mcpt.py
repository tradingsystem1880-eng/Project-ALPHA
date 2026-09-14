"""Monte Carlo permutation test over bar permutations (Masters 2018, ch. 7).

Provenance: github.com/neurotrader888/mcpt/{insample_donchian_mcpt,walkforward_donchian_mcpt}.py
@ 2c0d70c (MIT). Adapted: the strategy and its statistic arrive as one ``score`` callable over
typed ``OHLC`` bars (this package never imports the engine or an optimiser — the CLI composes
those), the permutations come from ``bar_permutation`` with an explicit seed, and the ranking
reuses ``montecarlo._rank_null`` so the p-value is Davison & Hinkley's ``(1 + c) / (1 + N)``.
Upstream seeds its counter at 1 and loops over ``N - 1`` permutations, so its ``count / N`` is
the same estimator with ``N - 1`` draws; the port makes the draw count explicit.

Two uses, decided by ``start_index``: an in-sample test permutes every bar after the first and
``score`` re-optimises on each permutation (Masters' MCPT: a selection-bias / overfitting test,
never out-of-sample evidence); the walk-forward variant, which is upstream's construction rather
than one of Masters' published programs, sets ``start_index`` to the last training bar so only
the out-of-sample bars are permuted while ``score`` re-applies the walk-forward procedure. The
seed follows the package convention of ``randomized_price_null`` (``None`` draws fresh entropy);
the CLI composer always passes a settings-derived seed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from alpha_core import DataError
from alpha_validation.bar_permutation import OHLC, permute_bars_multi
from alpha_validation.montecarlo import NullResult, _rank_null

ScoreFn = Callable[[OHLC], float]
MultiScoreFn = Callable[[Sequence[OHLC]], float]


def permutation_test_multi(
    markets: Sequence[OHLC],
    score: MultiScoreFn,
    *,
    n_perms: int,
    start_index: int = 0,
    seed: int | None,
    threshold: float = 0.95,
) -> NullResult:
    """Rank ``score(markets)`` against ``n_perms`` jointly permuted copies of the markets.

    ``passed`` means the observed statistic reaches the ``threshold`` percentile of the null.
    Fails loud on ``n_perms < 1``, a threshold outside ``(0, 1)``, or a non-finite score.
    """
    if n_perms < 1:
        raise DataError(f"n_perms must be >= 1, got {n_perms}")
    if not 0.0 < threshold < 1.0:
        raise DataError(f"threshold must be in (0, 1), got {threshold}")
    observed = float(score(markets))
    if not np.isfinite(observed):
        raise DataError("permutation test observed statistic is not finite")
    rng = np.random.default_rng(seed)
    null = np.empty(n_perms, dtype=np.float64)
    for i in range(n_perms):
        null[i] = float(score(permute_bars_multi(markets, start_index=start_index, rng=rng)))
    if not bool(np.all(np.isfinite(null))):
        raise DataError("permutation test produced a non-finite statistic on some permutation")
    return _rank_null(observed, null, threshold, n_perms)


def permutation_test(
    bars: OHLC,
    score: ScoreFn,
    *,
    n_perms: int,
    start_index: int = 0,
    seed: int | None,
    threshold: float = 0.95,
) -> NullResult:
    """Single-market ``permutation_test_multi``; see there."""
    return permutation_test_multi(
        [bars],
        lambda markets: score(markets[0]),
        n_perms=n_perms,
        start_index=start_index,
        seed=seed,
        threshold=threshold,
    )


__all__ = ["MultiScoreFn", "ScoreFn", "permutation_test", "permutation_test_multi"]
