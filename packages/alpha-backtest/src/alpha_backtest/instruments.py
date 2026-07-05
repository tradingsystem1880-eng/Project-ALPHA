"""Instrument definitions per asset class for the backtest venue.

``equity_instrument`` wraps nautilus's ``TestInstrumentProvider`` for a standard cash equity;
``crypto_instrument`` hand-builds a ``CurrencyPair`` for slash pairs (``BTC/USD``) with 5-decimal
prices — a precision-2 equity instrument quantizes sub-dollar tokens to garbage (a 0.074 open
becomes 0.07, and anything under $0.005 rounds to zero). ``instrument_for`` dispatches by symbol
form so the CLI needs no per-asset knowledge. Exchange-true precisions/lot sizes per venue are a
later refinement; routing through this module keeps the seam stable.
"""

from __future__ import annotations

from decimal import Decimal

from nautilus_trader.model.currencies import USD
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CurrencyPair, Instrument
from nautilus_trader.model.objects import Currency, Price, Quantity
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from alpha_core import DataError

_CRYPTO_PRICE_PRECISION = 5  # ticks of 1e-5: fine down to ~$0.001 tokens


def equity_instrument(symbol: str, venue: str = "SIM") -> Instrument:
    """A cash-equity instrument (price precision 2, integer lots) on ``venue``.

    Its ``InstrumentId`` (e.g. ``AAPL.SIM``) matches ``feed.daily_bar_type(symbol, venue)``.
    """
    return TestInstrumentProvider.equity(symbol=symbol, venue=venue)


def crypto_instrument(symbol: str, venue: str = "SIM") -> Instrument:
    """A crypto pair (``BASE/QUOTE``) with 5-decimal prices and integer lots on ``venue``.

    Both legs must be currencies nautilus knows (majors and the common alt/stable coins are
    registered); an unknown code fails loud rather than silently mispricing. Integer lots keep
    the sizing convention shared with equities — sub-dollar tokens trade thousands of units, so
    integer rounding is immaterial where it matters.
    """
    base_code, _, quote_code = symbol.partition("/")
    if not base_code or not quote_code:
        raise DataError(f"crypto symbol must be BASE/QUOTE, got {symbol!r}")
    try:
        base = Currency.from_str(base_code)
        quote = Currency.from_str(quote_code)
    except ValueError as exc:
        raise DataError(
            f"unknown currency in {symbol!r}: {exc} (register it or use a known pair)"
        ) from exc
    return CurrencyPair(
        instrument_id=InstrumentId(Symbol(symbol), Venue(venue)),
        raw_symbol=Symbol(symbol),
        base_currency=base,
        quote_currency=quote if quote_code != "USD" else USD,
        price_precision=_CRYPTO_PRICE_PRECISION,
        size_precision=0,
        price_increment=Price(10**-_CRYPTO_PRICE_PRECISION, _CRYPTO_PRICE_PRECISION),
        size_increment=Quantity(1, 0),
        lot_size=None,
        max_quantity=None,
        min_quantity=None,
        max_notional=None,
        min_notional=None,
        max_price=None,
        min_price=None,
        margin_init=Decimal("0.05"),
        margin_maint=Decimal("0.03"),
        maker_fee=Decimal("0"),
        taker_fee=Decimal("0"),
        ts_event=0,
        ts_init=0,
    )


def instrument_for(symbol: str, venue: str = "SIM") -> Instrument:
    """Dispatch by symbol form: slash pairs (``BTC/USD``) → crypto, everything else → equity."""
    return crypto_instrument(symbol, venue) if "/" in symbol else equity_instrument(symbol, venue)
