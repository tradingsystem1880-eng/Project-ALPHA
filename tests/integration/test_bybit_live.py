"""Bounded live smoke for Bybit public derivatives and option schemas."""

from __future__ import annotations

import json

import pytest

from alpha_data.crypto.providers.bybit import (
    fetch_bybit_public,
    parse_funding_history,
    parse_historical_volatility,
    parse_instruments,
    parse_long_short_ratio,
    parse_open_interest,
    parse_option_tickers,
    parse_price_klines,
)

pytestmark = pytest.mark.network


def test_bybit_public_btc_perpetual_and_option_bundle() -> None:
    catalog_raw = fetch_bybit_public("instruments", {"category": "linear", "symbol": "BTCUSDT"})
    catalog_time = int(json.loads(catalog_raw)["time"])
    catalog, _ = parse_instruments(catalog_raw, category="linear", fetched_at_ms=catalog_time)
    assert catalog.height == 1

    assert (
        parse_funding_history(
            fetch_bybit_public("funding", {"category": "linear", "symbol": "BTCUSDT", "limit": 2})
        ).height
        == 2
    )
    open_interest, _ = parse_open_interest(
        fetch_bybit_public(
            "open_interest",
            {"category": "linear", "symbol": "BTCUSDT", "intervalTime": "1h", "limit": 2},
        )
    )
    assert open_interest.height == 2
    ratios, _ = parse_long_short_ratio(
        fetch_bybit_public(
            "long_short_ratio",
            {"category": "linear", "symbol": "BTCUSDT", "period": "1h", "limit": 2},
        ),
        category="linear",
    )
    assert ratios.height == 2
    assert (
        parse_price_klines(
            fetch_bybit_public(
                "mark_kline",
                {"category": "linear", "symbol": "BTCUSDT", "interval": "60", "limit": 2},
            ),
            family="mark",
        ).height
        == 2
    )

    assert (
        parse_historical_volatility(
            fetch_bybit_public(
                "historical_volatility",
                {"category": "option", "baseCoin": "BTC", "quoteCoin": "USDT"},
            ),
            base_coin="BTC",
            quote_coin="USDT",
        ).height
        >= 1
    )
    option_catalog_raw = fetch_bybit_public(
        "instruments", {"category": "option", "baseCoin": "BTC", "limit": 1}
    )
    option_time = int(json.loads(option_catalog_raw)["time"])
    option_catalog, _ = parse_instruments(
        option_catalog_raw, category="option", fetched_at_ms=option_time
    )
    option_symbol = str(option_catalog.row(0, named=True)["symbol"])
    ticker_raw = fetch_bybit_public(
        "option_tickers", {"category": "option", "symbol": option_symbol}
    )
    ticker_time = int(json.loads(ticker_raw)["time"])
    tickers, _ = parse_option_tickers(ticker_raw, fetched_at_ms=ticker_time)
    assert tickers.height == 1
