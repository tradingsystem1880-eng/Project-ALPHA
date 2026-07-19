"""Opt-in smoke for the real Nautilus Binance public-data connection and one quote.

Run explicitly with ``uv run pytest -m network tests/integration/test_binance_paper_live.py``.
The test constructs no execution client and uses no credentials; a timer bounds network failure.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable

import pytest
from nautilus_trader.adapters.binance.factories import BinanceLiveDataClientFactory
from nautilus_trader.common.actor import Actor
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.identifiers import InstrumentId

from alpha_cli import _paper

pytestmark = pytest.mark.network


class _QuoteProbe(Actor):  # type: ignore[misc]  # Nautilus Actor is an untyped Cython class
    def __init__(self, instrument_id: InstrumentId, stop_node: Callable[[], None]) -> None:
        super().__init__()
        self._instrument_id = instrument_id
        self._stop_node = stop_node
        self.quote: QuoteTick | None = None

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self._instrument_id)

    def on_quote_tick(self, tick: QuoteTick) -> None:
        self.quote = tick
        self._stop_node()


def test_binance_public_live_data_receives_btc_usdt_quote() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        instrument_id = _paper.binance_instrument_id("BTC/USDT")
        config = TradingNodeConfig(
            trader_id="SMOKE-001",
            data_clients={"BINANCE": _paper.build_binance_data_config("BTC/USDT")},
        )
        # No execution config or factory is present: this smoke can only receive public market data.
        node = TradingNode(config=config)
        node.add_data_client_factory("BINANCE", BinanceLiveDataClientFactory)
        probe = _QuoteProbe(instrument_id, node.stop)
        node.trader.add_actor(probe)
        node.build()
        timeout = threading.Timer(30.0, node.stop)
        timeout.start()
        try:
            node.run(raise_exception=True)
        finally:
            timeout.cancel()
            node.dispose()

        assert probe.quote is not None, "no Binance BTC/USDT quote received within 30 seconds"
        assert float(probe.quote.bid_price) > 0.0
        assert float(probe.quote.ask_price) >= float(probe.quote.bid_price)
    finally:
        asyncio.set_event_loop(None)
        loop.close()
