from __future__ import annotations

import json

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
            "data": {"attributes": {"ohlcv_list": [[1700000000, 1, 2, 0.5, 1.5, 10]]}},
            "meta": {
                "base": {"address": "0xBase", "coingecko_coin_id": "base"},
                "quote": {"address": "0xQuote", "coingecko_coin_id": "quote"},
            },
        }
    ).encode()
    row = parse_pool_ohlcv(payload, network="eth", pool_address="0xPool").row(0, named=True)
    assert row["base_token_address"] == "0xbase"
    assert row["quote_token_address"] == "0xquote"
    assert row["volume_usd"] == 10.0


def test_pool_trades_preserve_transaction_and_contract_identity() -> None:
    payload = json.dumps(
        {
            "data": [
                {
                    "id": "eth_trade",
                    "type": "trade",
                    "attributes": {
                        "block_number": 123,
                        "tx_hash": "0xabc",
                        "from_token_amount": "0.1",
                        "to_token_amount": "200",
                        "price_from_in_usd": "2000",
                        "price_to_in_usd": "1",
                        "block_timestamp": "2026-08-14T00:00:00Z",
                        "kind": "buy",
                        "volume_in_usd": "200",
                        "from_token_address": "0xFrom",
                        "to_token_address": "0xTo",
                    },
                }
            ]
        }
    ).encode()
    row = parse_pool_trades(payload, network="eth", pool_address="0xPool").row(0, named=True)
    assert row["tx_hash"] == "0xabc"
    assert row["from_token_address"] == "0xfrom"
    assert row["kind"] == "buy"


class _Response:
    def __init__(self, payload: bytes, mime: str = "application/json") -> None:
        self.payload = payload
        self.headers = {"Content-Type": mime}

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return self.payload


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
