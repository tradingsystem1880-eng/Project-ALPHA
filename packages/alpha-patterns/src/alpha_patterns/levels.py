"""Horizontal price levels a trader actually watches: Fibonacci retracements and round numbers.

Both are pure chart folklore in the sense that neither has a mechanism, and both are worth testing
precisely because so many people act on them — a level that enough traders watch can become real
through their orders alone. That is a testable claim, and this module builds the geometry so it can
be tested rather than asserted.

**The causality trap here is the anchor, not the arithmetic.** A Fibonacci retracement is drawn
between a swing high and a swing low. On a finished chart those swings are obvious; in real time
they are not, and a swing is only *known* to be a swing once enough bars have passed to confirm it.
:func:`fib_levels_at` therefore takes swings from :func:`alpha_patterns.find_swings`, which stamps
confirmation at ``index + lookback``, and refuses to use any swing not yet confirmed at the bar
being asked about. Skipping that step is the single most common way a Fibonacci study produces a
spectacular and completely fake result: retracement levels drawn from tomorrow's high are, quite
naturally, excellent support.

Round numbers need no anchor and so have no such trap. They do have a scale problem — "round" for
XRP at 0.50 is not "round" for BTC at 68,000 — so :func:`round_levels` derives the grid from the
price's own order of magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import FloatArray
from alpha_patterns.swings import Swing

#: The retracement ratios in common use. 0.5 is not a Fibonacci number and is included anyway,
#: because traders draw it — the study is about what people watch, not about number theory.
FIB_RATIOS: tuple[float, ...] = (0.236, 0.382, 0.5, 0.618, 0.786)
#: Extension ratios used for targets beyond the prior swing.
FIB_EXTENSIONS: tuple[float, ...] = (1.272, 1.618, 2.618)


@dataclass(frozen=True)
class FibGrid:
    """A retracement grid anchored on one confirmed swing leg."""

    #: Bar the grid became knowable — the later of the two swings' confirmation bars.
    known_at: int
    swing_low: float
    swing_high: float
    #: Whether the leg being retraced went up (low → high) or down (high → low).
    upward: bool
    #: ratio → price, for :data:`FIB_RATIOS`.
    levels: dict[float, float]
    #: ratio → price, for :data:`FIB_EXTENSIONS`.
    extensions: dict[float, float]

    @property
    def span(self) -> float:
        return self.swing_high - self.swing_low

    def nearest(self, price: float) -> tuple[float, float]:
        """The ratio whose level is closest to ``price``, and the distance as a fraction of span."""
        if self.span <= 0.0:
            raise DataError("FibGrid.nearest needs a positive swing span")
        ratio = min(self.levels, key=lambda r: abs(self.levels[r] - price))
        return ratio, abs(self.levels[ratio] - price) / self.span


def _confirmed_by(swings: list[Swing], index: int) -> list[Swing]:
    """Swings whose confirmation bar is at or before ``index`` — all that is knowable there."""
    return [s for s in swings if s.confirmed_index <= index]


def fib_levels_at(swings: list[Swing], index: int) -> FibGrid | None:
    """The retracement grid a trader could legitimately have drawn at ``index``.

    Uses the most recent confirmed swing high and swing low, which is the construction a chartist
    actually performs. Returns None when fewer than one of each is confirmed, or when the two
    coincide in price — a zero-span leg has no retracement.
    """
    known = _confirmed_by(swings, index)
    highs = [s for s in known if s.kind == "high"]
    lows = [s for s in known if s.kind == "low"]
    if not highs or not lows:
        return None
    hi, lo = highs[-1], lows[-1]
    if hi.price <= lo.price:
        return None

    upward = lo.index < hi.index
    span = hi.price - lo.price
    # Retracing an up-leg counts down from the high; retracing a down-leg counts up from the low.
    levels = {r: (hi.price - r * span if upward else lo.price + r * span) for r in FIB_RATIOS}
    extensions = {
        r: (lo.price + r * span if upward else hi.price - r * span) for r in FIB_EXTENSIONS
    }
    return FibGrid(
        known_at=max(hi.confirmed_index, lo.confirmed_index),
        swing_low=float(lo.price),
        swing_high=float(hi.price),
        upward=upward,
        levels=levels,
        extensions=extensions,
    )


def nearest_fib_distance(
    close: FloatArray, swings: list[Swing], *, ratios: tuple[float, ...] = FIB_RATIOS
) -> FloatArray:
    """Per-bar distance to the nearest retracement level, as a fraction of the swing span.

    NaN where no grid was knowable. Distance rather than a boolean because "at a fib level" needs a
    tolerance, and burying that tolerance inside the indicator would hide the one free parameter
    that decides the answer.
    """
    out = np.full(close.size, np.nan, dtype=np.float64)
    for i in range(close.size):
        grid = fib_levels_at(swings, i)
        if grid is None or grid.span <= 0.0:
            continue
        price = float(close[i])
        best = min(abs(grid.levels[r] - price) for r in ratios if r in grid.levels)
        out[i] = best / grid.span
    return out


def round_levels(price: float, *, per_decade: int = 10) -> tuple[float, float]:
    """The round numbers bracketing ``price``, on a grid derived from its own magnitude.

    Roundness is a statement about significant figures, so the grid is a power of ten scaled by the
    price's own decade. Two settings matter:

    * ``per_decade=10`` — a two-significant-figure grid: 1.00/1.10/1.20 near 1, 0.53/0.54 near 0.5,
      65,000/66,000 near 65,400.
    * ``per_decade=1`` — the coarse grid a trader means by "big round number": 1/2/3 near 1,
      0.5/0.6 near 0.5, 60,000/70,000 near 65,400.

    Both are worth testing and they disagree, which is exactly why the setting is explicit rather
    than baked in. Note the grid necessarily steps down at each decade boundary — levels really are
    finer at 0.9 than at 1.1 — so a study spanning a decade boundary should say so.
    """
    if not np.isfinite(price) or price <= 0.0:
        raise DataError(f"round_levels needs a positive finite price, got {price!r}")
    if per_decade < 1:
        raise DataError(f"round_levels per_decade must be >= 1, got {per_decade}")
    decade = 10.0 ** np.floor(np.log10(price))
    step = decade / per_decade
    below = float(np.floor(price / step) * step)
    return below, below + step


def round_number_distance(close: FloatArray, *, per_decade: int = 10) -> FloatArray:
    """Distance from each close to its nearest round number, as a fraction of the grid step.

    0 sits exactly on a round number, 0.5 is as far from one as it is possible to be. Magnetism
    toward round numbers predicts a *low* value here more often than chance would give.
    """
    out = np.full(close.size, np.nan, dtype=np.float64)
    for i in range(close.size):
        price = float(close[i])
        if not np.isfinite(price) or price <= 0.0:
            continue
        below, above = round_levels(price, per_decade=per_decade)
        step = above - below
        if step <= 0.0:
            continue
        out[i] = min(price - below, above - price) / step
    return out
