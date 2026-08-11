"""Fractal swing-point detection — the primitive both studies are built on.

A swing low at bar ``i`` with lookback ``L`` is a bar whose low is the lowest of the ``2L+1`` bars
centred on it. The subtlety that decides whether a study is honest is **when you are allowed to know
about it**: the definition inspects ``L`` bars *after* ``i``, so the swing cannot be confirmed until
bar ``i + L``. Every event carries both indices:

- ``index`` — where the swing sits (used for geometry: price levels, line anchors)
- ``confirmed_index`` — the first bar at which a live trader could have known (used for entries)

Any code that enters a trade at ``index`` rather than ``confirmed_index`` is reading the future.
This split is what the ``bias_guard`` tests verify.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import OHLCV, FloatArray

SwingKind = Literal["high", "low"]


@dataclass(frozen=True)
class Swing:
    """One confirmed fractal swing point."""

    index: int  # bar where the extreme sits
    confirmed_index: int  # first bar at which it was knowable (index + lookback)
    price: float
    kind: SwingKind
    lookback: int


def _fractal_indices(values: FloatArray, lookback: int, *, find_low: bool) -> list[int]:
    n = values.size
    out: list[int] = []
    for i in range(lookback, n - lookback):
        window = values[i - lookback : i + lookback + 1]
        centre = values[i]
        if find_low:
            # Strict against the left, non-strict against the right: with equal lows the earlier
            # bar is taken as the swing, which keeps detection deterministic on flat bases.
            if centre <= np.min(window) and centre < np.min(values[i - lookback : i]):
                out.append(i)
        elif centre >= np.max(window) and centre > np.max(values[i - lookback : i]):
            out.append(i)
    return out


def find_swings(bars: OHLCV, *, lookback: int, kind: SwingKind) -> list[Swing]:
    """All fractal swings of one kind, in bar order.

    ``lookback`` is the ``L`` of a ``2L+1`` fractal: larger ``L`` yields fewer, more structurally
    significant points. The user's sweep is ``L in {3, 5, 8}``.
    """
    if lookback < 1:
        raise DataError(f"swing lookback must be >= 1, got {lookback}")
    if len(bars) < 2 * lookback + 1:
        return []

    values = bars.low if kind == "low" else bars.high
    idxs = _fractal_indices(values, lookback, find_low=(kind == "low"))
    return [
        Swing(
            index=i,
            confirmed_index=i + lookback,
            price=float(values[i]),
            kind=kind,
            lookback=lookback,
        )
        for i in idxs
    ]


def swings_known_by(swings: list[Swing], bar: int) -> list[Swing]:
    """Filter to the swings a trader standing at ``bar`` could actually have seen.

    The single most useful guard in the library: any point-in-time question ("what was the structure
    at the moment of the third tap?") must be answered through this, never through the full list.
    """
    return [s for s in swings if s.confirmed_index <= bar]
