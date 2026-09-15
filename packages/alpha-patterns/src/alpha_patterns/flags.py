"""Flags and pennants: a pole, a short counter-trend consolidation, and a breakout.

Two detectors share one result type. The **PIP** variant summarises the consolidation with five
perceptually important points, requires the middle point to be the local extreme (a zigzag of the
right sense), draws the two flag lines through the outer points and confirms on a close beyond
them. The **trendline** variant waits for a rolling-window pole tip, fits the consolidation's
support and resistance by slope optimisation on the bars before the current one, and confirms on
a close beyond the projected line. Both bound the flag to at most half the pole's width and a
fraction of its height, and both are knowable only on ``confirmed_index``.

Provenance: github.com/neurotrader888/TechnicalAnalysisAutomation/flags_pennants.py
@da99c20bf3d977b639451258cd6cfca9baa1dcc3 (MIT); adapted: one frozen ``FlagPattern`` with
``bullish``/``pennant`` fields instead of four mutable lists, ``DataError`` instead of ``assert``,
and the upstream rolling-window top/bottom test kept as a private helper so confirmation timing
matches upstream exactly (``find_swings`` differs only for extremes within ``order`` bars of the
start). Geometry, thresholds and confirmation rules are unchanged (parity fixture
``tests/fixtures/neurotrader/flags.json``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_patterns.pips import find_pips
from alpha_patterns.series import FloatArray
from alpha_patterns.trendline_fit import fit_trendlines_single


@dataclass(frozen=True)
class FlagPattern:
    """One confirmed flag or pennant; line intercepts are at ``tip_index``."""

    bullish: bool
    pennant: bool
    base_index: int
    base_price: float
    tip_index: int
    tip_price: float
    confirmed_index: int
    confirmed_price: float
    flag_width: int
    flag_height: float
    pole_width: int
    pole_height: float
    support_slope: float
    support_intercept: float
    resist_slope: float
    resist_intercept: float


def _rolling_top(data: FloatArray, i: int, order: int) -> bool:
    if i < order * 2 + 1:
        return False
    k = i - order
    v = data[k]
    return all(data[k + j] <= v and data[k - j] <= v for j in range(1, order + 1))


def _rolling_bottom(data: FloatArray, i: int, order: int) -> bool:
    if i < order * 2 + 1:
        return False
    k = i - order
    v = data[k]
    return all(data[k + j] >= v and data[k - j] >= v for j in range(1, order + 1))


def _check(values: FloatArray, order: int) -> FloatArray:
    data = np.asarray(values, dtype=np.float64)
    if data.ndim != 1 or data.size < 2:
        raise DataError(f"flag values need a 1-D array of >= 2 values, got shape {data.shape}")
    if not bool(np.all(np.isfinite(data))):
        raise DataError("flag values contain non-finite values")
    if order < 3:
        raise DataError(f"order must be >= 3, got {order}")
    return data


def _pips_pattern(
    data: FloatArray, base: int, i: int, order: int, *, bullish: bool
) -> FlagPattern | None:
    window = data[base : i + 1]
    tip = int(window.argmax() if bullish else window.argmin()) + base
    if i - tip < max(5, order * 0.5):
        return None
    pole_width, flag_width = tip - base, i - tip
    if flag_width > pole_width * 0.5:
        return None
    if bullish:
        pole_height = float(data[tip] - data[base])
        flag_height = float(data[tip] - data[tip : i + 1].min())
    else:
        pole_height = float(data[base] - data[tip])
        flag_height = float(data[tip : i + 1].max() - data[tip])
    if flag_height > pole_height * 0.5:
        return None
    px, py = find_pips(data[tip : i + 1], 5, distance="vertical")
    if bullish and not (py[2] > py[1] and py[2] > py[3]):
        return None
    if not bullish and not (py[2] < py[1] and py[2] < py[3]):
        return None
    # the line through points 0 and 2 anchors at the tip; the other through points 1 and 3
    outer_slope = float((py[2] - py[0]) / (px[2] - px[0]))
    outer_intercept = float(py[0])
    inner_slope = float((py[3] - py[1]) / (px[3] - px[1]))
    inner_intercept = float(py[1] + (px[0] - px[1]) * inner_slope)
    if bullish:
        resist_slope, resist_intercept = outer_slope, outer_intercept
        support_slope, support_intercept = inner_slope, inner_intercept
    else:
        support_slope, support_intercept = outer_slope, outer_intercept
        resist_slope, resist_intercept = inner_slope, inner_intercept
    if resist_slope != support_slope:
        intersection = (support_intercept - resist_intercept) / (resist_slope - support_slope)
    else:
        intersection = -flag_width * 100.0
    if 0.0 <= intersection <= px[4]:
        return None  # lines cross inside the flag
    if bullish:
        if intersection < 0.0 and intersection > -1.0 * flag_width:
            return None  # harshly diverging
        if py[4] < py[0] + resist_slope * px[4]:
            return None  # no breakout above the resistance line
        pennant = support_slope > 0.0
    else:
        if py[4] > py[0] + support_slope * px[4]:
            return None  # no breakout below the support line
        if intersection < 0.0 and intersection > -flag_width:
            return None
        pennant = resist_slope < 0.0
    return FlagPattern(
        bullish=bullish,
        pennant=pennant,
        base_index=base,
        base_price=float(data[base]),
        tip_index=tip,
        tip_price=float(data[tip]),
        confirmed_index=i,
        confirmed_price=float(data[i]),
        flag_width=flag_width,
        flag_height=flag_height,
        pole_width=pole_width,
        pole_height=pole_height,
        support_slope=support_slope,
        support_intercept=support_intercept,
        resist_slope=resist_slope,
        resist_intercept=resist_intercept,
    )


def detect_flags_pips(values: FloatArray, *, order: int) -> list[FlagPattern]:
    """PIP-variant flags and pennants over a price series (log closes, usually)."""
    data = _check(values, order)
    pending_bull: int | None = None
    pending_bear: int | None = None
    found: list[FlagPattern] = []
    for i in range(data.size):
        if _rolling_top(data, i, order):
            pending_bear = i - order
        if _rolling_bottom(data, i, order):
            pending_bull = i - order
        if pending_bear is not None:
            pat = _pips_pattern(data, pending_bear, i, order, bullish=False)
            if pat is not None:
                found.append(pat)
                pending_bear = None
        if pending_bull is not None:
            pat = _pips_pattern(data, pending_bull, i, order, bullish=True)
            if pat is not None:
                found.append(pat)
                pending_bull = None
    return found


def _trendline_pattern(
    data: FloatArray, base: int, tip: int, i: int, *, bullish: bool
) -> FlagPattern | None:
    after_tip = data[tip + 1 : i]
    if bullish and after_tip.max() > data[tip]:
        return None
    if not bullish and after_tip.min() < data[tip]:
        return None
    pole_width, flag_width = tip - base, i - tip
    if bullish:
        pole_height = float(data[tip] - data[base])
        flag_height = float(data[tip] - data[tip:i].min())
    else:
        pole_height = float(data[base] - data[tip])
        flag_height = float(data[tip:i].max() - data[tip])
    if flag_width > pole_width * 0.5 or flag_height > pole_height * 0.75:
        return None
    pair = fit_trendlines_single(data[tip:i])  # the bars before ``i``, never ``i`` itself
    if bullish:
        if data[i] <= pair.resistance.value_at(flag_width + 1):
            return None
        pennant = pair.support.slope > 0.0
    else:
        if data[i] >= pair.support.value_at(flag_width + 1):
            return None
        pennant = pair.resistance.slope < 0.0
    return FlagPattern(
        bullish=bullish,
        pennant=pennant,
        base_index=base,
        base_price=float(data[base]),
        tip_index=tip,
        tip_price=float(data[tip]),
        confirmed_index=i,
        confirmed_price=float(data[i]),
        flag_width=flag_width,
        flag_height=flag_height,
        pole_width=pole_width,
        pole_height=pole_height,
        support_slope=pair.support.slope,
        support_intercept=pair.support.intercept,
        resist_slope=pair.resistance.slope,
        resist_intercept=pair.resistance.intercept,
    )


def detect_flags_trendline(values: FloatArray, *, order: int) -> list[FlagPattern]:
    """Trendline-variant flags and pennants over a price series (log closes, usually)."""
    data = _check(values, order)
    last_top = last_bottom = -1
    pending_bull: tuple[int, int] | None = None  # (base, tip)
    pending_bear: tuple[int, int] | None = None
    found: list[FlagPattern] = []
    for i in range(data.size):
        if _rolling_top(data, i, order):
            last_top = i - order
            if last_bottom != -1:
                pending_bull = (last_bottom, last_top)
        if _rolling_bottom(data, i, order):
            last_bottom = i - order
            if last_top != -1:
                pending_bear = (last_top, last_bottom)
        if pending_bear is not None:
            pat = _trendline_pattern(data, *pending_bear, i, bullish=False)
            if pat is not None:
                found.append(pat)
                pending_bear = None
        if pending_bull is not None:
            pat = _trendline_pattern(data, *pending_bull, i, bullish=True)
            if pat is not None:
                found.append(pat)
                pending_bull = None
    return found


def flags_known_by(patterns: list[FlagPattern], bar: int) -> list[FlagPattern]:
    """Patterns confirmed at or before ``bar``."""
    return [p for p in patterns if p.confirmed_index <= bar]
