"""Phase 4d: a do-nothing strategy runs through the live sandbox node and sees all replayed data.

Proves the ``TradingNode`` + ``SandboxExecutionClient`` + ``FixtureLiveDataClient`` assembly works
offline and deterministically: every recorded bar/quote reaches the strategy through the full live
data → engine → sandbox path, and a strategy that never orders produces zero orders (no spurious
fills from the sandbox matching engine).
"""

from __future__ import annotations

import asyncio

from alpha_execution.instruments import crypto_instrument
from alpha_paper.config import PaperSpec
from alpha_paper.node import build_paper_node, run_node_for
from tests.fixtures.paper_fixtures import (
    CountingStrategy,
    FixtureDataClientConfig,
    FixtureLiveDataClientFactory,
    daily_bar_type,
    make_bar,
    make_quote,
    register_fixture_events,
)

_DAY_NS = 86_400_000_000_000


def test_do_nothing_strategy_sees_all_data_and_places_no_orders(
    paper_loop: asyncio.AbstractEventLoop,
) -> None:
    instrument = crypto_instrument("BTC/USDT")
    bar_type = daily_bar_type(instrument)

    # Interleave a quote then a decision bar per session, mirroring the backtest feed's ordering.
    events = []
    for i in range(4):
        ts = (i + 1) * _DAY_NS
        events.append(make_quote(instrument, bid=100.0 + i, ask=100.5 + i, ts=ts))
        events.append(make_bar(instrument, bar_type, price=100.0 + i, ts=ts + 1))
    register_fixture_events("sandbox-test", events)

    spec = PaperSpec(symbol="BTC/USDT", exchange="binance", venue=str(instrument.id.venue))
    node = build_paper_node(
        spec,
        instrument,
        data_client_name="FIXTURE",
        data_client_factory=FixtureLiveDataClientFactory,
        data_client_config=FixtureDataClientConfig(key="sandbox-test", feed_delay=0.2),
    )
    strategy = CountingStrategy(instrument, bar_type)
    node.trader.add_strategy(strategy)
    cache = node.cache

    paper_loop.run_until_complete(run_node_for(node, duration_seconds=1.0))

    assert strategy.bars_seen == 4  # every recorded decision bar reached the strategy
    assert strategy.quotes_seen == 4
    assert len(cache.orders()) == 0  # no orders (no spurious fills from the sandbox engine)
