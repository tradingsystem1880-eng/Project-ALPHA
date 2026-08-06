"""Point-in-time-valid technical-pattern detectors over research-only bars."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from alpha_core import DataError
from alpha_research.data import EqualDurationResearchBars


@dataclass(frozen=True, slots=True)
class DoubleBottomSpec:
    """Frozen geometry for a symmetric-pivot double-bottom observation."""

    pivot_left: int
    pivot_right: int
    min_separation: int
    max_separation: int
    trough_tolerance: float
    min_rebound: float

    def __post_init__(self) -> None:
        for name in ("pivot_left", "pivot_right", "min_separation", "max_separation"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise DataError(f"DoubleBottomSpec.{name} must be an integer >= 1")
        if self.max_separation < self.min_separation:
            raise DataError("DoubleBottomSpec.max_separation must be >= min_separation")
        if not math.isfinite(self.trough_tolerance) or not 0.0 <= self.trough_tolerance < 1.0:
            raise DataError("DoubleBottomSpec.trough_tolerance must be finite in [0, 1)")
        if not math.isfinite(self.min_rebound) or not 0.0 <= self.min_rebound < 1.0:
            raise DataError("DoubleBottomSpec.min_rebound must be finite in [0, 1)")


@dataclass(frozen=True, slots=True)
class DoubleBottomEvent:
    """One non-overlapping pattern, observable only at ``confirmed_at``."""

    first_trough_index: int
    second_trough_index: int
    confirmation_index: int
    first_trough_at: datetime
    second_trough_at: datetime
    confirmed_at: datetime
    neckline: float
    trough_difference: float
    rebound: float


def _pivot_lows(bars: EqualDurationResearchBars, spec: DoubleBottomSpec) -> tuple[int, ...]:
    lows = tuple(bar.low for bar in bars.bars)
    pivots: list[int] = []
    for index in range(spec.pivot_left, len(lows) - spec.pivot_right):
        neighbors = (
            lows[index - spec.pivot_left : index] + lows[index + 1 : index + spec.pivot_right + 1]
        )
        if all(lows[index] < neighbor for neighbor in neighbors):
            pivots.append(index)
    return tuple(pivots)


def detect_double_bottom_events(
    bars: EqualDurationResearchBars, spec: DoubleBottomSpec
) -> tuple[DoubleBottomEvent, ...]:
    """Detect delayed, greedy, non-overlapping double bottoms without future leakage.

    A trough is not available until its complete right pivot window has closed. When several first
    troughs could pair with one second trough, the most recent qualifying trough wins. Once emitted,
    a later pattern must begin strictly after the prior confirmation bar. ``confirmed_at`` covers
    every bar the pattern semantically depends on, including the first trough's left pivot window.
    """
    pivots = _pivot_lows(bars, spec)
    events: list[DoubleBottomEvent] = []
    last_confirmation = -1
    for second_position, second in enumerate(pivots):
        confirmation = second + spec.pivot_right
        for first in reversed(pivots[:second_position]):
            if first <= last_confirmation:
                break
            separation = second - first
            if separation > spec.max_separation:
                break
            if separation < spec.min_separation:
                continue
            first_low = bars.bars[first].low
            second_low = bars.bars[second].low
            trough_difference = abs(first_low - second_low) / max(first_low, second_low)
            if trough_difference > spec.trough_tolerance:
                continue
            neckline = max(bar.high for bar in bars.bars[first : second + 1])
            higher_trough = max(first_low, second_low)
            rebound = (neckline - higher_trough) / higher_trough
            if rebound < spec.min_rebound:
                continue
            events.append(
                DoubleBottomEvent(
                    first_trough_index=first,
                    second_trough_index=second,
                    confirmation_index=confirmation,
                    first_trough_at=bars.bars[first].end,
                    second_trough_at=bars.bars[second].end,
                    confirmed_at=max(
                        bar.available_at
                        for bar in bars.bars[first - spec.pivot_left : confirmation + 1]
                    ),
                    neckline=neckline,
                    trough_difference=trough_difference,
                    rebound=rebound,
                )
            )
            last_confirmation = confirmation
            break
    return tuple(events)
