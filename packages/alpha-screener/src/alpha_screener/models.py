"""Typed screener domain values (frozen)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    """A real-time-ish quote snapshot for one symbol."""

    symbol: str
    current: float
    change: float
    percent_change: float
    high: float
    low: float
    open: float
    prev_close: float


@dataclass(frozen=True)
class NewsItem:
    """One company-news headline."""

    headline: str
    source: str
    url: str
    datetime: int  # epoch seconds
    summary: str
