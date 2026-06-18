"""A live data client that replays a recorded ``Data`` sequence into the node.

Used to drive a paper session over stored/historical bars through the *same* live ``TradingNode`` —
a dry-run of the paper pipeline without a real-time feed (the live websocket feed is a later
increment). Events are passed via a process-local registry keyed by a string the (serializable)
config carries, since a live data client is built by a factory from config alone.
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
from nautilus_trader.model.identifiers import ClientId, Venue

# process-local recorded-event registry: config.key -> the data to replay
_REGISTRY: dict[str, list[Data]] = {}


def register_replay_events(key: str, events: Sequence[Data]) -> None:
    """Record the ``events`` a ``ReplayDataClient`` (configured with ``key``) will replay."""
    _REGISTRY[key] = list(events)


class ReplayDataClientConfig(LiveDataClientConfig, frozen=True):
    """Which recorded events to replay, plus replay timing.

    ``feed_interval`` paces events apart so each order's async fill round-trip settles before the
    next event — reproducing the spacing of real (e.g. daily) live data.
    """

    key: str = "default"
    feed_delay: float = 0.2  # let the strategy's on_start subscriptions register before replay
    feed_interval: float = 0.0  # delay between successive events (0 = back-to-back)


class ReplayDataClient(LiveMarketDataClient):
    """Replays recorded ``Data`` into the node after connecting; subscriptions are no-ops."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: ReplayDataClientConfig,
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
        self._interval = config.feed_interval

    async def _connect(self) -> None:
        async def _feed() -> None:
            await asyncio.sleep(self._delay)
            for event in self._events:
                self._handle_data(event)
                if self._interval:
                    await asyncio.sleep(self._interval)

        self._loop.create_task(_feed())

    async def _disconnect(self) -> None:
        pass

    async def _subscribe_quote_ticks(self, command: SubscribeQuoteTicks) -> None:
        pass

    async def _subscribe_bars(self, command: SubscribeBars) -> None:
        pass

    async def _subscribe_instrument(self, command: SubscribeInstrument) -> None:
        pass


class ReplayDataClientFactory(LiveDataClientFactory):
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
        assert isinstance(config, ReplayDataClientConfig)
        return ReplayDataClient(loop, name, config, msgbus, cache, clock)
