"""Instrument definitions per asset class for the backtest venue.

v1 wraps nautilus's ``TestInstrumentProvider`` for a standard cash equity — enough to run the
daily slice. Explicit, hand-built definitions per asset class (crypto, FX) with real
precisions/lot sizes are a later increment; routing them through this module keeps the seam stable.
"""

from __future__ import annotations

from nautilus_trader.model.instruments import Instrument
from nautilus_trader.test_kit.providers import TestInstrumentProvider


def equity_instrument(symbol: str, venue: str = "SIM") -> Instrument:
    """A cash-equity instrument (price precision 2, integer lots) on ``venue``.

    Its ``InstrumentId`` (e.g. ``AAPL.SIM``) matches ``feed.daily_bar_type(symbol, venue)``.
    """
    return TestInstrumentProvider.equity(symbol=symbol, venue=venue)
