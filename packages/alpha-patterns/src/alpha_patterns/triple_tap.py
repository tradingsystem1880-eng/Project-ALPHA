"""Study 1 — triple-tap lows: three tests of a level without a decisive break.

The informal claim ("price taps a level three times and the third resolves upward") hides several
free parameters, and the point of this module is to make every one of them explicit and sweepable
rather than settled by eye:

- how a swing low is identified (fractal ``lookback``)
- how close is "the same level" (``tolerance``), and **measured against what** — the first tap, the
  running mean of taps, or a volatility-normalised band (``band_reference``)
- how far apart taps must be to count as distinct tests (``gap_min``/``gap_max``)
- whether a genuine rally must separate them (``min_intervening_rally``), which distinguishes
  three distinct tests from one long consolidation
- whether the taps must be flat or may ascend (``population``) — the user's marked taps ascend, and
  an ascending sequence is a materially different claim from a horizontal one, so the two are kept
  as separate populations rather than pooled

**Point-in-time honesty.** The pattern is complete at the third swing low, but that low is not
*knowable* until ``lookback`` bars later. Every event therefore records ``confirmed_index``, and the
entry variants are built from it. The one exception is :attr:`TripleTap.entry_tap_close`, which the
brief asked for explicitly and which is only reachable with hindsight; it is kept for comparison
and flagged by :attr:`TripleTap.entry_tap_close_is_lookahead` so it can never be quoted by accident
as a tradeable result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import OHLCV, atr
from alpha_patterns.swings import Swing, find_swings

BandReference = Literal["first", "mean", "atr"]
Population = Literal["strict", "ascending"]


@dataclass(frozen=True)
class TripleTapConfig:
    """Every knob of the triple-tap definition. Defaults are the pre-registered primary spec."""

    lookback: int = 5
    tolerance: float = 0.02  # fraction (0.02 = 2%), or ATR multiple when band_reference="atr"
    band_reference: BandReference = "mean"
    gap_min: int = 12  # bars between consecutive taps, inclusive
    gap_max: int = 250
    min_intervening_rally: float = 0.0  # required rise between taps, as a fraction of tap price
    population: Population = "ascending"

    def __post_init__(self) -> None:
        if self.lookback < 1:
            raise DataError(f"lookback must be >= 1, got {self.lookback}")
        if self.tolerance <= 0.0:
            raise DataError(f"tolerance must be > 0, got {self.tolerance}")
        if self.gap_min < 1:
            raise DataError(f"gap_min must be >= 1, got {self.gap_min}")
        if self.gap_max < self.gap_min:
            raise DataError(f"gap_max ({self.gap_max}) must be >= gap_min ({self.gap_min})")
        if self.min_intervening_rally < 0.0:
            raise DataError("min_intervening_rally must be >= 0")

    @property
    def label(self) -> str:
        """Compact identifier used as the configuration key in sweep tables."""
        return (
            f"L{self.lookback}_tol{self.tolerance:g}_{self.band_reference}"
            f"_g{self.gap_min}-{self.gap_max}_{self.population}"
            f"_r{self.min_intervening_rally:g}"
        )


@dataclass(frozen=True)
class TripleTap:
    """One detected triple-tap, with every entry variant the brief asked for."""

    tap_indices: tuple[int, int, int]
    tap_prices: tuple[float, float, float]
    confirmed_index: int  # third tap's confirmation bar — the earliest honest decision point
    level: float  # the defended level (mean of the three taps)
    intervening_high_index: int  # highest swing high between tap 1 and tap 3 (-1 if none)
    intervening_high: float
    config_label: str
    symbol: str

    # Entry variants -------------------------------------------------------
    entry_touch_index: int  # limit fill at the level on the third tap's bar
    entry_touch_price: float
    entry_tap_close_index: int  # close of the third swing-low bar (NOT knowable live)
    entry_tap_close_price: float
    entry_confirm_index: int  # close of the confirmation bar — the honest analogue
    entry_confirm_price: float
    entry_breakout_index: int  # first close above the intervening swing high (-1 if never)
    entry_breakout_price: float

    entry_tap_close_is_lookahead: bool = True

    @property
    def span_bars(self) -> int:
        """Bars from first to third tap — how long the base took to build."""
        return self.tap_indices[2] - self.tap_indices[0]


def _band_ok(
    candidate: float, taps: list[float], cfg: TripleTapConfig, atr_at_first: float
) -> bool:
    """Is ``candidate`` within the tolerance band implied by the taps already accepted?"""
    if cfg.band_reference == "first":
        reference = taps[0]
        width = reference * cfg.tolerance
    elif cfg.band_reference == "mean":
        reference = float(np.mean(taps))
        width = reference * cfg.tolerance
    else:  # "atr" — volatility-normalised, so a 2% band means something comparable across regimes
        reference = float(np.mean(taps))
        width = atr_at_first * cfg.tolerance / 0.01
    return abs(candidate - reference) <= width


def _population_ok(prev: float, candidate: float, cfg: TripleTapConfig) -> bool:
    if cfg.population == "ascending":
        return candidate >= prev
    return True


def detect_triple_taps(bars: OHLCV, cfg: TripleTapConfig | None = None) -> list[TripleTap]:
    """All triple-tap events in ``bars`` under ``cfg``, in chronological order.

    At most one event is emitted per third tap: when several earlier pairs would qualify, the
    earliest first tap wins. Without that rule a single base emits a combinatorial pile of
    near-identical events and every downstream sample size is inflated.
    """
    cfg = cfg or TripleTapConfig()
    lows = find_swings(bars, lookback=cfg.lookback, kind="low")
    highs = find_swings(bars, lookback=cfg.lookback, kind="high")
    if len(lows) < 3:
        return []

    atr_series = atr(bars, window=14)
    by_third: dict[int, TripleTap] = {}

    for a in range(len(lows) - 2):
        t1 = lows[a]
        atr1 = float(atr_series[t1.index])
        for b in range(a + 1, len(lows) - 1):
            t2 = lows[b]
            gap12 = t2.index - t1.index
            if gap12 < cfg.gap_min:
                continue
            if gap12 > cfg.gap_max:
                break  # swings are ordered, so every later t2 is further still
            if not _band_ok(t2.price, [t1.price], cfg, atr1):
                continue
            if not _population_ok(t1.price, t2.price, cfg):
                continue
            if not _rally_ok(bars, t1.index, t2.index, t1.price, cfg):
                continue

            for c in range(b + 1, len(lows)):
                t3 = lows[c]
                gap23 = t3.index - t2.index
                if gap23 < cfg.gap_min:
                    continue
                if gap23 > cfg.gap_max:
                    break
                if not _band_ok(t3.price, [t1.price, t2.price], cfg, atr1):
                    continue
                if not _population_ok(t2.price, t3.price, cfg):
                    continue
                if not _rally_ok(bars, t2.index, t3.index, t2.price, cfg):
                    continue
                if t3.index in by_third:
                    continue  # earliest first tap already claimed this third tap
                by_third[t3.index] = _build_event(bars, t1, t2, t3, highs, cfg)

    return [by_third[k] for k in sorted(by_third)]


def _rally_ok(bars: OHLCV, i: int, j: int, base: float, cfg: TripleTapConfig) -> bool:
    """Did price rise far enough between two taps for them to be distinct tests?"""
    if cfg.min_intervening_rally <= 0.0:
        return True
    if j <= i + 1:
        return False
    peak = float(np.max(bars.high[i + 1 : j]))
    return (peak - base) / base >= cfg.min_intervening_rally


def _build_event(
    bars: OHLCV,
    t1: Swing,
    t2: Swing,
    t3: Swing,
    highs: list[Swing],
    cfg: TripleTapConfig,
) -> TripleTap:
    between = [h for h in highs if t1.index < h.index < t3.index]
    if between:
        top = max(between, key=lambda h: h.price)
        hi_idx, hi_px = top.index, top.price
    else:
        hi_idx, hi_px = -1, float(np.max(bars.high[t1.index : t3.index + 1]))

    n = len(bars)
    confirm = min(t3.confirmed_index, n - 1)

    # Breakout entry: first close above the intervening high, searched only from the confirmation
    # bar onward so the trigger is never evaluated on information the trader did not yet have.
    brk_idx, brk_px = -1, float("nan")
    if confirm + 1 < n:
        ahead = bars.close[confirm + 1 :]
        hits = np.flatnonzero(ahead > hi_px)
        if hits.size:
            brk_idx = int(confirm + 1 + hits[0])
            brk_px = float(bars.close[brk_idx])

    return TripleTap(
        tap_indices=(t1.index, t2.index, t3.index),
        tap_prices=(t1.price, t2.price, t3.price),
        confirmed_index=confirm,
        level=float(np.mean([t1.price, t2.price, t3.price])),
        intervening_high_index=hi_idx,
        intervening_high=hi_px,
        config_label=cfg.label,
        symbol=bars.symbol,
        entry_touch_index=t3.index,
        entry_touch_price=t3.price,
        entry_tap_close_index=t3.index,
        entry_tap_close_price=float(bars.close[t3.index]),
        entry_confirm_index=confirm,
        entry_confirm_price=float(bars.close[confirm]),
        entry_breakout_index=brk_idx,
        entry_breakout_price=brk_px,
    )


def detect_nth_taps(
    bars: OHLCV, cfg: TripleTapConfig | None = None, *, n_taps: int = 4
) -> list[int]:
    """Indices of the ``n_taps``-th tap of a level that had already been tapped ``n_taps-1`` times.

    Used for the fourth-tap question the brief raises: if third taps work but fourth taps fail, the
    level is being *exhausted* rather than defended, and that distinction changes what the pattern
    means. Returns the bar indices of the qualifying later taps.
    """
    cfg = cfg or TripleTapConfig()
    if n_taps < 4:
        raise DataError(f"detect_nth_taps is for the 4th tap onward, got n_taps={n_taps}")

    events = detect_triple_taps(bars, cfg)
    lows = find_swings(bars, lookback=cfg.lookback, kind="low")
    atr_series = atr(bars, window=14)

    out: list[int] = []
    for ev in events:
        taps = list(ev.tap_prices)
        last_idx = ev.tap_indices[2]
        atr1 = float(atr_series[ev.tap_indices[0]])
        for s in lows:
            if s.index <= last_idx:
                continue
            gap = s.index - last_idx
            if gap < cfg.gap_min:
                continue
            if gap > cfg.gap_max:
                break
            if _band_ok(s.price, taps, cfg, atr1) and _population_ok(taps[-1], s.price, cfg):
                taps.append(s.price)
                last_idx = s.index
                if len(taps) == n_taps:
                    out.append(s.index)
                    break
    return sorted(set(out))
