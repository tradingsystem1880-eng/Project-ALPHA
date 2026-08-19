"""Bounded CoinGecko Demo market-reference and identity ingestion."""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from typing import Final
from urllib.parse import urlencode
from urllib.request import Request

import polars as pl

from alpha_core import DataError

from ..contracts import normalize_crypto_address, parse_iso8601_utc

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
    encoded_params = [
        (key, "true" if value is True else "false" if value is False else value)
        for key, value in sorted(params.items())
    ]
    query = urlencode(encoded_params).replace("%2C", ",")
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
            if not str(response.geturl()).startswith("https://api.coingecko.com/api/v3/"):
                raise DataError("CoinGecko Demo redirect host is invalid")
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


def _decode_object(payload: bytes) -> dict[str, object]:
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("CoinGecko response is malformed") from exc
    if not isinstance(raw, dict):
        raise DataError("CoinGecko response must be an object")
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


def _optional_text(row: dict[str, object], key: str, *, limit: int = 500) -> str | None:
    value = row.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise DataError(f"CoinGecko field {key} is invalid")
    return value


def _optional_count(row: dict[str, object], key: str) -> int | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DataError(f"CoinGecko field {key} is invalid")
    return value


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
        observed = parse_iso8601_utc(str(updated), "CoinGecko market timestamp")
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
    return pl.DataFrame(
        rows,
        schema_overrides={
            "current_price": pl.Float64,
            "market_cap": pl.Float64,
            "market_cap_rank": pl.Float64,
            "fully_diluted_valuation": pl.Float64,
            "total_volume": pl.Float64,
            "circulating_supply": pl.Float64,
            "total_supply": pl.Float64,
            "max_supply": pl.Float64,
        },
    )


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
        if platforms is None:
            platforms = {}
        if not isinstance(platforms, dict):
            raise DataError("CoinGecko asset platforms are invalid")
        for network, contract in sorted(platforms.items()):
            if not isinstance(network, str):
                raise DataError("CoinGecko platform mapping shape is invalid")
            # A null or blank contract is CoinGecko's "no contract on this chain" convention;
            # any other shape is wire-schema drift and must fail loud.
            if contract is None:
                continue
            if not isinstance(contract, str):
                raise DataError("CoinGecko platform mapping shape is invalid")
            if not contract.strip():
                continue
            rows.append(
                {
                    "coingecko_id": coin_id,
                    "symbol": str(symbol).upper(),
                    "name": name,
                    "network": network.lower(),
                    "contract_address": normalize_crypto_address(network, contract),
                }
            )
    if not rows:
        raise DataError("CoinGecko asset catalog is empty")
    return pl.DataFrame(rows)


def parse_asset_detail(payload: bytes, *, fetched_at: datetime) -> pl.DataFrame:
    """Normalize one requested asset's bounded descriptive metadata without prose or links."""
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise DataError("CoinGecko fetch time must be timezone-aware")
    item = _decode_object(payload)
    coin_id, symbol, name = item.get("id"), item.get("symbol"), item.get("name")
    if not all(isinstance(value, str) and value for value in (coin_id, symbol, name)):
        raise DataError("CoinGecko asset detail identity is invalid")
    categories = item.get("categories")
    if (
        not isinstance(categories, list)
        or len(categories) > 500
        or any(not isinstance(value, str) or not value or len(value) > 200 for value in categories)
    ):
        raise DataError("CoinGecko asset detail categories are invalid")
    genesis_date = _optional_text(item, "genesis_date", limit=10)
    if genesis_date is not None:
        try:
            date.fromisoformat(genesis_date)
        except ValueError as exc:
            raise DataError("CoinGecko asset detail genesis date is invalid") from exc
    raw_updated = _optional_text(item, "last_updated", limit=64)
    last_updated: datetime | None = None
    if raw_updated is not None:
        last_updated = parse_iso8601_utc(raw_updated, "CoinGecko asset detail update time")
    for field in ("sentiment_votes_up_percentage", "sentiment_votes_down_percentage"):
        value = _number(item, field)
        if value is not None and not 0 <= value <= 100:
            raise DataError(f"CoinGecko field {field} is invalid")
    public_interest_score = _number(item, "public_interest_score")
    if public_interest_score is not None and public_interest_score < 0:
        raise DataError("CoinGecko field public_interest_score is invalid")
    return pl.DataFrame(
        [
            {
                "coingecko_id": coin_id,
                "symbol": str(symbol).upper(),
                "name": name,
                "asset_platform_id": _optional_text(item, "asset_platform_id"),
                "block_time_minutes": _optional_count(item, "block_time_in_minutes"),
                "hashing_algorithm": _optional_text(item, "hashing_algorithm"),
                "categories_json": json.dumps(
                    sorted(set(categories)), separators=(",", ":"), ensure_ascii=False
                ),
                "genesis_date": genesis_date,
                "market_cap_rank": _optional_count(item, "market_cap_rank"),
                "watchlist_users": _optional_count(item, "watchlist_portfolio_users"),
                "sentiment_up_pct": _number(item, "sentiment_votes_up_percentage"),
                "sentiment_down_pct": _number(item, "sentiment_votes_down_percentage"),
                "public_interest_score": public_interest_score,
                "last_updated": last_updated,
                "fetched_at": fetched_at.astimezone(UTC),
            }
        ]
    )


__all__ = [
    "coingecko_demo_request",
    "fetch_coingecko_demo",
    "parse_asset_detail",
    "parse_asset_catalog",
    "parse_market_universe",
]
