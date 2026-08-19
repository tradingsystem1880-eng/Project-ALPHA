from __future__ import annotations

import json
import urllib.error
from email.message import Message

import pytest

from alpha_core import DataError
from alpha_data.crypto.providers.geckoterminal import (
    fetch_geckoterminal_public,
    geckoterminal_public_url,
    parse_pool_ohlcv,
    parse_pool_trades,
    parse_top_pools,
)


def test_geckoterminal_url_is_keyless_closed_and_bounded() -> None:
    url = geckoterminal_public_url("top_pools", network="eth", params={"page": 5})
    assert url == "https://api.geckoterminal.com/api/v2/networks/eth/pools?page=5"
    with pytest.raises(DataError, match="supported network"):
        geckoterminal_public_url("top_pools", network="unknown", params={"page": 1})
    with pytest.raises(DataError, match="unsupported GeckoTerminal"):
        geckoterminal_public_url("top_pools", network="eth", params={"api_key": "leak"})


def test_pool_catalog_retains_contract_identity_liquidity_and_transactions() -> None:
    payload = json.dumps(
        {
            "data": [
                {
                    "id": "eth_0xpool",
                    "type": "pool",
                    "attributes": {
                        "address": "0xPool",
                        "name": "USDC / WETH",
                        "pool_created_at": "2021-12-30T20:32:10Z",
                        "base_token_price_usd": "1.0",
                        "quote_token_price_usd": "2000",
                        "reserve_in_usd": "4558978.84",
                        "volume_usd": {"h24": "39081025"},
                        "transactions": {"h24": {"buys": 8, "sells": 7}},
                    },
                    "relationships": {
                        "base_token": {"data": {"id": "eth_0xbase", "type": "token"}},
                        "quote_token": {"data": {"id": "eth_0xquote", "type": "token"}},
                        "dex": {"data": {"id": "uniswap_v3", "type": "dex"}},
                    },
                }
            ]
        }
    ).encode()
    row = parse_top_pools(payload, network="eth").row(0, named=True)
    assert row["pool_address"] == "0xpool"
    assert row["base_token_address"] == "0xbase"
    assert row["reserve_usd"] == 4558978.84
    assert row["h24_buys"] == 8


def test_pool_ohlcv_preserves_sparse_intervals_and_exact_token_addresses() -> None:
    payload = json.dumps(
        {
            "data": {
                "attributes": {
                    "ohlcv_list": [
                        [1700003600, 2, 3, 1.5, 2.5, 20],
                        [1700000000, 1, 2, 0.5, 1.5, 10],
                    ]
                }
            },
            "meta": {
                "base": {"address": "0xBase", "coingecko_coin_id": "base"},
                "quote": {"address": "0xQuote", "coingecko_coin_id": "quote"},
            },
        }
    ).encode()
    frame = parse_pool_ohlcv(payload, network="eth", pool_address="0xPool")
    row = frame.row(0, named=True)
    assert row["base_token_address"] == "0xbase"
    assert row["quote_token_address"] == "0xquote"
    assert row["volume_usd"] == 10.0
    assert row["provider_rank"] == 1
    assert frame["timestamp"].is_sorted()


def test_pool_trades_preserve_transaction_and_contract_identity() -> None:
    payload = json.dumps(
        {
            "data": [
                {
                    "id": "eth_trade_newer",
                    "type": "trade",
                    "attributes": {
                        "block_number": 124,
                        "tx_hash": "0xabc",
                        "from_token_amount": "0.1",
                        "to_token_amount": "200",
                        "price_from_in_usd": "2000",
                        "price_to_in_usd": "1",
                        "block_timestamp": "2026-08-14T00:01:00Z",
                        "kind": "buy",
                        "volume_in_usd": "200",
                        "from_token_address": "0xFrom",
                        "to_token_address": "0xTo",
                    },
                },
                {
                    "id": "eth_trade_older",
                    "type": "trade",
                    "attributes": {
                        "block_number": 123,
                        "tx_hash": "0xabc",
                        "from_token_amount": "0.2",
                        "to_token_amount": "400",
                        "price_from_in_usd": "2000",
                        "price_to_in_usd": "1",
                        "block_timestamp": "2026-08-14T00:00:00Z",
                        "kind": "sell",
                        "volume_in_usd": "400",
                        "from_token_address": "0xFrom",
                        "to_token_address": "0xTo",
                    },
                },
            ]
        }
    ).encode()
    frame = parse_pool_trades(payload, network="eth", pool_address="0xPool")
    row = frame.row(0, named=True)
    assert row["trade_id"] == "eth_trade_older"
    assert row["tx_hash"] == "0xabc"
    assert row["from_token_address"] == "0xfrom"
    assert row["kind"] == "sell"
    assert row["provider_rank"] == 1
    assert frame["trade_id"].n_unique() == 2
    assert frame["timestamp"].is_sorted()


def test_solana_pool_and_token_addresses_remain_case_sensitive() -> None:
    pool = "MixedCasePool1111111111111111111111111111111"
    base = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    quote = "So11111111111111111111111111111111111111112"
    catalog = json.dumps(
        {
            "data": [
                {
                    "id": f"solana_{pool}",
                    "type": "pool",
                    "attributes": {
                        "address": pool,
                        "name": "USDC / SOL",
                        "pool_created_at": "2021-12-30T20:32:10Z",
                        "base_token_price_usd": "1",
                        "quote_token_price_usd": "200",
                        "reserve_in_usd": "1000",
                        "volume_usd": {"h24": "100"},
                        "transactions": {"h24": {"buys": 1, "sells": 1}},
                    },
                    "relationships": {
                        "base_token": {"data": {"id": f"solana_{base}"}},
                        "quote_token": {"data": {"id": f"solana_{quote}"}},
                        "dex": {"data": {"id": "orca"}},
                    },
                }
            ]
        }
    ).encode()
    catalog_row = parse_top_pools(catalog, network="solana").row(0, named=True)
    assert catalog_row["pool_address"] == pool
    assert catalog_row["base_token_address"] == base

    ohlcv = json.dumps(
        {
            "data": {"attributes": {"ohlcv_list": [[1_700_000_000, 1, 2, 0.5, 1.5, 10]]}},
            "meta": {"base": {"address": base}, "quote": {"address": quote}},
        }
    ).encode()
    ohlcv_row = parse_pool_ohlcv(ohlcv, network="solana", pool_address=pool).row(0, named=True)
    assert ohlcv_row["pool_address"] == pool
    assert ohlcv_row["base_token_address"] == base

    trades = json.dumps(
        {
            "data": [
                {
                    "id": "solana_trade_1",
                    "type": "trade",
                    "attributes": {
                        "block_number": 1,
                        "tx_hash": "MixedCaseSignature",
                        "from_token_amount": "1",
                        "to_token_amount": "2",
                        "price_from_in_usd": "2",
                        "price_to_in_usd": "1",
                        "block_timestamp": "2026-08-14T00:00:00Z",
                        "kind": "buy",
                        "volume_in_usd": "2",
                        "from_token_address": base,
                        "to_token_address": quote,
                    },
                }
            ]
        }
    ).encode()
    trade_row = parse_pool_trades(trades, network="solana", pool_address=pool).row(0, named=True)
    assert trade_row["pool_address"] == pool
    assert trade_row["from_token_address"] == base
    assert trade_row["tx_hash"] == "MixedCaseSignature"


class _Response:
    def __init__(
        self,
        payload: bytes,
        mime: str = "application/json",
        url: str = "https://api.geckoterminal.com/api/v2/networks/eth/pools",
    ) -> None:
        self.payload = payload
        self.headers = {"Content-Type": mime}
        self.url = url

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return self.payload

    def geturl(self) -> str:
        return self.url


def test_keyless_fetch_is_bounded_and_host_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    url = geckoterminal_public_url("top_pools", network="eth", params={"page": 1})
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: _Response(b'{"data":[]}')
    )
    assert fetch_geckoterminal_public(url) == b'{"data":[]}'
    with pytest.raises(DataError, match="timeout"):
        fetch_geckoterminal_public(url, timeout_seconds=0)
    with pytest.raises(DataError, match="host"):
        fetch_geckoterminal_public("https://example.com/api/v2/pools")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(
            b'{"data":[]}', url="https://attacker.invalid/provider-data"
        ),
    )
    with pytest.raises(DataError, match="redirect host"):
        fetch_geckoterminal_public(url)
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: _Response(b"x", "text/html")
    )
    with pytest.raises(DataError, match="MIME"):
        fetch_geckoterminal_public(url)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(b"x" * (8 * 1024 * 1024 + 1)),
    )
    with pytest.raises(DataError, match="byte limit"):
        fetch_geckoterminal_public(url)
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError())
    )
    with pytest.raises(DataError, match="request failed"):
        fetch_geckoterminal_public(url)


def test_keyless_fetch_retries_a_bounded_rate_limit_without_exposing_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = geckoterminal_public_url("top_pools", network="bsc", params={"page": 2})
    headers = Message()
    headers["Retry-After"] = "0"
    responses: list[object] = [
        urllib.error.HTTPError(url, 429, "vendor body sentinel", headers, None),
        _Response(b'{"data":[]}'),
    ]
    sleeps: list[float] = []

    def open_next(*_args: object, **_kwargs: object) -> object:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("urllib.request.urlopen", open_next)
    monkeypatch.setattr("time.sleep", sleeps.append)

    assert fetch_geckoterminal_public(url) == b'{"data":[]}'
    assert sleeps == [2.1]


def test_keyless_fetch_rate_limit_backoff_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    url = geckoterminal_public_url("top_pools", network="bsc", params={"page": 2})
    calls = 0
    sleeps: list[float] = []

    def always_limited(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(url, 429, "vendor body sentinel", Message(), None)

    monkeypatch.setattr("urllib.request.urlopen", always_limited)
    monkeypatch.setattr("time.sleep", sleeps.append)

    with pytest.raises(DataError, match="request failed"):
        fetch_geckoterminal_public(url)
    assert calls == 4
    assert sleeps == [2.1, 4.2, 8.4]


def test_keyless_url_variants_are_closed_and_bounded() -> None:
    with pytest.raises(DataError, match="endpoint"):
        geckoterminal_public_url("orders", network="eth", params={})
    with pytest.raises(DataError, match="page"):
        geckoterminal_public_url("top_pools", network="eth", params={"page": 6})
    with pytest.raises(DataError, match="pool address"):
        geckoterminal_public_url("pool", network="eth", params={}, pool_address="../x")
    with pytest.raises(DataError, match="timeframe"):
        geckoterminal_public_url(
            "ohlcv", network="eth", params={}, pool_address="0x1", timeframe="week"
        )
    with pytest.raises(DataError, match="limit"):
        geckoterminal_public_url(
            "ohlcv",
            network="eth",
            params={"limit": 1001},
            pool_address="0x1",
            timeframe="hour",
        )
    assert "/trades" in geckoterminal_public_url(
        "trades", network="eth", params={}, pool_address="0x1"
    )


def test_keyless_envelope_and_pool_validation_fail_loud() -> None:
    for payload in (b"bad", b"[]"):
        with pytest.raises(DataError, match="response"):
            parse_top_pools(payload, network="eth")
    with pytest.raises(DataError, match="pool data"):
        parse_top_pools(b'{"data":{}}', network="eth")
    with pytest.raises(DataError, match="record"):
        parse_top_pools(b'{"data":[{"type":"token"}]}', network="eth")
    bad_pool = {
        "data": [
            {
                "type": "pool",
                "attributes": {"address": "x", "name": "X", "pool_created_at": "bad"},
                "relationships": {},
            }
        ]
    }
    with pytest.raises(DataError, match="activity"):
        parse_top_pools(json.dumps(bad_pool).encode(), network="eth")

    valid_attributes = {
        "address": "0xPool",
        "name": "USDC / WETH",
        "pool_created_at": "2021-12-30T20:32:10Z",
        "base_token_price_usd": "1",
        "quote_token_price_usd": "2000",
        "reserve_in_usd": "1000",
        "volume_usd": {"h24": "100"},
        "transactions": {"h24": {"buys": 1, "sells": 1}},
    }
    relationships = {
        "base_token": {"data": {"id": "eth_0xBase"}},
        "quote_token": {"data": {"id": "eth_0xQuote"}},
        "dex": {"data": {"id": "uniswap_v3"}},
    }
    wrong_pool_id = {
        "data": [
            {
                "id": "eth_0xOther",
                "type": "pool",
                "attributes": valid_attributes,
                "relationships": relationships,
            }
        ]
    }
    with pytest.raises(DataError, match="pool identity"):
        parse_top_pools(json.dumps(wrong_pool_id).encode(), network="eth")

    wrong_token_network = {
        "data": [
            {
                "id": "eth_0xPool",
                "type": "pool",
                "attributes": valid_attributes,
                "relationships": {
                    **relationships,
                    "base_token": {"data": {"id": "bsc_0xBase"}},
                },
            }
        ]
    }
    with pytest.raises(DataError, match="relationship network"):
        parse_top_pools(json.dumps(wrong_token_network).encode(), network="eth")


def test_keyless_ohlcv_and_trade_validation_fail_loud() -> None:
    with pytest.raises(DataError, match="OHLCV data"):
        parse_pool_ohlcv(b'{"data":{}}', network="eth", pool_address="x")
    with pytest.raises(DataError, match="trade data"):
        parse_pool_trades(b'{"data":{}}', network="eth", pool_address="x")
    with pytest.raises(DataError, match="trade record"):
        parse_pool_trades(b'{"data":[{"type":"pool"}]}', network="eth", pool_address="x")
    malformed = {
        "data": [
            {
                "type": "trade",
                "attributes": {
                    "tx_hash": "x",
                    "from_token_address": "a",
                    "to_token_address": "b",
                    "kind": "swap",
                    "block_timestamp": "2026-01-01",
                },
            }
        ]
    }
    with pytest.raises(DataError, match="identity"):
        parse_pool_trades(json.dumps(malformed).encode(), network="eth", pool_address="x")
