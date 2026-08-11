"""Head & shoulders, inverse head & shoulders, and Quasimodo — one detector, four variants.

All four share a five-point skeleton: three same-kind pivots (left shoulder, **head**, right
shoulder) with the head most extreme, plus the two opposite-kind pivots between them defining the
**neckline**. Inverting `direction` mirrors it, so H&S and inverse H&S are one code path.

Quasimodo is *not* a separate shape. It is this same skeleton plus a **break of structure** — after
the head, price must close beyond the pivot separating it from the left shoulder, flipping the trend
of highs (or lows) — plus a different trade convention: entry at the **left shoulder's level** (the
"QM line") rather than at a neckline break, and a stop beyond the head rather than the right
shoulder. Detecting one population and flagging ``has_bos`` therefore makes "does the break-of-
structure filter add anything?" a within-sample comparison at full power, rather than two studies
with incomparable denominators.

**Why one event per head.** A head with several admissible shoulder pairs would otherwise emit a
combinatorial pile of near-identical events and inflate every downstream sample size. For each head
the most *symmetric* admissible pair is kept — symmetry being the property the pattern's own
literature treats as defining — and everything else is discarded.

**Complexity.** A naive five-deep pivot nest is O(k⁵) and will not run at intraday resolution. This
anchors on the head and searches outward, with the neckline pivots looked up rather than looped, so
the cost is roughly O(k·w²) for ``w`` pivots inside the ``gap_max`` window.

**Point-in-time.** Five pivots mean five confirmation lags; the event's ``confirmed_index`` is the
**latest** of them. Every entry index is ≥ that bar, the BOS is searched only after the head is
confirmed, and the neckline break only after the whole structure is. Enforced by the bias guards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import OHLCV, FloatArray
from alpha_patterns.structure import Direction, break_of_structure, extreme_between
from alpha_patterns.swings import Swing, find_swings

ShoulderRule = Literal["any", "higher", "lower", "within_tol"]

#: Canonical names, for dataset labelling. QM is a flag on top of the base shape, not a shape.
VARIANT_NAMES: dict[tuple[Direction, bool], str] = {
    ("bullish", False): "inverse_head_shoulders",
    ("bullish", True): "bullish_quasimodo",
    ("bearish", False): "head_shoulders",
    ("bearish", True): "bearish_quasimodo",
}


@dataclass(frozen=True)
class HSConfig:
    """Every knob of the head-and-shoulders family definition."""

    direction: Direction = "bullish"
    lookback: int = 5
    head_prominence: float = 0.02  # head must exceed both shoulders by this fraction
    shoulder_tol: float = 0.5  # |LS-RS| as a fraction of head depth
    time_symmetry_tol: float = 0.25  # shorter leg / longer leg, in bars
    max_neckline_slope: float = 0.15  # |N2/N1 - 1|
    gap_min: int = 5  # bars between consecutive anchors
    gap_max: int = 250
    shoulder_rule: ShoulderRule = "any"
    require_bos: bool = False  # True => Quasimodo only
    atr_window: int = 14
    #: Bars after confirmation during which a neckline break still counts as *this* pattern's
    #: break. Unbounded search is both meaningless (a break three years later is a different
    #: event) and quadratic in series length. 0 means "use gap_max".
    break_window: int = 0

    def __post_init__(self) -> None:
        if self.direction not in ("bullish", "bearish"):
            raise DataError(f"direction must be bullish|bearish, got {self.direction}")
        if self.lookback < 1:
            raise DataError(f"lookback must be >= 1, got {self.lookback}")
        if self.head_prominence <= 0.0:
            raise DataError(f"head_prominence must be > 0, got {self.head_prominence}")
        if self.shoulder_tol <= 0.0:
            raise DataError(f"shoulder_tol must be > 0, got {self.shoulder_tol}")
        if not 0.0 <= self.time_symmetry_tol <= 1.0:
            raise DataError(f"time_symmetry_tol must be in [0, 1], got {self.time_symmetry_tol}")
        if self.max_neckline_slope < 0.0:
            raise DataError("max_neckline_slope must be >= 0")
        if self.gap_min < 1:
            raise DataError(f"gap_min must be >= 1, got {self.gap_min}")
        if self.gap_max < self.gap_min:
            raise DataError(f"gap_max ({self.gap_max}) must be >= gap_min ({self.gap_min})")
        if self.break_window < 0:
            raise DataError(f"break_window must be >= 0, got {self.break_window}")

    @property
    def effective_break_window(self) -> int:
        return self.break_window or self.gap_max

    @property
    def anchor_kind(self) -> Literal["high", "low"]:
        """Pivot kind forming the shoulders and head."""
        return "low" if self.direction == "bullish" else "high"

    @property
    def neckline_kind(self) -> Literal["high", "low"]:
        """Pivot kind forming the two neckline anchors."""
        return "high" if self.direction == "bullish" else "low"

    @property
    def label(self) -> str:
        return (
            f"{self.direction[:4]}_L{self.lookback}_hp{self.head_prominence:g}"
            f"_st{self.shoulder_tol:g}_ts{self.time_symmetry_tol:g}"
            f"_ns{self.max_neckline_slope:g}_g{self.gap_min}-{self.gap_max}"
            f"_{self.shoulder_rule}{'_bos' if self.require_bos else ''}"
        )


@dataclass(frozen=True)
class HSEvent:
    """One detected head-and-shoulders-family structure with every trade convention attached."""

    # identity ------------------------------------------------------------
    direction: Direction
    variant: str
    symbol: str
    config_label: str

    # geometry ------------------------------------------------------------
    ls_index: int
    ls_price: float
    head_index: int
    head_price: float
    rs_index: int
    rs_price: float
    n1_index: int  # neckline anchor between left shoulder and head
    n1_price: float
    n2_index: int  # neckline anchor between head and right shoulder
    n2_price: float

    confirmed_index: int  # latest of the five confirmation lags — earliest honest decision bar
    head_depth: float  # |mean(shoulders) - head| / mean(shoulders)
    shoulder_asymmetry: float  # |LS - RS| / head depth (0 = perfectly level shoulders)
    time_asymmetry: float  # shorter leg / longer leg, in bars (1 = perfectly timed)
    neckline_slope: float  # N2/N1 - 1
    span_bars: int

    # break of structure (the Quasimodo qualifier) -------------------------
    has_bos: bool
    bos_index: int  # -1 if absent
    bos_price: float

    # trade conventions ---------------------------------------------------
    neckline_break_index: int  # first close beyond the neckline after confirmation (-1 if none)
    neckline_break_price: float
    neckline_at_break: float
    break_volume_ratio: float  # break-bar volume / trailing 20-bar mean (nan if no break)
    retest_index: int  # first return to the neckline after the break (-1 if none)

    qm_entry_index: int  # first touch of the left-shoulder level after confirmation (-1 if none)
    qm_entry_price: float

    target_measured: float  # neckline_at_break +/- (neckline_at_break - head)
    stop_head: float  # beyond the head — the Quasimodo stop
    stop_rs: float  # beyond the right shoulder — the H&S stop

    @property
    def is_quasimodo(self) -> bool:
        return self.has_bos

    def reward_risk(self, *, entry: float, stop: float) -> float:
        """R:R of the measured-move target from an arbitrary entry/stop pair."""
        risk = abs(entry - stop)
        if risk <= 0.0:
            raise DataError("reward_risk needs a non-zero risk leg")
        return abs(self.target_measured - entry) / risk


def _more_extreme(a: float, b: float, direction: Direction) -> bool:
    """Is ``a`` further in the pattern's extreme direction than ``b``?"""
    return a < b if direction == "bullish" else a > b


def _prominent_enough(head: float, shoulder: float, cfg: HSConfig) -> bool:
    if cfg.direction == "bullish":
        return head <= shoulder * (1.0 - cfg.head_prominence)
    return head >= shoulder * (1.0 + cfg.head_prominence)


def _shoulder_rule_ok(ls: float, rs: float, cfg: HSConfig) -> bool:
    """Right shoulder's position relative to the left, in *pattern* terms.

    "higher" means further from the head — a rising right shoulder for an inverse H&S, a falling one
    for an H&S. This is the axis the user's own chart sits on, so it is a first-class parameter.
    """
    if cfg.shoulder_rule == "any":
        return True
    if cfg.shoulder_rule == "within_tol":
        return abs(rs - ls) <= abs(ls) * cfg.head_prominence
    higher = rs > ls if cfg.direction == "bullish" else rs < ls
    return higher if cfg.shoulder_rule == "higher" else not higher


def _neckline_value(ev_n1: Swing, ev_n2: Swing, index: float) -> float:
    """Linear neckline through the two anchors, extrapolated forward."""
    if ev_n2.index == ev_n1.index:
        return float(ev_n1.price)
    frac = (index - ev_n1.index) / (ev_n2.index - ev_n1.index)
    return float(ev_n1.price + frac * (ev_n2.price - ev_n1.price))


def _trailing_mean(values: np.ndarray, window: int) -> np.ndarray:
    csum = np.concatenate(([0.0], np.cumsum(values)))
    idx = np.arange(values.size)
    lo = np.maximum(0, idx - window + 1)
    return (csum[idx + 1] - csum[lo]) / (idx - lo + 1).astype(np.float64)


def detect_head_shoulders(bars: OHLCV, cfg: HSConfig | None = None) -> list[HSEvent]:
    """Every head-and-shoulders-family structure in ``bars``, in chronological order.

    Set ``cfg.require_bos`` to restrict output to Quasimodo structures; leave it False to get
    the full population with ``has_bos`` flagged per event, which is what the within-sample BOS
    comparison needs.
    """
    cfg = cfg or HSConfig()
    anchors = find_swings(bars, lookback=cfg.lookback, kind=cfg.anchor_kind)
    necks = find_swings(bars, lookback=cfg.lookback, kind=cfg.neckline_kind)
    if len(anchors) < 3 or len(necks) < 2:
        return []

    n = len(bars)
    vol_mean = _trailing_mean(bars.volume, 20)
    events: list[HSEvent] = []

    for h in range(1, len(anchors) - 1):
        head = anchors[h]

        # Search back for admissible left shoulders, forward for right shoulders. Both windows
        # are bounded by gap_max, which keeps this near-linear in the number of pivots.
        lefts: list[Swing] = []
        for i in range(h - 1, -1, -1):
            gap = head.index - anchors[i].index
            if gap > cfg.gap_max:
                break
            if gap >= cfg.gap_min and _prominent_enough(head.price, anchors[i].price, cfg):
                lefts.append(anchors[i])
        rights: list[Swing] = []
        for j in range(h + 1, len(anchors)):
            gap = anchors[j].index - head.index
            if gap > cfg.gap_max:
                break
            if gap >= cfg.gap_min and _prominent_enough(head.price, anchors[j].price, cfg):
                rights.append(anchors[j])
        if not lefts or not rights:
            continue

        best: tuple[float, HSEvent] | None = None
        for ls in lefts:
            for rs in rights:
                built = _try_build(bars, ls, head, rs, necks, cfg, vol_mean, n)
                if built is None:
                    continue
                # Rank by combined price+time asymmetry; lower is more symmetric.
                score = built.shoulder_asymmetry + (1.0 - built.time_asymmetry)
                if best is None or score < best[0]:
                    best = (score, built)
        if best is not None and (best[1].has_bos or not cfg.require_bos):
            events.append(best[1])

    return sorted(events, key=lambda e: e.confirmed_index)


def _try_build(
    bars: OHLCV,
    ls: Swing,
    head: Swing,
    rs: Swing,
    necks: list[Swing],
    cfg: HSConfig,
    vol_mean: np.ndarray,
    n: int,
) -> HSEvent | None:
    """Apply the shape constraints to one (LS, head, RS) triple; return an event or None."""
    if not _shoulder_rule_ok(ls.price, rs.price, cfg):
        return None
    if not _more_extreme(head.price, ls.price, cfg.direction):
        return None
    if not _more_extreme(head.price, rs.price, cfg.direction):
        return None

    shoulder_mean = (ls.price + rs.price) / 2.0
    head_depth = abs(shoulder_mean - head.price) / abs(shoulder_mean)
    if head_depth <= 0.0:
        return None
    if abs(ls.price - rs.price) / (abs(shoulder_mean) * head_depth) > cfg.shoulder_tol:
        return None

    d1 = head.index - ls.index
    d2 = rs.index - head.index
    time_asym = min(d1, d2) / max(d1, d2)
    if time_asym < cfg.time_symmetry_tol:
        return None

    n1 = extreme_between(necks, ls.index, head.index, cfg.neckline_kind)
    n2 = extreme_between(necks, head.index, rs.index, cfg.neckline_kind)
    if n1 is None or n2 is None:
        return None
    slope = n2.price / n1.price - 1.0
    if abs(slope) > cfg.max_neckline_slope:
        return None

    confirmed = min(
        max(s.confirmed_index for s in (ls, head, rs, n1, n2)),
        n - 1,
    )
    upward = cfg.direction == "bullish"

    # Break of structure: a close beyond the pivot separating head from left shoulder, occurring
    # after the head is confirmed and before the right shoulder prints. This is the QM qualifier.
    bos = break_of_structure(
        bars,
        level=n1.price,
        level_index=n1.index,
        search_from=min(head.confirmed_index, n - 1),
        upward=upward,
        search_to=rs.index,
    )

    # Neckline break, searched only from the bar after the whole structure was knowable, and only
    # within the pattern's validity window.
    lo = confirmed + 1
    hi = min(lo + cfg.effective_break_window, n)
    brk_idx, brk_px, neck_at_brk, vol_ratio = -1, float("nan"), float("nan"), float("nan")
    retest_idx = -1
    if hi > lo:
        neck_line = _neckline_series(n1, n2, lo, hi)
        closes = bars.close[lo:hi]
        hits = np.flatnonzero(closes > neck_line if upward else closes < neck_line)
        if hits.size:
            brk_idx = int(lo + hits[0])
            brk_px = float(bars.close[brk_idx])
            neck_at_brk = float(neck_line[int(hits[0])])
            vol_ratio = float(bars.volume[brk_idx] / max(float(vol_mean[brk_idx]), 1e-12))
            retest_idx = _first_retest(bars, n1, n2, brk_idx, upward, n, cfg)

    # QM entry: a return to the left shoulder's level after confirmation.
    qm_idx, qm_px = -1, float("nan")
    if hi > lo:
        probe = bars.low[lo:hi] if upward else bars.high[lo:hi]
        touch = np.flatnonzero(probe <= ls.price if upward else probe >= ls.price)
        if touch.size:
            qm_idx = int(lo + touch[0])
            qm_px = float(ls.price)

    reference = (
        neck_at_brk if np.isfinite(neck_at_brk) else _neckline_value(n1, n2, float(confirmed))
    )
    target = reference + (reference - head.price)

    return HSEvent(
        direction=cfg.direction,
        variant=VARIANT_NAMES[(cfg.direction, bos.occurred)],
        symbol=bars.symbol,
        config_label=cfg.label,
        ls_index=ls.index,
        ls_price=ls.price,
        head_index=head.index,
        head_price=head.price,
        rs_index=rs.index,
        rs_price=rs.price,
        n1_index=n1.index,
        n1_price=n1.price,
        n2_index=n2.index,
        n2_price=n2.price,
        confirmed_index=confirmed,
        head_depth=head_depth,
        shoulder_asymmetry=abs(ls.price - rs.price) / (abs(shoulder_mean) * head_depth),
        time_asymmetry=time_asym,
        neckline_slope=slope,
        span_bars=rs.index - ls.index,
        has_bos=bos.occurred,
        bos_index=bos.index,
        bos_price=bos.price,
        neckline_break_index=brk_idx,
        neckline_break_price=brk_px,
        neckline_at_break=neck_at_brk,
        break_volume_ratio=vol_ratio,
        retest_index=retest_idx,
        qm_entry_index=qm_idx,
        qm_entry_price=qm_px,
        target_measured=target,
        stop_head=head.price,
        stop_rs=rs.price,
    )


def _neckline_series(n1: Swing, n2: Swing, lo: int, hi: int) -> FloatArray:
    """Neckline values over ``[lo, hi)``, vectorised.

    Built with numpy rather than a per-bar Python call. This runs once per candidate shoulder pair,
    so a list comprehension over the remaining series dominates the detector's entire runtime — it
    was 42 seconds for 13k bars before this was vectorised and bounded.
    """
    idx = np.arange(lo, hi, dtype=np.float64)
    if n2.index == n1.index:
        return np.full(idx.size, float(n1.price))
    frac = (idx - n1.index) / (n2.index - n1.index)
    return np.asarray(n1.price + frac * (n2.price - n1.price), dtype=np.float64)


def _first_retest(
    bars: OHLCV, n1: Swing, n2: Swing, brk_idx: int, upward: bool, n: int, cfg: HSConfig
) -> int:
    """First bar after the break whose range returns to the (extrapolated) neckline."""
    lo = brk_idx + 1
    hi = min(lo + cfg.effective_break_window, n)
    if hi <= lo:
        return -1
    line = _neckline_series(n1, n2, lo, hi)
    probe = bars.low[lo:hi] if upward else bars.high[lo:hi]
    hits = np.flatnonzero(probe <= line if upward else probe >= line)
    return int(lo + hits[0]) if hits.size else -1
