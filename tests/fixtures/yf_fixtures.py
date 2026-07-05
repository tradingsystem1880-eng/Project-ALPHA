"""Build a pandas DataFrame shaped like yfinance Ticker.history(auto_adjust=False)."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd


def yf_history(rows: list[dict[str, float]], dates: list[datetime]) -> pd.DataFrame:
    """rows: dicts with Open/High/Low/Close/Volume/Dividends/Stock Splits."""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates], name="Date")
    return pd.DataFrame(rows, index=idx)


def aapl_like() -> pd.DataFrame:
    """3 daily bars; 4:1 split and 0.82 dividend both on day 2 (2020-08-31).

    Mirrors what Yahoo actually serves with ``auto_adjust=False``: the OHLCV series is
    retroactively SPLIT-adjusted (the pre-split session shows 125, not the 500 that traded;
    its volume is shown multiplied by the ratio). The parser reconstructs the raw 500-scale
    prices from the in-window split event.
    """
    dates = [
        datetime(2020, 8, 28, tzinfo=UTC),
        datetime(2020, 8, 31, tzinfo=UTC),
        datetime(2020, 9, 1, tzinfo=UTC),
    ]
    rows = [
        {
            "Open": 125.0,  # traded 500.0; Yahoo shows it /4 after the 4:1 split
            "High": 126.25,
            "Low": 124.5,
            "Close": 125.0,
            "Volume": 4e6,  # traded 1e6 shares; Yahoo shows them x4
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        },
        {
            "Open": 127.0,
            "High": 131.0,
            "Low": 126.0,
            "Close": 129.0,
            "Volume": 2e6,
            "Dividends": 0.82,
            "Stock Splits": 4.0,
        },  # split ex-day: price post-split, no further adjustment
        {
            "Open": 132.0,
            "High": 134.0,
            "Low": 130.0,
            "Close": 133.0,
            "Volume": 1.5e6,
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        },
    ]
    return yf_history(rows, dates)
