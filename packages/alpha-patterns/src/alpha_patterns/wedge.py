"""Converging trendline pairs — wedges and contracting triangles, with a computed apex.

This is the formalisation of the single most common chart-analysis claim there is: *"price is
coiling, it is about to break out."* The claim has three testable parts, and the value of a detector
is that it forces all three to be stated:

1. **Convergence.** Two lines — one over the swing highs, one under the swing lows — whose gap is
   shrinking. If the gap is not shrinking there is no wedge, only a channel.
2. **The apex.** Converging lines meet at a computable bar. "About to break out" means *near the
   apex*, and once that bar is a number, "near" stops being a feeling.
3. **Resolution.** The pattern either breaks up, breaks down, or drifts past its own apex without
   doing either. That third outcome is the interesting one, because chart folklore has no name for
   it and no statistics on it — and it is where a lot of "imminent breakout" calls actually end up.

**Construction is deliberately the chartist's own.** At each bar, take the two most recent
*confirmed* swing highs and the two most recent confirmed swing lows; those four points define the
two lines. This is O(n) rather than O(n^4) over all anchor quadruples, and more importantly it is
the construction a human actually uses — the newest structure, not the best-fitting one found by
searching the whole history. A best-fit search would be a different (and much more overfittable)
detector wearing the same name.

Point-in-time throughout: a wedge does not exist until the last of its four anchors is confirmed,
which is ``lookback`` bars after that pivot printed. ``confirmed_index`` records that bar and every
forward measurement starts from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_patterns.indicators import rolling_mean
from alpha_patterns.series import OHLCV, FloatArray, IntArray
from alpha_patterns.swings import Swing, find_swings
from alpha_patterns.trendline import Scale

WedgeKind = Literal["falling", "rising", "symmetrical"]

#: Integer codes for :func:`wedge_panel`, which must return plain numeric arrays.
KIND_CODES: dict[WedgeKind, int] = {"falling": 1, "rising": 2, "symmetrical": 3}


@dataclass(frozen=True)
class WedgeConfig:
    """Construction and resolution parameters. Defaults are the pre-registered primary spec."""

    lookback: int = 5
    min_span: int = 20  # bars from the earliest anchor to the latest
    max_span: int = 250
    min_convergence: float = 0.15  # the gap must shrink by at least this fraction across the span
    max_apex_bars: int = 200  # apex must lie within this many bars beyond the last anchor
    track_bars: int = 250  # how far past confirmation a break is still attributed to the wedge
    scale: Scale = "log"
    volume_window: int = 20

    def __post_init__(self) -> None:
        if self.lookback < 1:
            raise DataError(f"lookback must be >= 1, got {self.lookback}")
        if self.min_span < 4:
            raise DataError(f"min_span must be >= 4, got {self.min_span}")
        if self.max_span < self.min_span:
            raise DataError("max_span must be >= min_span")
        if not 0.0 < self.min_convergence < 1.0:
            raise DataError(f"min_convergence must be in (0, 1), got {self.min_convergence}")
        if self.max_apex_bars < 1:
            raise DataError(f"max_apex_bars must be >= 1, got {self.max_apex_bars}")
        if self.track_bars < 1:
            raise DataError(f"track_bars must be >= 1, got {self.track_bars}")

    @property
    def label(self) -> str:
        return (
            f"L{self.lookback}_span{self.min_span}-{self.max_span}"
            f"_conv{self.min_convergence}_apex{self.max_apex_bars}_{self.scale}"
        )


@dataclass(frozen=True)
class Wedge:
    """One converging trendline pair, its apex, and how it resolved."""

    kind: WedgeKind
    symbol: str
    config_label: str
    scale: Scale

    upper_indices: tuple[int, int]
    upper_prices: tuple[float, float]
    lower_indices: tuple[int, int]
    lower_prices: tuple[float, float]

    start_index: int  # earliest of the four anchors
    end_index: int  # latest of the four anchors
    confirmed_index: int  # first bar at which all four were knowable
    apex_index: float  # fractional bar where the lines meet (>= end_index by construction)

    width_start: float  # (upper - lower) / lower at start_index
    width_confirm: float  # ... at confirmed_index
    convergence: float  # 1 - width_confirm / width_start
    upper_slope: float  # per-bar fractional slope of the upper line
    lower_slope: float

    break_index: int  # first close outside the lines after confirmation (-1 if none)
    break_direction: int  # +1 up, -1 down, 0 none
    break_price: float
    break_volume_ratio: float
    bars_past_apex: int  # break_index - apex; negative means it broke *before* the apex
    apex_passed_unbroken: bool  # drifted through its own apex with no break — the "failed apex"

    @property
    def bars_to_apex(self) -> float:
        """Distance from the confirmation bar to the apex. Small = 'about to break out'."""
        return self.apex_index - self.confirmed_index


def _fit(i1: int, p1: float, i2: int, p2: float, scale: Scale) -> tuple[float, float]:
    """Intercept and per-bar slope of the line through two anchors, in price or log-price space."""
    if i2 == i1:
        raise DataError("wedge anchors must sit on distinct bars")
    y1 = float(np.log(p1)) if scale == "log" else p1
    y2 = float(np.log(p2)) if scale == "log" else p2
    slope = (y2 - y1) / (i2 - i1)
    return y1 - slope * i1, slope


def _line(intercept: float, slope: float, idx: FloatArray, scale: Scale) -> FloatArray:
    vals = intercept + slope * idx
    return np.asarray(np.exp(vals) if scale == "log" else vals, dtype=np.float64)


def detect_wedges(bars: OHLCV, cfg: WedgeConfig | None = None) -> list[Wedge]:
    """Every converging trendline pair in ``bars``, one event per distinct anchor quadruple.

    Walks forward one bar at a time, and at each bar considers only the structure a live trader
    could have drawn: the last two confirmed swing highs and the last two confirmed swing lows. A
    quadruple is emitted once — at the bar its final anchor was confirmed — so a wedge that stays
    valid for a hundred bars produces one event rather than a hundred.
    """
    cfg = cfg or WedgeConfig()
    highs = find_swings(bars, lookback=cfg.lookback, kind="high")
    lows = find_swings(bars, lookback=cfg.lookback, kind="low")
    if len(highs) < 2 or len(lows) < 2:
        return []

    n = len(bars)
    vol_mean = rolling_mean(bars.volume, cfg.volume_window)
    idx_axis = np.arange(n, dtype=np.float64)

    seen: set[tuple[int, int, int, int]] = set()
    out: list[Wedge] = []
    hi_ptr = lo_ptr = 0

    for bar in range(n):
        while hi_ptr < len(highs) and highs[hi_ptr].confirmed_index <= bar:
            hi_ptr += 1
        while lo_ptr < len(lows) and lows[lo_ptr].confirmed_index <= bar:
            lo_ptr += 1
        if hi_ptr < 2 or lo_ptr < 2:
            continue

        h1, h2 = highs[hi_ptr - 2], highs[hi_ptr - 1]
        l1, l2 = lows[lo_ptr - 2], lows[lo_ptr - 1]
        key = (h1.index, h2.index, l1.index, l2.index)
        if key in seen:
            continue
        seen.add(key)

        wedge = _build(bars, cfg, h1, h2, l1, l2, vol_mean, idx_axis)
        if wedge is not None:
            out.append(wedge)
    return out


def _build(  # noqa: PLR0911 — each early return is a distinct, named rejection reason
    bars: OHLCV,
    cfg: WedgeConfig,
    h1: Swing,
    h2: Swing,
    l1: Swing,
    l2: Swing,
    vol_mean: FloatArray,
    idx_axis: FloatArray,
) -> Wedge | None:
    n = len(bars)
    start = min(h1.index, l1.index)
    end = max(h2.index, l2.index)
    span = end - start
    if span < cfg.min_span or span > cfg.max_span:
        return None

    confirmed = max(h1.confirmed_index, h2.confirmed_index, l1.confirmed_index, l2.confirmed_index)
    if confirmed >= n - 1:
        return None

    a_u, b_u = _fit(h1.index, h1.price, h2.index, h2.price, cfg.scale)
    a_l, b_l = _fit(l1.index, l1.price, l2.index, l2.price, cfg.scale)

    # In log space the gap between the lines is linear in the bar index, so the apex is exact.
    # Converging means the gap is closing: (b_u - b_l) < 0 with a positive gap at the start.
    gap_slope = b_u - b_l
    gap_start = (a_u + b_u * start) - (a_l + b_l * start)
    if gap_start <= 0.0 or gap_slope >= 0.0:
        return None  # lines already crossed, or diverging (a broadening formation, not a wedge)

    apex = -(a_u - a_l) / gap_slope
    if apex < end or apex > end + cfg.max_apex_bars:
        return None  # apex behind the structure, or so far ahead it says nothing about "soon"

    upper = _line(a_u, b_u, idx_axis, cfg.scale)
    lower = _line(a_l, b_l, idx_axis, cfg.scale)

    # A wedge that price has already closed outside of is not a wedge — it is a broken one, and
    # attributing a later break to it would be reading the chart backwards.
    inner = slice(start, end + 1)
    if bool(np.any(bars.close[inner] > upper[inner])) or bool(
        np.any(bars.close[inner] < lower[inner])
    ):
        return None

    width_start = float((upper[start] - lower[start]) / max(lower[start], 1e-12))
    width_confirm = float((upper[confirmed] - lower[confirmed]) / max(lower[confirmed], 1e-12))
    if width_start <= 0.0:
        return None
    convergence = 1.0 - width_confirm / width_start
    if convergence < cfg.min_convergence:
        return None

    kind = _classify(b_u, b_l)
    brk_idx, brk_dir, brk_px, brk_vol = _first_break(bars, upper, lower, vol_mean, confirmed, cfg)
    past_apex = int(round(brk_idx - apex)) if brk_idx >= 0 else 0

    # "Failed apex": the search window ran past the apex and no close ever left the lines. This is
    # a distinct outcome, so it is flagged explicitly rather than inferred.
    watch_end = min(confirmed + cfg.track_bars, n - 1)
    apex_passed_unbroken = brk_idx < 0 and watch_end > apex

    return Wedge(
        kind=kind,
        symbol=bars.symbol,
        config_label=cfg.label,
        scale=cfg.scale,
        upper_indices=(h1.index, h2.index),
        upper_prices=(h1.price, h2.price),
        lower_indices=(l1.index, l2.index),
        lower_prices=(l1.price, l2.price),
        start_index=start,
        end_index=end,
        confirmed_index=confirmed,
        apex_index=float(apex),
        width_start=width_start,
        width_confirm=width_confirm,
        convergence=float(convergence),
        upper_slope=_fractional_slope(b_u, cfg.scale, upper[end]),
        lower_slope=_fractional_slope(b_l, cfg.scale, lower[end]),
        break_index=brk_idx,
        break_direction=brk_dir,
        break_price=brk_px,
        break_volume_ratio=brk_vol,
        bars_past_apex=past_apex,
        apex_passed_unbroken=apex_passed_unbroken,
    )


def _classify(upper_slope: float, lower_slope: float) -> WedgeKind:
    """Both lines down = falling wedge; both up = rising wedge; opposed = symmetrical triangle."""
    if upper_slope < 0.0 and lower_slope < 0.0:
        return "falling"
    if upper_slope > 0.0 and lower_slope > 0.0:
        return "rising"
    return "symmetrical"


def _fractional_slope(slope: float, scale: Scale, level: float) -> float:
    """Report both scales' slopes in comparable per-bar fractional terms."""
    if scale == "log":
        return float(np.expm1(slope))
    return float(slope / max(level, 1e-12))


def _first_break(
    bars: OHLCV,
    upper: FloatArray,
    lower: FloatArray,
    vol_mean: FloatArray,
    confirmed: int,
    cfg: WedgeConfig,
) -> tuple[int, int, float, float]:
    """First close outside either line within the tracking window, with its direction and volume."""
    n = len(bars)
    end = min(confirmed + cfg.track_bars, n - 1)
    if end <= confirmed:
        return -1, 0, float("nan"), float("nan")

    seg = slice(confirmed + 1, end + 1)
    up = bars.close[seg] > upper[seg]
    dn = bars.close[seg] < lower[seg]
    hits = np.flatnonzero(up | dn)
    if not hits.size:
        return -1, 0, float("nan"), float("nan")

    j = int(hits[0])
    i = confirmed + 1 + j
    direction = 1 if bool(up[j]) else -1
    ratio = float(bars.volume[i] / vol_mean[i]) if vol_mean[i] > 1e-12 else float("nan")
    return i, direction, float(bars.close[i]), ratio


def wedge_lines(w: Wedge, n: int) -> tuple[FloatArray, FloatArray]:
    """The wedge's two boundary lines evaluated over ``n`` bars — for plotting and for panels."""
    idx_axis = np.arange(n, dtype=np.float64)
    a_u, b_u = _fit(
        w.upper_indices[0], w.upper_prices[0], w.upper_indices[1], w.upper_prices[1], w.scale
    )
    a_l, b_l = _fit(
        w.lower_indices[0], w.lower_prices[0], w.lower_indices[1], w.lower_prices[1], w.scale
    )
    return _line(a_u, b_u, idx_axis, w.scale), _line(a_l, b_l, idx_axis, w.scale)


@dataclass(frozen=True)
class WedgePanel:
    """Per-bar wedge state — the shape a conditioning study consumes.

    A bar is "inside a wedge" from the formation's confirmation bar until it breaks or its tracking
    window expires. Where several wedges overlap, the **most recently confirmed** one wins: that is
    the structure a trader would be watching.
    """

    active: np.ndarray  # bool
    kind_code: IntArray  # 0 = none, else KIND_CODES
    bars_past_apex: IntArray  # negative before the apex, positive after; 0 when inactive
    width: FloatArray  # current (upper - lower) / lower, NaN when inactive
    convergence: FloatArray  # the formation's own convergence, NaN when inactive


def wedge_panel(bars: OHLCV, wedges: list[Wedge]) -> WedgePanel:
    """Project a list of wedge events onto one row per bar.

    ``bars_past_apex`` is the field the study actually conditions on: it turns "about to break out"
    into a signed bar count, so *before the apex*, *at the apex*, and *past the apex with nothing
    having happened* become three separately measurable populations.
    """
    n = len(bars)
    active = np.zeros(n, dtype=bool)
    kind_code = np.zeros(n, dtype=np.intp)
    past = np.zeros(n, dtype=np.intp)
    width = np.full(n, np.nan, dtype=np.float64)
    convergence = np.full(n, np.nan, dtype=np.float64)

    for w in sorted(wedges, key=lambda x: x.confirmed_index):
        upper, lower = wedge_lines(w, n)
        stop = w.break_index if w.break_index >= 0 else min(w.confirmed_index + 250, n - 1)
        lo, hi = w.confirmed_index, min(stop, n - 1)
        if hi < lo:
            continue
        rng = slice(lo, hi + 1)
        active[rng] = True
        kind_code[rng] = KIND_CODES[w.kind]
        past[rng] = np.arange(lo, hi + 1) - int(round(w.apex_index))
        width[rng] = (upper[rng] - lower[rng]) / np.maximum(lower[rng], 1e-12)
        convergence[rng] = w.convergence

    return WedgePanel(
        active=active,
        kind_code=kind_code,
        bars_past_apex=past,
        width=width,
        convergence=convergence,
    )
