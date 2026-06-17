"""The execution feed: bar types and the look-ahead-safe open-quote + close-bar event stream."""

from __future__ import annotations

from datetime import UTC, datetime

from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import QuoteTick

from alpha_backtest.feed import daily_bar_type, to_execution_feed
from tests.fixtures.nautilus_fixtures import bars_from_closes, ns


def test_daily_bar_type_equity_and_slash_symbol() -> None:
    assert str(daily_bar_type("AAPL")) == "AAPL.SIM-1-DAY-LAST-EXTERNAL"
    assert str(daily_bar_type("BTC/USD").instrument_id) == "BTC/USD.SIM"  # slash survives


def test_feed_emits_open_quote_then_close_bar_in_order() -> None:
    feed = to_execution_feed(bars_from_closes("AAPL", [100.0, 110.0]), daily_bar_type("AAPL"))
    assert [type(x) for x in feed] == [QuoteTick, NautilusBar, QuoteTick, NautilusBar]
    # open quote at the session open; decision bar strictly later (same session close); the next
    # session's open quote strictly after that -> decide-on-close-t precedes fill-at-open-(t+1).
    ts = [x.ts_event for x in feed]
    assert ts[0] == ns(datetime(2024, 1, 2, tzinfo=UTC))  # session-0 open quote
    assert ts[0] < ts[1] < ts[2] < ts[3]
    assert ts[2] == ns(datetime(2024, 1, 3, tzinfo=UTC))  # session-1 open quote


def test_feed_slippage_is_a_side_aware_spread() -> None:
    quote, _bar = to_execution_feed(
        bars_from_closes("AAPL", [100.0]), daily_bar_type("AAPL"), slippage_bps=50.0
    )
    assert float(quote.bid_price) == 99.5  # open * (1 - 0.005): a market sell hits the bid
    assert float(quote.ask_price) == 100.5  # open * (1 + 0.005): a market buy lifts the ask


def test_feed_respects_price_precision() -> None:
    # FX-grade precision survives the round-trip (the default precision 2 would truncate 1.23456)
    quote, bar = to_execution_feed(
        bars_from_closes("EURUSD", [1.23456]), daily_bar_type("EURUSD"), price_precision=5
    )
    assert float(bar.close) == 1.23456
    assert float(quote.bid_price) == 1.23456  # no slippage -> bid == open at full precision
