"""Pure Binance public archive/REST parsing and reconciliation."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from datetime import UTC, datetime
from typing import Final, Literal

import polars as pl

from alpha_core import DataError

type BinanceArchiveMarket = Literal["spot", "um", "cm"]
type BinanceKlineSource = Literal["archive_csv", "rest_json"]
type BinanceArchiveFamily = Literal["klines", "trades", "aggTrades"]
type BinanceCategory = Literal["spot", "linear", "inverse"]
type BinancePublicResource = Literal["depth", "klines"]
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
_PUBLIC_API_ROOTS: Final = {
    "spot": "https://api.binance.com/api/v3",
    "linear": "https://fapi.binance.com/fapi/v1",
    "inverse": "https://dapi.binance.com/dapi/v1",
}


def _boolean(value: WireScalar, *, label: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise DataError(f"Binance {label} boolean is invalid")


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


def _optional_timestamp(raw: object, *, label: str) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, str | int | float):
        raise DataError(f"Binance {label} timestamp is invalid")
    return _timestamp(raw)


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


def parse_binance_trades(payload: bytes) -> pl.DataFrame:
    """Parse spot/futures trade archives without erasing venue-specific quote/base quantity."""
    try:
        rows = [row for row in csv.reader(io.StringIO(payload.decode("utf-8"))) if row]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise DataError("Binance trade archive is malformed") from exc
    parsed: list[dict[str, object]] = []
    for row in rows:
        if len(row) not in {6, 7}:
            raise DataError("Binance trade row must contain six or seven fields")
        try:
            parsed.append(
                {
                    "trade_id": int(row[0]),
                    "price": float(row[1]),
                    "quantity": float(row[2]),
                    "quote_quantity": float(row[3]),
                    "timestamp": _timestamp(row[4]),
                    "buyer_is_maker": _boolean(row[5], label="trade maker"),
                    "best_match": _boolean(row[6], label="trade best-match")
                    if len(row) == 7
                    else None,
                }
            )
        except ValueError as exc:
            raise DataError("Binance trade row contains an invalid numeric field") from exc
    if not parsed:
        raise DataError("Binance trade archive is empty")
    frame = pl.DataFrame(parsed).sort(["timestamp", "trade_id"])
    if frame["trade_id"].n_unique() != frame.height:
        raise DataError("Binance trade archive contains duplicate trade ids")
    if frame.filter(
        (pl.col("price") <= 0) | (pl.col("quantity") < 0) | (pl.col("quote_quantity") < 0)
    ).height:
        raise DataError("Binance trade prices and quantities violate bounds")
    return frame


def parse_binance_aggregate_trades(payload: bytes) -> pl.DataFrame:
    """Parse spot/futures aggregate trades with their exact component-id interval."""
    try:
        rows = [row for row in csv.reader(io.StringIO(payload.decode("utf-8"))) if row]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise DataError("Binance aggregate-trade archive is malformed") from exc
    parsed: list[dict[str, object]] = []
    for row in rows:
        if len(row) not in {7, 8}:
            raise DataError("Binance aggregate-trade row must contain seven or eight fields")
        try:
            first_id, last_id = int(row[3]), int(row[4])
            if last_id < first_id:
                raise DataError("Binance aggregate-trade component ids are inverted")
            parsed.append(
                {
                    "aggregate_trade_id": int(row[0]),
                    "price": float(row[1]),
                    "quantity": float(row[2]),
                    "first_trade_id": first_id,
                    "last_trade_id": last_id,
                    "timestamp": _timestamp(row[5]),
                    "buyer_is_maker": _boolean(row[6], label="aggregate-trade maker"),
                    "best_match": _boolean(row[7], label="aggregate-trade best-match")
                    if len(row) == 8
                    else None,
                }
            )
        except ValueError as exc:
            raise DataError("Binance aggregate-trade row has an invalid numeric field") from exc
    if not parsed:
        raise DataError("Binance aggregate-trade archive is empty")
    frame = pl.DataFrame(parsed).sort(["timestamp", "aggregate_trade_id"])
    if frame["aggregate_trade_id"].n_unique() != frame.height:
        raise DataError("Binance aggregate-trade archive contains duplicate ids")
    if frame.filter((pl.col("price") <= 0) | (pl.col("quantity") < 0)).height:
        raise DataError("Binance aggregate-trade price or quantity violates bounds")
    return frame


def parse_binance_book_snapshot(
    payload: bytes,
    *,
    symbol: str,
    category: BinanceCategory,
    fetched_at: datetime,
) -> pl.DataFrame:
    """Parse one bounded REST depth snapshot while preserving venue ordering and update ids."""
    if _SAFE.fullmatch(symbol) is None or category not in {"spot", "linear", "inverse"}:
        raise DataError("Binance book snapshot identity is invalid")
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise DataError("Binance book snapshot fetch time must be timezone-aware")
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("Binance book snapshot response is malformed") from exc
    if not isinstance(raw, dict):
        raise DataError("Binance book snapshot response must be an object")
    update_id = raw.get("lastUpdateId")
    if isinstance(update_id, bool) or not isinstance(update_id, int) or update_id < 0:
        raise DataError("Binance book snapshot update id is invalid")
    provider_event_time = _optional_timestamp(raw.get("E"), label="book event")
    transaction_time = _optional_timestamp(raw.get("T"), label="book transaction")
    observed_at = fetched_at.astimezone(UTC)
    parsed: list[dict[str, object]] = []
    prices_by_side: dict[str, list[float]] = {"bid": [], "ask": []}
    for side, field in (("bid", "bids"), ("ask", "asks")):
        levels = raw.get(field)
        if not isinstance(levels, list):
            raise DataError(f"Binance book snapshot {field} are invalid")
        for level, item in enumerate(levels):
            if not isinstance(item, list) or len(item) != 2:
                raise DataError("Binance book snapshot level is invalid")
            try:
                price, quantity = float(item[0]), float(item[1])
            except (TypeError, ValueError) as exc:
                raise DataError("Binance book snapshot level is invalid") from exc
            if (
                not math.isfinite(price)
                or not math.isfinite(quantity)
                or price <= 0
                or quantity <= 0
            ):
                raise DataError("Binance book snapshot price or quantity violates bounds")
            prices_by_side[side].append(price)
            parsed.append(
                {
                    "observed_at": observed_at,
                    "provider_event_time": provider_event_time,
                    "transaction_time": transaction_time,
                    "symbol": symbol,
                    "category": category,
                    "update_id": update_id,
                    "side": side,
                    "level": level,
                    "price": price,
                    "quantity": quantity,
                }
            )
    bids, asks = prices_by_side["bid"], prices_by_side["ask"]
    if not bids or not asks:
        raise DataError("Binance book snapshot is empty")
    if len(set(bids)) != len(bids) or len(set(asks)) != len(asks):
        raise DataError("Binance book snapshot contains duplicate prices")
    if any(right >= left for left, right in zip(bids, bids[1:], strict=False)):
        raise DataError("Binance book snapshot bids are not strictly descending")
    if any(right <= left for left, right in zip(asks, asks[1:], strict=False)):
        raise DataError("Binance book snapshot asks are not strictly ascending")
    if bids[0] >= asks[0]:
        raise DataError("Binance book snapshot is crossed")
    return pl.DataFrame(parsed)


def parse_binance_archive_zip(
    payload: bytes, *, family: BinanceArchiveFamily = "klines"
) -> pl.DataFrame:
    """Extract one bounded flat official CSV member and parse it without path writes."""
    if not isinstance(payload, bytes) or not payload or len(payload) > 512 * 1024 * 1024:
        raise DataError("Binance archive ZIP exceeds the compressed byte limit")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) != 1:
                raise DataError("Binance archive ZIP must contain exactly one CSV member")
            member = members[0]
            if (
                "/" in member.filename
                or "\\" in member.filename
                or not member.filename.endswith(".csv")
            ):
                raise DataError("Binance archive ZIP member path is invalid")
            if member.flag_bits & 0x1 or member.file_size > 1024 * 1024 * 1024:
                raise DataError("Binance archive ZIP member exceeds extraction bounds")
            csv_payload = archive.read(member)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise DataError("Binance archive ZIP is malformed") from exc
    if family == "klines":
        return parse_binance_klines(csv_payload, source="archive_csv")
    if family == "trades":
        return parse_binance_trades(csv_payload)
    if family == "aggTrades":
        return parse_binance_aggregate_trades(csv_payload)
    raise DataError("Binance archive family is invalid")


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
    for value, label in ((family, "family"), (symbol, "symbol"), (period, "period")):
        if _SAFE.fullmatch(value) is None:
            raise DataError(f"invalid Binance archive {label}")
    if family not in {"klines", "trades", "aggTrades"}:
        raise DataError("unsupported Binance archive family")
    root = "spot" if market == "spot" else f"futures/{market}"
    if family == "klines":
        if _SAFE.fullmatch(interval) is None:
            raise DataError("invalid Binance archive interval")
        name = f"{symbol}-{interval}-{period}.zip"
        return (
            f"https://data.binance.vision/data/{root}/monthly/{family}/{symbol}/{interval}/{name}"
        )
    if interval:
        raise DataError("Binance trade archives do not accept an interval")
    name = f"{symbol}-{family}-{period}.zip"
    return f"https://data.binance.vision/data/{root}/monthly/{family}/{symbol}/{name}"


def binance_public_api_url(
    category: BinanceCategory,
    resource: BinancePublicResource,
    params: dict[str, str | int],
) -> str:
    """Build one public market-data URL from a closed endpoint and parameter contract."""
    if category not in _PUBLIC_API_ROOTS or resource not in {"depth", "klines"}:
        raise DataError("Binance public API endpoint is invalid")
    allowed = (
        {"symbol", "limit"}
        if resource == "depth"
        else {"symbol", "interval", "limit", "startTime", "endTime"}
    )
    if set(params) - allowed or not {"symbol", "limit"}.issubset(params):
        raise DataError("Binance public API parameter contract is invalid")
    symbol, limit = params["symbol"], params["limit"]
    if not isinstance(symbol, str) or _SAFE.fullmatch(symbol) is None:
        raise DataError("Binance public API symbol is invalid")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1_000:
        raise DataError("Binance public API limit must be between 1 and 1000")
    if resource == "klines":
        interval = params.get("interval")
        if interval not in {"1m", "5m", "1h", "1d"}:
            raise DataError("Binance public API kline interval is invalid")
        start, end = params.get("startTime"), params.get("endTime")
        for value in (start, end):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise DataError("Binance public API time range is invalid")
        if isinstance(start, int) and isinstance(end, int) and end < start:
            raise DataError("Binance public API time range is inverted")
    from urllib.parse import urlencode  # noqa: PLC0415

    query = urlencode(sorted(params.items()))
    return f"{_PUBLIC_API_ROOTS[category]}/{resource}?{query}"


def fetch_binance_public_api(url: str, *, timeout_seconds: int = 30) -> bytes:
    """Fetch one bounded keyless Binance market-data response with redirect revalidation."""
    if not 1 <= timeout_seconds <= 60:
        raise DataError("Binance public API timeout must be between 1 and 60 seconds")
    allowed_prefixes = tuple(f"{root}/" for root in _PUBLIC_API_ROOTS.values())
    if not url.startswith(allowed_prefixes):
        raise DataError("Binance public API host is invalid")
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    request = urllib.request.Request(url, headers={"User-Agent": "Project-ALPHA/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            if not str(response.geturl()).startswith(allowed_prefixes):
                raise DataError("Binance public API redirect host is invalid")
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0]
            if content_type != "application/json":
                raise DataError("Binance public API response MIME is invalid")
            payload = bytes(response.read(16 * 1024 * 1024 + 1))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise DataError("Binance public API request failed") from exc
    if len(payload) > 16 * 1024 * 1024:
        raise DataError("Binance public API response exceeds the byte limit")
    return payload


def _fetch_archive_resource(
    url: str,
    *,
    timeout_seconds: int,
    max_bytes: int,
    content_types: frozenset[str],
) -> bytes:
    if not 1 <= timeout_seconds <= 120:
        raise DataError("Binance archive timeout must be between 1 and 120 seconds")
    if not url.startswith("https://data.binance.vision/data/"):
        raise DataError("Binance archive host is invalid")
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    request = urllib.request.Request(url, headers={"User-Agent": "Project-ALPHA/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            if not str(response.geturl()).startswith("https://data.binance.vision/data/"):
                raise DataError("Binance archive redirect host is invalid")
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0]
            if content_type not in content_types:
                raise DataError("Binance archive response MIME is invalid")
            payload = bytes(response.read(max_bytes + 1))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise DataError("Binance archive request failed") from exc
    if len(payload) > max_bytes:
        raise DataError("Binance archive response exceeds the byte limit")
    return payload


def fetch_binance_archive(url: str, *, timeout_seconds: int = 120) -> bytes:
    if not url.endswith(".zip"):
        raise DataError("Binance archive URL must identify a ZIP")
    return _fetch_archive_resource(
        url,
        timeout_seconds=timeout_seconds,
        max_bytes=512 * 1024 * 1024,
        content_types=frozenset({"application/zip", "application/octet-stream"}),
    )


def fetch_binance_checksum(url: str, *, timeout_seconds: int = 30) -> bytes:
    if not url.endswith(".zip.CHECKSUM"):
        raise DataError("Binance checksum URL is invalid")
    return _fetch_archive_resource(
        url,
        timeout_seconds=timeout_seconds,
        max_bytes=4_096,
        content_types=frozenset({"text/plain", "application/octet-stream"}),
    )


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
