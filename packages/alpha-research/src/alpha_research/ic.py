"""Pure rank information-coefficient primitives (spec §9, ADR-0025).

Spearman rank IC over a full sample plus a strictly trailing rolling variant. The
rolling series reads window ``[i-window+1 .. i]`` only, so poisoning the future can
never rewrite earlier values (bias-guarded). Degenerate trailing windows yield ``None``
— explicitly undefined, never fabricated — while a degenerate full sample fails loud.
"""

from __future__ import annotations

from collections.abc import Sequence

from alpha_core import DataError
from alpha_research._arrays import average_ranks, finite_array, pearson_or_none


def rank_ic(signal: Sequence[float], outcome: Sequence[float]) -> float:
    """Spearman rank correlation between a signal and its realized outcomes."""
    signals = finite_array(signal, "rank IC signal")
    outcomes = finite_array(outcome, "rank IC outcome")
    if signals.size != outcomes.size:
        raise DataError("rank IC signal and outcome must share one length")
    if signals.size < 3:
        raise DataError("rank IC requires at least three observations")
    value = pearson_or_none(average_ranks(signals), average_ranks(outcomes))
    if value is None:
        raise DataError("rank IC is undefined for a constant signal or outcome series")
    return value


def rolling_rank_ic(
    signal: Sequence[float], outcome: Sequence[float], *, window: int = 21
) -> list[float | None]:
    """Trailing-window Spearman rank IC series; warmup and degenerate windows are None."""
    if isinstance(window, bool) or not isinstance(window, int) or window < 3:
        raise DataError(f"rolling rank IC window must be an integer >= 3; got {window!r}")
    signals = finite_array(signal, "rolling rank IC signal")
    outcomes = finite_array(outcome, "rolling rank IC outcome")
    if signals.size != outcomes.size:
        raise DataError("rolling rank IC signal and outcome must share one length")
    series: list[float | None] = []
    for index in range(signals.size):
        if index < window - 1:
            series.append(None)
            continue
        signal_window = signals[index - window + 1 : index + 1]
        outcome_window = outcomes[index - window + 1 : index + 1]
        series.append(pearson_or_none(average_ranks(signal_window), average_ranks(outcome_window)))
    return series


__all__ = ["rank_ic", "rolling_rank_ic"]
