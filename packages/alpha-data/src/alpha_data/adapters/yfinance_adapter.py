"""yfinance adapter: raw OHLCV + splits/dividends. Parse is pure/offline; fetch is live.

Vendor semantics (verified against yfinance's own ``utils.auto_adjust``/``back_adjust`` sources):
Yahoo's chart OHLCV is **retroactively split-adjusted** — ``auto_adjust=False`` only skips the
dividend adjustment (which lives in ``Adj Close``). The store's contract is RAW unadjusted rows
(the PIT reader applies splits itself, knowledge-gated, spec §6.1), so the parser reconstructs raw
prices by multiplying each bar back by the ratios of every in-window split *after* it (volume is
divided; dividend amounts are scaled the same way). Splits after the fetched window are invisible
and leave a uniform scale on the whole series — harmless to returns, signals, and sizing.

A cross-ex-date discontinuity check fails loud if the vendor's convention ever drifts: after
reconstruction, the overnight move across each split must show the mechanical ~1/ratio drop.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime

import pandas as pd
import polars as pl
from pydantic import ValidationError

from alpha_core import ActionType, Bar, CorporateAction, DataError
from alpha_data.adapters.base import FetchResult

_VERSION = "1"
PARSER_VERSION = "2"  # 2: reconstruct raw prices from Yahoo's split-adjusted series
_OHLCV = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
# Splits smaller than this (log-space) are indistinguishable from ordinary overnight moves, so the
# discontinuity check only runs for ratios outside [1/1.25, 1.25].
_MIN_DETECTABLE_LOG_RATIO = math.log(1.25)


def _session_ts(ts: pd.Timestamp) -> datetime:
    """Daily bar → midnight UTC of the bar's LOCAL session date.

    A daily bar is date-keyed, not instant-keyed. yfinance's daily index is local-midnight;
    taking the local calendar date and stamping it at 00:00 UTC makes `ts.date()` the session
    date for ANY venue (US, Tokyo, Sydney) and keeps the corporate-action ex_date consistent.
    """
    d = ts.to_pydatetime().date()
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def _unadjust_factor(session: date, splits: list[tuple[date, float]]) -> float:
    """Product of ratios of every in-window split strictly after ``session`` (1.0 if none).

    Yahoo divides all history before a split's ex-date by its ratio; multiplying back by this
    factor restores the price actually traded on ``session`` (volume divides by it).
    """
    factor = 1.0
    for ex, ratio in splits:
        if ex > session:
            factor *= ratio
    return factor


def _check_split_discontinuity(
    rows: list[dict[str, object]], splits: list[tuple[date, float]], symbol: str
) -> None:
    """Fail loud unless each reconstructed split shows its mechanical ex-date price drop.

    After un-adjustment the close before ex and the open on/after ex must differ by roughly the
    split ratio. If they do not, the vendor did not deliver split-adjusted prices (their semantics
    drifted, or the series was already raw) and silently storing it would corrupt the PIT store.
    Ratios within ~25% of 1 are skipped — too small to separate from a real overnight move.
    """
    for ex, ratio in splits:
        expected = math.log(ratio)
        if abs(expected) < _MIN_DETECTABLE_LOG_RATIO:
            continue
        prev = next((r for r in reversed(rows) if _row_date(r) < ex), None)
        after = next((r for r in rows if _row_date(r) >= ex), None)
        if prev is None or after is None:
            continue  # split sits at the window edge — nothing to compare
        step = math.log(float(prev["close"]) / float(after["open"]))  # type: ignore[arg-type]
        if abs(step - expected) > abs(expected) / 2.0:
            raise DataError(
                f"yfinance split reconstruction failed for {symbol}: the {ratio:g}:1 split on "
                f"{ex} shows a close->open factor of {math.exp(step):.3f} instead of ~{ratio:g}. "
                "Yahoo's split-adjustment convention appears to have changed - refusing to store "
                "prices of unknown adjustment state."
            )


def _row_date(row: dict[str, object]) -> date:
    ts = row["ts"]
    assert isinstance(ts, datetime)  # rows are built locally; ts is always a datetime
    return ts.date()


def parse_yfinance_history(df: pd.DataFrame, symbol: str) -> FetchResult:
    """Convert a yfinance history frame (auto_adjust=False, actions=True) to a raw FetchResult.

    Yahoo serves split-adjusted OHLCV; this reconstructs the RAW series (see module docstring),
    validates each reconstructed row by constructing a Bar (1a invariants), and fails loud on bad
    vendor data or on a split whose mechanical ex-date discontinuity is missing after
    reconstruction.
    """
    missing = [c for c in (*_OHLCV, "Dividends", "Stock Splits") if c not in df.columns]
    if missing:
        raise DataError(f"yfinance frame for {symbol} missing columns: {missing}")

    # Pass 1 - collect the vendor rows and the in-window split/dividend events.
    raw_rows: list[dict[str, object]] = []
    splits: list[tuple[date, float]] = []
    dividends: list[tuple[date, float]] = []
    for idx, row in df.iterrows():
        ts = _session_ts(pd.Timestamp(idx))  # type: ignore[arg-type]  # iterrows index is Any
        raw_rows.append(
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
            splits.append((ex, splits_val))
        div_val = float(row["Dividends"])
        if div_val != 0.0 and not math.isnan(div_val):
            dividends.append((ex, div_val))

    # Pass 2 - undo Yahoo's retroactive split adjustment, then validate the raw rows.
    for r in raw_rows:
        factor = _unadjust_factor(_row_date(r), splits)
        if factor != 1.0:
            for col in ("open", "high", "low", "close"):
                r[col] = float(r[col]) * factor  # type: ignore[arg-type]
            r["volume"] = float(r["volume"]) / factor  # type: ignore[arg-type]
    _check_split_discontinuity(raw_rows, splits, symbol)
    for r in raw_rows:
        try:
            Bar(symbol=symbol, **r)
        except ValidationError as exc:
            raise DataError(f"invalid bar from yfinance for {symbol} at {r['ts']}: {exc}") from exc

    actions: list[CorporateAction] = [
        CorporateAction(symbol=symbol, action_type=ActionType.SPLIT, ex_date=ex, ratio=ratio)
        for ex, ratio in splits
    ]
    # Dividend amounts arrive in the same split-adjusted per-share basis; scale them back too so
    # `amount` is cash per share as traded on the ex-date.
    actions += [
        CorporateAction(
            symbol=symbol,
            action_type=ActionType.DIVIDEND,
            ex_date=ex,
            amount=amount * _unadjust_factor(ex, splits),
        )
        for ex, amount in dividends
    ]
    actions.sort(key=lambda a: (a.ex_date, a.action_type.value))

    bars = pl.DataFrame(
        raw_rows,
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
