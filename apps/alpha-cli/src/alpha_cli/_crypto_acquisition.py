"""Pure request planning and parsing seams for native crypto acquisition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Literal, cast

import polars as pl

from alpha_core import DataError
from alpha_data.crypto.contracts import (
    FAMILY_AUTHORITIES,
    CryptoDatasetIdentityV1,
    CryptoFamily,
    CryptoMarketType,
)
from alpha_data.crypto.providers.bybit import (
    BybitCategory,
    PriceFamily,
    parse_funding_history,
    parse_historical_volatility,
    parse_instruments,
    parse_long_short_ratio,
    parse_open_interest,
    parse_option_tickers,
    parse_orderbook_snapshot,
    parse_price_klines,
    parse_recent_trades,
)

_BYBIT_PRICE_FAMILIES: dict[CryptoFamily, tuple[str, PriceFamily]] = {
    "derivative_bars": ("trade_kline", "trade"),
    "mark_bars": ("mark_kline", "mark"),
    "index_bars": ("index_kline", "index"),
    "premium_bars": ("premium_kline", "premium"),
}


@dataclass(frozen=True)
class AcquisitionPlan:
    endpoint: str
    params: dict[str, str | int]
    dataset: CryptoDatasetIdentityV1
    parser: Callable[[bytes], pl.DataFrame]
    observed_column: str
    key_columns: tuple[str, ...]
    availability_column: str | None = None
    next_cursor: Callable[[bytes], str | None] | None = None
    page_limit: int | None = None
    parser_at: Callable[[datetime], Callable[[bytes], pl.DataFrame]] | None = None
    expected_cadence_seconds: int | None = None
    period_start_timestamps: bool = False


def open_interest_frame(payload: bytes) -> pl.DataFrame:
    return parse_open_interest(payload)[0]


def open_interest_cursor(payload: bytes) -> str | None:
    return parse_open_interest(payload)[1]


def long_short_frame(payload: bytes, *, category: Literal["linear", "inverse"]) -> pl.DataFrame:
    if category not in {"linear", "inverse"}:
        raise DataError("Bybit ratio category must be linear or inverse")
    return parse_long_short_ratio(payload, category=category)[0]


def long_short_cursor(payload: bytes, *, category: Literal["linear", "inverse"]) -> str | None:
    return parse_long_short_ratio(payload, category=category)[1]


def iso_milliseconds(value: str, *, label: str) -> int:
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError(f"Bybit {label} must be an ISO-8601 timestamp") from exc
    if instant.tzinfo is None:
        raise DataError(f"Bybit {label} must include a timezone")
    return int(instant.astimezone(UTC).timestamp() * 1_000)


def bybit_range(
    start: str | None, end: str | None, *, fetched_at: datetime
) -> tuple[int, int] | None:
    if (start is None) != (end is None):
        raise DataError("Bybit --start and --end must be supplied together")
    if start is None or end is None:
        return None
    start_ms = iso_milliseconds(start, label="start")
    end_ms = iso_milliseconds(end, label="end")
    if end_ms <= start_ms:
        raise DataError("Bybit end must be later than start")
    if end_ms > int(fetched_at.timestamp() * 1_000):
        raise DataError("Bybit end exceeds the acquisition knowledge time")
    return start_ms, end_ms


def instrument_frame(payload: bytes, *, fetched_at_ms: int, base: str, quote: str) -> pl.DataFrame:
    frame = parse_instruments(payload, category="option", fetched_at_ms=fetched_at_ms)[0]
    selected = frame.filter((pl.col("base_coin") == base) & (pl.col("quote_coin") == quote))
    if selected.is_empty():
        raise DataError("Bybit option page has no contracts for the requested base and quote")
    return selected


def instrument_cursor(payload: bytes, *, fetched_at_ms: int) -> str | None:
    return parse_instruments(payload, category="option", fetched_at_ms=fetched_at_ms)[1]


def catalog_frame(payload: bytes, *, category: BybitCategory, fetched_at_ms: int) -> pl.DataFrame:
    return parse_instruments(payload, category=category, fetched_at_ms=fetched_at_ms)[0]


def catalog_cursor(payload: bytes, *, category: BybitCategory, fetched_at_ms: int) -> str | None:
    return parse_instruments(payload, category=category, fetched_at_ms=fetched_at_ms)[1]


def catalog_parser_at(
    completed_at: datetime, *, category: BybitCategory
) -> Callable[[bytes], pl.DataFrame]:
    return partial(
        catalog_frame,
        category=category,
        fetched_at_ms=int(completed_at.timestamp() * 1_000),
    )


def recent_trades_parser_at(completed_at: datetime) -> Callable[[bytes], pl.DataFrame]:
    return partial(parse_recent_trades, fetched_at_ms=int(completed_at.timestamp() * 1_000))


def orderbook_parser_at(
    completed_at: datetime, *, category: BybitCategory
) -> Callable[[bytes], pl.DataFrame]:
    return partial(
        parse_orderbook_snapshot,
        category=category,
        fetched_at_ms=int(completed_at.timestamp() * 1_000),
    )


def option_symbol_assets(symbol: str) -> tuple[str, str]:
    parts = symbol.split("-")
    if len(parts) == 4 and parts[0] and parts[3] in {"C", "P"}:
        return parts[0], "USD"
    if len(parts) == 5 and parts[0] and parts[3] in {"C", "P"} and parts[4]:
        return parts[0], parts[4]
    raise DataError("Bybit option symbol cannot establish exact base and quote identity")


def option_quote_frame(
    payload: bytes, *, fetched_at_ms: int, base: str, quote: str
) -> pl.DataFrame:
    frame = parse_option_tickers(payload, fetched_at_ms=fetched_at_ms)[0]
    identities = [option_symbol_assets(symbol) for symbol in frame["symbol"].to_list()]
    selected = frame.filter(
        pl.Series([identity == (base, quote) for identity in identities], dtype=pl.Boolean)
    )
    if selected.is_empty():
        raise DataError("Bybit option page has no contracts for the requested base and quote")
    return selected


def option_instrument_parser_at(
    completed_at: datetime, *, base: str, quote: str
) -> Callable[[bytes], pl.DataFrame]:
    return partial(
        instrument_frame,
        fetched_at_ms=int(completed_at.timestamp() * 1_000),
        base=base,
        quote=quote,
    )


def option_quote_parser_at(
    completed_at: datetime, *, base: str, quote: str
) -> Callable[[bytes], pl.DataFrame]:
    return partial(
        option_quote_frame,
        fetched_at_ms=int(completed_at.timestamp() * 1_000),
        base=base,
        quote=quote,
    )


def validated_bybit_identity(
    family: CryptoFamily,
    instrument: str,
    *,
    base: str,
    quote: str,
    category: str,
) -> tuple[Literal["linear", "inverse"], CryptoMarketType, str, str, str]:
    diagnostic_spot = family == "comparison_bars" and category == "spot"
    if FAMILY_AUTHORITIES[family] != "bybit" and not diagnostic_spot:
        raise DataError(f"{family} is not a Bybit-authoritative dataset family")
    if diagnostic_spot:
        pass
    elif family == "instrument_catalog":
        if category not in {"spot", "linear", "inverse", "option"}:
            raise DataError(
                "Bybit instrument catalog category must be spot, linear, inverse, or option"
            )
    elif family in {"derivative_trades", "derivative_book_snapshots"}:
        if category not in {"linear", "inverse", "option"}:
            raise DataError("Bybit derivative event category must be linear, inverse, or option")
    elif family in {"option_instruments", "option_quotes", "historical_volatility"}:
        if category != "option":
            raise DataError(f"Bybit {family} requires the option category")
    elif category not in {"linear", "inverse"}:
        raise DataError("Bybit derivative category must be linear or inverse")
    category_value = cast(Literal["linear", "inverse"], category)
    market_type = cast(CryptoMarketType, category)
    base_value, quote_value = base.strip().upper(), quote.strip().upper()
    symbol = instrument.strip().upper()
    if (
        not base_value.isalnum()
        or not quote_value.isalnum()
        or not symbol.replace("-", "").isalnum()
    ):
        raise DataError("Bybit instrument, base, or quote identity is invalid")
    return category_value, market_type, base_value, quote_value, symbol


def apply_bybit_range(
    family: CryptoFamily,
    params: dict[str, str | int],
    bounded_range: tuple[int, int] | None,
) -> None:
    if bounded_range is None:
        return
    if family in {
        "instrument_catalog",
        "derivative_trades",
        "derivative_book_snapshots",
        "option_instruments",
        "option_quotes",
    }:
        raise DataError(f"Bybit {family} is a point-in-time snapshot and rejects a time range")
    start_ms, end_ms = bounded_range
    if family in _BYBIT_PRICE_FAMILIES or family == "comparison_bars":
        params.update({"start": start_ms, "end": end_ms})
    else:
        params.update({"startTime": start_ms, "endTime": end_ms})
    if family == "historical_volatility" and end_ms - start_ms > 30 * 86_400_000:
        raise DataError("Bybit historical volatility windows cannot exceed 30 days")


def bybit_option_plan(
    family: Literal["option_instruments", "option_quotes", "historical_volatility"],
    symbol: str,
    *,
    base: str,
    quote: str,
    frequency: str,
    bounded_range: tuple[int, int] | None,
    fetched_at: datetime,
) -> AcquisitionPlan:
    observed_column = "timestamp"
    key_columns: tuple[str, ...] = ("timestamp", "symbol")
    availability_column: str | None = None
    parser_at: Callable[[datetime], Callable[[bytes], pl.DataFrame]] | None = None
    next_cursor: Callable[[bytes], str | None] | None = None
    dataset_frequency = frequency
    if family == "option_instruments":
        endpoint = "instruments"
        params: dict[str, str | int] = {"category": "option", "baseCoin": base, "limit": 1_000}
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(instrument_frame, fetched_at_ms=fetched_at_ms, base=base, quote=quote)
        parser_at = partial(option_instrument_parser_at, base=base, quote=quote)
        observed_column = "fetched_at"
        key_columns = ("symbol",)
        dataset_frequency = "catalog_snapshot"
        next_cursor = partial(instrument_cursor, fetched_at_ms=fetched_at_ms)
    elif family == "option_quotes":
        endpoint = "option_tickers"
        params = {"category": "option", "baseCoin": base}
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(option_quote_frame, fetched_at_ms=fetched_at_ms, base=base, quote=quote)
        parser_at = partial(option_quote_parser_at, base=base, quote=quote)
        observed_column = "available_at"
        availability_column = "available_at"
        key_columns = ("available_at", "symbol")
        dataset_frequency = "point_in_time_chain"
    else:
        endpoint = "historical_volatility"
        params = {"category": "option", "baseCoin": base, "quoteCoin": quote}
        parser = partial(
            parse_historical_volatility,
            base_coin=base,
            quote_coin=cast(Literal["USD", "USDT"], quote),
        )
        key_columns = ("timestamp", "period_days")
    apply_bybit_range(family, params, bounded_range)
    return AcquisitionPlan(
        endpoint=endpoint,
        params=params,
        dataset=CryptoDatasetIdentityV1(
            provider="bybit",
            venue="bybit",
            market_type="option",
            family=family,
            instrument=symbol,
            base_asset=base,
            quote_asset=quote,
            frequency=dataset_frequency,
            units="provider_native",
            timestamp_convention="provider_event_utc",
        ),
        parser=parser,
        observed_column=observed_column,
        key_columns=key_columns,
        availability_column=availability_column,
        next_cursor=next_cursor,
        parser_at=parser_at,
    )


def bybit_plan(
    family: CryptoFamily,
    instrument: str,
    *,
    base: str,
    quote: str,
    category: str,
    frequency: str,
    start: str | None,
    end: str | None,
    fetched_at: datetime,
) -> AcquisitionPlan:
    category_value, market_type, base_value, quote_value, symbol = validated_bybit_identity(
        family, instrument, base=base, quote=quote, category=category
    )
    endpoint: str
    params: dict[str, str | int]
    parser: Callable[[bytes], pl.DataFrame]
    observed_column = "timestamp"
    key_columns: tuple[str, ...] = ("timestamp", "symbol")
    availability_column: str | None = None
    units = "provider_native"
    dataset_frequency = frequency
    dataset_instrument = symbol
    dataset_base: str | None = base_value
    dataset_quote: str | None = quote_value
    timestamp_convention = "provider_event_utc"
    expected_cadence_seconds: int | None = None
    period_start_timestamps = False
    next_cursor: Callable[[bytes], str | None] | None = None
    page_limit: int | None = None
    parser_at: Callable[[datetime], Callable[[bytes], pl.DataFrame]] | None = None
    bounded_range = bybit_range(start, end, fetched_at=fetched_at)

    if family in {"option_instruments", "option_quotes", "historical_volatility"}:
        return bybit_option_plan(
            cast(Literal["option_instruments", "option_quotes", "historical_volatility"], family),
            symbol,
            base=base_value,
            quote=quote_value,
            frequency=frequency,
            bounded_range=bounded_range,
            fetched_at=fetched_at,
        )
    if family == "comparison_bars":
        endpoint = "trade_kline"
        interval = {"1h": "60", "1d": "D", "5m": "5", "1m": "1"}.get(frequency)
        if interval is None:
            raise DataError("Bybit spot comparison frequency must be 1m, 5m, 1h, or 1d")
        params = {
            "category": "spot",
            "symbol": symbol,
            "interval": interval,
            "limit": 1_000,
        }
        parser = partial(parse_price_klines, family="trade")
        units = "quote_per_base_and_base_volume"
        page_limit = 1_000
        expected_cadence_seconds = {"1m": 60, "5m": 300, "1h": 3_600, "1d": 86_400}[frequency]
        period_start_timestamps = True
        timestamp_convention = "interval_start_utc"
    elif family == "instrument_catalog":
        endpoint = "instruments"
        params = {"category": category}
        if category != "spot":
            params["limit"] = 1_000
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        catalog_category = cast(BybitCategory, category)
        parser = partial(catalog_frame, category=catalog_category, fetched_at_ms=fetched_at_ms)
        parser_at = partial(catalog_parser_at, category=catalog_category)
        observed_column = "fetched_at"
        key_columns = ("symbol",)
        dataset_frequency = "catalog_snapshot"
        dataset_instrument = category
        dataset_base = None
        dataset_quote = None
        timestamp_convention = "fetch_knowledge_utc"
        if category != "spot":
            next_cursor = partial(
                catalog_cursor, category=catalog_category, fetched_at_ms=fetched_at_ms
            )
    elif family == "derivative_trades":
        endpoint = "recent_trades"
        params = {"category": category, "symbol": symbol, "limit": 1_000}
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(parse_recent_trades, fetched_at_ms=fetched_at_ms)
        parser_at = recent_trades_parser_at
        key_columns = ("timestamp", "trade_id")
        availability_column = "available_at"
        units = "provider_native_price_quantity"
        dataset_frequency = "recent_trade_snapshot"
    elif family == "derivative_book_snapshots":
        endpoint = "orderbook"
        params = {
            "category": category,
            "symbol": symbol,
            "limit": 25 if category == "option" else 1_000,
        }
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(
            parse_orderbook_snapshot,
            category=cast(BybitCategory, category),
            fetched_at_ms=fetched_at_ms,
        )
        parser_at = partial(orderbook_parser_at, category=cast(BybitCategory, category))
        observed_column = "observed_at"
        key_columns = ("observed_at", "side", "level")
        availability_column = "available_at"
        units = "provider_native_price_quantity"
        dataset_frequency = "point_in_time_book"
        timestamp_convention = "provider_generation_utc"
    elif family == "funding":
        endpoint = "funding"
        params = {"category": category, "symbol": symbol, "limit": 200}
        parser = parse_funding_history
        units = "dimensionless_rate"
        dataset_frequency = "funding_interval"
        page_limit = 200
    elif family == "open_interest":
        endpoint = "open_interest"
        params = {
            "category": category,
            "symbol": symbol,
            "intervalTime": frequency,
            "limit": 200,
        }
        parser = open_interest_frame
        next_cursor = open_interest_cursor
        units = "base_coin_if_linear_quote_coin_if_inverse"
    elif family == "long_short_ratio":
        endpoint = "long_short_ratio"
        params = {"category": category, "symbol": symbol, "period": frequency, "limit": 200}
        parser = partial(long_short_frame, category=category_value)
        next_cursor = partial(long_short_cursor, category=category_value)
        units = "dimensionless_ratio"
    elif family in _BYBIT_PRICE_FAMILIES:
        endpoint, price_family = _BYBIT_PRICE_FAMILIES[family]
        interval = {"1h": "60", "1d": "D", "5m": "5", "1m": "1"}.get(frequency)
        if interval is None:
            raise DataError("Bybit price-bar frequency must be 1m, 5m, 1h, or 1d")
        params = {"category": category, "symbol": symbol, "interval": interval, "limit": 1_000}
        parser = partial(parse_price_klines, family=price_family)
        units = "quote_price"
        page_limit = 1_000
        expected_cadence_seconds = {"1m": 60, "5m": 300, "1h": 3_600, "1d": 86_400}[frequency]
        period_start_timestamps = True
        timestamp_convention = "interval_start_utc"
    else:
        raise DataError(f"Bybit acquisition is not implemented for {family}")

    apply_bybit_range(family, params, bounded_range)
    return AcquisitionPlan(
        endpoint=endpoint,
        params=params,
        dataset=CryptoDatasetIdentityV1(
            provider="bybit",
            venue="bybit",
            market_type=market_type,
            family=family,
            instrument=dataset_instrument,
            base_asset=dataset_base,
            quote_asset=dataset_quote,
            frequency=dataset_frequency,
            units=units,
            timestamp_convention=timestamp_convention,
        ),
        parser=parser,
        observed_column=observed_column,
        key_columns=key_columns,
        availability_column=availability_column,
        next_cursor=next_cursor,
        page_limit=page_limit,
        parser_at=parser_at,
        expected_cadence_seconds=expected_cadence_seconds,
        period_start_timestamps=period_start_timestamps,
    )
