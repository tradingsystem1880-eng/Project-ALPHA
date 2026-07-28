"""Matched control sampling — the comparison that turns a statistic into evidence.

"Triple taps resolve upward 58% of the time" is not a finding until you know what an *arbitrary* bar
does. But an arbitrary bar is the wrong comparison too: triple taps occur near support, after a
decline, and support bounces at a decent rate for reasons that have nothing to do with the pattern.
Comparing against unmatched bars therefore credits the pattern for its location.

Controls here are drawn from bars sharing the event's **trend state** and **distance above the
trailing low**, so the surviving difference is attributable to the pattern's geometry rather than to
where in the cycle it tends to appear. Sampling excludes a buffer around each event so a "control"
cannot be the event itself viewed a few bars early.

Determinism: every draw derives from an explicit seed, per the repo convention.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_patterns.context import TrendState
from alpha_patterns.series import FloatArray


@dataclass(frozen=True)
class MatchedControls:
    """Control bar indices drawn to match a set of event bars."""

    event_indices: tuple[int, ...]
    control_indices: tuple[int, ...]
    n_per_event: int
    unmatched_events: int  # events for which no acceptable control existed
    seed: int


def sample_matched_controls(
    event_indices: list[int],
    *,
    trend: list[TrendState],
    distance: FloatArray,
    n_bars: int,
    n_per_event: int = 5,
    distance_tolerance: float = 0.25,
    exclusion_bars: int = 60,
    horizon_bars: int = 0,
    seed: int = 7,
) -> MatchedControls:
    """Draw ``n_per_event`` control bars per event, matched on trend state and location.

    ``distance_tolerance`` is a *relative* band on distance-above-trailing-low: a control must sit
    within ±25% (by default) of the event's own value. ``exclusion_bars`` keeps controls away from
    any event, and ``horizon_bars`` reserves enough room at the end of the series for the control's
    forward window to be measurable — without it, controls drawn near the end would resolve as
    "unresolved" far more often than events and quietly bias the comparison.
    """
    if n_per_event < 1:
        raise DataError(f"n_per_event must be >= 1, got {n_per_event}")
    if distance_tolerance <= 0.0:
        raise DataError(f"distance_tolerance must be > 0, got {distance_tolerance}")
    if len(trend) != n_bars or distance.size != n_bars:
        raise DataError(
            f"trend/distance must cover {n_bars} bars, got {len(trend)}/{distance.size}"
        )

    rng = np.random.default_rng(seed)
    last_usable = n_bars - horizon_bars - 1
    if last_usable < 1:
        raise DataError("series is shorter than the requested horizon; no controls are drawable")

    excluded = np.zeros(n_bars, dtype=bool)
    for e in event_indices:
        excluded[max(0, e - exclusion_bars) : min(n_bars, e + exclusion_bars + 1)] = True
    excluded[last_usable + 1 :] = True

    trend_arr = np.array(trend, dtype=object)
    picked: list[int] = []
    unmatched = 0

    for e in event_indices:
        if e >= n_bars:
            unmatched += 1
            continue
        target = float(distance[e])
        band = abs(target) * distance_tolerance + 1e-9
        eligible = np.flatnonzero(
            (~excluded) & (trend_arr == trend[e]) & (np.abs(distance - target) <= band)
        )
        if eligible.size == 0:
            unmatched += 1
            continue
        take = min(n_per_event, eligible.size)
        picked.extend(int(x) for x in rng.choice(eligible, size=take, replace=False))

    return MatchedControls(
        event_indices=tuple(event_indices),
        control_indices=tuple(sorted(picked)),
        n_per_event=n_per_event,
        unmatched_events=unmatched,
        seed=seed,
    )
