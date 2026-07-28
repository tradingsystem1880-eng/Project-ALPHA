"""Alternating swing structure and break-of-structure detection.

Every pattern in the head-and-shoulders family is a statement about *alternating* pivots — a low,
then a high, then a low — and about whether price has **broken structure** between them. Both
primitives live here because the triple-tap module never needed them: it iterated lows alone and
consulted highs afterwards as decoration.

**Break of structure (BOS)** is what separates a Quasimodo from a plain inverse head and shoulders.
After the head prints, a bullish QM requires price to *close* above the swing high that preceded
it — a shift from lower-highs to a higher-high — before the right shoulder forms. A close is
required rather than a wick: an intraday poke closing back inside has not changed the structure.

Point-in-time throughout. A pivot enters the sequence at its ``confirmed_index``, never at its
``index``, and a BOS is searched only from the bar after the reference pivot was confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import OHLCV
from alpha_patterns.swings import Swing, find_swings

Direction = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class StructureBreak:
    """The first close beyond a structural level, with the level it broke."""

    index: int  # bar whose close broke the level (-1 if never)
    price: float  # that close (nan if never)
    level: float  # the level broken
    level_index: int  # bar the level came from
    is_upward: bool

    @property
    def occurred(self) -> bool:
        return self.index >= 0


def swing_sequence(bars: OHLCV, *, lookback: int) -> list[Swing]:
    """Confirmed highs and lows merged into one strictly alternating sequence, in bar order.

    Raw fractal detection can emit two lows with no intervening high (a stair-step down). A pattern
    defined over alternating pivots needs that collapsed, so consecutive same-kind pivots reduce
    to the more extreme one — the lower low, or the higher high. That keeps the sequence a faithful
    zig-zag without inventing pivots.
    """
    if lookback < 1:
        raise DataError(f"swing_sequence lookback must be >= 1, got {lookback}")

    merged = sorted(
        find_swings(bars, lookback=lookback, kind="high")
        + find_swings(bars, lookback=lookback, kind="low"),
        key=lambda s: s.index,
    )
    if not merged:
        return []

    out: list[Swing] = [merged[0]]
    for s in merged[1:]:
        prev = out[-1]
        if s.kind != prev.kind:
            out.append(s)
            continue
        # Same kind twice running: keep whichever is the genuine extreme.
        keep_new = s.price < prev.price if s.kind == "low" else s.price > prev.price
        if keep_new:
            out[-1] = s
    return out


def break_of_structure(
    bars: OHLCV,
    *,
    level: float,
    level_index: int,
    search_from: int,
    upward: bool,
    search_to: int | None = None,
) -> StructureBreak:
    """First **close** beyond ``level``, searched forward from ``search_from`` (inclusive).

    ``search_from`` must already be a bar at which the level was knowable — callers pass a
    ``confirmed_index``, not a pivot ``index``. Closes are used rather than highs/lows precisely
    because a wick beyond a level is not a break of structure.
    """
    n = len(bars)
    if search_from < 0:
        raise DataError(f"search_from must be >= 0, got {search_from}")
    if not np.isfinite(level):
        raise DataError("break_of_structure requires a finite level")

    end = n if search_to is None else min(search_to + 1, n)
    if search_from >= end:
        return StructureBreak(-1, float("nan"), level, level_index, upward)

    window = bars.close[search_from:end]
    hits = np.flatnonzero(window > level if upward else window < level)
    if not hits.size:
        return StructureBreak(-1, float("nan"), level, level_index, upward)

    idx = int(search_from + hits[0])
    return StructureBreak(idx, float(bars.close[idx]), level, level_index, upward)


def last_pivot_before(
    swings: list[Swing], index: int, kind: Literal["high", "low"], *, known_by: int | None = None
) -> Swing | None:
    """The most recent pivot of ``kind`` strictly before ``index``.

    ``known_by`` additionally restricts to pivots confirmed by that bar — the point-in-time filter a
    live trader is subject to.
    """
    best: Swing | None = None
    for s in swings:
        if s.index >= index:
            break
        if s.kind != kind:
            continue
        if known_by is not None and s.confirmed_index > known_by:
            continue
        best = s
    return best


def extreme_between(
    swings: list[Swing], lo: int, hi: int, kind: Literal["high", "low"]
) -> Swing | None:
    """The most extreme pivot of ``kind`` strictly between bars ``lo`` and ``hi``.

    This is how the two neckline anchors are chosen: the highest high between the left shoulder and
    the head, and between the head and the right shoulder.
    """
    candidates = [s for s in swings if lo < s.index < hi and s.kind == kind]
    if not candidates:
        return None
    return (
        max(candidates, key=lambda s: s.price)
        if kind == "high"
        else min(candidates, key=lambda s: s.price)
    )
