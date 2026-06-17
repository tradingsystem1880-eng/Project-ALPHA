"""Synthetic price paths for the full-engine randomized-price null (Tier 2, spec §7.4).

The cheap Tier-1 null resamples *returns*; the faithfulness check (Tier 2) resamples whole OHLCV
bars and re-runs the real engine on each synthetic path. ``synthetic_bar_paths`` generates those
paths; the full-engine orchestration that runs them through ``run_backtest`` is added alongside.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from alpha_core import Bar, DataError
from alpha_validation import stationary_bootstrap_indices


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
