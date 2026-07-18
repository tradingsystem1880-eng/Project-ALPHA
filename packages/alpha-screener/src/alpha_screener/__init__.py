"""Screener & news via finnhub — opt-in, API-key-gated (``ALPHA_FINNHUB_API_KEY``).

Pure parsers (offline-testable) plus one network module (``finnhub``) that lazily builds the client
and fails loud with setup instructions when the key is absent — the minimal key handling a keyed
provider requires. Imports nothing internal but ``alpha_core``.
"""

from __future__ import annotations

from importlib.metadata import version

from alpha_screener.models import NewsItem, Quote
from alpha_screener.parse import parse_news, parse_quote

__version__ = version("alpha-screener")
__all__ = ["NewsItem", "Quote", "parse_news", "parse_quote"]
