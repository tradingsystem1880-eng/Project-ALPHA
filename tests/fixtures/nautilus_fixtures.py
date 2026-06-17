"""Shared deterministic fixtures for nautilus-backed integration tests.

Bar builders + minimal reusable test strategies. Centralizes the single ``# type: ignore[misc]``
needed to subclass the (Cython-untyped) nautilus ``Strategy`` base, so individual test files don't
each repeat it. Strategy classes are not named ``Test*`` so pytest does not collect them.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from alpha_core import Bar


def ns(dt: datetime) -> int:
    """A tz-aware datetime as integer nanoseconds since the UNIX epoch."""
    return int(dt.timestamp() * 1_000_000_000)


def ladder_bars(
    symbol: str = "AAPL", *, n: int = 5, first_open: float = 100.0, step: float = 10.0
) -> list[Bar]:
    """``n`` daily bars whose opens climb by ``step`` (100, 110, ...); close = open + 5.

    Distinct opens make a next-open fill identifiable, and ``close != next open`` exposes a
    wrong-bar fill. The wide high/low range keeps any intrabar reference inside the bar.
    """
    return [
        Bar(
            symbol=symbol,
            ts=datetime(2024, 1, 2 + i, tzinfo=UTC),
            open=first_open + step * i,
            high=first_open + step * i + 40.0,
            low=first_open + step * i - 10.0,
            close=first_open + step * i + 5.0,
            volume=1000.0,
        )
        for i in range(n)
    ]


def trend_bars(symbol: str, step: float, *, n: int = 14) -> list[Bar]:
    """``n`` daily bars trending by ``step``/bar (positive = up, negative = down)."""
    return [
        Bar(
            symbol=symbol,
            ts=datetime(2024, 1, 2 + i, tzinfo=UTC),
            open=100.0 + step * i - (0.5 if step > 0 else -0.5),
            high=100.0 + step * i + 2.0,
            low=100.0 + step * i - 2.0,
            close=100.0 + step * i,
            volume=1000.0,
        )
        for i in range(n)
    ]


def bars_from_closes(symbol: str, closes: list[float]) -> list[Bar]:
    """Daily bars with a given close path (open=high=low=close); for signal/vol-driven tests."""
    return [
        Bar(
            symbol=symbol,
            ts=datetime(2024, 1, 2 + i, tzinfo=UTC),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1000.0,
        )
        for i, c in enumerate(closes)
    ]


class DoNothing(Strategy):  # type: ignore[misc]  # nautilus Strategy is untyped (Cython)
    """Subscribes to bars and counts them; never trades."""

    def __init__(self, bar_type: BarType) -> None:
        super().__init__()
        self._bar_type = bar_type
        self.bars_seen = 0

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)

    def on_bar(self, bar: object) -> None:
        self.bars_seen += 1


class DecideCloseExecuteOpen(Strategy):  # type: ignore[misc]
    """Decide once on the first bar's close; submit a market BUY on the next open quote."""

    def __init__(self, bar_type: BarType, instrument_id: InstrumentId) -> None:
        super().__init__()
        self._bar_type = bar_type
        self._iid = instrument_id
        self._decided = False
        self._want = False
        self.fill_price: float | None = None
        self.fill_ts: int | None = None

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)
        self.subscribe_quote_ticks(self._iid)

    def on_bar(self, bar: object) -> None:
        if not self._decided:  # decide exactly once, on the close of t
            self._decided = True
            self._want = True

    def on_quote_tick(self, quote: object) -> None:
        if self._want:  # execute at the next session open (t+1)
            self._want = False
            self.submit_order(
                self.order_factory.market(
                    instrument_id=self._iid, order_side=OrderSide.BUY, quantity=Quantity.from_int(1)
                )
            )

    def on_order_filled(self, event: object) -> None:
        self.fill_price = float(event.last_px)  # type: ignore[attr-defined]  # nautilus OrderFilled
        self.fill_ts = int(event.ts_event)  # type: ignore[attr-defined]


class RoundTrip(Strategy):  # type: ignore[misc]
    """Open ``qty`` at the first open quote, close it at the ``exit_at``-th quote (one round-trip).

    ``opening_side`` BUY = long round-trip (buy then sell); SELL = short round-trip (sell then buy).
    """

    def __init__(
        self,
        instrument_id: InstrumentId,
        *,
        qty: int = 100,
        exit_at: int = 3,
        opening_side: object = OrderSide.BUY,
    ) -> None:
        super().__init__()
        self._iid = instrument_id
        self._qty = qty
        self._exit_at = exit_at
        self._open_side = opening_side
        self._close_side = OrderSide.SELL if opening_side == OrderSide.BUY else OrderSide.BUY
        self._n = 0

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self._iid)

    def on_quote_tick(self, quote: object) -> None:
        self._n += 1
        if self._n == 1:
            self._market(self._open_side)
        elif self._n == self._exit_at:
            self._market(self._close_side)

    def _market(self, side: object) -> None:
        self.submit_order(
            self.order_factory.market(
                instrument_id=self._iid, order_side=side, quantity=Quantity.from_int(self._qty)
            )
        )


class BuyAndHold(Strategy):  # type: ignore[misc]
    """Buy ``qty`` at the first open quote and hold (never close)."""

    def __init__(self, instrument_id: InstrumentId, *, qty: int = 100) -> None:
        super().__init__()
        self._iid = instrument_id
        self._qty = qty
        self._bought = False

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self._iid)

    def on_quote_tick(self, quote: object) -> None:
        if not self._bought:
            self._bought = True
            self.submit_order(
                self.order_factory.market(
                    instrument_id=self._iid,
                    order_side=OrderSide.BUY,
                    quantity=Quantity.from_int(self._qty),
                )
            )
