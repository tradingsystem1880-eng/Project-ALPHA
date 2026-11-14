"""Time-bar syntax, provider encodings and the UTC-midnight alignment contract."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from alpha_core import DataError
from alpha_data.adapters.base import DatasetIdentity
from alpha_data.timeframe import DAILY, BarTimeframe, parse_timeframe, store_dir


@pytest.mark.parametrize("text", ["1D", "1d", "D1", "1day", "day", "daily", " DAILY "])
def test_daily_spellings(text: str) -> None:
    assert parse_timeframe(text) == DAILY


@pytest.mark.parametrize("text", ["5m", "5min", "5minute", "5minutes", "5T", "M5", " 5MINUTES "])
def test_minute_spellings(text: str) -> None:
    assert parse_timeframe(text) == BarTimeframe(5)


@pytest.mark.parametrize("text", ["2h", "2hour", "2hours", "2H", "H2", " 2HOURS ", "120m"])
def test_hour_spellings(text: str) -> None:
    assert parse_timeframe(text) == BarTimeframe(120)


@pytest.mark.parametrize("minutes", [*range(1, 60), *range(60, 1441, 60)])
def test_roundtrip_and_properties(minutes: int) -> None:
    tf = BarTimeframe(minutes)
    unit, n = (
        ("DAY", 1)
        if minutes == 1440
        else ("HOUR", minutes // 60)
        if minutes % 60 == 0
        else ("MINUTE", minutes)
    )
    assert parse_timeframe(tf.canonical) == tf
    assert tf.nautilus == f"{n}-{unit}"
    assert tf.alpaca == f"{n}" + {"DAY": "Day", "HOUR": "Hour", "MINUTE": "Min"}[unit]
    assert tf.ccxt == f"{n}" + {"DAY": "d", "HOUR": "h", "MINUTE": "m"}[unit]
    assert tf.duration == timedelta(minutes=minutes)
    assert tf.seconds == minutes * 60
    assert tf.is_daily == (minutes == 1440)


@pytest.mark.parametrize(
    "text",
    [
        "1s",
        "30s",
        "500ms",
        "S1",
        "tick",
        "ticks",
        "trade",
        "trades",
        "aggtrades",
        "quote",
        "quotes",
        "book",
        "orderbook",
        "order_book",
        "depth",
        "l2",
        "l3",
        " TICKS ",
    ],
)
def test_no_hft_message(text: str) -> None:
    with pytest.raises(DataError) as caught:
        parse_timeframe(text)
    assert str(caught.value).startswith(
        f"{text}: ALPHA uses time bars of one minute or longer only; sub-minute bars and tick, "
        "trade, quote or order-book data are excluded by the owner's no-high-frequency-trading rule"
    )


@pytest.mark.parametrize(
    "text", ["", "0m", "61m", "25h", "1w", "1month", "2D", "-5m", "1.5h", "junk"]
)
def test_invalid(text: str) -> None:
    with pytest.raises(DataError, match="accepted"):
        parse_timeframe(text)


@pytest.mark.parametrize("minutes", [0, -1, 61, 1439, 1441, True, 5.0])
def test_constructor_validation(minutes: int) -> None:
    with pytest.raises(DataError):
        BarTimeframe(minutes)


def test_long_bars_are_a_design_limit() -> None:
    with pytest.raises(DataError, match="resample stored daily bars instead"):
        parse_timeframe("25h")


def test_store_roots(tmp_path: Path) -> None:
    assert store_dir(tmp_path, DAILY) == tmp_path / "store"
    assert store_dir(tmp_path, parse_timeframe("60m")) == tmp_path / "store-1h"
    assert store_dir(tmp_path, parse_timeframe("5m")) == tmp_path / "store-5m"


def test_grid_restarts_at_utc_midnight() -> None:
    tf = parse_timeframe("7h")
    for day in (1, 2):
        for hour in range(24):
            ts = datetime(2024, 1, day, hour, tzinfo=UTC)
            assert tf.is_aligned(ts) == (hour in (0, 7, 14, 21))
    assert tf.is_aligned(datetime(2024, 1, 2, 9, tzinfo=timezone(timedelta(hours=2))))
    assert not tf.is_aligned(datetime(2024, 1, 2, 7, 0, 1, tzinfo=UTC))
    assert not tf.is_aligned(datetime(2024, 1, 2, 7, microsecond=1, tzinfo=UTC))


@pytest.mark.parametrize(
    "text,valid", [("1D", True), ("5m", True), ("1h", True), ("60m", False), ("1d", False)]
)
def test_identity_requires_canonical(text: str, valid: bool) -> None:
    kwargs = dict(
        symbol="SPY",
        provider="alpaca",
        provider_symbol="SPY",
        venue="US",
        timeframe=text,
        calendar="XNYS",
        currency="USD",
    )
    if valid:
        assert DatasetIdentity(asset_class="etf", price_basis="raw", **kwargs).timeframe == text
    else:
        with pytest.raises(DataError):
            DatasetIdentity(asset_class="etf", price_basis="raw", **kwargs)


@pytest.mark.parametrize("text", ["1M", "3M", "1Month", "1W", "2weeks", "1Y"])
def test_month_week_year_spellings_are_refused_not_guessed(text: str) -> None:
    # "1M" is one month in pandas and CCXT; it must never silently become one minute.
    with pytest.raises(DataError, match="accepted forms"):
        parse_timeframe(text)
