"""Instrument definitions per asset class, shared by the backtest and paper venues.

v1 wraps nautilus's ``TestInstrumentProvider`` helpers: a cash equity (integer lots) and crypto
``CurrencyPair``s (fractional, ``size_precision`` > 0). Routing every venue through this seam keeps
instrument construction identical whether the engine is a historical replay or a live sandbox.
Explicit hand-built definitions with bespoke precisions/lot sizes are a later increment behind the
same functions.
"""

from __future__ import annotations

from collections.abc import Callable

from nautilus_trader.model.instruments import Instrument
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from alpha_core import DataError

# Known crypto pairs -> the nautilus provider helper that builds them. The instrument carries its
# own native venue (e.g. ``BTCUSDT.BINANCE``); the data/exec venue wiring lives at the node seam.
_CRYPTO: dict[str, Callable[[], Instrument]] = {
    "BTCUSDT": TestInstrumentProvider.btcusdt_binance,
    "ETHUSDT": TestInstrumentProvider.ethusdt_binance,
    "ADAUSDT": TestInstrumentProvider.adausdt_binance,
}


def equity_instrument(symbol: str, venue: str = "SIM") -> Instrument:
    """A cash-equity instrument (price precision 2, integer lots) on ``venue``.

    Its ``InstrumentId`` (e.g. ``AAPL.SIM``) matches ``feed.daily_bar_type(symbol, venue)``.
    """
    return TestInstrumentProvider.equity(symbol=symbol, venue=venue)


def crypto_instrument(symbol: str) -> Instrument:
    """A crypto ``CurrencyPair`` for a supported ``symbol`` (e.g. ``"BTC/USDT"``, ``"BTCUSDT"``).

    Fractional sizing (``size_precision`` > 0) — unlike equities' integer lots. Fails loud with a
    typed ``DataError`` on an unsupported symbol rather than silently substituting one.
    """
    key = symbol.replace("/", "").replace("-", "").upper()
    factory = _CRYPTO.get(key)
    if factory is None:
        raise DataError(f"unsupported crypto symbol {symbol!r}; known: {sorted(_CRYPTO)}")
    return factory()
