"""yfinance adapter: raw OHLCV + splits/dividends. Parse is pure/offline; fetch is live."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime

import pandas as pd
import polars as pl
from pydantic import ValidationError

from alpha_core import ActionType, Bar, CorporateAction, DataError
from alpha_data.adapters.base import FetchResult

_VERSION = "1"
PARSER_VERSION = "1"
_OHLCV = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}


def _session_ts(ts: pd.Timestamp) -> datetime:
    """Daily bar → midnight UTC of the bar's LOCAL session date.

    A daily bar is date-keyed, not instant-keyed. yfinance's daily index is local-midnight;
    taking the local calendar date and stamping it at 00:00 UTC makes `ts.date()` the session
    date for ANY venue (US, Tokyo, Sydney) and keeps the corporate-action ex_date consistent.
    """
    d = ts.to_pydatetime().date()
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def parse_yfinance_history(df: pd.DataFrame, symbol: str) -> FetchResult:
    """Convert a yfinance history frame (auto_adjust=False, actions=True) to a FetchResult.

    Validates each row by constructing a Bar (1a invariants) — fails loud on bad vendor data.
    """
    missing = [c for c in (*_OHLCV, "Dividends", "Stock Splits") if c not in df.columns]
    if missing:
        raise DataError(f"yfinance frame for {symbol} missing columns: {missing}")

    bars_rows: list[dict[str, object]] = []
    actions: list[CorporateAction] = []
    for idx, row in df.iterrows():
        ts = _session_ts(pd.Timestamp(idx))  # type: ignore[arg-type]  # iterrows index is Any
        # fail-loud validation via the canonical Bar invariants
        try:
            Bar(
                symbol=symbol,
                ts=ts,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
        except ValidationError as exc:
            raise DataError(f"invalid bar from yfinance for {symbol} at {ts}: {exc}") from exc
        bars_rows.append(
            {
                "ts": ts,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            }
        )
        ex: date = ts.date()
        splits_val = float(row["Stock Splits"])
        if splits_val != 0.0 and not math.isnan(splits_val):
            actions.append(
                CorporateAction(
                    symbol=symbol,
                    action_type=ActionType.SPLIT,
                    ex_date=ex,
                    ratio=splits_val,
                )
            )
        div_val = float(row["Dividends"])
        if div_val != 0.0 and not math.isnan(div_val):
            actions.append(
                CorporateAction(
                    symbol=symbol,
                    action_type=ActionType.DIVIDEND,
                    ex_date=ex,
                    amount=div_val,
                )
            )
    bars = pl.DataFrame(
        bars_rows,
        schema={
            "ts": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        },
    )
    return FetchResult(symbol=symbol, bars=bars, actions=actions)


class YFinanceAdapter:
    """Live yfinance adapter. Network call isolated to `fetch`; logic lives in the parser."""

    name = "yfinance"
    version = _VERSION
    parser_version = PARSER_VERSION

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        import yfinance as yf  # type: ignore[import-untyped]  # yfinance has no stubs

        df = yf.Ticker(symbol).history(
            start=start.isoformat(), end=end.isoformat(), auto_adjust=False, actions=True
        )
        if df.empty:
            raise DataError(f"yfinance returned no data for {symbol} {start}..{end}")
        return parse_yfinance_history(df, symbol)
