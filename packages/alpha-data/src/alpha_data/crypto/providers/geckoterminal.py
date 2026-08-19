"""Keyless GeckoTerminal DEX pool and OHLCV parsing."""

from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from typing import Final
from urllib.parse import urlencode

import polars as pl

from alpha_core import DataError

from ..contracts import normalize_crypto_address

type QueryScalar = str | int | bool

NETWORKS: Final = frozenset({"eth", "solana", "base", "bsc", "arbitrum"})
_ENDPOINTS: Final = {
    "top_pools": ("/networks/{network}/pools", frozenset({"page"})),
    "pool": ("/networks/{network}/pools/{pool_address}", frozenset()),
    "ohlcv": (
        "/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}",
        frozenset({"aggregate", "before_timestamp", "limit", "currency", "token"}),
    ),
    "trades": ("/networks/{network}/pools/{pool_address}/trades", frozenset()),
}


def geckoterminal_public_url(
    endpoint: str,
    *,
    network: str,
    params: dict[str, QueryScalar],
    pool_address: str | None = None,
    timeframe: str | None = None,
) -> str:
    if network not in NETWORKS:
        raise DataError("GeckoTerminal network is not a supported network")
    definition = _ENDPOINTS.get(endpoint)
    if definition is None:
        raise DataError(f"unsupported GeckoTerminal endpoint {endpoint!r}")
    path, allowed = definition
    if set(params) - allowed:
        raise DataError("unsupported GeckoTerminal query parameters")
    if endpoint == "top_pools":
        page = params.get("page", 1)
        if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= 5:
            raise DataError("GeckoTerminal top-pool page must be between 1 and 5")
    if "{pool_address}" in path:
        if not pool_address or not pool_address.strip() or "/" in pool_address:
            raise DataError("GeckoTerminal pool address is invalid")
        path = path.replace("{pool_address}", pool_address)
    if "{timeframe}" in path:
        if timeframe not in {"day", "hour", "minute"}:
            raise DataError("GeckoTerminal timeframe is invalid")
        path = path.replace("{timeframe}", timeframe)
        limit = params.get("limit", 100)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise DataError("GeckoTerminal OHLCV limit is invalid")
    path = path.replace("{network}", network)
    query = urlencode(sorted(params.items()))
    return f"https://api.geckoterminal.com/api/v2{path}" + (f"?{query}" if query else "")


def fetch_geckoterminal_public(url: str, *, timeout_seconds: int = 30) -> bytes:
    """Fetch one bounded keyless response from the exact GeckoTerminal root."""
    if not 1 <= timeout_seconds <= 60:
        raise DataError("GeckoTerminal timeout must be between 1 and 60 seconds")
    if not url.startswith("https://api.geckoterminal.com/api/v2/"):
        raise DataError("GeckoTerminal request host is invalid")
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "Project-ALPHA/1.0"}
    )
    payload: bytes | None = None
    max_attempts = 4
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                if not str(response.geturl()).startswith("https://api.geckoterminal.com/api/v2/"):
                    raise DataError("GeckoTerminal redirect host is invalid")
                content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0]
                if content_type not in {"application/json", "text/json"}:
                    raise DataError("GeckoTerminal response MIME is not JSON")
                payload = bytes(response.read(8 * 1024 * 1024 + 1))
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == max_attempts - 1:
                raise DataError("GeckoTerminal request failed") from exc
            retry_header = exc.headers.get("Retry-After") if exc.headers is not None else None
            try:
                provider_delay = float(retry_header) if retry_header is not None else 0.0
            except ValueError:
                provider_delay = 0.0
            time.sleep(min(10.0, max(2.1 * (2**attempt), provider_delay)))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise DataError("GeckoTerminal request failed") from exc
    if payload is None:
        raise DataError("GeckoTerminal request failed")
    if len(payload) > 8 * 1024 * 1024:
        raise DataError("GeckoTerminal response exceeds the byte limit")
    return payload


def _decode(payload: bytes) -> dict[str, object]:
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("GeckoTerminal response is malformed") from exc
    if not isinstance(raw, dict):
        raise DataError("GeckoTerminal response must be an object")
    return raw


def _finite(value: object, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise DataError(f"GeckoTerminal {label} is invalid")
    try:
        number = float(value)
    except ValueError as exc:
        raise DataError(f"GeckoTerminal {label} is invalid") from exc
    if not math.isfinite(number):
        raise DataError(f"GeckoTerminal {label} is not finite")
    return number


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DataError(f"GeckoTerminal {label} must be a non-negative integer")
    return value


def _relationship(record: dict[str, object], name: str, network: str) -> str:
    relationships = record.get("relationships")
    if not isinstance(relationships, dict) or not isinstance(relationships.get(name), dict):
        raise DataError("GeckoTerminal pool relationships are invalid")
    relation = relationships[name]
    assert isinstance(relation, dict)
    data = relation.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("id"), str):
        raise DataError("GeckoTerminal pool relationship identity is invalid")
    identity = str(data["id"])
    prefix = f"{network}_"
    if name != "dex" and not identity.startswith(prefix):
        raise DataError("GeckoTerminal pool relationship network is invalid")
    value = identity[len(prefix) :] if identity.startswith(prefix) else identity
    return normalize_crypto_address(network, value)


def parse_top_pools(payload: bytes, *, network: str) -> pl.DataFrame:
    if network not in NETWORKS:
        raise DataError("GeckoTerminal network is not a supported network")
    data = _decode(payload).get("data")
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise DataError("GeckoTerminal pool data is invalid")
    rows: list[dict[str, object]] = []
    for record in data:
        assert isinstance(record, dict)
        attributes = record.get("attributes")
        if record.get("type") != "pool" or not isinstance(attributes, dict):
            raise DataError("GeckoTerminal pool record is invalid")
        address, name, created = (
            attributes.get("address"),
            attributes.get("name"),
            attributes.get("pool_created_at"),
        )
        if not all(isinstance(value, str) and value for value in (address, name, created)):
            raise DataError("GeckoTerminal pool identity is invalid")
        volume = attributes.get("volume_usd")
        transactions = attributes.get("transactions")
        if not isinstance(volume, dict) or not isinstance(transactions, dict):
            raise DataError("GeckoTerminal pool activity is invalid")
        h24 = transactions.get("h24")
        if not isinstance(h24, dict):
            raise DataError("GeckoTerminal pool transaction window is invalid")
        record_id = record.get("id")
        prefix = f"{network}_"
        if not isinstance(record_id, str) or not record_id.startswith(prefix):
            raise DataError("GeckoTerminal pool identity is invalid")
        if normalize_crypto_address(network, record_id[len(prefix) :]) != normalize_crypto_address(
            network, str(address)
        ):
            raise DataError("GeckoTerminal pool identity is invalid")
        try:
            created_at = datetime.fromisoformat(str(created).replace("Z", "+00:00")).astimezone(UTC)
        except ValueError as exc:
            raise DataError("GeckoTerminal pool creation time is invalid") from exc
        rows.append(
            {
                "network": network,
                "pool_address": normalize_crypto_address(network, str(address)),
                "name": name,
                "dex_id": _relationship(record, "dex", network),
                "base_token_address": _relationship(record, "base_token", network),
                "quote_token_address": _relationship(record, "quote_token", network),
                "pool_created_at": created_at,
                "base_token_price_usd": _finite(
                    attributes.get("base_token_price_usd"), "base price"
                ),
                "quote_token_price_usd": _finite(
                    attributes.get("quote_token_price_usd"), "quote price"
                ),
                "reserve_usd": _finite(attributes.get("reserve_in_usd"), "reserve"),
                "h24_volume_usd": _finite(volume.get("h24"), "24-hour volume"),
                "h24_buys": _non_negative_int(h24.get("buys"), "24-hour buy transaction count"),
                "h24_sells": _non_negative_int(h24.get("sells"), "24-hour sell transaction count"),
            }
        )
    return pl.DataFrame(rows)


def parse_pool_ohlcv(payload: bytes, *, network: str, pool_address: str) -> pl.DataFrame:
    raw = _decode(payload)
    data, meta = raw.get("data"), raw.get("meta")
    if not isinstance(data, dict) or not isinstance(data.get("attributes"), dict):
        raise DataError("GeckoTerminal OHLCV data is invalid")
    attributes = data["attributes"]
    assert isinstance(attributes, dict)
    values = attributes.get("ohlcv_list")
    if not isinstance(values, list):
        raise DataError("GeckoTerminal OHLCV list is invalid")
    if (
        not isinstance(meta, dict)
        or not isinstance(meta.get("base"), dict)
        or not isinstance(meta.get("quote"), dict)
    ):
        raise DataError("GeckoTerminal OHLCV token identity is invalid")
    base, quote = meta["base"], meta["quote"]
    assert isinstance(base, dict) and isinstance(quote, dict)
    base_address, quote_address = base.get("address"), quote.get("address")
    if not isinstance(base_address, str) or not isinstance(quote_address, str):
        raise DataError("GeckoTerminal OHLCV contract identity is invalid")
    if not values:
        raise DataError("GeckoTerminal pool OHLCV response is empty")
    rows: list[dict[str, object]] = []
    for provider_rank, point in enumerate(values):
        if not isinstance(point, list) or len(point) != 6:
            raise DataError("GeckoTerminal OHLCV point is invalid")
        timestamp = point[0]
        if not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp < 0:
            raise DataError("GeckoTerminal OHLCV timestamp is invalid")
        open_, high, low, close = (_finite(point[index], "price") for index in (1, 2, 3, 4))
        if (
            open_ is None
            or high is None
            or low is None
            or close is None
            or high < max(open_, close)
            or low > min(open_, close)
            or high < low
        ):
            raise DataError("GeckoTerminal pool OHLCV bar violates OHLC invariants")
        rows.append(
            {
                "network": network,
                "provider_rank": provider_rank,
                "pool_address": normalize_crypto_address(network, pool_address),
                "base_token_address": normalize_crypto_address(network, base_address),
                "quote_token_address": normalize_crypto_address(network, quote_address),
                "timestamp": datetime.fromtimestamp(timestamp, tz=UTC),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume_usd": _finite(point[5], "volume"),
            }
        )
    return pl.DataFrame(rows).sort("timestamp")


def parse_pool_trades(payload: bytes, *, network: str, pool_address: str) -> pl.DataFrame:
    data = _decode(payload).get("data")
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise DataError("GeckoTerminal trade data is invalid")
    rows: list[dict[str, object]] = []
    for provider_rank, record in enumerate(data):
        assert isinstance(record, dict)
        attributes = record.get("attributes")
        trade_id = record.get("id")
        if record.get("type") != "trade" or not isinstance(attributes, dict):
            raise DataError("GeckoTerminal trade record is invalid")
        if not isinstance(trade_id, str) or not trade_id:
            raise DataError("GeckoTerminal trade identity record id is invalid")
        timestamp = attributes.get("block_timestamp")
        kind = attributes.get("kind")
        tx_hash = attributes.get("tx_hash")
        from_address = attributes.get("from_token_address")
        to_address = attributes.get("to_token_address")
        if (
            not isinstance(timestamp, str)
            or kind not in {"buy", "sell"}
            or not all(
                isinstance(value, str) and value for value in (tx_hash, from_address, to_address)
            )
        ):
            raise DataError("GeckoTerminal trade identity is invalid")
        try:
            observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError as exc:
            raise DataError("GeckoTerminal trade timestamp is invalid") from exc
        rows.append(
            {
                "network": network,
                "provider_rank": provider_rank,
                "pool_address": normalize_crypto_address(network, pool_address),
                "block_number": _non_negative_int(
                    attributes.get("block_number"), "trade block number"
                ),
                "trade_id": trade_id,
                "tx_hash": tx_hash,
                "timestamp": observed,
                "kind": kind,
                "from_token_address": normalize_crypto_address(network, str(from_address)),
                "to_token_address": normalize_crypto_address(network, str(to_address)),
                "from_token_amount": _finite(attributes.get("from_token_amount"), "from amount"),
                "to_token_amount": _finite(attributes.get("to_token_amount"), "to amount"),
                "price_from_usd": _finite(attributes.get("price_from_in_usd"), "from price"),
                "price_to_usd": _finite(attributes.get("price_to_in_usd"), "to price"),
                "volume_usd": _finite(attributes.get("volume_in_usd"), "trade volume"),
            }
        )
    return pl.DataFrame(rows).sort(["timestamp", "trade_id"])


__all__ = [
    "NETWORKS",
    "fetch_geckoterminal_public",
    "geckoterminal_public_url",
    "parse_pool_ohlcv",
    "parse_pool_trades",
    "parse_top_pools",
]
