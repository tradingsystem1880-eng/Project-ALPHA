"""Pure Binance public archive/REST parsing and reconciliation."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from typing import Final, Literal

import polars as pl

from alpha_core import DataError

type BinanceArchiveMarket = Literal["spot", "um", "cm"]
type BinanceKlineSource = Literal["archive_csv", "rest_json"]
type WireScalar = str | int | float

_COLUMNS: Final = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "base_volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
)
_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")


def _timestamp(raw: WireScalar) -> datetime:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise DataError("Binance kline timestamp is invalid") from exc
    divisor = 1_000_000 if value >= 1_000_000_000_000_000 else 1_000
    try:
        return datetime.fromtimestamp(value / divisor, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise DataError("Binance kline timestamp is outside the supported range") from exc


def _rows(payload: bytes, source: BinanceKlineSource) -> list[list[WireScalar]]:
    try:
        if source == "archive_csv":
            return [list(row) for row in csv.reader(io.StringIO(payload.decode("utf-8"))) if row]
        if source == "rest_json":
            raw = json.loads(payload)
            if not isinstance(raw, list):
                raise DataError("Binance REST kline response must be a list")
            rows: list[list[WireScalar]] = []
            for row in raw:
                if not isinstance(row, list) or any(
                    not isinstance(item, str | int | float) for item in row
                ):
                    raise DataError("Binance REST kline row contains an unsupported value")
                rows.append(row)
            return rows
    except (UnicodeDecodeError, csv.Error, json.JSONDecodeError) as exc:
        raise DataError("Binance kline response is malformed") from exc
    raise DataError(f"unsupported Binance kline source {source!r}")


def parse_binance_klines(payload: bytes, *, source: BinanceKlineSource) -> pl.DataFrame:
    """Parse exact archive/REST bytes without discarding provider-native fields."""
    parsed: list[dict[str, object]] = []
    for row in _rows(payload, source):
        if len(row) < 11:
            raise DataError("Binance kline row has fewer than eleven fields")
        try:
            open_price = float(row[1])
            high = float(row[2])
            low = float(row[3])
            close = float(row[4])
            base_volume = float(row[5])
            quote_volume = float(row[7])
            trade_count = int(row[8])
            values = {
                "open_time": _timestamp(row[0]),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "base_volume": base_volume,
                "close_time": _timestamp(row[6]),
                "quote_volume": quote_volume,
                "trade_count": trade_count,
                "taker_buy_base_volume": float(row[9]),
                "taker_buy_quote_volume": float(row[10]),
            }
        except (TypeError, ValueError) as exc:
            raise DataError("Binance kline row contains an invalid numeric field") from exc
        if not (low <= min(open_price, close) and high >= max(open_price, close) and high >= low):
            raise DataError("Binance kline violates OHLC invariants")
        if base_volume < 0 or quote_volume < 0 or trade_count < 0:
            raise DataError("Binance kline volumes and trade count must be non-negative")
        parsed.append(values)
    if not parsed:
        raise DataError("Binance kline response is empty")
    frame = pl.DataFrame(parsed).select(_COLUMNS).sort("open_time")
    if frame["open_time"].n_unique() != frame.height:
        raise DataError("Binance kline response contains duplicate open times")
    return frame


def verify_archive_checksum(payload: bytes, checksum_payload: bytes) -> None:
    """Verify one official SHA-256 checksum sidecar."""
    try:
        expected = checksum_payload.decode("ascii").strip().split()[0].lower()
    except (UnicodeDecodeError, IndexError) as exc:
        raise DataError("Binance archive checksum sidecar is malformed") from exc
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise DataError("Binance archive checksum sidecar is malformed")
    if hashlib.sha256(payload).hexdigest() != expected:
        raise DataError("Binance archive checksum does not match exact bytes")


def archive_url(
    market: BinanceArchiveMarket, family: str, symbol: str, interval: str, period: str
) -> str:
    """Construct a closed official monthly archive URL."""
    if market not in {"spot", "um", "cm"}:
        raise DataError(f"unsupported Binance archive market {market!r}")
    for value, label in (
        (family, "family"),
        (symbol, "symbol"),
        (interval, "interval"),
        (period, "period"),
    ):
        if _SAFE.fullmatch(value) is None:
            raise DataError(f"invalid Binance archive {label}")
    root = "spot" if market == "spot" else f"futures/{market}"
    name = f"{symbol}-{interval}-{period}.zip"
    return f"https://data.binance.vision/data/{root}/monthly/{family}/{symbol}/{interval}/{name}"


def reconcile_archive_tail(archive: pl.DataFrame, tail: pl.DataFrame) -> pl.DataFrame:
    """Join a REST tail only when every overlapping provider value is identical."""
    if archive.columns != list(_COLUMNS) or tail.columns != list(_COLUMNS):
        raise DataError("Binance archive/tail schema does not match the kline contract")
    archive_rows = {row["open_time"]: row for row in archive.iter_rows(named=True)}
    for row in tail.iter_rows(named=True):
        prior = archive_rows.get(row["open_time"])
        if prior is not None and prior != row:
            raise DataError("Binance REST tail conflicts with archive overlap")
        archive_rows[row["open_time"]] = row
    return pl.DataFrame([archive_rows[key] for key in sorted(archive_rows)]).select(_COLUMNS)


def point_in_time_liquid_universe(
    observations: pl.DataFrame, *, as_of: datetime, limit: int
) -> tuple[str, ...]:
    """Select the top symbols from the last fully available session before ``as_of``."""
    required = {"session", "symbol", "quote_volume"}
    if not required.issubset(observations.columns):
        raise DataError("Binance liquidity observations have an invalid schema")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise DataError("Binance liquidity as_of must be timezone-aware")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 250:
        raise DataError("Binance liquidity limit must be between 1 and 250")
    known = observations.filter(pl.col("session") < as_of.astimezone(UTC))
    if known.is_empty():
        raise DataError("no Binance liquidity session is available before as_of")
    latest = known["session"].max()
    ranked = (
        known.filter(pl.col("session") == latest)
        .sort(["quote_volume", "symbol"], descending=[True, False])
        .head(limit)
    )
    if ranked["symbol"].n_unique() != ranked.height:
        raise DataError("Binance liquidity session contains duplicate symbols")
    return tuple(ranked["symbol"].to_list())
