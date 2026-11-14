"""Stooq adapter: free end-of-day OHLCV for equities, ETFs, indices, commodities, and FX.

Stooq serves key-free daily CSV (``Date,Open,High,Low,Close,Volume``) for a broad cross-asset
universe. The adapter never solves or bypasses Stooq checks; it fails loud instead. The pure
``parse_stooq_csv`` validates every row through ``Bar`` (1a invariants) and is fully unit-tested
offline; the live ``fetch`` is network-gated.

Caveat (documented free-data limitation, like survivorship): Stooq prices are provider-adjusted, so
this adapter emits no separate corporate actions (``actions=[]``) — the PIT two-clock firewall has
nothing to apply.
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

# Identify ALPHA as a generic client; never solve or bypass Stooq checks, and fail loud instead.
_UA = "Project-ALPHA/1.0"
_CHALLENGE_MARKER = "verify your browser"


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


def _fetch_stooq_text(url: str) -> str:
    """GET once as a generic client, refusing browser verification rather than bypassing it.

    Return the raw body unless Stooq asks for browser verification. The caller classifies other
    blocked or non-CSV responses. HTTP errors and interrupted reads fail loud as ``DataError``.
    """
    import http.client
    import urllib.error
    import urllib.request

    opener = urllib.request.build_opener()
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA, "Accept": "text/csv,text/plain,*/*"}
    )
    try:
        with opener.open(req, timeout=30) as resp:
            body: str = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise DataError(
            f"Stooq anti-bot/transport rejected the request with HTTP {exc.code}"
        ) from exc
    except (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        http.client.IncompleteRead,
    ) as exc:
        raise DataError(f"Stooq transport failed: {exc}") from exc
    if _CHALLENGE_MARKER in body.lower():
        raise DataError(
            "Stooq asked for a browser verification check (anti-bot); "
            "ALPHA does not get past bot checks, so this download is refused; "
            "data already stored stays readable."
        )
    return body


def _csv_or_raise(text: str, symbol: str, window: str) -> FetchResult:
    """Turn a raw Stooq response body into a ``FetchResult``, failing loud if it isn't CSV.

    Stooq gates its free CSV behind an anti-bot challenge + per-IP download quota; a blocked client
    gets an empty body, a bare ``Access denied``, a leftover proof-of-work page, or HTML. Rather
    than feed non-CSV to the parser, raise a clear ``DataError``. Pure and offline-testable — the
    network lives in ``_fetch_stooq_text``.
    """
    stripped = text.strip()
    if not stripped or "No data" in text:
        raise DataError(f"Stooq returned no data for {symbol} {window} (possible anti-bot refusal)")
    if stripped == "Access denied" or _CHALLENGE_MARKER in text.lower() or stripped.startswith("<"):
        raise DataError(
            f"Stooq withheld the free CSV for {symbol} ({stripped[:40]!r}): the /q/d/l/ endpoint "
            "is gated behind an anti-bot challenge + per-IP download quota."
        )
    return parse_stooq_csv(text, symbol)


class StooqAdapter:
    """Live Stooq adapter: key-free daily CSV over HTTP.

    ``symbol`` is the Stooq ticker (e.g. ``spy.us``, ``^spx``, FX/commodity codes).
    """

    name = "stooq"
    version = _VERSION
    parser_version = PARSER_VERSION

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        import urllib.parse

        quoted = urllib.parse.quote(symbol, safe="^.")  # ^spx etc. stay literal; &/? cannot inject
        url = f"https://stooq.com/q/d/l/?s={quoted}&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
        return _csv_or_raise(_fetch_stooq_text(url), symbol, f"{start}..{end}")
