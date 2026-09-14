"""Bar permutation null: reorder OHLC bars while keeping every bar's shape and gap.

Provenance: github.com/neurotrader888/mcpt/bar_permute.py @ 2c0d70c (MIT). Adapted: takes typed
``OHLC`` arrays instead of DataFrames, threads a ``numpy.random.Generator`` instead of seeding the
global state, and fails loud on malformed bars or a start index that leaves nothing to permute.
The construction is Masters' bar permutation (*Testing and Tuning Market Trading Systems*, Apress
2018, ch. 7, companion code ``MCPT_BARS.CPP``): each bar after ``start_index`` is split
into its overnight log gap (open vs the previous close) and its intrabar log shape (high, low and
close vs its own open); the gaps are shuffled as one multiset and the intrabar rows as another,
independently, then the series is rebuilt bar by bar from the untouched prefix. The marginal
distributions of both components are preserved exactly (so the final close is too), only their
order — the exploitable structure — is destroyed. Several markets receive the same two orders so
their cross-sectional dependence survives.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from alpha_core import DataError
from alpha_validation.metrics import FloatArray

IntArray = npt.NDArray[np.intp]


@dataclass(frozen=True, slots=True)
class OHLC:
    """Aligned open/high/low/close arrays, validated once (finite, positive, high/low ordered)."""

    open: FloatArray
    high: FloatArray
    low: FloatArray
    close: FloatArray

    def __post_init__(self) -> None:
        arrays = tuple(np.array(getattr(self, k), dtype=np.float64) for k in _KEYS)  # copies
        if any(a.ndim != 1 for a in arrays) or len({a.shape for a in arrays}) != 1:
            raise DataError("OHLC arrays must be one-dimensional and share one length")
        for key, array in zip(_KEYS, arrays, strict=True):
            object.__setattr__(self, key, array)
        if any(not np.all(np.isfinite(a)) or np.any(a <= 0.0) for a in arrays):
            raise DataError("OHLC prices must be finite and positive")
        top = np.maximum(self.open, self.close)
        bottom = np.minimum(self.open, self.close)
        bad = np.flatnonzero((self.high < top) | (self.low > bottom))
        if bad.size:
            raise DataError(
                f"bar {int(bad[0])} violates high >= max(open, close) >= min(open, close) >= low"
            )

    @property
    def size(self) -> int:
        return int(self.close.size)


_KEYS = ("open", "high", "low", "close")


def _rebuild(bars: OHLC, start_index: int, gap_order: IntArray, bar_order: IntArray) -> OHLC:
    """Copy bars ``0 .. start_index`` verbatim and rebuild the rest from the shuffled components."""
    log_o, log_h, log_l, log_c = (np.log(getattr(bars, k)) for k in _KEYS)
    first = start_index + 1
    gaps = (log_o[1:] - log_c[:-1])[start_index:][gap_order]
    rel_h = (log_h - log_o)[first:][bar_order]
    rel_l = (log_l - log_o)[first:][bar_order]
    rel_c = (log_c - log_o)[first:][bar_order]
    new_o = np.empty(gaps.size, dtype=np.float64)
    new_c = np.empty(gaps.size, dtype=np.float64)
    prev_close = float(log_c[start_index])
    for k in range(gaps.size):
        new_o[k] = prev_close + gaps[k]
        new_c[k] = new_o[k] + rel_c[k]
        prev_close = new_c[k]
    out = {k: np.array(getattr(bars, k), dtype=np.float64) for k in _KEYS}
    out["open"][first:] = np.exp(new_o)
    out["high"][first:] = np.exp(new_o + rel_h)
    out["low"][first:] = np.exp(new_o + rel_l)
    out["close"][first:] = np.exp(new_c)
    return OHLC(**out)


def permute_bars_multi(
    markets: Sequence[OHLC], *, start_index: int = 0, rng: np.random.Generator
) -> list[OHLC]:
    """Permute several aligned markets with ONE shared gap order and ONE shared intrabar order.

    Bars ``0 .. start_index`` are copied untouched in every market; the remaining bars are
    rebuilt from the shuffled components. The intrabar order is drawn first and the gap order
    second, as upstream does, so a single-market call and market 0 of a multi-market call agree
    for the same generator state.
    """
    if not markets:
        raise DataError("permute_bars_multi needs at least one market")
    n = markets[0].size
    if n < 2:
        raise DataError(f"permutation needs at least two bars, got {n}")
    for i, market in enumerate(markets):
        if market.size != n:
            raise DataError(f"every market must have {n} bars; market {i} has {market.size}")
    if start_index < 0 or start_index > n - 2:
        raise DataError(f"start_index must be in [0, {n - 2}], got {start_index}")
    count = n - start_index - 1
    bar_order = np.asarray(rng.permutation(count), dtype=np.intp)
    gap_order = np.asarray(rng.permutation(count), dtype=np.intp)
    return [_rebuild(market, start_index, gap_order, bar_order) for market in markets]


def permute_bars(bars: OHLC, *, start_index: int = 0, rng: np.random.Generator) -> OHLC:
    """Permute one market; see ``permute_bars_multi``."""
    return permute_bars_multi([bars], start_index=start_index, rng=rng)[0]


__all__ = ["OHLC", "permute_bars", "permute_bars_multi"]
