"""Build a pandas DataFrame shaped like yfinance Ticker.history(auto_adjust=False)."""
from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd


def yf_history(rows: list[dict[str, float]], dates: list[datetime]) -> pd.DataFrame:
    """rows: dicts with Open/High/Low/Close/Volume/Dividends/Stock Splits."""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates], name="Date")
    return pd.DataFrame(rows, index=idx)


def aapl_like() -> pd.DataFrame:
    """3 daily bars; a 4:1 split on day 3 and a 0.82 dividend on day 2. Raw (unadjusted) prices."""
    dates = [datetime(2020, 8, 28, tzinfo=UTC), datetime(2020, 8, 31, tzinfo=UTC),
             datetime(2020, 9, 1, tzinfo=UTC)]
    rows = [
        {"Open": 500.0, "High": 505.0, "Low": 498.0, "Close": 500.0, "Volume": 1e6,
         "Dividends": 0.0, "Stock Splits": 0.0},
        {"Open": 127.0, "High": 131.0, "Low": 126.0, "Close": 129.0, "Volume": 2e6,
         "Dividends": 0.82, "Stock Splits": 4.0},  # split ex-day: price already post-split
        {"Open": 132.0, "High": 134.0, "Low": 130.0, "Close": 133.0, "Volume": 1.5e6,
         "Dividends": 0.0, "Stock Splits": 0.0},
    ]
    return yf_history(rows, dates)
