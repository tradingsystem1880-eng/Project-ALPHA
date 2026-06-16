"""ccxt crypto adapter: raw daily OHLCV (UTC-native, no corporate actions)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
from pydantic import ValidationError

from alpha_core import Bar, DataError
from alpha_data.adapters.base import FetchResult

_VERSION = "1"
PARSER_VERSION = "1"


def parse_ccxt_ohlcv(ohlcv: list[list[float]], symbol: str) -> FetchResult:
    """Convert a ccxt fetch_ohlcv list ([ms, o, h, l, c, v], ...) to a FetchResult.

    Validates each row via Bar (1a invariants) — fails loud on bad data. No corporate actions.
    """
    rows: list[dict[str, object]] = []
    for ms, o, h, low, c, v in ohlcv:
        ts = datetime.fromtimestamp(ms / 1000, tz=UTC)
        try:
            Bar(
                symbol=symbol,
                ts=ts,
                open=float(o),
                high=float(h),
                low=float(low),
                close=float(c),
                volume=float(v),
            )
        except ValidationError as exc:
            raise DataError(f"invalid ccxt bar for {symbol} at {ts}: {exc}") from exc
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

    name = "ccxt"
    version = _VERSION
    parser_version = PARSER_VERSION

    def __init__(self, exchange: str = "kraken") -> None:
        self._exchange = exchange

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        import ccxt  # type: ignore[import-untyped]  # ccxt has no stubs  # noqa: PLC0415

        ex = getattr(ccxt, self._exchange)()
        since = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp() * 1000)
        raw = ex.fetch_ohlcv(symbol, timeframe="1d", since=since)
        end_ms = int(datetime(end.year, end.month, end.day, tzinfo=UTC).timestamp() * 1000)
        raw = [r for r in raw if r[0] <= end_ms]
        if not raw:
            raise DataError(f"ccxt returned no data for {symbol} {start}..{end}")
        return parse_ccxt_ohlcv(raw, symbol)
