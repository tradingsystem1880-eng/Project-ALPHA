"""Pure lead-lag alignment diagnostics (spec §9, ADR-0025).

Correlates ``signal[t]`` against ``outcome[t + lag]`` across a symmetric lag range. A
genuinely predictive signal peaks at positive lags (the signal leads the outcome); a
signal whose strongest association sits at negative lags is echoing the PAST outcome —
the classic construction-leak signature — and is flagged suspicious. The diagnostic is
an advisory screen for plan review, never an admission authority.
"""

from __future__ import annotations

from collections.abc import Sequence

from alpha_core import DataError
from alpha_research._arrays import finite_array, pearson_or_none

# A negative-lag peak below this magnitude is noise, not a leak signature.
_LEAK_MAGNITUDE_FLOOR = 0.2
# Guards float ties: equal-magnitude peaks on both sides must not read as leakage.
_LEAK_MARGIN = 1e-9


def leadlag_profile(
    signal: Sequence[float], outcome: Sequence[float], *, max_lag: int = 5
) -> list[dict[str, float | int | None]]:
    """Correlation of ``signal[t]`` with ``outcome[t + lag]`` for lag in [-max_lag, max_lag]."""
    if isinstance(max_lag, bool) or not isinstance(max_lag, int) or max_lag < 1:
        raise DataError(f"lead-lag max_lag must be a positive integer; got {max_lag!r}")
    signals = finite_array(signal, "lead-lag signal")
    outcomes = finite_array(outcome, "lead-lag outcome")
    if signals.size != outcomes.size:
        raise DataError("lead-lag signal and outcome must share one length")
    if signals.size - max_lag < 3:
        raise DataError(
            f"lead-lag max_lag {max_lag} leaves fewer than three pairs for {signals.size} points"
        )
    rows: list[dict[str, float | int | None]] = []
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            paired_signal = signals[: signals.size - lag]
            paired_outcome = outcomes[lag:]
        else:
            paired_signal = signals[-lag:]
            paired_outcome = outcomes[: outcomes.size + lag]
        rows.append(
            {
                "lag": lag,
                "n": int(paired_signal.size),
                "correlation": pearson_or_none(paired_signal, paired_outcome),
            }
        )
    return rows


def leakage_diagnostic(
    profile: Sequence[dict[str, float | int | None]],
) -> dict[str, bool | str]:
    """Flag a profile whose negative-lag peak dominates every positive-lag correlation."""
    if not profile:
        raise DataError("leakage diagnostic requires a non-empty lead-lag profile")
    best_negative: tuple[float, int] | None = None
    best_positive: tuple[float, int] | None = None
    for row in profile:
        lag = row["lag"]
        correlation = row["correlation"]
        if not isinstance(lag, int) or lag == 0 or not isinstance(correlation, float):
            continue
        magnitude = abs(correlation)
        if lag < 0 and (best_negative is None or magnitude > best_negative[0]):
            best_negative = (magnitude, lag)
        if lag > 0 and (best_positive is None or magnitude > best_positive[0]):
            best_positive = (magnitude, lag)
    positive_peak = best_positive[0] if best_positive is not None else 0.0
    if (
        best_negative is not None
        and best_negative[0] >= _LEAK_MAGNITUDE_FLOOR
        and best_negative[0] > positive_peak + _LEAK_MARGIN
    ):
        return {
            "suspicious": True,
            "reason": (
                f"peak |correlation| {best_negative[0]:.3f} at negative lag "
                f"{best_negative[1]} exceeds the best positive-lag |correlation| "
                f"{positive_peak:.3f}: the signal echoes the past outcome"
            ),
        }
    return {
        "suspicious": False,
        "reason": "no negative-lag correlation dominates the positive-lag structure",
    }


__all__ = ["leadlag_profile", "leakage_diagnostic"]
