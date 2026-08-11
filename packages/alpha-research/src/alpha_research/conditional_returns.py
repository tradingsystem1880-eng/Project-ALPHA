"""Pure conditional forward-return analysis primitives (spec §9, ADR-0025).

Deterministic, engine-free D1 analysis-family building blocks: forward-return outcome
construction with explicit ``None`` tails (never fabricated), per-group conditional
summaries, treatment-vs-control effect estimates, and rank-bucket breakdowns. All
functions fail loud on non-finite, degenerate, or mismatched inputs.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np

from alpha_core import DataError
from alpha_research._arrays import finite_array


def forward_returns(closes: Sequence[float], *, horizon: int) -> list[float | None]:
    """Simple ``horizon``-bar forward returns; tail entries with no future close are None."""
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise DataError(f"forward returns horizon must be a positive integer; got {horizon!r}")
    array = finite_array(closes, "forward returns closes")
    if np.any(array <= 0):
        raise DataError("forward returns require strictly positive closes")
    outcomes: list[float | None] = []
    for index in range(array.size):
        if index + horizon >= array.size:
            outcomes.append(None)
        else:
            outcomes.append(float(array[index + horizon] / array[index] - 1.0))
    return outcomes


def conditional_return_summary(
    groups: Mapping[str, Sequence[float]],
) -> list[dict[str, float | int | str]]:
    """Per-group n/mean/median rows, sorted by group name for determinism."""
    if not groups:
        raise DataError("conditional return summary requires at least one group")
    rows: list[dict[str, float | int | str]] = []
    for name in sorted(groups):
        values = finite_array(groups[name], f"conditional returns for group {name!r}")
        if values.size == 0:
            raise DataError(f"conditional return group {name!r} is empty")
        rows.append(
            {
                "group": name,
                "n": int(values.size),
                "mean": float(np.mean(values)),
                "median": float(np.median(values)),
            }
        )
    return rows


def difference_in_means(
    treatment: Sequence[float], control: Sequence[float]
) -> dict[str, float | int]:
    """Mean/median difference plus the pooled-variance standardized effect (Cohen's d)."""
    treated = finite_array(treatment, "difference-in-means treatment outcomes")
    controls = finite_array(control, "difference-in-means control outcomes")
    if treated.size < 2 or controls.size < 2:
        raise DataError("difference in means requires at least two outcomes per arm")
    difference = float(np.mean(treated) - np.mean(controls))
    pooled_variance = (
        (treated.size - 1) * float(np.var(treated, ddof=1))
        + (controls.size - 1) * float(np.var(controls, ddof=1))
    ) / (treated.size + controls.size - 2)
    if pooled_variance <= 0.0:
        raise DataError("difference in means is unstandardizable for zero pooled variance")
    return {
        "difference": difference,
        "difference_in_medians": float(np.median(treated) - np.median(controls)),
        "standardized_effect": difference / math.sqrt(pooled_variance),
        "n_treatment": int(treated.size),
        "n_control": int(controls.size),
    }


def quantile_breakdown(
    signal: Sequence[float], outcome: Sequence[float], *, quantiles: int = 4
) -> list[dict[str, float | int]]:
    """Mean outcome per signal-rank bucket (1..quantiles, ascending signal)."""
    if isinstance(quantiles, bool) or not isinstance(quantiles, int) or quantiles < 2:
        raise DataError(f"quantiles must be an integer >= 2; got {quantiles!r}")
    signals = finite_array(signal, "quantile breakdown signal")
    outcomes = finite_array(outcome, "quantile breakdown outcome")
    if signals.size != outcomes.size:
        raise DataError("quantile breakdown signal and outcome must share one length")
    if signals.size < quantiles:
        raise DataError(
            f"quantile breakdown needs at least {quantiles} observations; got {signals.size}"
        )
    order = np.argsort(signals, kind="stable")
    buckets: list[list[float]] = [[] for _ in range(quantiles)]
    for position, index in enumerate(order):
        buckets[position * quantiles // signals.size].append(float(outcomes[index]))
    return [
        {
            "bucket": bucket_index + 1,
            "n": len(values),
            "mean_outcome": float(np.mean(values)),
        }
        for bucket_index, values in enumerate(buckets)
    ]


__all__ = [
    "conditional_return_summary",
    "difference_in_means",
    "forward_returns",
    "quantile_breakdown",
]
