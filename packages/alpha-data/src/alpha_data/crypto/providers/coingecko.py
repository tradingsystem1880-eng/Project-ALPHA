"""Bounded CoinGecko Demo market-reference and identity ingestion."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Final
from urllib.parse import urlencode
from urllib.request import Request

import polars as pl

from alpha_core import DataError

type QueryScalar = str | int | bool

_ENDPOINTS: Final = {
    "ping": ("/ping", frozenset()),
    "markets": (
        "/coins/markets",
        frozenset({"vs_currency", "ids", "order", "per_page", "page", "sparkline"}),
    ),
    "asset_catalog": ("/coins/list", frozenset({"include_platform"})),
    "coin_detail": (
        "/coins/{coin_id}",
        frozenset({"localization", "tickers", "market_data", "community_data", "developer_data"}),
    ),
}


def coingecko_demo_request(
    endpoint: str,
    params: dict[str, QueryScalar],
    *,
    api_key: str,
    coin_id: str | None = None,
) -> Request:
    definition = _ENDPOINTS.get(endpoint)
    if definition is None:
        raise DataError(f"unsupported CoinGecko Demo endpoint {endpoint!r}")
    path, allowed = definition
    if set(params) - allowed:
        raise DataError("unsupported CoinGecko Demo query parameters")
    if not api_key.strip():
        raise DataError("CoinGecko Demo key is not injected")
    if "{coin_id}" in path:
        if not coin_id or not coin_id.replace("-", "").isalnum():
            raise DataError("CoinGecko coin id is invalid")
        path = path.format(coin_id=coin_id)
    if endpoint == "markets":
        page = params.get("page", 1)
        per_page = params.get("per_page", 100)
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise DataError("CoinGecko page is invalid")
        if not isinstance(per_page, int) or isinstance(per_page, bool) or not 1 <= per_page <= 250:
            raise DataError("CoinGecko page size is invalid")
    query = urlencode(sorted(params.items())).replace("%2C", ",")
    url = f"https://api.coingecko.com/api/v3{path}" + (f"?{query}" if query else "")
    return Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Project-ALPHA/1.0",
            "x-cg-demo-api-key": api_key,
        },
    )


def fetch_coingecko_demo(request: Request, *, timeout_seconds: int = 30) -> bytes:
    """Fetch one bounded JSON response from the exact Demo host."""
    if not 1 <= timeout_seconds <= 60:
        raise DataError("CoinGecko Demo timeout must be between 1 and 60 seconds")
    if not request.full_url.startswith("https://api.coingecko.com/api/v3/"):
        raise DataError("CoinGecko Demo request host is invalid")
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0]
            if content_type not in {"application/json", "text/json"}:
                raise DataError("CoinGecko Demo response MIME is not JSON")
            payload = bytes(response.read(8 * 1024 * 1024 + 1))
    except urllib.error.HTTPError as exc:
        raise DataError(f"CoinGecko Demo request failed with HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DataError("CoinGecko Demo request failed") from exc
    if len(payload) > 8 * 1024 * 1024:
        raise DataError("CoinGecko Demo response exceeds the byte limit")
    return payload


def _decode_list(payload: bytes) -> list[dict[str, object]]:
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("CoinGecko response is malformed") from exc
    if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
        raise DataError("CoinGecko response must be a list of objects")
    return raw


def _number(row: dict[str, object], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DataError(f"CoinGecko field {key} is invalid")
    result = float(value)
    if not math.isfinite(result):
        raise DataError(f"CoinGecko field {key} is not finite")
    return result


def parse_market_universe(
    payload: bytes, *, vs_currency: str, fetched_at: datetime
) -> pl.DataFrame:
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise DataError("CoinGecko fetch time must be timezone-aware")
    quote = vs_currency.strip().upper()
    if not quote:
        raise DataError("CoinGecko quote currency is invalid")
    rows: list[dict[str, object]] = []
    for item in _decode_list(payload):
        coin_id, symbol, name, updated = (
            item.get("id"),
            item.get("symbol"),
            item.get("name"),
            item.get("last_updated"),
        )
        if not all(isinstance(value, str) and value for value in (coin_id, symbol, name, updated)):
            raise DataError("CoinGecko market identity is invalid")
        try:
            observed = datetime.fromisoformat(str(updated).replace("Z", "+00:00")).astimezone(UTC)
        except ValueError as exc:
            raise DataError("CoinGecko market timestamp is invalid") from exc
        rows.append(
            {
                "coingecko_id": coin_id,
                "symbol": str(symbol).upper(),
                "name": name,
                "quote_asset": quote,
                "current_price": _number(item, "current_price"),
                "market_cap": _number(item, "market_cap"),
                "market_cap_rank": _number(item, "market_cap_rank"),
                "fully_diluted_valuation": _number(item, "fully_diluted_valuation"),
                "total_volume": _number(item, "total_volume"),
                "circulating_supply": _number(item, "circulating_supply"),
                "total_supply": _number(item, "total_supply"),
                "max_supply": _number(item, "max_supply"),
                "observed_at": observed,
                "fetched_at": fetched_at.astimezone(UTC),
            }
        )
    return pl.DataFrame(rows)


def parse_asset_catalog(payload: bytes) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for item in _decode_list(payload):
        coin_id, symbol, name, platforms = (
            item.get("id"),
            item.get("symbol"),
            item.get("name"),
            item.get("platforms"),
        )
        if (
            not isinstance(coin_id, str)
            or not coin_id
            or not isinstance(symbol, str)
            or not isinstance(name, str)
        ):
            raise DataError("CoinGecko asset identity is invalid")
        if not isinstance(platforms, dict):
            raise DataError("CoinGecko asset platforms are invalid")
        for network, contract in sorted(platforms.items()):
            if (
                not isinstance(network, str)
                or not isinstance(contract, str)
                or not contract.strip()
            ):
                continue
            rows.append(
                {
                    "coingecko_id": coin_id,
                    "symbol": str(symbol).upper(),
                    "name": name,
                    "network": network.lower(),
                    "contract_address": contract.lower(),
                }
            )
    return pl.DataFrame(rows)


__all__ = [
    "coingecko_demo_request",
    "fetch_coingecko_demo",
    "parse_asset_catalog",
    "parse_market_universe",
]
