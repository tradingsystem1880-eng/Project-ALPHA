"""Offline fixtures for paper-trading sandbox tests.

A ``FixtureLiveDataClient`` replays a pre-recorded list of nautilus ``Data`` (quotes/bars) into a
live ``TradingNode`` so sandbox sessions are deterministic and run with no network. Because a live
data client is built by a factory from a (serializable) config, the recorded events are passed via a
process-local registry keyed by a string the config carries — the same monkeypatch-seam pattern the
CLI tests use. Helpers build ticks/bars through ``instrument.make_price``/``make_qty`` so their
precision always matches the instrument (a mismatch makes nautilus reject the data).

Strategy classes are not named ``Test*`` so pytest does not collect them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock, MessageBus
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.core.data import Data
from nautilus_trader.data.messages import SubscribeBars, SubscribeInstrument, SubscribeQuoteTicks
from nautilus_trader.live.config import LiveDataClientConfig
from nautilus_trader.live.data_client import LiveDataClient, LiveMarketDataClient
from nautilus_trader.live.factories import LiveDataClientFactory
from nautilus_trader.model.data import (
    Bar,
    BarAggregation,
    BarSpecification,
    BarType,
    QuoteTick,
)
from nautilus_trader.model.enums import AggregationSource, PriceType
from nautilus_trader.model.identifiers import ClientId, Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.trading.strategy import Strategy

# process-local recorded-event registry: config.key -> the data to replay
_REGISTRY: dict[str, list[Data]] = {}


def register_fixture_events(key: str, events: Sequence[Data]) -> None:
    """Record the ``events`` a ``FixtureLiveDataClient`` (configured with ``key``) will replay."""
    _REGISTRY[key] = list(events)


class FixtureDataClientConfig(LiveDataClientConfig, frozen=True):
    """Config for the offline replay client: which recorded events, and the pre-replay delay."""

    key: str = "default"
    feed_delay: float = 0.2  # let the strategy's on_start subscriptions register before replay


class FixtureLiveDataClient(LiveMarketDataClient):
    """Replays recorded ``Data`` into the node after connecting; subscriptions are no-ops."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: FixtureDataClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> None:
        events = _REGISTRY.get(config.key, [])
        venue = events[0].instrument_id.venue if events else Venue("SANDBOX")
        super().__init__(
            loop=loop,
            client_id=ClientId(name),
            venue=venue,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=InstrumentProvider(),
        )
        self._events = events
        self._delay = config.feed_delay

    async def _connect(self) -> None:
        async def _feed() -> None:
            await asyncio.sleep(self._delay)
            for event in self._events:
                self._handle_data(event)

        self._loop.create_task(_feed())

    async def _disconnect(self) -> None:
        pass

    async def _subscribe_quote_ticks(self, command: SubscribeQuoteTicks) -> None:
        pass

    async def _subscribe_bars(self, command: SubscribeBars) -> None:
        pass

    async def _subscribe_instrument(self, command: SubscribeInstrument) -> None:
        pass


class FixtureLiveDataClientFactory(LiveDataClientFactory):
    """Factory the ``TradingNode`` uses to build the replay client."""

    @staticmethod
    def create(
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: LiveDataClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> LiveDataClient:
        assert isinstance(config, FixtureDataClientConfig)
        return FixtureLiveDataClient(loop, name, config, msgbus, cache, clock)


def daily_bar_type(instrument: Instrument) -> BarType:
    """An external daily-LAST ``BarType`` for ``instrument`` (the strategy's decision bar)."""
    spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
    return BarType(instrument.id, spec, AggregationSource.EXTERNAL)


def make_quote(instrument: Instrument, bid: float, ask: float, ts: int) -> QuoteTick:
    """A 1-lot ``QuoteTick`` with prices/sizes at the instrument's precision."""
    return QuoteTick(
        instrument_id=instrument.id,
        bid_price=instrument.make_price(bid),
        ask_price=instrument.make_price(ask),
        bid_size=instrument.make_qty(1),
        ask_size=instrument.make_qty(1),
        ts_event=ts,
        ts_init=ts,
    )


def make_bar(instrument: Instrument, bar_type: BarType, price: float, ts: int) -> Bar:
    """A flat OHLC ``Bar`` (all legs = ``price``) at the instrument's precision."""
    px = instrument.make_price(price)
    return Bar(
        bar_type=bar_type,
        open=px,
        high=px,
        low=px,
        close=px,
        volume=instrument.make_qty(1),
        ts_event=ts,
        ts_init=ts,
    )


class CountingStrategy(Strategy):  # type: ignore[misc]  # nautilus Strategy is untyped (Cython)
    """A do-nothing strategy: subscribes to bars + quotes, counts them, never orders."""

    def __init__(self, instrument: Instrument, bar_type: BarType) -> None:
        super().__init__()
        self._iid = instrument.id
        self._bar_type = bar_type
        self.bars_seen = 0
        self.quotes_seen = 0

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)
        self.subscribe_quote_ticks(self._iid)

    def on_bar(self, bar: Bar) -> None:
        self.bars_seen += 1

    def on_quote_tick(self, quote: QuoteTick) -> None:
        self.quotes_seen += 1
