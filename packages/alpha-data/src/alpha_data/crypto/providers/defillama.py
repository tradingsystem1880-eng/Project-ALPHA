"""Bounded, keyless DefiLlama protocol, stablecoin and yield data contracts."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from urllib.parse import quote

import polars as pl

from alpha_core import DataError

from ..contracts import require_utc
from ._wire import decode_json_object, fetch_bounded, finite_float, resolve_endpoint

type QueryScalar = str | int

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
_INTEGER_ID = re.compile(r"^[1-9][0-9]{0,15}$")
_POOL_ID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_ENDPOINTS = {
    "protocol": ("https://api.llama.fi/protocol/{slug}", frozenset({"slug"})),
    "stablecoin": (
        "https://stablecoins.llama.fi/stablecoin/{stablecoin_id}",
        frozenset({"stablecoin_id"}),
    ),
    "yield_pools": ("https://yields.llama.fi/pools", frozenset()),
    "yield_history": ("https://yields.llama.fi/chart/{pool_id}", frozenset({"pool_id"})),
}
_HOSTS = {
    "protocol": "https://api.llama.fi/",
    "stablecoin": "https://stablecoins.llama.fi/",
    "yield_pools": "https://yields.llama.fi/",
    "yield_history": "https://yields.llama.fi/",
}


def defillama_url(endpoint: str, params: Mapping[str, QueryScalar]) -> str:
    """Build one exact public endpoint, rejecting untrusted path components."""
    template = _ENDPOINTS.get(endpoint)
    if template is None:
        raise DataError("unsupported DefiLlama endpoint")
    path, _ = resolve_endpoint(
        {endpoint: template}, endpoint, params, provider="DefiLlama", max_params=1
    )
    if endpoint == "protocol":
        value = params.get("slug", "")
        if not isinstance(value, str) or not _SLUG.fullmatch(value):
            raise DataError("DefiLlama protocol slug is invalid")
        path = path.format(slug=quote(value, safe=""))
    elif endpoint == "stablecoin":
        value = params.get("stablecoin_id", "")
        if not isinstance(value, str) or not _INTEGER_ID.fullmatch(value):
            raise DataError("DefiLlama stablecoin id is invalid")
        path = path.format(stablecoin_id=value)
    elif endpoint == "yield_history":
        value = params.get("pool_id", "")
        if not isinstance(value, str) or not _POOL_ID.fullmatch(value):
            raise DataError("DefiLlama yield pool id is invalid")
        path = path.format(pool_id=value.lower())
    return path


def fetch_defillama_public(url: str, *, timeout_seconds: int = 30) -> bytes:
    """Fetch one allowlisted public response with provider-specific size limits."""
    provider = "DefiLlama"
    hosts = tuple(_HOSTS.values())
    if not any(url.startswith(host) for host in hosts):
        raise DataError("DefiLlama request host is invalid")
    host_prefix = next(host for host in hosts if url.startswith(host))
    return fetch_bounded(
        url,
        provider=provider,
        host_prefix=host_prefix,
        content_types=frozenset({"application/json", "text/json"}),
        max_bytes=64 * 1024 * 1024,
        timeout_seconds=timeout_seconds,
        retry_429=True,
    )


def _seconds(value: object, label: str) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DataError(f"DefiLlama {label} timestamp is invalid")
    try:
        result = datetime.fromtimestamp(float(value), tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise DataError(f"DefiLlama {label} timestamp is invalid") from exc
    if not datetime(2010, 1, 1, tzinfo=UTC) <= result < datetime(2100, 1, 1, tzinfo=UTC):
        raise DataError(f"DefiLlama {label} timestamp is outside the supported range")
    return result


def _records(raw: dict[str, object], key: str) -> list[dict[str, object]]:
    rows = raw.get(key)
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise DataError(f"DefiLlama {key} data is empty or malformed")
    return cast(list[dict[str, object]], rows)


def _optional_number(value: object, label: str) -> float | None:
    if value is None:
        return None
    return finite_float(value, label)


def parse_protocol_tvl(payload: bytes, *, fetched_at: datetime) -> pl.DataFrame:
    available_at = require_utc(fetched_at, "fetch time")
    raw = decode_json_object(payload, provider="DefiLlama", shape_message="protocol is invalid")
    rows = [
        {
            "timestamp": _seconds(row.get("date"), "protocol TVL"),
            "fetched_at": available_at,
            "tvl_usd": finite_float(row.get("totalLiquidityUSD"), "DefiLlama TVL"),
        }
        for row in _records(raw, "tvl")
    ]
    if any(cast(float, row["tvl_usd"]) < 0 for row in rows):
        raise DataError("DefiLlama TVL must be non-negative")
    if len({row["timestamp"] for row in rows}) != len(rows):
        raise DataError("DefiLlama protocol TVL contains duplicate dates")
    return pl.DataFrame(rows).sort("timestamp")


def parse_stablecoin_supply(payload: bytes, *, fetched_at: datetime) -> pl.DataFrame:
    available_at = require_utc(fetched_at, "fetch time")
    raw = decode_json_object(payload, provider="DefiLlama", shape_message="stablecoin is invalid")
    rows: list[dict[str, object]] = []
    for row in _records(raw, "tokens"):
        circulating = row.get("circulating")
        if not isinstance(circulating, dict) or "peggedUSD" not in circulating:
            raise DataError("DefiLlama stablecoin USD circulation is missing")
        rows.append(
            {
                "timestamp": _seconds(row.get("date"), "stablecoin supply"),
                "fetched_at": available_at,
                # Peg denomination is not historical USD valuation: balances are token units.
                "circulating_supply": finite_float(circulating["peggedUSD"], "DefiLlama supply"),
            }
        )
    if any(cast(float, row["circulating_supply"]) < 0 for row in rows):
        raise DataError("DefiLlama stablecoin supply must be non-negative")
    if len({row["timestamp"] for row in rows}) != len(rows):
        raise DataError("DefiLlama stablecoin supply contains duplicate dates")
    return pl.DataFrame(rows).sort("timestamp")


def _status_data(payload: bytes, *, label: str) -> list[dict[str, object]]:
    raw = decode_json_object(payload, provider="DefiLlama", shape_message=f"{label} is invalid")
    if raw.get("status") not in ("success", "ok", None):
        raise DataError(f"DefiLlama {label} request did not succeed")
    return _records(raw, "data")


def _apy_fields(row: dict[str, object], *, label: str) -> dict[str, float | None]:
    apy = _optional_number(row.get("apy"), f"DefiLlama {label} APY")
    if apy is None:
        raise DataError(f"DefiLlama {label} APY is missing")
    return {
        "apy": apy,
        "apy_base": _optional_number(row.get("apyBase"), f"DefiLlama {label} base APY"),
        "apy_reward": _optional_number(row.get("apyReward"), f"DefiLlama {label} reward APY"),
    }


def parse_yield_pools(payload: bytes, *, fetched_at: datetime) -> pl.DataFrame:
    available_at = require_utc(fetched_at, "fetch time")
    rows: list[dict[str, object]] = []
    for row in _status_data(payload, label="yield pools"):
        pool_id = row.get("pool")
        chain, project, symbol = row.get("chain"), row.get("project"), row.get("symbol")
        if not isinstance(pool_id, str) or not _POOL_ID.fullmatch(pool_id):
            raise DataError("DefiLlama yield pool id is invalid")
        if any(not isinstance(value, str) or not value for value in (chain, project, symbol)):
            raise DataError("DefiLlama yield pool identity is invalid")
        apy = _apy_fields(row, label="yield pool")
        tvl = _optional_number(row.get("tvlUsd"), "DefiLlama yield TVL")
        if tvl is None or tvl < 0:
            raise DataError("DefiLlama yield TVL is missing")
        rows.append(
            {
                "pool_id": pool_id.lower(),
                "fetched_at": available_at,
                "chain": chain,
                "project": project,
                "symbol": symbol,
                "tvl_usd": tvl,
                **apy,
                "stablecoin": (
                    row.get("stablecoin") if isinstance(row.get("stablecoin"), bool) else None
                ),
                "exposure": row.get("exposure") if isinstance(row.get("exposure"), str) else None,
            }
        )
    if len({row["pool_id"] for row in rows}) != len(rows):
        raise DataError("DefiLlama yield pool catalog contains duplicate pool ids")
    return pl.DataFrame(rows).sort("pool_id")


def parse_yield_history(payload: bytes, *, fetched_at: datetime) -> pl.DataFrame:
    available_at = require_utc(fetched_at, "fetch time")
    rows: list[dict[str, object]] = []
    for row in _status_data(payload, label="yield history"):
        timestamp_raw = row.get("timestamp")
        if not isinstance(timestamp_raw, str):
            raise DataError("DefiLlama yield timestamp is invalid")
        try:
            timestamp = require_utc(
                datetime.fromisoformat(timestamp_raw), "yield history", prefix="DefiLlama"
            )
        except ValueError as exc:
            raise DataError("DefiLlama yield timestamp is invalid") from exc
        tvl = _optional_number(row.get("tvlUsd"), "DefiLlama yield TVL")
        if tvl is None or tvl < 0:
            raise DataError("DefiLlama yield TVL is missing")
        rows.append(
            {
                "timestamp": timestamp,
                "fetched_at": available_at,
                "tvl_usd": tvl,
                **_apy_fields(row, label="yield history"),
            }
        )
    if len({row["timestamp"] for row in rows}) != len(rows):
        raise DataError("DefiLlama yield history contains duplicate timestamps")
    return pl.DataFrame(rows).sort("timestamp")


__all__ = [
    "defillama_url",
    "fetch_defillama_public",
    "parse_protocol_tvl",
    "parse_stablecoin_supply",
    "parse_yield_history",
    "parse_yield_pools",
]
