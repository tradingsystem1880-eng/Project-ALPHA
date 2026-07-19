"""ccxt crypto adapter: raw daily OHLCV (UTC-native, no corporate actions)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

import polars as pl
from pydantic import ValidationError

from alpha_core import Bar, DataError
from alpha_data.adapters.base import FetchResult

_VERSION = "2"
PARSER_VERSION = "1"
_DAY_MS = 86_400_000
_PAGE_LIMIT = 300  # coinbase caps fetch_ohlcv at 300 candles/call; page forward past it
SUPPORTED_CCXT_EXCHANGES = ("coinbase", "binance")


def _paginate_ohlcv(
    fetch_page: Callable[[int], list[list[float]]],
    *,
    since_ms: int,
    end_ms: int,
    page_limit: int = _PAGE_LIMIT,
    step_ms: int = _DAY_MS,
) -> list[list[float]]:
    """Walk a page-capped ``fetch_ohlcv`` forward from ``since_ms`` until it covers ``end_ms``.

    A single ``fetch_ohlcv`` call returns at most ``page_limit`` candles, so for any range wider
    than that a lone call silently drops the tail. We advance the cursor past the last bar of each
    page (``last_ts + step_ms``) and re-request until we pass ``end_ms`` or the exchange stops
    yielding new data. The forward-progress guard (``last_ts <= prev_last``) ensures a broken
    exchange that ignores ``since`` terminates instead of looping forever. Returns bars ascending;
    page seams may overlap, so the caller dedupes by timestamp.
    """
    out: list[list[float]] = []
    cursor = since_ms
    prev_last: int | None = None
    while cursor <= end_ms:
        page = fetch_page(cursor)
        if not page:
            break
        last_ts = int(page[-1][0])
        if prev_last is not None and last_ts <= prev_last:
            break  # no forward progress — stop rather than loop forever
        out.extend(page)
        prev_last = last_ts
        cursor = last_ts + step_ms
    return out


def clip_ohlcv(
    raw: list[list[float]], *, since_ms: int, end_ms: int, now_ms: int
) -> list[list[float]]:
    """Clip candles to the requested window, dedupe page-seam overlaps, drop the live candle.

    Crypto trades 24/7, so the daily candle whose session contains ``now_ms`` is still forming -
    storing it would freeze a partial OHLCV row in the PIT store that silently disagrees with the
    finished candle on the next pull. Candles from the current (incomplete) UTC day are excluded;
    ascending, timestamp-deduped output.
    """
    today_start_ms = (now_ms // _DAY_MS) * _DAY_MS
    by_ts = {int(r[0]): r for r in raw if since_ms <= r[0] <= end_ms and r[0] < today_start_ms}
    return [by_ts[ts] for ts in sorted(by_ts)]


def parse_ccxt_ohlcv(ohlcv: list[list[float]], symbol: str) -> FetchResult:
    """Convert a ccxt fetch_ohlcv list ([ms, o, h, l, c, v], ...) to a FetchResult.

    Validates each row via Bar (1a invariants) — fails loud on bad data. No corporate actions.
    """
    rows: list[dict[str, object]] = []
    for i, row in enumerate(ohlcv):
        try:
            ms, o, h, low, c, v = row
            ts = datetime.fromtimestamp(ms / 1000, tz=UTC)
            Bar(
                symbol=symbol,
                ts=ts,
                open=float(o),
                high=float(h),
                low=float(low),
                close=float(c),
                volume=float(v),
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise DataError(f"invalid ccxt row {i} for {symbol} ({row!r}): {exc}") from exc
        rows.append(
            {
                "ts": ts,
                "open": float(o),
                "high": float(h),
                "low": float(low),
                "close": float(c),
                "volume": float(v),
            }
        )
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


class CCXTAdapter:
    """Live crypto adapter via ccxt. Defaults to a US-accessible, key-free exchange."""

    version = _VERSION
    parser_version = PARSER_VERSION

    def __init__(self, exchange: str = "coinbase") -> None:
        # coinbase: US-accessible, key-free public OHLCV, accepts the unified ``BTC/USD``,
        # and honours ``since`` for historical ranges (kraken's OHLC endpoint ignores
        # ``since`` and returns only a recent ~720-bar window, breaking dated fetches).
        if exchange not in SUPPORTED_CCXT_EXCHANGES:
            raise DataError(
                f"unsupported CCXT exchange {exchange!r}; known: {list(SUPPORTED_CCXT_EXCHANGES)}"
            )
        self._exchange = exchange
        # Venue-qualified source id is copied into immutable snapshot provenance.
        self.name = f"ccxt:{self._exchange}"

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        import ccxt  # type: ignore[import-untyped]  # ccxt has no stubs  # noqa: PLC0415

        # enableRateLimit: pagination issues one call per ~300-day page (≈9 for a 7y range);
        # rate-limiting keeps us a good public-API citizen and avoids throttling/bans.
        ex = getattr(ccxt, self._exchange)({"enableRateLimit": True})
        since = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp() * 1000)
        end_ms = int(datetime(end.year, end.month, end.day, tzinfo=UTC).timestamp() * 1000)

        raw = _paginate_ohlcv(
            lambda cur: ex.fetch_ohlcv(symbol, timeframe="1d", since=cur, limit=_PAGE_LIMIT),
            since_ms=since,
            end_ms=end_ms,
        )
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        clipped = clip_ohlcv(raw, since_ms=since, end_ms=end_ms, now_ms=now_ms)
        if not clipped:
            raise DataError(f"ccxt returned no data for {symbol} {start}..{end}")
        return parse_ccxt_ohlcv(clipped, symbol)
