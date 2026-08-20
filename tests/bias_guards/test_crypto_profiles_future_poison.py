"""Future-poison guards for the three crypto universe selectors (survivorship both ways)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from alpha_data.crypto.profiles import (
    _active_perpetuals,
    active_binance_markets,
    active_option_markets,
)

AS_OF = datetime(2026, 8, 15, tzinfo=UTC)
LATER = AS_OF + timedelta(hours=1)


def _perpetuals(*, poisoned: bool) -> pl.DataFrame:
    rows = [
        {
            "fetched_at": AS_OF - timedelta(minutes=1),
            "status": "Trading",
            "contract_type": "LinearPerpetual",
            "symbol": "BTCUSDT",
            "base_coin": "BTC",
            "quote_coin": "USDT",
            "launch_time": AS_OF - timedelta(days=1_000),
            "delivery_time": None,
        }
    ]
    if poisoned:
        rows.append(
            {
                "fetched_at": LATER,
                "status": "Trading",
                "contract_type": "LinearPerpetual",
                "symbol": "AAAUSDT",
                "base_coin": "AAA",
                "quote_coin": "USDT",
                "launch_time": AS_OF - timedelta(days=1),
                "delivery_time": None,
            }
        )
    return pl.DataFrame(rows)


def _options(*, poisoned: bool) -> pl.DataFrame:
    rows = [
        {
            "fetched_at": AS_OF - timedelta(minutes=1),
            "status": "Trading",
            "symbol": "BTC-C",
            "base_coin": "BTC",
            "quote_coin": "USDT",
            "launch_time": AS_OF - timedelta(days=10),
            "delivery_time": AS_OF + timedelta(days=10),
        }
    ]
    if poisoned:
        rows.append(
            {
                "fetched_at": LATER,
                "status": "Trading",
                "symbol": "AAA-C",
                "base_coin": "AAA",
                "quote_coin": "USDT",
                "launch_time": AS_OF - timedelta(days=10),
                "delivery_time": AS_OF + timedelta(days=10),
            }
        )
    return pl.DataFrame(rows)


def _memberships(*, poisoned: bool) -> tuple[pl.DataFrame, ...]:
    def frame(category: str, symbol: str, base: str, contract: str) -> pl.DataFrame:
        rows = [
            {
                "fetched_at": AS_OF - timedelta(minutes=1),
                "category": category,
                "symbol": symbol,
                "status": "TRADING",
                "contract_type": contract,
                "base_asset": base,
                "quote_asset": "USDT" if category != "inverse" else "USD",
                "onboard_time": AS_OF - timedelta(days=1_000),
                "delivery_time": None,
                "contract_size": 100.0 if category == "inverse" else None,
            }
        ]
        if poisoned:
            rows.append(
                rows[0]
                | {
                    "fetched_at": LATER,
                    "symbol": f"AAA{symbol}",
                    "base_asset": "AAA",
                }
            )
        return pl.DataFrame(rows)

    return (
        frame("spot", "BTCUSDT", "BTC", "SPOT"),
        frame("linear", "ETHUSDT", "ETH", "PERPETUAL"),
        frame("inverse", "BTCUSD_PERP", "BTC", "PERPETUAL"),
    )


@pytest.mark.bias_guard
def test_active_perpetuals_ignore_catalog_rows_fetched_after_as_of() -> None:
    """Knowledge time gates the universe: a later catalog fetch is unknowable at ``as_of``."""
    clean = _active_perpetuals(_perpetuals(poisoned=False), category="linear", as_of=AS_OF)
    poisoned = _active_perpetuals(_perpetuals(poisoned=True), category="linear", as_of=AS_OF)

    assert clean == (("BTCUSDT", "BTC", "USDT", "linear"),)
    assert poisoned == clean
    assert _active_perpetuals(_perpetuals(poisoned=True), category="linear", as_of=LATER) != clean


@pytest.mark.bias_guard
def test_active_option_markets_ignore_catalog_rows_fetched_after_as_of() -> None:
    clean = active_option_markets(_options(poisoned=False), as_of=AS_OF)
    poisoned = active_option_markets(_options(poisoned=True), as_of=AS_OF)

    assert clean == (("BTC", "USDT"),)
    assert poisoned == clean
    assert active_option_markets(_options(poisoned=True), as_of=LATER) != clean


@pytest.mark.bias_guard
def test_active_binance_markets_ignore_catalog_rows_fetched_after_as_of() -> None:
    clean = active_binance_markets(_memberships(poisoned=False), as_of=AS_OF)
    poisoned = active_binance_markets(_memberships(poisoned=True), as_of=AS_OF)

    assert clean == (
        ("BTCUSD_PERP", "BTC", "USD", "inverse"),
        ("ETHUSDT", "ETH", "USDT", "linear"),
        ("BTCUSDT", "BTC", "USDT", "spot"),
    )
    assert poisoned == clean
    assert active_binance_markets(_memberships(poisoned=True), as_of=LATER) != clean
