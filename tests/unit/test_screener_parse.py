"""finnhub response parsers + key gating (all offline; the live fetch is @network)."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_screener import parse_news, parse_quote


def test_parse_quote() -> None:
    q = parse_quote(
        "AAPL", {"c": 150.0, "d": 1.5, "dp": 1.0, "h": 151, "l": 148, "o": 149, "pc": 148.5}
    )
    assert q.symbol == "AAPL"
    assert q.current == 150.0 and q.percent_change == 1.0 and q.prev_close == 148.5


def test_parse_quote_unknown_symbol_fails_loud() -> None:
    with pytest.raises(DataError):  # finnhub returns an all-zero body for an unknown symbol
        parse_quote("ZZZZ", {"c": 0, "d": None, "dp": None, "h": 0, "l": 0, "o": 0, "pc": 0})


def test_parse_quote_malformed_fails_loud() -> None:
    with pytest.raises(DataError):
        parse_quote("AAPL", {"c": "nope"})


def test_parse_news_limits_and_shapes() -> None:
    rows = [
        {"headline": f"H{i}", "source": "s", "url": "u", "datetime": i, "summary": "x"}
        for i in range(30)
    ]
    items = parse_news(rows, limit=5)
    assert len(items) == 5 and items[0].headline == "H0" and items[0].datetime == 0


def test_parse_news_malformed_fails_loud() -> None:
    with pytest.raises(DataError):
        parse_news([{"source": "s"}])  # missing headline


def test_finnhub_fails_loud_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from alpha_screener import finnhub as fh

    monkeypatch.delenv("ALPHA_FINNHUB_API_KEY", raising=False)
    with pytest.raises(DataError):
        fh.fetch_quote("AAPL")
