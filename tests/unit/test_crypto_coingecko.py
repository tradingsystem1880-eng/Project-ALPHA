from __future__ import annotations

import json
import urllib.error
from datetime import UTC, datetime
from email.message import Message
from urllib.request import Request

import pytest

from alpha_core import DataError
from alpha_data.crypto.providers.coingecko import (
    coingecko_demo_request,
    fetch_coingecko_demo,
    parse_asset_catalog,
    parse_market_universe,
)


def test_demo_request_uses_header_and_closed_bounded_query() -> None:
    request = coingecko_demo_request(
        "markets", {"vs_currency": "usd", "per_page": 250, "page": 1}, api_key="secret"
    )
    assert request.full_url.startswith("https://api.coingecko.com/api/v3/coins/markets?")
    assert "secret" not in request.full_url
    assert request.get_header("X-cg-demo-api-key") == "secret"
    with pytest.raises(DataError, match="unsupported CoinGecko"):
        coingecko_demo_request("markets", {"x_cg_demo_api_key": "leak"}, api_key="secret")


def test_market_universe_preserves_reference_units_and_nulls() -> None:
    payload = json.dumps(
        [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "current_price": 60000,
                "market_cap": 1_200_000,
                "market_cap_rank": 1,
                "fully_diluted_valuation": None,
                "total_volume": 100,
                "circulating_supply": 20,
                "total_supply": 21,
                "max_supply": 21,
                "last_updated": "2026-08-14T00:00:00Z",
            }
        ]
    ).encode()
    frame = parse_market_universe(
        payload, vs_currency="usd", fetched_at=datetime(2026, 8, 15, tzinfo=UTC)
    )
    row = frame.row(0, named=True)
    assert row["coingecko_id"] == "bitcoin"
    assert row["quote_asset"] == "USD"
    assert row["fully_diluted_valuation"] is None


def test_asset_catalog_explodes_contracts_without_ticker_join() -> None:
    payload = json.dumps(
        [
            {
                "id": "usd-coin",
                "symbol": "usdc",
                "name": "USDC",
                "platforms": {
                    "ethereum": "0xA0B8",
                    "solana": "EPjF",
                },
            }
        ]
    ).encode()
    frame = parse_asset_catalog(payload)
    assert set(frame["network"]) == {"ethereum", "solana"}
    assert set(frame["contract_address"]) == {"0xa0b8", "epjf"}


def test_asset_catalog_does_not_lose_contract_identity_when_optional_symbol_is_empty() -> None:
    payload = json.dumps(
        [{"id": "contract-only", "symbol": "", "name": "Contract", "platforms": {"base": "0x1"}}]
    ).encode()
    row = parse_asset_catalog(payload).row(0, named=True)
    assert row["coingecko_id"] == "contract-only"
    assert row["symbol"] == ""


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


def test_demo_fetch_is_bounded_and_host_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    request = coingecko_demo_request("ping", {}, api_key="key")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: _Response(b"{}"))
    assert fetch_coingecko_demo(request) == b"{}"
    with pytest.raises(DataError, match="timeout"):
        fetch_coingecko_demo(request, timeout_seconds=0)
    with pytest.raises(DataError, match="host"):
        fetch_coingecko_demo(Request("https://example.com/api/v3/ping"))
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: _Response(b"x", "text/html")
    )
    with pytest.raises(DataError, match="MIME"):
        fetch_coingecko_demo(request)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(b"x" * (8 * 1024 * 1024 + 1)),
    )
    with pytest.raises(DataError, match="byte limit"):
        fetch_coingecko_demo(request)
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError())
    )
    with pytest.raises(DataError, match="request failed"):
        fetch_coingecko_demo(request)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError(request.full_url, 401, "private vendor detail", Message(), None)
        ),
    )
    with pytest.raises(DataError, match="HTTP 401") as failure:
        fetch_coingecko_demo(request)
    assert "private vendor detail" not in str(failure.value)


def test_demo_request_and_payload_validation_fail_loud() -> None:
    with pytest.raises(DataError, match="endpoint"):
        coingecko_demo_request("orders", {}, api_key="key")
    with pytest.raises(DataError, match="not injected"):
        coingecko_demo_request("ping", {}, api_key="")
    with pytest.raises(DataError, match="coin id"):
        coingecko_demo_request("coin_detail", {}, api_key="key", coin_id="../btc")
    assert (
        "/coins/bitcoin"
        in coingecko_demo_request("coin_detail", {}, api_key="key", coin_id="bitcoin").full_url
    )
    invalid_queries: tuple[dict[str, str | int | bool], ...] = (
        {"page": 0},
        {"per_page": 251},
        {"page": True},
    )
    for params in invalid_queries:
        with pytest.raises(DataError, match="page"):
            coingecko_demo_request("markets", params, api_key="key")
    for payload in (b"bad", b"{}", b"[1]"):
        with pytest.raises(DataError, match="CoinGecko"):
            parse_asset_catalog(payload)


def test_market_and_catalog_field_validation_fail_loud() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(DataError, match="timezone"):
        parse_market_universe(b"[]", vs_currency="usd", fetched_at=datetime(2026, 1, 1))
    with pytest.raises(DataError, match="quote"):
        parse_market_universe(b"[]", vs_currency=" ", fetched_at=now)
    base: dict[str, object] = {
        "id": "btc",
        "symbol": "btc",
        "name": "Bitcoin",
        "last_updated": "bad",
    }
    with pytest.raises(DataError, match="timestamp"):
        parse_market_universe(json.dumps([base]).encode(), vs_currency="usd", fetched_at=now)
    base["last_updated"] = "2026-01-01T00:00:00Z"
    base["current_price"] = float("inf")
    with pytest.raises(DataError, match="finite"):
        parse_market_universe(json.dumps([base]).encode(), vs_currency="usd", fetched_at=now)
    with pytest.raises(DataError, match="platforms"):
        parse_asset_catalog(b'[{"id":"x","symbol":"x","name":"X","platforms":[]}]')
