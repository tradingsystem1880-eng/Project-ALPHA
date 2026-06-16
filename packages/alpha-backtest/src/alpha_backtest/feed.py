"""Translate point-in-time ``alpha_core.Bar`` objects into ``nautilus_trader`` bars.

The PIT firewall (``alpha_data.PointInTimeSource``) is the ONLY source of bars; this module
is the single seam that converts its typed, look-ahead-safe ``Bar`` objects into the engine's
data-feed objects. Chronology and the bar-close timestamp are preserved; nothing is fetched
or reordered here. Price/size precision is parameterised pending real instrument definitions.
"""

from __future__ import annotations

from collections.abc import Sequence

from nautilus_trader.core.data import Data
from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import BarType, QuoteTick
from nautilus_trader.model.objects import Price, Quantity

from alpha_core import Bar

_NS_PER_SECOND = 1_000_000_000
# A daily decision bar is "known" at its session close; we stamp it 23h after the session open.
# Any offset in (0, 24h) keeps close(t) strictly before open(t+1), so the strategy decides on the
# close of t and the next price event it sees is the open of t+1 (the execution convention).
_SESSION_CLOSE_OFFSET_NS = 23 * 3600 * _NS_PER_SECOND


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


def to_execution_feed(
    bars: Sequence[Bar],
    bar_type: BarType,
    *,
    price_precision: int = 2,
    size_precision: int = 0,
    quote_size: float = 1_000_000_000.0,
) -> list[Data]:
    """Build a look-ahead-safe nautilus feed honoring decide-on-close-t / fill-at-open-t+1.

    nautilus's default bar execution fills market orders at the bar *close*; the spec requires
    fills at the *open of t+1*. So for each session we emit TWO chronological events:

    * an open-priced ``QuoteTick`` stamped at the session **open** (``bar.ts``) — the price a
      market order decided on the prior session's close fills against. ``quote_size`` is large by
      default so the order fills fully at the open; realistic slippage is modeled separately by a
      ``FillModel`` in a later increment, not by book depth here.
    * the **decision** ``Bar`` (full OHLC) stamped at the session **close** (``+23h``), the event a
      strategy reads to choose its target.

    Run this feed with a venue configured ``bar_execution=False`` (see ``engine.run_backtest``) so
    that only the quotes drive fills. The returned list is chronologically ordered.
    """
    iid = bar_type.instrument_id
    size = Quantity(quote_size, size_precision)
    out: list[Data] = []
    for b in bars:
        open_ns = int(b.ts.timestamp() * _NS_PER_SECOND)
        close_ns = open_ns + _SESSION_CLOSE_OFFSET_NS
        open_px = Price(b.open, price_precision)
        out.append(QuoteTick(iid, open_px, open_px, size, size, open_ns, open_ns))
        out.append(
            NautilusBar(
                bar_type,
                open_px,
                Price(b.high, price_precision),
                Price(b.low, price_precision),
                Price(b.close, price_precision),
                Quantity(b.volume, size_precision),
                close_ns,
                close_ns,
            )
        )
    return out
