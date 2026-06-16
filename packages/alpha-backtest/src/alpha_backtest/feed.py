"""Translate point-in-time ``alpha_core.Bar`` objects into ``nautilus_trader`` bars.

The PIT firewall (``alpha_data.PointInTimeSource``) is the ONLY source of bars; this module
is the single seam that converts its typed, look-ahead-safe ``Bar`` objects into the engine's
data-feed objects. Chronology and the bar-close timestamp are preserved; nothing is fetched
or reordered here. Price/size precision is parameterised pending real instrument definitions.
"""

from __future__ import annotations

from collections.abc import Sequence

from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.objects import Price, Quantity

from alpha_core import Bar

_NS_PER_SECOND = 1_000_000_000


def daily_bar_type(symbol: str, venue: str = "SIM") -> BarType:
    """A daily, last-price, externally-aggregated ``BarType`` for ``symbol`` on ``venue``.

    ``EXTERNAL`` aggregation marks the bars as already-aggregated daily data (we never let
    nautilus build them from ticks), and ``LAST`` keys them off the close price.
    """
    return BarType.from_str(f"{symbol}.{venue}-1-DAY-LAST-EXTERNAL")


def to_nautilus_bar(
    bar: Bar, bar_type: BarType, *, price_precision: int = 2, size_precision: int = 0
) -> NautilusBar:
    """Convert one ``alpha_core.Bar`` into a nautilus ``Bar`` under ``bar_type``.

    ``ts_event`` and ``ts_init`` are both the bar-close instant in integer nanoseconds: a
    daily bar is decided on the close of ``t`` and filled at the open of ``t+1`` by the engine,
    so there is no intrabar instant to model here.
    """
    ts = int(bar.ts.timestamp() * _NS_PER_SECOND)
    return NautilusBar(
        bar_type,
        Price(bar.open, price_precision),
        Price(bar.high, price_precision),
        Price(bar.low, price_precision),
        Price(bar.close, price_precision),
        Quantity(bar.volume, size_precision),
        ts,
        ts,
    )


def to_nautilus_bars(
    bars: Sequence[Bar],
    bar_type: BarType,
    *,
    price_precision: int = 2,
    size_precision: int = 0,
) -> list[NautilusBar]:
    """Convert a chronological run of ``alpha_core.Bar``s (e.g. ``PointInTimeSource.as_of``)."""
    return [
        to_nautilus_bar(b, bar_type, price_precision=price_precision, size_precision=size_precision)
        for b in bars
    ]
