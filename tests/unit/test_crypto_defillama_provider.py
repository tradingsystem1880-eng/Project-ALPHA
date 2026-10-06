"""Strict parsing and endpoint scope for the keyless DefiLlama public APIs."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.providers.defillama import (
    defillama_url,
    parse_protocol_tvl,
    parse_stablecoin_supply,
    parse_yield_history,
    parse_yield_pools,
)

_FETCHED_AT = datetime(2026, 10, 2, tzinfo=UTC)


def test_protocol_tvl_normalizes_timestamp_and_usd_value() -> None:
    frame = parse_protocol_tvl(
        json.dumps({"tvl": [{"date": 1_756_684_800, "totalLiquidityUSD": 123.5}]}).encode(),
        fetched_at=_FETCHED_AT,
    )

    assert frame.to_dicts() == [
        {
            "timestamp": datetime(2025, 9, 1, tzinfo=UTC),
            "fetched_at": _FETCHED_AT,
            "tvl_usd": 123.5,
        }
    ]


def test_stablecoin_supply_flattens_daily_supply() -> None:
    frame = parse_stablecoin_supply(
        json.dumps(
            {"tokens": [{"date": 1_756_684_800, "circulating": {"peggedUSD": 42.0}}]}
        ).encode(),
        fetched_at=_FETCHED_AT,
    )

    assert frame.to_dicts() == [
        {
            "timestamp": datetime(2025, 9, 1, tzinfo=UTC),
            "fetched_at": _FETCHED_AT,
            "circulating_supply": 42.0,
        }
    ]


def test_yield_pool_catalog_and_history_keep_market_fields() -> None:
    pool_id = "747c1d2a-c668-4682-b9f9-296708a3dd90"
    catalog = parse_yield_pools(
        json.dumps(
            {
                "status": "success",
                "data": [
                    {
                        "pool": pool_id,
                        "chain": "Ethereum",
                        "project": "lido",
                        "symbol": "STETH",
                        "tvlUsd": 1000,
                        "apy": -3.2,
                        "apyBase": 3.0,
                        "apyReward": 0.2,
                    }
                ],
            }
        ).encode(),
        fetched_at=_FETCHED_AT,
    )
    history = parse_yield_history(
        json.dumps(
            {
                "status": "success",
                "data": [
                    {
                        "timestamp": "2025-09-01T00:00:00.000Z",
                        "tvlUsd": 1000,
                        "apy": 3.2,
                        "apyBase": 3.0,
                        "apyReward": 0.2,
                    }
                ],
            }
        ).encode(),
        fetched_at=_FETCHED_AT,
    )

    assert catalog.row(0, named=True)["pool_id"] == pool_id
    assert catalog.row(0, named=True)["apy"] == -3.2
    assert history.row(0, named=True)["timestamp"] == datetime(2025, 9, 1, tzinfo=UTC)
    assert history.row(0, named=True)["tvl_usd"] == 1000


@pytest.mark.parametrize(
    ("endpoint", "params", "expected"),
    [
        ("protocol", {"slug": "aave-v3"}, "https://api.llama.fi/protocol/aave-v3"),
        ("stablecoin", {"stablecoin_id": "1"}, "https://stablecoins.llama.fi/stablecoin/1"),
        ("yield_pools", {}, "https://yields.llama.fi/pools"),
        (
            "yield_history",
            {"pool_id": "747c1d2a-c668-4682-b9f9-296708a3dd90"},
            "https://yields.llama.fi/chart/747c1d2a-c668-4682-b9f9-296708a3dd90",
        ),
    ],
)
def test_defillama_endpoints_are_allowlisted(
    endpoint: str, params: dict[str, str], expected: str
) -> None:
    assert defillama_url(endpoint, params) == expected


def test_defillama_endpoint_rejects_unknown_endpoint_and_untrusted_slug() -> None:
    with pytest.raises(DataError, match=r"^DefiLlama endpoint 'arbitrary' is not registered$"):
        defillama_url("arbitrary", {})
    with pytest.raises(DataError, match="slug"):
        defillama_url("protocol", {"slug": "https://attacker.test"})


@pytest.mark.parametrize(
    ("parser", "payload"),
    [
        (parse_protocol_tvl, b'{"tvl": []}'),
        (parse_protocol_tvl, b'{"tvl": [{"date": 1700000000, "totalLiquidityUSD": -1}]}'),
        (parse_stablecoin_supply, b'{"tokens": [{"date": 1700000000, "circulating": {}}]}'),
        (parse_yield_pools, b'{"status": "success", "data": []}'),
        (parse_yield_history, b'{"status": "success", "data": []}'),
    ],
)
def test_defillama_parsers_reject_empty_or_invalid_market_data(
    parser: Callable[..., pl.DataFrame], payload: bytes
) -> None:
    with pytest.raises(DataError):
        partial(parser, fetched_at=_FETCHED_AT)(payload)


@pytest.mark.parametrize("timestamp", ["2025-09-01T00:00:00", "not-a-date"])
def test_yield_history_rejects_ambiguous_timestamps(timestamp: str) -> None:
    payload = json.dumps(
        {"status": "success", "data": [{"timestamp": timestamp, "tvlUsd": 1000, "apy": 3.2}]}
    ).encode()
    with pytest.raises(DataError):
        parse_yield_history(payload, fetched_at=_FETCHED_AT)


def test_yield_history_rejects_malformed_status() -> None:
    with pytest.raises(DataError):
        parse_yield_history(b'{"status": [], "data": []}', fetched_at=_FETCHED_AT)
