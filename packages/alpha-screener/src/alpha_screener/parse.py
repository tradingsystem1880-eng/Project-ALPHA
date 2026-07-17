"""Pure parsers: finnhub JSON dicts → typed values. Offline-testable, fail-loud on bad data."""

from __future__ import annotations

from typing import Any

from alpha_core import DataError
from alpha_screener.models import NewsItem, Quote


def parse_quote(symbol: str, payload: dict[str, Any]) -> Quote:
    """Parse a finnhub ``/quote`` response (keys ``c/d/dp/h/l/o/pc``).

    Finnhub returns an all-zero body for an unknown symbol; that is treated as no data (fail loud).
    """
    try:
        current = float(payload["c"])
        quote = Quote(
            symbol=symbol,
            current=current,
            change=float(payload.get("d") or 0.0),
            percent_change=float(payload.get("dp") or 0.0),
            high=float(payload["h"]),
            low=float(payload["l"]),
            open=float(payload["o"]),
            prev_close=float(payload["pc"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DataError(f"malformed finnhub quote for {symbol!r}: {exc}") from exc
    if current == 0.0 and quote.prev_close == 0.0:
        raise DataError(f"no finnhub quote for {symbol!r} (unknown symbol?)")
    return quote


def parse_news(payload: list[dict[str, Any]], *, limit: int = 20) -> list[NewsItem]:
    """Parse a finnhub ``/company-news`` response (a list of headline dicts), newest ``limit``."""
    items: list[NewsItem] = []
    for row in payload[:limit]:
        try:
            items.append(
                NewsItem(
                    headline=str(row["headline"]),
                    source=str(row.get("source", "")),
                    url=str(row.get("url", "")),
                    datetime=int(row.get("datetime", 0)),
                    summary=str(row.get("summary", "")),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError(f"malformed finnhub news row: {exc}") from exc
    return items
