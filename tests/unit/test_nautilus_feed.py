"""The execution feed: bar types and the look-ahead-safe open-quote + close-bar event stream."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import QuoteTick

from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_core import Bar
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


def test_sub_daily_bars_fail_loud() -> None:
    # The +23h decision stamp assumes calendar-daily sessions; an hourly feed would interleave
    # events non-chronologically and the engine would run to completion with zero fills.
    from datetime import timedelta

    from alpha_core import DataError

    t0 = datetime(2024, 1, 2, tzinfo=UTC)
    hourly = [
        Bar(
            symbol="X",
            ts=t0 + timedelta(hours=i),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.0,
            volume=1.0,
        )  # noqa: E501
        for i in range(3)
    ]
    with pytest.raises(DataError, match="24h"):
        to_execution_feed(hourly, daily_bar_type("X"))


def test_duplicate_or_disordered_bars_fail_loud() -> None:
    from alpha_core import DataError

    t0 = datetime(2024, 1, 2, tzinfo=UTC)
    dup = [
        Bar(symbol="X", ts=t0, open=10.0, high=11.0, low=9.0, close=10.0, volume=1.0),
        Bar(symbol="X", ts=t0, open=10.0, high=11.0, low=9.0, close=10.0, volume=1.0),
    ]
    with pytest.raises(DataError):
        to_execution_feed(dup, daily_bar_type("X"))


def test_negative_slippage_fails_loud() -> None:
    from datetime import timedelta

    from alpha_core import DataError

    t0 = datetime(2024, 1, 2, tzinfo=UTC)
    bars = [
        Bar(
            symbol="X",
            ts=t0 + timedelta(days=i),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.0,
            volume=1.0,
        )  # noqa: E501
        for i in range(2)
    ]
    with pytest.raises(DataError, match="slippage"):
        to_execution_feed(bars, daily_bar_type("X"), slippage_bps=-1.0)


def test_negative_fee_fails_loud() -> None:
    from alpha_backtest.frictions import BpsFeeModel
    from alpha_core import DataError

    with pytest.raises(DataError, match="fee_bps"):
        BpsFeeModel(-1.0)
