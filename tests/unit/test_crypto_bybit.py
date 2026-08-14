from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.providers.bybit import (
    bybit_public_url,
    fetch_bybit_public,
    parse_funding_history,
    parse_historical_volatility,
    parse_instruments,
    parse_long_short_ratio,
    parse_open_interest,
    parse_option_tickers,
    parse_price_klines,
    price_bundle_diagnostics,
)
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

_TEST_VOLUME_UUID = "758CBD77-1003-3BA3-AD28-1D647F5E2A08"


def _payload(result: object, *, time: int = 1_787_878_400_000) -> bytes:
    return json.dumps({"retCode": 0, "retMsg": "OK", "result": result, "time": time}).encode()


def test_option_chain_preserves_provider_iv_greeks_and_market_diagnostics() -> None:
    payload = _payload(
        {
            "category": "option",
            "list": [
                {
                    "symbol": "BTC-29AUG26-100000-C",
                    "bid1Price": "2",
                    "bid1Size": "3",
                    "ask1Price": "1",
                    "ask1Size": "4",
                    "markPrice": "1.5",
                    "indexPrice": "90000",
                    "underlyingPrice": "90001",
                    "bid1Iv": "0.5",
                    "ask1Iv": "0.6",
                    "markIv": "0.55",
                    "delta": "0.4",
                    "gamma": "0.0001",
                    "vega": "12",
                    "theta": "-3",
                    "openInterest": "100",
                    "turnover24h": "42",
                    "volume24h": "7",
                }
            ],
            "nextPageCursor": "",
        }
    )
    frame, cursor = parse_option_tickers(payload, fetched_at_ms=1_787_878_400_000)

    assert cursor is None
    row = frame.row(0, named=True)
    assert row["mark_iv"] == 0.55
    assert row["delta"] == 0.4
    assert row["open_interest"] == 100.0
    assert row["crossed_market"] is True
    assert row["stale_snapshot"] is False
    assert row["server_lag_ms"] == 0


def test_instrument_catalog_retains_lifecycle_funding_and_option_identity() -> None:
    linear, cursor = parse_instruments(
        _payload(
            {
                "category": "linear",
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "contractType": "LinearPerpetual",
                        "status": "Trading",
                        "baseCoin": "BTC",
                        "quoteCoin": "USDT",
                        "settleCoin": "USDT",
                        "launchTime": "1585526400000",
                        "deliveryTime": "0",
                        "fundingInterval": 480,
                        "priceFilter": {"tickSize": "0.1"},
                        "lotSizeFilter": {"qtyStep": "0.001"},
                    }
                ],
                "nextPageCursor": "page-2",
            }
        ),
        category="linear",
        fetched_at_ms=1_787_878_400_000,
    )
    option, _ = parse_instruments(
        _payload(
            {
                "category": "option",
                "list": [
                    {
                        "symbol": "BTC-29AUG26-100000-C",
                        "optionsType": "Call",
                        "status": "Trading",
                        "baseCoin": "BTC",
                        "quoteCoin": "USD",
                        "settleCoin": "USDC",
                        "launchTime": "1750000000000",
                        "deliveryTime": "1787961600000",
                        "priceFilter": {"tickSize": "5"},
                        "lotSizeFilter": {"qtyStep": "0.01"},
                    }
                ],
            }
        ),
        category="option",
        fetched_at_ms=1_787_878_400_000,
    )

    assert cursor == "page-2"
    assert linear.row(0, named=True)["funding_interval_minutes"] == 480
    option_row = option.row(0, named=True)
    assert option_row["expiry_code"] == "29AUG26"
    assert option_row["strike_price"] == 100000.0
    assert option_row["option_kind"] == "call"

    usdt_option, _ = parse_instruments(
        _payload(
            {
                "category": "option",
                "list": [
                    {
                        "symbol": "BTC-25JUN27-150000-P-USDT",
                        "optionsType": "Put",
                        "status": "PreLaunch",
                        "baseCoin": "BTC",
                        "quoteCoin": "USDT",
                        "settleCoin": "USDT",
                        "launchTime": "1783584000000",
                        "deliveryTime": "1813910400000",
                        "priceFilter": {"tickSize": "5"},
                        "lotSizeFilter": {"qtyStep": "0.01"},
                    }
                ],
            }
        ),
        category="option",
        fetched_at_ms=1_787_878_400_000,
    )
    assert usdt_option.row(0, named=True)["option_kind"] == "put"


def test_derivatives_histories_preserve_native_units_and_pagination() -> None:
    funding = parse_funding_history(
        _payload(
            {
                "category": "linear",
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "fundingRate": "0.0001",
                        "fundingRateTimestamp": "1787875200000",
                    }
                ],
            }
        )
    )
    open_interest, oi_cursor = parse_open_interest(
        _payload(
            {
                "category": "inverse",
                "symbol": "BTCUSD",
                "list": [{"openInterest": "63910691", "timestamp": "1787875200000"}],
                "nextPageCursor": "older",
            }
        )
    )
    ratios, ratio_cursor = parse_long_short_ratio(
        _payload(
            {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "buyRatio": "0.49",
                        "sellRatio": "0.51",
                        "timestamp": "1787875200000",
                    }
                ],
                "nextPageCursor": "",
            }
        ),
        category="linear",
    )

    assert funding.row(0, named=True)["funding_rate"] == 0.0001
    assert open_interest.row(0, named=True)["unit_rule"] == "quote_coin"
    assert oi_cursor == "older"
    assert ratios.row(0, named=True)["long_short_ratio"] == pytest.approx(0.49 / 0.51)
    assert ratio_cursor is None


def test_price_kline_families_and_hourly_volatility_are_distinct() -> None:
    mark = parse_price_klines(
        _payload(
            {
                "category": "linear",
                "symbol": "BTCUSDT",
                "list": [["1787875200000", "10", "12", "9", "11"]],
            }
        ),
        family="mark",
    )
    trade = parse_price_klines(
        _payload(
            {
                "category": "linear",
                "symbol": "BTCUSDT",
                "list": [["1787875200000", "10", "12", "9", "11", "4", "44"]],
            }
        ),
        family="trade",
    )
    volatility = parse_historical_volatility(
        _payload([{"period": 30, "value": "0.45024716", "time": "1787875200000"}]),
        base_coin="BTC",
        quote_coin="USD",
    )

    assert mark.row(0, named=True)["family"] == "mark"
    assert mark.row(0, named=True)["volume"] is None
    assert trade.row(0, named=True)["turnover"] == 44.0
    assert volatility.row(0, named=True)["volatility"] == 0.45024716


def test_mark_index_premium_diagnostics_preserve_reported_and_observed_values() -> None:
    def frame(family: Literal["mark", "index", "premium"], close: str) -> pl.DataFrame:
        return parse_price_klines(
            _payload(
                {
                    "category": "linear",
                    "symbol": "BTCUSDT",
                    "list": [["1787875200000", close, close, close, close]],
                }
            ),
            family=family,
        )

    diagnostics = price_bundle_diagnostics(
        mark=frame("mark", "101"),
        index=frame("index", "100"),
        premium=frame("premium", "0.008"),
    )

    row = diagnostics.row(0, named=True)
    assert row["observed_mark_index_basis"] == pytest.approx(0.01)
    assert row["reported_premium"] == 0.008
    assert row["basis_premium_difference"] == pytest.approx(0.002)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda: parse_option_tickers(
                b'{"retCode":10001,"retMsg":"secret vendor body","result":{}}',
                fetched_at_ms=1,
            ),
            "reported an error",
        ),
        (
            lambda: parse_long_short_ratio(
                _payload(
                    {
                        "list": [
                            {
                                "symbol": "BTCUSDT",
                                "buyRatio": "1.1",
                                "sellRatio": "-0.1",
                                "timestamp": "1787875200000",
                            }
                        ]
                    }
                ),
                category="linear",
            ),
            "ratios",
        ),
        (
            lambda: parse_price_klines(
                _payload(
                    {
                        "category": "linear",
                        "symbol": "BTCUSDT",
                        "list": [["1787875200000", "10", "8", "9", "11"]],
                    }
                ),
                family="mark",
            ),
            "OHLC",
        ),
    ],
)
def test_malformed_or_impossible_provider_values_fail_loud(
    call: Callable[[], object], message: str
) -> None:
    with pytest.raises(DataError, match=message):
        call()


def test_public_url_is_closed_to_supported_read_only_market_endpoints() -> None:
    assert bybit_public_url(
        "open_interest", {"category": "linear", "symbol": "BTCUSDT", "limit": 200}
    ) == ("https://api.bybit.com/v5/market/open-interest?category=linear&limit=200&symbol=BTCUSDT")
    with pytest.raises(DataError, match="unsupported Bybit public endpoint"):
        bybit_public_url("create_order", {"symbol": "BTCUSDT"})
    with pytest.raises(DataError, match="unsupported Bybit query parameters"):
        bybit_public_url("open_interest", {"apiKey": "not-allowed"})
    with pytest.raises(DataError, match="unsupported value"):
        bybit_public_url("open_interest", {"limit": True})


def test_public_fetch_is_bounded_and_returns_exact_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = _payload({"category": "linear", "list": [{"symbol": "BTCUSDT"}]})

    class Response:
        headers = {"Content-Type": "application/json; charset=utf-8"}

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self, _: int) -> bytes:
            return expected

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: Response())

    assert fetch_bybit_public("funding", {"category": "linear"}) == expected
    with pytest.raises(DataError, match="timeout"):
        fetch_bybit_public("funding", {}, timeout_seconds=0)


def test_public_fetch_rejects_wrong_mime_and_oversize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def __init__(self, *, content_type: str, payload: bytes) -> None:
            self.headers = {"Content-Type": content_type}
            self._payload = payload

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self, _: int) -> bytes:
            return self._payload

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: Response(content_type="text/html", payload=b"blocked"),
    )
    with pytest.raises(DataError, match="MIME"):
        fetch_bybit_public("funding", {})

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: Response(
            content_type="application/json", payload=b"x" * (8 * 1024 * 1024 + 1)
        ),
    )
    with pytest.raises(DataError, match="byte limit"):
        fetch_bybit_public("funding", {})


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"[]",
        b'{"retCode":0}',
        b'{"retCode":0,"result":{},"time":"bad"}',
        b'{"retCode":0,"result":[]}',
        b'{"retCode":0,"result":{"category":"linear","list":[]}}',
        b'{"retCode":0,"result":{"category":"linear","list":[1]}}',
    ],
)
def test_invalid_envelopes_and_record_lists_fail_loud(payload: bytes) -> None:
    with pytest.raises(DataError, match="Bybit"):
        parse_funding_history(payload)


def test_invalid_cursor_and_duplicate_observation_fail_loud() -> None:
    bad_cursor = _payload(
        {
            "category": "inverse",
            "symbol": "BTCUSD",
            "list": [{"openInterest": "1", "timestamp": "1787875200000"}],
            "nextPageCursor": 7,
        }
    )
    duplicate = _payload(
        {
            "category": "linear",
            "list": [
                {
                    "symbol": "BTCUSDT",
                    "fundingRate": "0.1",
                    "fundingRateTimestamp": "1787875200000",
                },
                {
                    "symbol": "BTCUSDT",
                    "fundingRate": "0.2",
                    "fundingRateTimestamp": "1787875200000",
                },
            ],
        }
    )
    with pytest.raises(DataError, match="cursor"):
        parse_open_interest(bad_cursor)
    with pytest.raises(DataError, match="duplicate"):
        parse_funding_history(duplicate)


@pytest.mark.parametrize(
    ("mutations", "message"),
    [
        ({"deliveryTime": "1500000000000"}, "delivery precedes launch"),
        ({"launchTime": "1999999999999", "deliveryTime": "0"}, "launch is in the future"),
        ({"fundingInterval": 0}, "funding interval"),
        ({"priceFilter": None}, "filters"),
        ({"symbol": "BTC-BAD-C"}, "option symbol"),
        ({"symbol": "BTC-29AUG26-100000-C-USDC"}, "option symbol"),
        ({"symbol": "BTC-29AUG26-NAN-C"}, "strike"),
        ({"optionsType": "Put"}, "option type"),
    ],
)
def test_instrument_lifecycle_and_option_identity_fail_closed(
    mutations: dict[str, object], message: str
) -> None:
    record: dict[str, object] = {
        "symbol": "BTC-29AUG26-100000-C",
        "optionsType": "Call",
        "status": "Trading",
        "baseCoin": "BTC",
        "quoteCoin": "USD",
        "settleCoin": "USDC",
        "launchTime": "1750000000000",
        "deliveryTime": "1787961600000",
        "fundingInterval": 480,
        "priceFilter": {"tickSize": "5"},
        "lotSizeFilter": {"qtyStep": "0.01"},
    }
    record.update(mutations)
    payload = _payload({"category": "option", "list": [record]})
    with pytest.raises(DataError, match=message):
        parse_instruments(payload, category="option", fetched_at_ms=1_787_878_400_000)


def test_category_and_numeric_boundaries_fail_closed() -> None:
    spot_funding = _payload(
        {
            "category": "spot",
            "list": [
                {
                    "symbol": "BTCUSDT",
                    "fundingRate": "0.1",
                    "fundingRateTimestamp": "1787875200000",
                }
            ],
        }
    )
    bad_oi = _payload(
        {
            "category": "inverse",
            "symbol": "BTCUSD",
            "list": [
                {
                    "openInterest": "1",
                    "singleOpenInterest": "2",
                    "timestamp": "1787875200000",
                }
            ],
        }
    )
    zero_short = _payload(
        {
            "list": [
                {
                    "symbol": "BTCUSDT",
                    "buyRatio": "1",
                    "sellRatio": "0",
                    "timestamp": "1787875200000",
                }
            ]
        }
    )
    with pytest.raises(DataError, match="funding category"):
        parse_funding_history(spot_funding)
    with pytest.raises(DataError, match="open interest"):
        parse_open_interest(bad_oi)
    with pytest.raises(DataError, match="cannot be zero"):
        parse_long_short_ratio(zero_short, category="linear")


def test_kline_volatility_and_option_numeric_boundaries_fail_closed() -> None:
    negative_trade = _payload(
        {
            "category": "linear",
            "symbol": "BTCUSDT",
            "list": [["1787875200000", "10", "12", "9", "11", "-1", "44"]],
        }
    )
    non_hourly_vol = _payload([{"period": 30, "value": "0.4", "time": "1787875200001"}])
    bad_delta = _payload(
        {
            "category": "option",
            "list": [{"symbol": "BTC-X", "delta": "2"}],
        }
    )
    future_server = _payload({"category": "option", "list": [{"symbol": "BTC-X"}]}, time=2_000_000)
    with pytest.raises(DataError, match="non-negative"):
        parse_price_klines(negative_trade, family="trade")
    with pytest.raises(DataError, match="hourly numeric bounds"):
        parse_historical_volatility(non_hourly_vol, base_coin="BTC", quote_coin="USD")
    with pytest.raises(DataError, match="delta"):
        parse_option_tickers(bad_delta, fetched_at_ms=1_787_878_400_000)
    with pytest.raises(DataError, match="later than the fetch clock"):
        parse_option_tickers(future_server, fetched_at_ms=1)


@pytest.mark.parametrize(
    "record",
    [
        {"symbol": "BTC-X", "bid1Price": True},
        {"symbol": "BTC-X", "bid1Price": "bad"},
        {"symbol": "BTC-X", "bid1Price": "inf"},
        {"symbol": "BTC-X", "openInterest": "-1"},
        {"bid1Price": "1"},
    ],
)
def test_option_ticker_invalid_field_types_fail_loud(record: dict[str, object]) -> None:
    with pytest.raises(DataError, match="Bybit"):
        parse_option_tickers(
            _payload({"category": "option", "list": [record]}),
            fetched_at_ms=1_787_878_400_000,
        )


def test_invalid_category_timestamp_and_row_shapes_fail_loud() -> None:
    mismatched = _payload({"category": "spot", "list": [{"symbol": "BTC-X"}]})
    missing_symbol = _payload(
        {"category": "linear", "list": [["1787875200000", "1", "2", "0", "1"]]}
    )
    malformed_row = _payload({"category": "linear", "symbol": "BTC", "list": [["1"]]})
    missing_oi_symbol = _payload(
        {"category": "linear", "list": [{"openInterest": "1", "timestamp": "1"}]}
    )
    with pytest.raises(DataError, match="does not match"):
        parse_instruments(mismatched, category="option", fetched_at_ms=1_787_878_400_000)
    with pytest.raises(DataError, match="timestamp"):
        parse_option_tickers(
            _payload({"category": "option", "list": [{"symbol": "BTC-X"}]}),
            fetched_at_ms=-1,
        )
    with pytest.raises(DataError, match="kline symbol"):
        parse_price_klines(missing_symbol, family="mark")
    with pytest.raises(DataError, match="row is malformed"):
        parse_price_klines(malformed_row, family="mark")
    with pytest.raises(DataError, match="open-interest symbol"):
        parse_open_interest(missing_oi_symbol)


def test_volatility_object_shape_and_identity_are_validated() -> None:
    object_payload = _payload({"list": [{"period": 30, "value": "0.4", "time": "1787875200000"}]})
    assert (
        parse_historical_volatility(object_payload, base_coin="BTC", quote_coin="USD").height == 1
    )
    with pytest.raises(DataError, match="contains no records"):
        parse_historical_volatility(_payload([]), base_coin="BTC", quote_coin="USD")
    with pytest.raises(DataError, match="identity"):
        parse_historical_volatility(object_payload, base_coin="btc", quote_coin="USD")


def test_exact_same_receipt_bytes_replay_to_identical_frames() -> None:
    payload = _payload(
        {
            "category": "linear",
            "list": [
                {
                    "symbol": "BTCUSDT",
                    "fundingRate": "0.0001",
                    "fundingRateTimestamp": "1787875200000",
                }
            ],
        }
    )

    first = parse_funding_history(payload)
    second = parse_funding_history(payload)

    assert first.equals(second)
    assert first["timestamp"].to_list() == [datetime(2026, 8, 28, tzinfo=UTC)]


def test_perpetual_and_option_receipts_freeze_verify_and_replay_exactly(
    tmp_path: Path,
) -> None:
    bulk_root = tmp_path / "bulk"
    bulk_root.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk_root,
        manifest_root=tmp_path / "internal" / "manifests",
        expected_volume_uuid=_TEST_VOLUME_UUID,
        volume_uuid=lambda _: _TEST_VOLUME_UUID,
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=1_000_000),
        reserve_fraction=0.15,
        minimum_free_bytes=100,
    )
    receipts = {
        "funding.json": _payload(
            {
                "category": "linear",
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "fundingRate": "0.0001",
                        "fundingRateTimestamp": "1787875200000",
                    }
                ],
            }
        ),
        "option-chain.json": _payload(
            {
                "category": "option",
                "list": [
                    {
                        "symbol": "BTC-29AUG26-100000-C",
                        "markIv": "0.55",
                        "delta": "0.4",
                        "openInterest": "100",
                    }
                ],
            }
        ),
    }
    manifests: dict[str, dict[str, object]] = {}
    for logical_name, payload in receipts.items():
        receipt_id = hashlib.sha256(payload).hexdigest()
        handle = store.begin_staging(
            provider="bybit",
            receipt_id=receipt_id,
            logical_name=logical_name,
            expected_bytes=len(payload),
        )
        handle = store.append_staging(handle, payload)
        manifests[logical_name] = store.publish_staging(handle, expected_sha256=receipt_id)

    funding_manifest = store.verify_manifest(manifests["funding.json"]["manifest_id"])
    option_manifest = store.verify_manifest(manifests["option-chain.json"]["manifest_id"])
    frozen_funding = (store.bulk_root / str(funding_manifest["artifact_key"])).read_bytes()
    frozen_options = (store.bulk_root / str(option_manifest["artifact_key"])).read_bytes()

    assert parse_funding_history(frozen_funding).equals(
        parse_funding_history(receipts["funding.json"])
    )
    replayed, _ = parse_option_tickers(frozen_options, fetched_at_ms=1_787_878_400_000)
    original, _ = parse_option_tickers(
        receipts["option-chain.json"], fetched_at_ms=1_787_878_400_000
    )
    assert replayed.equals(original)
