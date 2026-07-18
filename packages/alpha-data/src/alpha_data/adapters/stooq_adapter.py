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

# Stooq blocks the bare ``Python-urllib`` user-agent (HTTP 404) and, for fresh clients, serves a
# SHA-256 proof-of-work "verify your browser" gate before releasing the CSV. A browser UA + solving
# that gate is the documented browser flow; we still fail loud on its per-IP "Access denied" quota.
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_CHALLENGE_MARKER = "verify your browser"
_POW_MAX_ITERS = 8_000_000  # difficulty-4 needs ~65k hashes; this is a runaway backstop


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


def _solve_pow(challenge: str, difficulty: int) -> str:
    """Solve Stooq's browser-verification proof-of-work.

    Find the smallest ``n`` such that ``hex(sha256(challenge + n))`` has ``difficulty`` leading
    zeros — exactly what Stooq's ``<noscript>This site requires JavaScript to verify your
    browser</noscript>`` page asks any JS-capable client to do. Difficulty 4 ≈ 65k hashes.
    """
    import hashlib  # noqa: PLC0415

    target = "0" * difficulty
    for n in range(_POW_MAX_ITERS):
        if hashlib.sha256(f"{challenge}{n}".encode()).hexdigest().startswith(target):
            return str(n)
    raise DataError(
        f"Stooq proof-of-work unsolved after {_POW_MAX_ITERS} iterations (difficulty={difficulty})"
    )


def _fetch_stooq_text(url: str) -> str:
    """GET a Stooq CSV URL, transparently clearing the JS browser-verification gate if served.

    Sends a browser user-agent (the bare ``Python-urllib`` UA 404s) and, if Stooq returns its
    proof-of-work page instead of CSV, solves it like a browser would — POST ``/__verify`` then
    reload carrying the auth cookie. Returns the raw response body; the caller decides whether the
    body is CSV, "No data", or a still-blocked response and fails loud accordingly.
    """
    import http.cookiejar  # noqa: PLC0415
    import re  # noqa: PLC0415
    import urllib.error  # noqa: PLC0415
    import urllib.parse  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(target: str, data: bytes | None = None, *, form: bool = False) -> str:
        headers = {"User-Agent": _UA, "Accept": "text/csv,text/plain,*/*"}
        if form:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Origin"] = "https://stooq.com"
            headers["Referer"] = url
        req = urllib.request.Request(target, data=data, headers=headers)
        try:
            with opener.open(req, timeout=30) as resp:  # noqa: S310 — fixed https host
                body: str = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raise DataError(
                f"Stooq anti-bot/transport rejected the request with HTTP {exc.code}; "
                "use --source yfinance for equities/ETFs"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise DataError(f"Stooq transport failed: {exc}") from exc
        return body

    text = _get(url)
    challenge = re.search(r'c="([^"]+)"', text)
    if challenge is not None and _CHALLENGE_MARKER in text.lower():
        diff_match = re.search(r"\bd=(\d+)", text)
        nonce = _solve_pow(challenge.group(1), int(diff_match.group(1)) if diff_match else 4)
        verify = urllib.parse.urlencode({"c": challenge.group(1), "n": nonce}).encode()
        _get("https://stooq.com/__verify", data=verify, form=True)
        text = _get(url)  # reload now carries the auth cookie set by /__verify
    return text


def _csv_or_raise(text: str, symbol: str, window: str) -> FetchResult:
    """Turn a raw Stooq response body into a ``FetchResult``, failing loud if it isn't CSV.

    Stooq gates its free CSV behind an anti-bot challenge + per-IP download quota; a blocked client
    gets an empty body, a bare ``Access denied``, a leftover proof-of-work page, or HTML. Rather
    than feed non-CSV to the parser, raise a clear ``DataError``. Pure and offline-testable — the
    network lives in ``_fetch_stooq_text``.
    """
    stripped = text.strip()
    if not stripped or "No data" in text:
        raise DataError(f"Stooq returned no data for {symbol} {window}")
    if stripped == "Access denied" or _CHALLENGE_MARKER in text.lower() or stripped.startswith("<"):
        raise DataError(
            f"Stooq withheld the free CSV for {symbol} ({stripped[:40]!r}): the /q/d/l/ endpoint "
            "is gated behind an anti-bot challenge + per-IP download quota. "
            "Use --source yfinance for equities/ETFs."
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
        import urllib.parse  # noqa: PLC0415

        quoted = urllib.parse.quote(symbol, safe="^.")  # ^spx etc. stay literal; &/? cannot inject
        url = f"https://stooq.com/q/d/l/?s={quoted}&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
        return _csv_or_raise(_fetch_stooq_text(url), symbol, f"{start}..{end}")
