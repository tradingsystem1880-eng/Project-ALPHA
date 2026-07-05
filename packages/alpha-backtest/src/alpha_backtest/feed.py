"""Translate point-in-time ``alpha_core.Bar`` objects into a ``nautilus_trader`` data feed.

``to_execution_feed`` is the single seam that converts the look-ahead-safe daily bars produced by
``alpha_data.source.PointInTimeSource.as_of`` into the engine's data stream, encoding the
"decide on close of t, fill at open of t+1" convention (see ``engine.run_backtest``).
``daily_bar_type`` names the matching nautilus ``BarType``.
"""

from __future__ import annotations

from collections.abc import Sequence

from nautilus_trader.core.data import Data
from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import BarType, QuoteTick
from nautilus_trader.model.objects import Price, Quantity

from alpha_core import Bar, DataError

_NS_PER_SECOND = 1_000_000_000
# A daily decision bar is "known" at its session close; we stamp it 23h after the session open.
# Any offset in (0, 24h) keeps close(t) strictly before open(t+1) for daily (calendar-spaced) bars,
# so the strategy decides on the close of t and the next price event it sees is the open of t+1.
_SESSION_CLOSE_OFFSET_NS = 23 * 3600 * _NS_PER_SECOND


def daily_bar_type(symbol: str, venue: str = "SIM") -> BarType:
    """A daily, last-price, externally-aggregated ``BarType`` for ``symbol`` on ``venue``.

    ``EXTERNAL`` aggregation marks the bars as already-aggregated daily data (we never let
    nautilus build them from ticks), and ``LAST`` keys them off the close price.
    """
    return BarType.from_str(f"{symbol}.{venue}-1-DAY-LAST-EXTERNAL")


def to_execution_feed(
    bars: Sequence[Bar],
    bar_type: BarType,
    *,
    price_precision: int = 2,
    size_precision: int = 0,
    quote_size: float = 1_000_000_000.0,
    slippage_bps: float = 0.0,
) -> list[Data]:
    """Build a look-ahead-safe nautilus feed honoring decide-on-close-t / fill-at-open-t+1.

    nautilus's default bar execution fills market orders at the bar *close*; the spec requires
    fills at the *open of t+1*. So for each session we emit TWO chronological events:

    * an open-priced ``QuoteTick`` stamped at the session **open** (``bar.ts``) — the price a
      market order decided on the prior session's close fills against. ``slippage_bps`` widens the
      quote into a side-aware half-spread around the open (bid = open·(1−s), ask = open·(1+s)), so a
      market buy fills at the ask and a sell at the bid — conservative slippage on the t+1 open
      (spec §7). ``quote_size`` is large by default so the order fills fully (book depth is not the
      slippage model here). Note: the spread is quantized to ``price_precision``, so a slippage
      smaller than one tick at the instrument's price has no effect.
    * the **decision** ``Bar`` (full OHLC) stamped at the session **close** (``+23h``), the event a
      strategy reads to choose its target.

    Run this feed with a venue configured ``bar_execution=False`` (see ``engine.run_backtest``) so
    that only the quotes drive fills. The returned list is chronologically ordered.
    """
    if slippage_bps < 0.0:
        raise DataError(
            f"slippage_bps must be >= 0 (a negative value pays you), got {slippage_bps}"
        )
    # The +23h close stamp encodes DAILY (calendar-spaced) sessions; anything tighter would emit a
    # non-chronological feed the engine silently runs with zero fills. Fail loud instead.
    for prev, cur in zip(bars, bars[1:], strict=False):
        gap_s = (cur.ts - prev.ts).total_seconds()
        if gap_s < 24 * 3600:
            raise DataError(
                f"to_execution_feed requires daily (>= 24h-spaced, strictly increasing) bars; "
                f"got {prev.ts.isoformat()} -> {cur.ts.isoformat()} ({gap_s / 3600:.1f}h apart)"
            )
    iid = bar_type.instrument_id
    size = Quantity(quote_size, size_precision)
    half_spread = slippage_bps / 10_000.0
    out: list[Data] = []
    for b in bars:
        open_ns = int(b.ts.timestamp() * _NS_PER_SECOND)
        close_ns = open_ns + _SESSION_CLOSE_OFFSET_NS
        bid = Price(b.open * (1.0 - half_spread), price_precision)
        ask = Price(b.open * (1.0 + half_spread), price_precision)
        out.append(QuoteTick(iid, bid, ask, size, size, open_ns, open_ns))
        out.append(
            NautilusBar(
                bar_type,
                Price(b.open, price_precision),
                Price(b.high, price_precision),
                Price(b.low, price_precision),
                Price(b.close, price_precision),
                Quantity(b.volume, size_precision),
                close_ns,
                close_ns,
            )
        )
    return out
