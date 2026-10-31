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


def crypto_instrument(
    symbol: str,
    venue: str = "SIM",
    *,
    price_precision: int = _CRYPTO_PRICE_PRECISION,
    size_precision: int = 0,
    size_increment: float = 1.0,
) -> Instrument:
    """A crypto pair (``BASE/QUOTE``), defaulting to 5-decimal prices and integer lots.

    Both legs must be currencies nautilus knows (majors and the common alt/stable coins are
    registered); an unknown code fails loud rather than silently mispricing. Integer lots keep
    the legacy sizing convention. Explicit precisions and an exactly representable size
    increment support fractional research quantities; they do not establish venue qualification.
    """
    if (
        type(price_precision) is not int
        or not 0 <= price_precision <= 8
        or type(size_precision) is not int
        or not 0 <= size_precision <= 8
        or type(size_increment) not in (int, float)
        or not Decimal(str(size_increment)).is_finite()
        or size_increment <= 0
        or Decimal(str(size_increment)) % Decimal(10) ** -size_precision != 0
    ):
        raise DataError("crypto instrument requires representable positive precision/increment")
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
        price_precision=price_precision,
        size_precision=size_precision,
        price_increment=Price(10**-price_precision, price_precision),
        size_increment=Quantity(size_increment, size_precision),
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
