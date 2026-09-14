"""Directional-change extremes: zigzag turning points confirmed by a fixed retracement.

A top is the highest high since the last bottom, and it becomes *knowable* only on the first bar
whose close has retraced ``sigma`` (a fraction) below it; bottoms mirror this. Unlike fractal
swings, the confirmation lag is not fixed in bars but depends on how fast price turns, so every
event carries both ``index`` (where the extreme sits) and ``confirmed_index`` (the first bar a live
trader could have known). Entries keyed on ``index`` read the future; ``dc_known_by`` is the guard.

Provenance: github.com/neurotrader888/TechnicalAnalysisAutomation/directional_change.py
@da99c20bf3d977b639451258cd6cfca9baa1dcc3 (MIT); adapted: typed ``DCExtreme`` events over the
validated ``OHLCV`` container, explicit ``confirmed_index`` semantics, ``dc_known_by`` filter,
fail-loud ``sigma`` validation; the pandas wrapper and plotting were dropped. The state machine
and its comparisons are unchanged (parity fixture
``tests/fixtures/neurotrader/directional_change.json``).
"""

from __future__ import annotations

from dataclasses import dataclass

from alpha_core import DataError
from alpha_patterns.series import OHLCV
from alpha_patterns.swings import SwingKind


@dataclass(frozen=True)
class DCExtreme:
    """One confirmed directional-change extreme."""

    index: int  # bar where the extreme sits
    confirmed_index: int  # first bar whose close retraced ``sigma`` from it
    price: float
    kind: SwingKind


def directional_change(bars: OHLCV, *, sigma: float) -> list[DCExtreme]:
    """Alternating tops and bottoms in confirmation order.

    The machine starts by looking for a top (the series is assumed to begin at a bottom), tracks
    the running high, and confirms it when ``close < high * (1 - sigma)``; it then tracks the
    running low and confirms it when ``close > low * (1 + sigma)``. ``sigma`` is a fraction in
    ``(0, 1)``.
    """
    if not 0.0 < sigma < 1.0:
        raise DataError(f"directional-change sigma must be in (0, 1), got {sigma}")
    close, high, low = bars.close, bars.high, bars.low
    events: list[DCExtreme] = []
    up_zig = True  # last extreme is a bottom; the next one is a top
    tmp_max, tmp_max_i = float(high[0]), 0
    tmp_min, tmp_min_i = float(low[0]), 0
    for i in range(len(bars)):
        if up_zig:
            if high[i] > tmp_max:
                tmp_max, tmp_max_i = float(high[i]), i
            elif close[i] < tmp_max - tmp_max * sigma:
                events.append(DCExtreme(tmp_max_i, i, tmp_max, "high"))
                up_zig = False
                tmp_min, tmp_min_i = float(low[i]), i
        elif low[i] < tmp_min:
            tmp_min, tmp_min_i = float(low[i]), i
        elif close[i] > tmp_min + tmp_min * sigma:
            events.append(DCExtreme(tmp_min_i, i, tmp_min, "low"))
            up_zig = True
            tmp_max, tmp_max_i = float(high[i]), i
    return events


def dc_known_by(events: list[DCExtreme], bar: int) -> list[DCExtreme]:
    """The extremes a trader standing at ``bar`` could have seen (confirmed at or before it)."""
    return [e for e in events if e.confirmed_index <= bar]
