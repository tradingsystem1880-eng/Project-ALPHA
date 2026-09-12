"""Multiscale market structure: ATR-scaled directional change and hierarchical extremes.

A base-level extreme is confirmed when price reverses by one ATR from the pending high or low
(volatility-scaled, so the same detector works across regimes). Each higher level promotes a
lower-level extreme once two later same-kind extremes prove it was the more significant one, and
inserts the intervening opposite extreme so every level stays strictly alternating. Everything is
streaming: ``update(i, bars)`` reads bars ``<= i`` only, and an extreme's ``confirmed_index`` is the
bar on which its level learned of it, which is what makes a "level-3 low" usable as a live signal.

Provenance: github.com/neurotrader888/market-structure/{local_extreme,atr_directional_change,
hierarchical_extremes}.py@36a7d89 (MIT); adapted: frozen ``LocalExtreme`` keyed by bar index
(timestamps come from ``OHLCV.ts``), ``DataError`` instead of ``assert`` for the structural
invariants, ``update`` returns the newly confirmed extreme, ``dataclasses.replace`` instead of
copy-and-mutate, and ``get_level_high/low`` return ``None`` instead of NaN. The promotion logic and
the rolling true-range sum are unchanged (parity fixture
``tests/fixtures/neurotrader/market_structure.json``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

from alpha_core import DataError
from alpha_patterns.series import OHLCV
from alpha_patterns.swings import SwingKind


@dataclass(frozen=True)
class LocalExtreme:
    """One confirmed extreme; ``confirmed_*`` is where and at what price it became knowable."""

    kind: SwingKind
    index: int
    price: float
    confirmed_index: int
    confirmed_price: float


def _opposite(kind: SwingKind) -> SwingKind:
    return "low" if kind == "high" else "high"


def _beats(x: float, y: float, kind: SwingKind) -> bool:
    """``x`` is the more extreme of the two for ``kind`` (higher high / lower low)."""
    return x > y if kind == "high" else x < y


def extremes_sanity_checks(extremes: Sequence[LocalExtreme]) -> None:
    """The structural invariants every level must satisfy; a violation is a ``DataError``."""
    for prev, cur in zip(extremes, extremes[1:], strict=False):
        if cur.kind == prev.kind:
            raise DataError(
                f"extremes must alternate; two {cur.kind}s at bars {prev.index},{cur.index}"
            )
        if cur.index < prev.index:
            raise DataError(f"extreme indices must be non-decreasing ({prev.index} -> {cur.index})")
        if cur.kind == "high" and cur.price <= prev.price:
            raise DataError(f"high at bar {cur.index} does not exceed the prior low {prev.price}")
        if cur.kind == "low" and cur.price >= prev.price:
            raise DataError(f"low at bar {cur.index} is not below the prior high {prev.price}")


def extremes_known_by(extremes: Sequence[LocalExtreme], bar: int) -> list[LocalExtreme]:
    """The extremes a trader standing at ``bar`` could have seen."""
    return [e for e in extremes if e.confirmed_index <= bar]


class ATRDirectionalChange:
    """Streaming directional change whose reversal threshold is one rolling ATR.

    ``update`` must be called for every bar in order; it returns the extreme confirmed on that
    bar, if any. Nothing is emitted until ``atr_lookback`` bars exist.
    """

    def __init__(self, atr_lookback: int) -> None:
        if atr_lookback < 1:
            raise DataError(f"atr_lookback must be >= 1, got {atr_lookback}")
        self.atr_lookback = atr_lookback
        self.extremes: list[LocalExtreme] = []
        self.current_atr: float | None = None
        self._up_move = True
        self._pend_max = math.nan
        self._pend_min = math.nan
        self._pend_max_i = 0
        self._pend_min_i = 0
        self._atr_sum = math.nan
        self._next_i = 0

    @staticmethod
    def _true_range(bars: OHLCV, i: int) -> float:
        return max(
            float(bars.high[i] - bars.low[i]),
            abs(float(bars.high[i] - bars.close[i - 1])),
            abs(float(bars.low[i] - bars.close[i - 1])),
        )

    def update(self, i: int, bars: OHLCV) -> LocalExtreme | None:
        if i != self._next_i:
            raise DataError(
                f"update must be called for every bar in order; expected {self._next_i}, got {i}"
            )
        self._next_i = i + 1
        lb = self.atr_lookback
        if i < lb:
            return None
        if i == lb:
            self._atr_sum = sum(self._true_range(bars, k) for k in range(i - lb + 1, i + 1))
        else:
            self._atr_sum += self._true_range(bars, i) - self._true_range(bars, i - lb)
        atr = self._atr_sum / lb
        self.current_atr = atr
        high, low, close = float(bars.high[i]), float(bars.low[i]), float(bars.close[i])
        if math.isnan(self._pend_max):
            self._pend_max, self._pend_min = high, low
            self._pend_max_i = self._pend_min_i = i

        if self._up_move:
            if high > self._pend_max:
                self._pend_max, self._pend_max_i = high, i
            elif low < self._pend_max - atr:
                ext = LocalExtreme("high", self._pend_max_i, self._pend_max, i, close)
                self.extremes.append(ext)
                self._up_move = False
                self._pend_min, self._pend_min_i = low, i
                return ext
        elif low < self._pend_min:
            self._pend_min, self._pend_min_i = low, i
        elif high > self._pend_min + atr:
            ext = LocalExtreme("low", self._pend_min_i, self._pend_min, i, close)
            self.extremes.append(ext)
            self._up_move = True
            self._pend_max, self._pend_max_i = high, i
            return ext
        return None


class HierarchicalExtremes:
    """``levels`` nested extreme sequences; level 0 is the ATR directional change."""

    def __init__(self, levels: int, atr_lookback: int) -> None:
        if levels < 1:
            raise DataError(f"levels must be >= 1, got {levels}")
        self._base = ATRDirectionalChange(atr_lookback)
        self.levels = levels
        self.extremes: list[list[LocalExtreme]] = [[] for _ in range(levels)]

    def update(self, i: int, bars: OHLCV) -> LocalExtreme | None:
        """Feed bar ``i``; returns the base-level extreme confirmed on it, if any."""
        ext = self._base.update(i, bars)
        if ext is None:
            return None
        self.extremes[0].append(ext)
        self._promote(0, i, float(bars.close[i]), ext.kind)
        return ext

    def _promote(self, level: int, conf_i: int, conf_price: float, kind: SwingKind) -> None:
        """Check whether the newest level-``level`` extreme confirms one at ``level + 1``."""
        if level >= self.levels - 1:
            return
        seq = self.extremes[level]
        ext_i = len(seq) - 1
        new_ext = seq[ext_i]
        if new_ext.kind != kind:
            raise DataError(f"level {level} newest extreme is a {new_ext.kind}, expected {kind}")
        if ext_i < 4:  # fewer than two prior extremes of the same kind
            return
        prev_ext = seq[ext_i - 2]
        if prev_ext.kind != kind:
            raise DataError(f"level {level} does not alternate at position {ext_i - 2}")
        if not _beats(prev_ext.price, new_ext.price, kind):
            return

        prev_next: LocalExtreme | None = None
        if self.extremes[level + 1]:
            prev_next = self.extremes[level + 1][-1]
            if prev_next.kind != kind and not _beats(prev_ext.price, prev_next.price, kind):
                return

        # Walk back over earlier same-kind extremes; the loop also handles equal prices.
        for prior_i in range(ext_i - 4, -1, -2):
            prior = seq[prior_i]
            if prior.kind != kind:
                raise DataError(f"level {level} does not alternate at position {prior_i}")
            if _beats(prior.price, prev_ext.price, kind):
                return  # an earlier, more extreme point invalidates the candidate
            if prev_next is not None and prior.index <= prev_next.index:
                break
            if prior.price == prev_ext.price:
                prev_ext = prior
            elif _beats(prior.price, prev_ext.price, _opposite(kind)):
                break

        promoted = replace(prev_ext, confirmed_index=conf_i, confirmed_price=conf_price)

        # Same kind as the last next-level extreme: upgrade the most extreme opposite point
        # between them so the next level keeps alternating.
        if prev_next is not None and prev_next.kind == kind:
            upgrade: LocalExtreme | None = None
            for j in range(ext_i - 1, -1, -2):
                prior = seq[j]
                if prior.kind != _opposite(kind):
                    raise DataError(f"level {level} does not alternate at position {j}")
                if prior.index >= promoted.index:
                    continue
                if prior.index <= prev_next.index:
                    break
                if upgrade is None or not _beats(prior.price, upgrade.price, kind):
                    upgrade = prior
            if upgrade is None:
                raise DataError(
                    f"no intermediate {_opposite(kind)} to keep level {level + 1} alternating"
                )
            self.extremes[level + 1].append(
                replace(upgrade, confirmed_index=conf_i, confirmed_price=conf_price)
            )
            self._promote(level + 1, conf_i, conf_price, _opposite(kind))

        self.extremes[level + 1].append(promoted)
        self._promote(level + 1, conf_i, conf_price, kind)

    def _level_extreme(self, level: int, kind: SwingKind, lag: int) -> LocalExtreme | None:
        if not 0 <= level < self.levels:
            raise DataError(f"level must be in [0, {self.levels}), got {level}")
        if lag < 0:
            raise DataError(f"lag must be >= 0, got {lag}")
        seq = self.extremes[level]
        if not seq:
            return None
        offset = 0 if seq[-1].kind == kind else 1
        pos = lag * 2 + offset
        return seq[-(pos + 1)] if pos < len(seq) else None

    def get_level_high(self, level: int, lag: int = 0) -> LocalExtreme | None:
        """The most recent confirmed high at ``level`` (``lag`` highs back), or ``None``."""
        return self._level_extreme(level, "high", lag)

    def get_level_low(self, level: int, lag: int = 0) -> LocalExtreme | None:
        """The most recent confirmed low at ``level`` (``lag`` lows back), or ``None``."""
        return self._level_extreme(level, "low", lag)


def atr_directional_change(bars: OHLCV, *, atr_lookback: int) -> list[LocalExtreme]:
    """Batch convenience: every base-level extreme over ``bars``."""
    dc = ATRDirectionalChange(atr_lookback)
    for i in range(len(bars)):
        dc.update(i, bars)
    return dc.extremes


def hierarchical_extremes(
    bars: OHLCV, *, levels: int, atr_lookback: int
) -> list[list[LocalExtreme]]:
    """Batch convenience: the extremes of every level over ``bars``."""
    he = HierarchicalExtremes(levels, atr_lookback)
    for i in range(len(bars)):
        he.update(i, bars)
    return he.extremes
