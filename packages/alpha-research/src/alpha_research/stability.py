"""Pure effect-stability primitives (spec §9, ADR-0025).

Deterministic checks that an estimated effect is not an artifact of one period or one
subsample: chronological period splits, interleaved-subsample sign agreement, and a
strictly trailing rolling standardized-effect series (bias-guarded — window ``i`` reads
outcomes ``[i-window+1 .. i]`` only). Degenerate trailing windows yield ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from alpha_core import DataError
from alpha_research._arrays import finite_array


def temporal_split_effects(
    event_outcomes: Sequence[float], *, n_periods: int = 2
) -> list[dict[str, float | int]]:
    """Mean outcome per contiguous chronological period (period 1 = earliest)."""
    if isinstance(n_periods, bool) or not isinstance(n_periods, int) or n_periods < 2:
        raise DataError(f"temporal split requires an integer n_periods >= 2; got {n_periods!r}")
    outcomes = finite_array(event_outcomes, "temporal split outcomes")
    if outcomes.size < n_periods:
        raise DataError(f"temporal split needs at least {n_periods} outcomes; got {outcomes.size}")
    return [
        {"period": period_index + 1, "mean": float(np.mean(chunk)), "n": int(chunk.size)}
        for period_index, chunk in enumerate(np.array_split(outcomes, n_periods))
    ]


def subsample_consistency(
    outcomes: Sequence[float], *, n_splits: int = 4
) -> dict[str, float | int]:
    """Sign agreement across deterministic interleaved subsamples (index ``i % n_splits``)."""
    if isinstance(n_splits, bool) or not isinstance(n_splits, int) or n_splits < 2:
        raise DataError(
            f"subsample consistency requires an integer n_splits >= 2; got {n_splits!r}"
        )
    array = finite_array(outcomes, "subsample consistency outcomes")
    if array.size < n_splits:
        raise DataError(
            f"subsample consistency needs at least {n_splits} outcomes; got {array.size}"
        )
    positive = sum(1 for start in range(n_splits) if float(np.mean(array[start::n_splits])) > 0.0)
    return {"n_splits": n_splits, "positive_fraction": positive / n_splits}


def rolling_effect_size(outcomes: Sequence[float], *, window: int = 21) -> list[float | None]:
    """Trailing-window mean/std standardized effect; warmup and zero-variance windows are None."""
    if isinstance(window, bool) or not isinstance(window, int) or window < 2:
        raise DataError(f"rolling effect window must be an integer >= 2; got {window!r}")
    array = finite_array(outcomes, "rolling effect outcomes")
    series: list[float | None] = []
    for index in range(array.size):
        if index < window - 1:
            series.append(None)
            continue
        trailing = array[index - window + 1 : index + 1]
        std = float(np.std(trailing, ddof=1))
        series.append(float(np.mean(trailing)) / std if std > 0.0 else None)
    return series


__all__ = ["rolling_effect_size", "subsample_consistency", "temporal_split_effects"]
