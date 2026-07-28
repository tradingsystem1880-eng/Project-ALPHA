"""Study 2 — algorithmic descending trendlines and their breaks.

Trendlines are where a pattern study usually dies, because a line drawn *after* the fact can be
placed to touch whatever the analyst wishes. Everything here is therefore constrained to information
available at the time:

- Anchors are **confirmed** swing highs only; a line does not exist until its second anchor is
  confirmed (``lookback`` bars after that swing prints).
- A line is invalid if any close between its anchors already pierced it — a line the market has
  gone through is not resistance.
- A line is **retired** after ``max_age`` bars, so a break in 2026 cannot be attributed to a line
  anchored in 2020.
- Both **linear and logarithmic** fitting are supported. Over a multi-year downtrend spanning an
  order of magnitude these disagree substantially: a straight line in price terms is a decaying
  percentage slope, and which one the market respects is an empirical question, not an assumption.

Break definitions are kept separate rather than blended, because "any close beyond" and "close
beyond by a full ATR on 1.5× volume" are different claims with different false-break rates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import OHLCV, FloatArray, atr
from alpha_patterns.swings import find_swings

Scale = Literal["linear", "log"]
BreakRule = Literal["any_close", "atr_half", "atr_full", "two_closes", "volume"]

ALL_BREAK_RULES: tuple[BreakRule, ...] = (
    "any_close",
    "atr_half",
    "atr_full",
    "two_closes",
    "volume",
)


@dataclass(frozen=True)
class TrendlineConfig:
    """Construction and break parameters. Defaults are the pre-registered primary spec."""

    lookback: int = 5
    min_anchor_gap: int = 12  # bars between the two anchors
    max_anchor_gap: int = 500
    max_age: int = 500  # bars a line stays active after confirmation
    require_third_touch: bool = False
    scale: Scale = "log"
    volume_multiple: float = 1.5
    volume_window: int = 20

    def __post_init__(self) -> None:
        if self.lookback < 1:
            raise DataError(f"lookback must be >= 1, got {self.lookback}")
        if self.min_anchor_gap < 1:
            raise DataError(f"min_anchor_gap must be >= 1, got {self.min_anchor_gap}")
        if self.max_anchor_gap < self.min_anchor_gap:
            raise DataError("max_anchor_gap must be >= min_anchor_gap")
        if self.max_age < 1:
            raise DataError(f"max_age must be >= 1, got {self.max_age}")
        if self.volume_multiple <= 0.0:
            raise DataError("volume_multiple must be > 0")

    @property
    def label(self) -> str:
        return (
            f"L{self.lookback}_gap{self.min_anchor_gap}-{self.max_anchor_gap}"
            f"_age{self.max_age}_{self.scale}"
            f"_{'3touch' if self.require_third_touch else 'no3touch'}"
        )


@dataclass(frozen=True)
class Trendline:
    """A descending resistance line that was valid and active over a bar range."""

    anchor_indices: tuple[int, int]
    anchor_prices: tuple[float, float]
    active_from: int  # second anchor's confirmation bar
    retire_at: int
    scale: Scale
    touches: int
    config_label: str
    symbol: str

    def value_at(self, index: float) -> float:
        """Line price at a (possibly fractional) bar index, extrapolated forward."""
        i1, i2 = self.anchor_indices
        p1, p2 = self.anchor_prices
        frac = (index - i1) / (i2 - i1)
        if self.scale == "log":
            return float(np.exp(np.log(p1) + frac * (np.log(p2) - np.log(p1))))
        return float(p1 + frac * (p2 - p1))


@dataclass(frozen=True)
class TrendlineBreak:
    """A break of a trendline under one specific rule."""

    line: Trendline
    rule: BreakRule
    break_index: int
    break_price: float
    line_price: float
    excess_atr: float  # how far beyond the line the close was, in ATR units
    retest_index: int  # first later bar to touch the line again (-1 if none within the window)
    retest_held: bool  # after the retest, did price stay above the line?
    false_break_1: bool  # closed back below within 1 bar
    false_break_3: bool
    false_break_6: bool


def _line_series(line: Trendline, n: int) -> FloatArray:
    idx = np.arange(n, dtype=np.float64)
    i1, i2 = line.anchor_indices
    p1, p2 = line.anchor_prices
    frac = (idx - i1) / (i2 - i1)
    if line.scale == "log":
        return np.asarray(np.exp(np.log(p1) + frac * (np.log(p2) - np.log(p1))), dtype=np.float64)
    return np.asarray(p1 + frac * (p2 - p1), dtype=np.float64)


def build_trendlines(bars: OHLCV, cfg: TrendlineConfig | None = None) -> list[Trendline]:
    """Every valid descending trendline in ``bars``.

    A pair of confirmed swing highs qualifies when the second is lower than the first (descending),
    the spacing is within bounds, and **no close between the anchors** rose above the line.
    """
    cfg = cfg or TrendlineConfig()
    highs = find_swings(bars, lookback=cfg.lookback, kind="high")
    if len(highs) < 2:
        return []

    n = len(bars)
    out: list[Trendline] = []

    for a in range(len(highs) - 1):
        h1 = highs[a]
        for b in range(a + 1, len(highs)):
            h2 = highs[b]
            gap = h2.index - h1.index
            if gap < cfg.min_anchor_gap:
                continue
            if gap > cfg.max_anchor_gap:
                break
            if h2.price >= h1.price:
                continue  # ascending or flat: not a descending resistance line

            candidate = Trendline(
                anchor_indices=(h1.index, h2.index),
                anchor_prices=(h1.price, h2.price),
                active_from=min(h2.confirmed_index, n - 1),
                retire_at=min(h2.confirmed_index + cfg.max_age, n - 1),
                scale=cfg.scale,
                touches=2,
                config_label=cfg.label,
                symbol=bars.symbol,
            )
            line = _line_series(candidate, n)

            # Invalidate if the market already closed through the line between the anchors.
            span = slice(h1.index + 1, h2.index)
            if span.stop > span.start and bool(np.any(bars.close[span] > line[span])):
                continue

            touches = _count_touches(bars, line, candidate, cfg)
            if cfg.require_third_touch and touches < 3:
                continue

            out.append(
                Trendline(
                    anchor_indices=candidate.anchor_indices,
                    anchor_prices=candidate.anchor_prices,
                    active_from=candidate.active_from,
                    retire_at=candidate.retire_at,
                    scale=candidate.scale,
                    touches=touches,
                    config_label=candidate.config_label,
                    symbol=candidate.symbol,
                )
            )
    return out


def _count_touches(
    bars: OHLCV, line: FloatArray, candidate: Trendline, cfg: TrendlineConfig
) -> int:
    """Anchors plus any later bar whose high reached the line without closing through it."""
    lo = candidate.active_from
    hi = candidate.retire_at
    if hi <= lo:
        return 2
    atr_series = atr(bars, window=14)
    seg = slice(lo, hi + 1)
    near = np.abs(bars.high[seg] - line[seg]) <= 0.25 * atr_series[seg]
    respected = bars.close[seg] <= line[seg]
    return 2 + int(np.count_nonzero(near & respected))


def find_breaks(
    bars: OHLCV,
    lines: list[Trendline],
    *,
    rules: tuple[BreakRule, ...] = ALL_BREAK_RULES,
    cfg: TrendlineConfig | None = None,
    retest_window: int = 30,
) -> list[TrendlineBreak]:
    """First break of each line under each requested rule, with retest and false-break outcomes.

    Only the *first* break per (line, rule) is returned: once broken, a line is no longer the object
    under study, and counting every subsequent close above it would multiply one event into dozens.
    """
    cfg = cfg or TrendlineConfig()
    if retest_window < 1:
        raise DataError(f"retest_window must be >= 1, got {retest_window}")

    n = len(bars)
    atr_series = atr(bars, window=14)
    vol_avg = _trailing_mean(bars.volume, cfg.volume_window)
    out: list[TrendlineBreak] = []

    for line in lines:
        lvl = _line_series(line, n)
        above = bars.close > lvl
        lo, hi = line.active_from, line.retire_at
        if hi <= lo:
            continue

        for rule in rules:
            idx = _first_break(bars, lvl, above, atr_series, vol_avg, lo, hi, rule, cfg)
            if idx < 0:
                continue
            out.append(
                _describe_break(bars, line, lvl, above, atr_series, idx, rule, retest_window)
            )
    return out


def _first_break(
    bars: OHLCV,
    lvl: FloatArray,
    above: np.ndarray,
    atr_series: FloatArray,
    vol_avg: FloatArray,
    lo: int,
    hi: int,
    rule: BreakRule,
    cfg: TrendlineConfig,
) -> int:
    window = np.arange(lo, hi + 1)
    if window.size == 0:
        return -1
    excess = (bars.close[window] - lvl[window]) / np.maximum(atr_series[window], 1e-12)

    if rule == "any_close":
        ok = above[window]
    elif rule == "atr_half":
        ok = above[window] & (excess >= 0.5)
    elif rule == "atr_full":
        ok = above[window] & (excess >= 1.0)
    elif rule == "two_closes":
        prev = np.concatenate(([False], above[window][:-1]))
        ok = above[window] & prev
    else:  # "volume"
        ok = above[window] & (bars.volume[window] >= cfg.volume_multiple * vol_avg[window])

    hits = np.flatnonzero(ok)
    return int(window[hits[0]]) if hits.size else -1


def _describe_break(
    bars: OHLCV,
    line: Trendline,
    lvl: FloatArray,
    above: np.ndarray,
    atr_series: FloatArray,
    idx: int,
    rule: BreakRule,
    retest_window: int,
) -> TrendlineBreak:
    n = len(bars)

    def closed_back(k: int) -> bool:
        end = min(idx + k, n - 1)
        return bool(np.any(~above[idx + 1 : end + 1])) if end > idx else False

    retest_idx, retest_held = -1, False
    end = min(idx + retest_window, n - 1)
    if end > idx:
        touched = np.flatnonzero(bars.low[idx + 1 : end + 1] <= lvl[idx + 1 : end + 1])
        if touched.size:
            retest_idx = int(idx + 1 + touched[0])
            tail_end = min(retest_idx + retest_window, n - 1)
            # "Held" = price was still above the line at the end of the follow-up window.
            retest_held = bool(above[tail_end])

    return TrendlineBreak(
        line=line,
        rule=rule,
        break_index=idx,
        break_price=float(bars.close[idx]),
        line_price=float(lvl[idx]),
        excess_atr=float((bars.close[idx] - lvl[idx]) / max(float(atr_series[idx]), 1e-12)),
        retest_index=retest_idx,
        retest_held=retest_held,
        false_break_1=closed_back(1),
        false_break_3=closed_back(3),
        false_break_6=closed_back(6),
    )


def _trailing_mean(values: FloatArray, window: int) -> FloatArray:
    csum = np.concatenate(([0.0], np.cumsum(values)))
    idx = np.arange(values.size)
    lo = np.maximum(0, idx - window + 1)
    return (csum[idx + 1] - csum[lo]) / (idx - lo + 1).astype(np.float64)
