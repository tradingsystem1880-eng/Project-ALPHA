"""The one network edge — the finnhub client, gated on ``ALPHA_FINNHUB_API_KEY``.

Lazily imports the ``finnhub`` client and fails loud with setup instructions when the key is
absent, so the rest of the package (and its parsers) stay importable and offline-testable.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from alpha_core import DataError
from alpha_screener.models import NewsItem, Quote
from alpha_screener.parse import parse_news, parse_quote

_KEY_ENV = "ALPHA_FINNHUB_API_KEY"


def _client() -> object:
    key = os.environ.get(_KEY_ENV)
    if not key:
        raise DataError(
            f"finnhub requires an API key — set {_KEY_ENV} (a free key from finnhub.io). "
            "The screener is opt-in; without the key it fails loud rather than degrading silently."
        )
    import finnhub  # lazy: only imported on a real fetch

    return finnhub.Client(api_key=key)


def fetch_quote(symbol: str) -> Quote:
    """Live quote for ``symbol`` (needs network + ``ALPHA_FINNHUB_API_KEY``)."""
    return parse_quote(symbol, _client().quote(symbol))  # type: ignore[attr-defined]


def fetch_news(symbol: str, *, days: int = 7, limit: int = 20) -> list[NewsItem]:
    """Recent company news for ``symbol`` over the trailing ``days`` (needs network + key)."""
    to = date.today()
    frm = to - timedelta(days=days)
    payload = _client().company_news(  # type: ignore[attr-defined]
        symbol, _from=frm.isoformat(), to=to.isoformat()
    )
    return parse_news(payload, limit=limit)
