"""Stooq adapter: free end-of-day OHLCV for equities, ETFs, indices, commodities, and FX.

Stooq serves key-free daily CSV (``Date,Open,High,Low,Close,Volume``) for a broad cross-asset
universe — the cheapest way to widen ALPHA beyond yfinance/crypto to commodities and FX. The pure
``parse_stooq_csv`` validates every row through ``Bar`` (1a invariants) and is fully unit-tested
offline; the live ``fetch`` is network-gated.

Caveat (documented free-data limitation, like survivorship): Stooq prices are provider-adjusted, so
this adapter emits no separate corporate actions (``actions=[]``) — the PIT two-clock firewall has
nothing to apply. Use the yfinance adapter when point-in-time split/dividend handling matters.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
from pydantic import ValidationError

from alpha_core import Bar, DataError
from alpha_data.adapters.base import FetchResult

_VERSION = "1"
PARSER_VERSION = "1"
_REQUIRED = ("date", "open", "high", "low", "close")


def parse_stooq_csv(text: str, symbol: str) -> FetchResult:
    """Parse a Stooq daily CSV into a ``FetchResult`` (no corporate actions).

    Accepts the standard ``Date,Open,High,Low,Close[,Volume]`` header (case-insensitive); a missing
    or blank volume becomes ``0.0``. Each row is validated via ``Bar`` — fails loud (``DataError``)
    on a missing column, an unparseable number, an empty CSV, or any bar-invariant violation.
    """
    lines = [ln.strip().lstrip("﻿") for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise DataError(f"empty Stooq CSV for {symbol}")
    header = [h.strip().lower() for h in lines[0].split(",")]
    col = {name: header.index(name) for name in _REQUIRED if name in header}
    missing = [name for name in _REQUIRED if name not in col]
    if missing:
        raise DataError(f"Stooq CSV for {symbol} missing columns {missing}; header={header}")
    has_volume = "volume" in header
    vol_idx = header.index("volume") if has_volume else -1

    rows: list[dict[str, object]] = []
    for i, line in enumerate(lines[1:], start=1):
        fields = line.split(",")
        try:
            ts = datetime.fromisoformat(fields[col["date"]]).replace(tzinfo=UTC)
            o = float(fields[col["open"]])
            h = float(fields[col["high"]])
            low = float(fields[col["low"]])
            c = float(fields[col["close"]])
            raw_vol = fields[vol_idx] if has_volume and vol_idx < len(fields) else ""
            v = float(raw_vol) if raw_vol not in ("", "N/D") else 0.0
            Bar(symbol=symbol, ts=ts, open=o, high=h, low=low, close=c, volume=v)
        except (ValidationError, ValueError, IndexError) as exc:
            raise DataError(f"invalid Stooq row {i} for {symbol} ({line!r}): {exc}") from exc
        rows.append({"ts": ts, "open": o, "high": h, "low": low, "close": c, "volume": v})

    if not rows:
        raise DataError(f"Stooq CSV for {symbol} has a header but no data rows")
    bars = pl.DataFrame(
        rows,
        schema={
            "ts": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        },
    )
    return FetchResult(symbol=symbol, bars=bars, actions=[])


class StooqAdapter:
    """Live Stooq adapter: key-free daily CSV over HTTP.

    ``symbol`` is the Stooq ticker (e.g. ``spy.us``, ``^spx``, FX/commodity codes).
    """

    name = "stooq"
    version = _VERSION
    parser_version = PARSER_VERSION

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        import urllib.request  # noqa: PLC0415

        url = f"https://stooq.com/q/d/l/?s={symbol}&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 — fixed https host
            text = resp.read().decode("utf-8")
        if "No data" in text or not text.strip():
            raise DataError(f"Stooq returned no data for {symbol} {start}..{end}")
        return parse_stooq_csv(text, symbol)
