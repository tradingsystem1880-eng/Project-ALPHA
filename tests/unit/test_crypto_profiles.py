from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.profiles import CryptoCoverageProfileV1, build_default_coverage_tasks


def _binance_memberships(as_of: datetime) -> tuple[pl.DataFrame, ...]:
    def frame(
        category: str,
        symbols: list[str],
        bases: list[str],
        quotes: list[str],
        contracts: list[str],
        onboard: list[datetime | None],
        delivery: list[datetime | None],
    ) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "fetched_at": [as_of - timedelta(minutes=1)] * len(symbols),
                "category": [category] * len(symbols),
                "symbol": symbols,
                "status": ["TRADING"] * len(symbols),
                "contract_type": contracts,
                "base_asset": bases,
                "quote_asset": quotes,
                "onboard_time": onboard,
                "delivery_time": delivery,
                "contract_size": [100.0 if category == "inverse" else None] * len(symbols),
            }
        )

    return (
        frame("spot", ["BTCUSDT"], ["BTC"], ["USDT"], ["SPOT"], [None], [None]),
        frame(
            "linear",
            ["ETHUSDT", "FUTUREUSDT"],
            ["ETH", "FUTURE"],
            ["USDT", "USDT"],
            ["PERPETUAL", "PERPETUAL"],
            [as_of - timedelta(days=1_000), as_of + timedelta(days=1)],
            [as_of + timedelta(days=10_000), as_of + timedelta(days=10_000)],
        ),
        frame(
            "inverse",
            ["BTCUSD_PERP"],
            ["BTC"],
            ["USD"],
            ["PERPETUAL"],
            [as_of - timedelta(days=1_000)],
            [as_of + timedelta(days=10_000)],
        ),
    )


def test_default_coverage_tasks_are_pit_bounded_and_provider_native() -> None:
    as_of = datetime(2026, 8, 15, tzinfo=UTC)
    linear = pl.DataFrame(
        {
            "status": ["Trading", "Trading", "Trading"],
            "contract_type": ["LinearPerpetual", "LinearFutures", "LinearPerpetual"],
            "symbol": ["BTCUSDT", "BTC-30SEP26", "FUTUREUSDT"],
            "base_coin": ["BTC", "BTC", "FUTURE"],
            "quote_coin": ["USDT", "USDT", "USDT"],
            "launch_time": [
                as_of - timedelta(days=1_000),
                as_of - timedelta(days=100),
                as_of + timedelta(days=1),
            ],
            "delivery_time": [None, as_of + timedelta(days=30), None],
        }
    )
    inverse = pl.DataFrame(
        {
            "status": ["Trading"],
            "contract_type": ["InversePerpetual"],
            "symbol": ["ETHUSD"],
            "base_coin": ["ETH"],
            "quote_coin": ["USD"],
            "launch_time": [as_of - timedelta(days=1_000)],
            "delivery_time": [None],
        }
    )
    options = pl.DataFrame(
        {
            "status": ["Trading", "Trading", "Settled"],
            "symbol": ["BTC-C", "ETH-C", "SOL-C"],
            "base_coin": ["BTC", "ETH", "SOL"],
            "quote_coin": ["USDT", "USDT", "USDT"],
            "launch_time": [as_of - timedelta(days=10)] * 3,
            "delivery_time": [as_of + timedelta(days=10)] * 3,
        }
    )
    option_open_interest = {
        ("BTC", "USDT"): 100.0,
        ("ETH", "USDT"): 200.0,
    }
    hourly_membership = pl.DataFrame(
        {
            "session": [as_of - timedelta(days=1)],
            "rank": [1],
            "category": ["spot"],
            "symbol": ["BTCUSDT"],
            "base_asset": ["BTC"],
            "quote_asset": ["USDT"],
            "liquidity_score": [1_000_000.0],
            "liquidity_units": ["USDT_quote_volume"],
        }
    )

    tasks = build_default_coverage_tasks(
        linear_catalog=linear,
        inverse_catalog=inverse,
        option_catalog=options,
        option_open_interest=option_open_interest,
        as_of=as_of,
        binance_memberships=_binance_memberships(as_of),
        binance_hourly_memberships=(hourly_membership,),
    )

    by_id = {task.task_id: task for task in tasks}
    assert len(by_id) == len(tasks)
    assert not any(task.instrument in {"BTC-30SEP26", "FUTUREUSDT", "SOL"} for task in tasks)
    assert {
        (task.family, task.instrument, task.category, task.cadence)
        for task in tasks
        if task.provider == "bybit" and task.instrument in {"BTCUSDT", "ETHUSD"}
    } >= {
        ("funding", "BTCUSDT", "linear", "funding_interval"),
        ("open_interest", "BTCUSDT", "linear", "hourly"),
        ("long_short_ratio", "ETHUSD", "inverse", "hourly"),
        ("premium_bars", "BTCUSDT", "linear", "hourly"),
    }
    assert {
        (task.instrument, task.cadence) for task in tasks if task.family == "option_quotes"
    } == {
        ("BTC-OPTIONS", "hourly"),
        ("ETH-OPTIONS", "hourly"),
        ("BTC-OPTIONS", "five_minute"),
        ("ETH-OPTIONS", "five_minute"),
    }
    assert (
        sum(task.provider == "geckoterminal" and task.family == "dex_pools" for task in tasks) == 5
    )
    assert any(
        task.provider == "coingecko"
        and task.family == "market_reference"
        and task.instrument == "all"
        for task in tasks
    )
    assert all(task.execution_authority is False for task in tasks)
    assert {
        (task.instrument, task.category, task.frequency)
        for task in tasks
        if task.provider == "binance" and task.family == "market_bars" and task.frequency == "1d"
    } == {
        ("BTCUSDT", "spot", "1d"),
        ("ETHUSDT", "linear", "1d"),
        ("BTCUSD_PERP", "inverse", "1d"),
    }
    assert sum(task.family == "market_membership" for task in tasks) == 3
    assert any(
        task.provider == "binance"
        and task.instrument == "BTCUSDT"
        and task.frequency == "1h"
        and task.cadence == "hourly"
        for task in tasks
    )


def test_option_five_minute_profile_is_limited_to_top_three_aggregate_oi() -> None:
    as_of = datetime(2026, 8, 15, tzinfo=UTC)
    empty_perpetual = pl.DataFrame(
        schema={
            "status": pl.String,
            "contract_type": pl.String,
            "symbol": pl.String,
            "base_coin": pl.String,
            "quote_coin": pl.String,
            "launch_time": pl.Datetime(time_zone="UTC"),
            "delivery_time": pl.Datetime(time_zone="UTC"),
        }
    )
    bases = ["BTC", "ETH", "SOL", "XRP"]
    options = pl.DataFrame(
        {
            "status": ["Trading"] * 4,
            "symbol": [f"{base}-C" for base in bases],
            "base_coin": bases,
            "quote_coin": ["USDT"] * 4,
            "launch_time": [as_of - timedelta(days=10)] * 4,
            "delivery_time": [as_of + timedelta(days=10)] * 4,
        }
    )
    tasks = build_default_coverage_tasks(
        linear_catalog=empty_perpetual,
        inverse_catalog=empty_perpetual,
        option_catalog=options,
        option_open_interest={
            ("BTC", "USDT"): 100.0,
            ("ETH", "USDT"): 400.0,
            ("SOL", "USDT"): 300.0,
            ("XRP", "USDT"): 200.0,
        },
        as_of=as_of,
    )
    fast = [task.instrument for task in tasks if task.cadence == "five_minute"]
    assert fast == ["ETH-OPTIONS", "SOL-OPTIONS", "XRP-OPTIONS"]

    profile = CryptoCoverageProfileV1.create(
        as_of=as_of,
        source_manifest_ids=("a" * 64, "b" * 64, "c" * 64),
        tasks=tasks,
    )
    assert CryptoCoverageProfileV1.from_dict(profile.to_dict()) == profile
    forged = profile.to_dict() | {"profile_id": "f" * 64}
    with pytest.raises(DataError, match="identity"):
        CryptoCoverageProfileV1.from_dict(forged)
    with pytest.raises(DataError, match="open-interest coverage"):
        build_default_coverage_tasks(
            linear_catalog=empty_perpetual,
            inverse_catalog=empty_perpetual,
            option_catalog=options,
            option_open_interest={("BTC", "USDT"): 100.0},
            as_of=as_of,
        )
