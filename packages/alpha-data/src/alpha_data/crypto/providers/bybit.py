"""Bybit V5 public derivatives and options parsing with native semantics intact."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Final, Literal
from urllib.parse import urlencode

import polars as pl

from alpha_core import DataError

type BybitCategory = Literal["spot", "linear", "inverse", "option"]
type PriceFamily = Literal["trade", "mark", "index", "premium"]
type QueryScalar = str | int

_CATEGORIES: Final = frozenset({"spot", "linear", "inverse", "option"})
_PRICE_FAMILIES: Final = frozenset({"trade", "mark", "index", "premium"})
_MAX_RESPONSE_BYTES: Final = 8 * 1024 * 1024
_ENDPOINTS: Final = {
    "instruments": (
        "/v5/market/instruments-info",
        frozenset({"category", "symbol", "status", "baseCoin", "limit", "cursor"}),
    ),
    "funding": (
        "/v5/market/funding/history",
        frozenset({"category", "symbol", "startTime", "endTime", "limit"}),
    ),
    "open_interest": (
        "/v5/market/open-interest",
        frozenset(
            {"category", "symbol", "intervalTime", "startTime", "endTime", "limit", "cursor"}
        ),
    ),
    "long_short_ratio": (
        "/v5/market/account-ratio",
        frozenset({"category", "symbol", "period", "startTime", "endTime", "limit", "cursor"}),
    ),
    "trade_kline": (
        "/v5/market/kline",
        frozenset({"category", "symbol", "interval", "start", "end", "limit"}),
    ),
    "mark_kline": (
        "/v5/market/mark-price-kline",
        frozenset({"category", "symbol", "interval", "start", "end", "limit"}),
    ),
    "index_kline": (
        "/v5/market/index-price-kline",
        frozenset({"category", "symbol", "interval", "start", "end", "limit"}),
    ),
    "premium_kline": (
        "/v5/market/premium-index-price-kline",
        frozenset({"category", "symbol", "interval", "start", "end", "limit"}),
    ),
    "historical_volatility": (
        "/v5/market/historical-volatility",
        frozenset({"category", "baseCoin", "quoteCoin", "period", "startTime", "endTime"}),
    ),
    "option_tickers": (
        "/v5/market/tickers",
        frozenset({"category", "symbol", "baseCoin", "expDate"}),
    ),
    "recent_trades": (
        "/v5/market/recent-trade",
        frozenset({"category", "symbol", "baseCoin", "optionType", "limit"}),
    ),
    "orderbook": (
        "/v5/market/orderbook",
        frozenset({"category", "symbol", "limit"}),
    ),
}


def bybit_public_url(endpoint: str, params: dict[str, QueryScalar]) -> str:
    """Build one closed, read-only Bybit public-market URL."""
    definition = _ENDPOINTS.get(endpoint)
    if definition is None:
        raise DataError(f"unsupported Bybit public endpoint {endpoint!r}")
    path, allowed = definition
    unknown = set(params) - allowed
    if unknown:
        raise DataError(f"unsupported Bybit query parameters for {endpoint}")
    if len(params) > 12 or any(
        isinstance(value, bool) or not isinstance(value, str | int) for value in params.values()
    ):
        raise DataError("Bybit public query contains an unsupported value")
    return f"https://api.bybit.com{path}?{urlencode(sorted(params.items()))}"


def fetch_bybit_public(
    endpoint: str, params: dict[str, QueryScalar], *, timeout_seconds: int = 30
) -> bytes:
    """Fetch one bounded credential-free public response from the pinned Bybit host."""
    if not 1 <= timeout_seconds <= 60:
        raise DataError("Bybit public timeout must be between 1 and 60 seconds")
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    request = urllib.request.Request(
        bybit_public_url(endpoint, params),
        headers={"Accept": "application/json", "User-Agent": "Project-ALPHA/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            if not str(response.geturl()).startswith("https://api.bybit.com/v5/"):
                raise DataError("Bybit public redirect host is invalid")
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0]
            if content_type not in {"application/json", "text/json"}:
                raise DataError("Bybit public response MIME is not JSON")
            payload = bytes(response.read(_MAX_RESPONSE_BYTES + 1))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise DataError("Bybit public request failed") from exc
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise DataError("Bybit public response exceeds the byte limit")
    return payload


def _decode(payload: bytes) -> tuple[object, int | None]:
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("Bybit public response is malformed") from exc
    if not isinstance(raw, dict):
        raise DataError("Bybit public response must be an object")
    if raw.get("retCode") != 0:
        raise DataError("Bybit public response reported an error")
    if "result" not in raw:
        raise DataError("Bybit public response has no result")
    response_time = raw.get("time")
    if response_time is not None and (
        isinstance(response_time, bool) or not isinstance(response_time, int)
    ):
        raise DataError("Bybit public response time is invalid")
    return raw["result"], response_time


def _result_object(payload: bytes) -> tuple[dict[str, object], int | None]:
    result, response_time = _decode(payload)
    if not isinstance(result, dict):
        raise DataError("Bybit public result must be an object")
    return result, response_time


def _record_list(result: dict[str, object]) -> list[dict[str, object]]:
    records = result.get("list")
    if not isinstance(records, list) or not records:
        raise DataError("Bybit public result contains no records")
    if any(not isinstance(record, dict) for record in records):
        raise DataError("Bybit public result contains a malformed record")
    return records


def _cursor(result: dict[str, object]) -> str | None:
    cursor = result.get("nextPageCursor")
    if cursor in (None, ""):
        return None
    if not isinstance(cursor, str):
        raise DataError("Bybit pagination cursor is invalid")
    return cursor


def _text(record: dict[str, object], name: str, *, optional: bool = False) -> str | None:
    value = record.get(name)
    if optional and value in (None, ""):
        return None
    if not isinstance(value, str) or not value:
        raise DataError(f"Bybit record field {name} is invalid")
    return value


def _number(record: dict[str, object], name: str, *, optional: bool = False) -> float | None:
    value = record.get(name)
    if optional and value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise DataError(f"Bybit record field {name} is invalid")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise DataError(f"Bybit record field {name} is invalid") from exc
    if not math.isfinite(parsed):
        raise DataError(f"Bybit record field {name} is not finite")
    return parsed


def _integer(record: dict[str, object], name: str, *, optional: bool = False) -> int | None:
    value = record.get(name)
    if optional and value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise DataError(f"Bybit record field {name} is invalid")
    try:
        return int(value)
    except ValueError as exc:
        raise DataError(f"Bybit record field {name} is invalid") from exc


def _timestamp(value: int | None, label: str, *, allow_zero: bool = False) -> datetime | None:
    if value is None or (allow_zero and value == 0):
        return None
    if value < 0:
        raise DataError(f"Bybit {label} timestamp is invalid")
    try:
        return datetime.fromtimestamp(value / 1_000, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise DataError(f"Bybit {label} timestamp is outside the supported range") from exc


def _category(value: object, expected: BybitCategory | None = None) -> BybitCategory:
    if not isinstance(value, str) or value not in _CATEGORIES:
        raise DataError("Bybit category is invalid")
    if expected is not None and value != expected:
        raise DataError("Bybit result category does not match the requested category")
    return value  # type: ignore[return-value]


def _option_identity(symbol: str, base_coin: str, quote_coin: str) -> tuple[str, float, str]:
    parts = symbol.split("-")
    if (
        len(parts) not in {4, 5}
        or parts[0] != base_coin
        or parts[3] not in {"C", "P"}
        or (len(parts) == 5 and parts[4] != quote_coin)
    ):
        raise DataError("Bybit option symbol identity is invalid")
    try:
        strike = float(parts[2])
    except ValueError as exc:
        raise DataError("Bybit option strike is invalid") from exc
    if not math.isfinite(strike) or strike <= 0:
        raise DataError("Bybit option strike is invalid")
    return parts[1], strike, "call" if parts[3] == "C" else "put"


def parse_instruments(
    payload: bytes, *, category: BybitCategory, fetched_at_ms: int
) -> tuple[pl.DataFrame, str | None]:
    """Parse one instrument-catalog page with lifecycle and native contract identity."""
    if category not in _CATEGORIES:
        raise DataError("Bybit requested category is invalid")
    fetched_at = _timestamp(fetched_at_ms, "fetch")
    assert fetched_at is not None
    result, _ = _result_object(payload)
    _category(result.get("category"), category)
    rows: list[dict[str, object]] = []
    for record in _record_list(result):
        symbol = _text(record, "symbol")
        base_coin = _text(record, "baseCoin")
        assert symbol is not None and base_coin is not None
        launch_ms = _integer(record, "launchTime", optional=category == "spot")
        delivery_ms = _integer(record, "deliveryTime", optional=True)
        if category != "spot" and launch_ms is None:
            raise DataError("Bybit derivative instrument launch time is missing")
        launch_time = _timestamp(launch_ms, "launch")
        delivery_time = _timestamp(delivery_ms, "delivery", allow_zero=True)
        if launch_time is not None and delivery_time is not None and delivery_time < launch_time:
            raise DataError("Bybit instrument delivery precedes launch")
        status = _text(record, "status")
        if status == "Trading" and launch_time is not None and launch_time > fetched_at:
            raise DataError("Bybit trading instrument launch is in the future")
        contract_type = _text(record, "contractType", optional=True)
        funding_interval = _integer(record, "fundingInterval", optional=True)
        if funding_interval is not None and (
            funding_interval < 0
            or (funding_interval == 0 and not (contract_type or "").endswith("Futures"))
        ):
            raise DataError("Bybit funding interval must be positive")
        expiry_code: str | None = None
        strike_price: float | None = None
        option_kind: str | None = None
        if category == "option":
            quote_coin = _text(record, "quoteCoin")
            assert quote_coin is not None
            expiry_code, strike_price, option_kind = _option_identity(symbol, base_coin, quote_coin)
            provider_kind = _text(record, "optionsType")
            if provider_kind is None or provider_kind.casefold() != option_kind:
                raise DataError("Bybit option type conflicts with its symbol")
        price_filter = record.get("priceFilter")
        lot_filter = record.get("lotSizeFilter")
        if not isinstance(price_filter, dict) or not isinstance(lot_filter, dict):
            raise DataError("Bybit instrument filters are invalid")
        rows.append(
            {
                "fetched_at": fetched_at,
                "category": category,
                "symbol": symbol,
                "status": status,
                "base_coin": base_coin,
                "quote_coin": _text(record, "quoteCoin"),
                "settle_coin": _text(record, "settleCoin", optional=True),
                "contract_type": contract_type,
                "launch_time": launch_time,
                "delivery_time": delivery_time,
                "funding_interval_minutes": funding_interval,
                "tick_size": _number(price_filter, "tickSize"),
                "qty_step": _number(lot_filter, "qtyStep", optional=True),
                "expiry_code": expiry_code,
                "strike_price": strike_price,
                "option_kind": option_kind,
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).sort("symbol"), _cursor(result)


def parse_funding_history(payload: bytes) -> pl.DataFrame:
    """Parse native funding observations without annualising or interval substitution."""
    result, _ = _result_object(payload)
    category = _category(result.get("category"))
    if category not in {"linear", "inverse"}:
        raise DataError("Bybit funding category must be linear or inverse")
    rows: list[dict[str, object]] = []
    for record in _record_list(result):
        timestamp_ms = _integer(record, "fundingRateTimestamp")
        funding_rate = _number(record, "fundingRate")
        assert timestamp_ms is not None and funding_rate is not None
        rows.append(
            {
                "timestamp": _timestamp(timestamp_ms, "funding"),
                "category": category,
                "symbol": _text(record, "symbol"),
                "funding_rate": funding_rate,
            }
        )
    return _unique_sorted(rows, "timestamp", "Bybit funding history")


def parse_open_interest(payload: bytes) -> tuple[pl.DataFrame, str | None]:
    """Parse OI while retaining Bybit's linear-base/inverse-quote unit rule."""
    result, _ = _result_object(payload)
    category = _category(result.get("category"))
    if category not in {"linear", "inverse"}:
        raise DataError("Bybit open-interest category must be linear or inverse")
    symbol = result.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise DataError("Bybit open-interest symbol is invalid")
    rows: list[dict[str, object]] = []
    for record in _record_list(result):
        timestamp_ms = _integer(record, "timestamp")
        value = _number(record, "openInterest")
        single = _number(record, "singleOpenInterest", optional=True)
        assert timestamp_ms is not None and value is not None
        if value < 0 or (single is not None and (single < 0 or single > value)):
            raise DataError("Bybit open interest is outside valid bounds")
        rows.append(
            {
                "timestamp": _timestamp(timestamp_ms, "open-interest"),
                "category": category,
                "symbol": symbol,
                "open_interest": value,
                "single_open_interest": single,
                "unit_rule": "base_coin" if category == "linear" else "quote_coin",
            }
        )
    return _unique_sorted(rows, "timestamp", "Bybit open-interest history"), _cursor(result)


def parse_long_short_ratio(
    payload: bytes, *, category: Literal["linear", "inverse"]
) -> tuple[pl.DataFrame, str | None]:
    """Parse holder ratios and derive only their exact dimensionless quotient."""
    if category not in {"linear", "inverse"}:
        raise DataError("Bybit ratio category must be linear or inverse")
    result, _ = _result_object(payload)
    rows: list[dict[str, object]] = []
    for record in _record_list(result):
        timestamp_ms = _integer(record, "timestamp")
        buy = _number(record, "buyRatio")
        sell = _number(record, "sellRatio")
        assert timestamp_ms is not None and buy is not None and sell is not None
        if (
            not 0 <= buy <= 1
            or not 0 <= sell <= 1
            or not math.isclose(buy + sell, 1.0, abs_tol=1e-6)
        ):
            raise DataError("Bybit long/short ratios are outside valid bounds")
        if sell == 0:
            raise DataError("Bybit short-holder ratio cannot be zero")
        rows.append(
            {
                "timestamp": _timestamp(timestamp_ms, "ratio"),
                "category": category,
                "symbol": _text(record, "symbol"),
                "long_ratio": buy,
                "short_ratio": sell,
                "long_short_ratio": buy / sell,
            }
        )
    return _unique_sorted(rows, "timestamp", "Bybit ratio history"), _cursor(result)


def parse_price_klines(payload: bytes, *, family: PriceFamily) -> pl.DataFrame:
    """Parse one Bybit trade/mark/index/premium kline response as a distinct family."""
    if family not in _PRICE_FAMILIES:
        raise DataError("Bybit price family is invalid")
    result, _ = _result_object(payload)
    category = _category(result.get("category"))
    symbol = result.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise DataError("Bybit kline symbol is invalid")
    raw_rows = result.get("list")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise DataError("Bybit public result contains no records")
    rows: list[dict[str, object]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, list) or len(raw_row) < (7 if family == "trade" else 5):
            raise DataError("Bybit kline row is malformed")
        record = {str(index): value for index, value in enumerate(raw_row)}
        timestamp_ms = _integer(record, "0")
        open_price = _number(record, "1")
        high = _number(record, "2")
        low = _number(record, "3")
        close = _number(record, "4")
        assert None not in (timestamp_ms, open_price, high, low, close)
        assert isinstance(timestamp_ms, int)
        assert isinstance(open_price, float)
        assert isinstance(high, float)
        assert isinstance(low, float)
        assert isinstance(close, float)
        if family != "premium" and not (
            low <= min(open_price, close) and high >= max(open_price, close) and high >= low
        ):
            raise DataError("Bybit kline violates OHLC invariants")
        if family != "premium" and min(open_price, high, low, close) <= 0:
            raise DataError("Bybit trade/mark/index kline prices must be positive")
        volume = _number(record, "5") if family == "trade" else None
        turnover = _number(record, "6") if family == "trade" else None
        if (volume is not None and volume < 0) or (turnover is not None and turnover < 0):
            raise DataError("Bybit kline volume and turnover must be non-negative")
        rows.append(
            {
                "timestamp": _timestamp(timestamp_ms, "kline"),
                "category": category,
                "symbol": symbol,
                "family": family,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "turnover": turnover,
                "volume_unit_rule": (
                    None
                    if family != "trade"
                    else ("base_coin" if category in {"spot", "linear"} else "quote_coin")
                ),
                "turnover_unit_rule": (
                    None
                    if family != "trade"
                    else ("quote_coin" if category in {"spot", "linear"} else "base_coin")
                ),
            }
        )
    return _unique_sorted(rows, "timestamp", f"Bybit {family} kline history")


def price_bundle_diagnostics(
    *, mark: pl.DataFrame, index: pl.DataFrame, premium: pl.DataFrame
) -> pl.DataFrame:
    """Align native close values and expose, but never rewrite, their basis discrepancy."""
    keys = ["timestamp", "category", "symbol"]

    def projection(frame: pl.DataFrame, family: str, close_name: str) -> pl.DataFrame:
        required = {*keys, "family", "close"}
        if frame.is_empty() or not required.issubset(frame.columns):
            raise DataError(f"Bybit {family} diagnostic input is invalid")
        if set(frame["family"].unique().to_list()) != {family}:
            raise DataError(f"Bybit {family} diagnostic family is invalid")
        if frame.select(keys).n_unique() != frame.height:
            raise DataError(f"Bybit {family} diagnostic keys are duplicated")
        return frame.select(*keys, pl.col("close").alias(close_name))

    joined = projection(mark, "mark", "mark_close").join(
        projection(index, "index", "index_close"), on=keys, how="inner", validate="1:1"
    )
    joined = joined.join(
        projection(premium, "premium", "reported_premium"),
        on=keys,
        how="inner",
        validate="1:1",
    )
    if (
        joined.height != mark.height
        or joined.height != index.height
        or joined.height != premium.height
    ):
        raise DataError("Bybit mark/index/premium observations are not exactly aligned")
    return joined.with_columns(
        (pl.col("mark_close") / pl.col("index_close") - 1).alias("observed_mark_index_basis")
    ).with_columns(
        (pl.col("observed_mark_index_basis") - pl.col("reported_premium")).alias(
            "basis_premium_difference"
        )
    )


def parse_historical_volatility(
    payload: bytes, *, base_coin: str, quote_coin: Literal["USD", "USDT"]
) -> pl.DataFrame:
    """Parse the provider's hourly option historical-volatility observations."""
    result, _ = _decode(payload)
    if isinstance(result, dict):
        records = _record_list(result)
    elif isinstance(result, list):
        if not result:
            raise DataError("Bybit historical-volatility result contains no records")
        if not all(isinstance(item, dict) for item in result):
            raise DataError("Bybit historical-volatility result is invalid")
        records = result
    else:
        raise DataError("Bybit historical-volatility result is invalid")
    if not base_coin or not base_coin.isupper() or quote_coin not in {"USD", "USDT"}:
        raise DataError("Bybit volatility identity is invalid")
    rows: list[dict[str, object]] = []
    for record in records:
        timestamp_ms = _integer(record, "time")
        period = _integer(record, "period")
        value = _number(record, "value")
        assert timestamp_ms is not None and period is not None and value is not None
        if timestamp_ms % 3_600_000 != 0 or period <= 0 or value < 0:
            raise DataError("Bybit historical volatility violates hourly numeric bounds")
        rows.append(
            {
                "timestamp": _timestamp(timestamp_ms, "volatility"),
                "base_coin": base_coin,
                "quote_coin": quote_coin,
                "period_days": period,
                "volatility": value,
            }
        )
    return _unique_sorted(rows, "timestamp", "Bybit historical volatility")


def parse_option_tickers(payload: bytes, *, fetched_at_ms: int) -> tuple[pl.DataFrame, str | None]:
    """Parse a full option-chain ticker page and retain provider IV/Greeks unchanged."""
    result, response_time = _result_object(payload)
    if "category" in result:
        _category(result.get("category"), "option")
    fetched_at = _timestamp(fetched_at_ms, "fetch")
    assert fetched_at is not None
    if response_time is not None and response_time > fetched_at_ms + 60_000:
        raise DataError("Bybit option response time is later than the fetch clock")
    server_lag_ms = None if response_time is None else fetched_at_ms - response_time
    rows: list[dict[str, object]] = []
    for record in _record_list(result):
        bid = _number(record, "bid1Price", optional=True)
        ask = _number(record, "ask1Price", optional=True)
        bid_iv = _number(record, "bid1Iv", optional=True)
        ask_iv = _number(record, "ask1Iv", optional=True)
        mark_iv = _number(record, "markIv", optional=True)
        delta = _number(record, "delta", optional=True)
        gamma = _number(record, "gamma", optional=True)
        vega = _number(record, "vega", optional=True)
        open_interest = _number(record, "openInterest", optional=True)
        non_negative = (
            bid,
            ask,
            bid_iv,
            ask_iv,
            mark_iv,
            gamma,
            vega,
            open_interest,
        )
        if any(value is not None and value < 0 for value in non_negative):
            raise DataError("Bybit option ticker has a negative bounded field")
        if delta is not None and not -1 <= delta <= 1:
            raise DataError("Bybit option delta is outside [-1, 1]")
        rows.append(
            {
                "available_at": fetched_at,
                "symbol": _text(record, "symbol"),
                "bid_price": bid,
                "bid_size": _number(record, "bid1Size", optional=True),
                "ask_price": ask,
                "ask_size": _number(record, "ask1Size", optional=True),
                "last_price": _number(record, "lastPrice", optional=True),
                "mark_price": _number(record, "markPrice", optional=True),
                "index_price": _number(record, "indexPrice", optional=True),
                "underlying_price": _number(record, "underlyingPrice", optional=True),
                "bid_iv": bid_iv,
                "ask_iv": ask_iv,
                "mark_iv": mark_iv,
                "delta": delta,
                "gamma": gamma,
                "vega": vega,
                "theta": _number(record, "theta", optional=True),
                "open_interest": open_interest,
                "turnover_24h": _number(record, "turnover24h", optional=True),
                "volume_24h": _number(record, "volume24h", optional=True),
                "crossed_market": bid is not None and ask is not None and bid > ask,
                "stale_snapshot": server_lag_ms is not None and server_lag_ms > 60_000,
                "server_lag_ms": server_lag_ms,
            }
        )
    return pl.DataFrame(rows).sort("symbol"), _cursor(result)


def parse_recent_trades(payload: bytes, *, fetched_at_ms: int) -> pl.DataFrame:
    """Parse bounded public trades without collapsing multiple executions in one millisecond."""
    result, response_time = _result_object(payload)
    category = _category(result.get("category"))
    fetched_at = _timestamp(fetched_at_ms, "fetch")
    assert fetched_at is not None
    if response_time is not None and response_time > fetched_at_ms + 60_000:
        raise DataError("Bybit recent-trade response is later than the fetch clock")
    rows: list[dict[str, object]] = []
    for record in _record_list(result):
        trade_id = _text(record, "execId")
        symbol = _text(record, "symbol")
        price = _number(record, "price")
        size = _number(record, "size")
        timestamp_ms = _integer(record, "time")
        side = _text(record, "side")
        is_block = record.get("isBlockTrade", False)
        is_rpi = record.get("isRPITrade", False)
        assert trade_id is not None and symbol is not None
        assert price is not None and size is not None and timestamp_ms is not None
        if timestamp_ms > fetched_at_ms + 60_000:
            raise DataError("Bybit recent trade is later than the fetch clock")
        if price <= 0 or size <= 0:
            raise DataError("Bybit recent trade price and size must be positive")
        if side not in {"Buy", "Sell"}:
            raise DataError("Bybit recent trade side is invalid")
        if not isinstance(is_block, bool) or not isinstance(is_rpi, bool):
            raise DataError("Bybit recent trade flags are invalid")
        rows.append(
            {
                "timestamp": _timestamp(timestamp_ms, "trade"),
                "available_at": fetched_at,
                "category": category,
                "symbol": symbol,
                "trade_id": trade_id,
                "side": side.lower(),
                "price": price,
                "size": size,
                "is_block_trade": is_block,
                "is_rpi_trade": is_rpi,
                "mark_price": _number(record, "mP", optional=True),
                "index_price": _number(record, "iP", optional=True),
                "mark_iv": _number(record, "mIv", optional=True),
                "trade_iv": _number(record, "iv", optional=True),
            }
        )
    frame = pl.DataFrame(rows).sort("timestamp", "trade_id")
    if frame["trade_id"].n_unique() != frame.height:
        raise DataError("Bybit recent trades contain duplicate execution IDs")
    return frame


def parse_orderbook_snapshot(
    payload: bytes, *, category: BybitCategory, fetched_at_ms: int
) -> pl.DataFrame:
    """Parse one exact public orderbook snapshot with sequence and knowledge clocks."""
    result, response_time = _result_object(payload)
    if category not in _CATEGORIES:
        raise DataError("Bybit requested category is invalid")
    symbol = _text(result, "s")
    generated_ms = _integer(result, "ts")
    update_id = _integer(result, "u")
    cross_sequence = _integer(result, "seq")
    engine_ms = _integer(result, "cts", optional=True)
    assert symbol is not None and generated_ms is not None
    assert update_id is not None and cross_sequence is not None
    generated_at = _timestamp(generated_ms, "orderbook generation")
    fetched_at = _timestamp(fetched_at_ms, "fetch")
    engine_at = _timestamp(engine_ms, "orderbook engine")
    assert generated_at is not None and fetched_at is not None
    if generated_ms > fetched_at_ms + 60_000 or (
        response_time is not None and response_time > fetched_at_ms + 60_000
    ):
        raise DataError("Bybit orderbook response is later than the fetch clock")
    if engine_at is not None and engine_at > generated_at:
        raise DataError("Bybit orderbook engine time exceeds generation time")

    rows: list[dict[str, object]] = []
    prices: dict[str, list[float]] = {"bid": [], "ask": []}
    for side, field in (("bid", "b"), ("ask", "a")):
        levels = result.get(field)
        if not isinstance(levels, list) or not levels:
            raise DataError("Bybit orderbook side is empty or malformed")
        for level, raw in enumerate(levels, start=1):
            if not isinstance(raw, list) or len(raw) != 2:
                raise DataError("Bybit orderbook level is malformed")
            record = {"price": raw[0], "size": raw[1]}
            price = _number(record, "price")
            size = _number(record, "size")
            assert price is not None and size is not None
            if price <= 0 or size <= 0:
                raise DataError("Bybit orderbook price and size must be positive")
            prices[side].append(price)
            rows.append(
                {
                    "observed_at": generated_at,
                    "available_at": fetched_at,
                    "engine_at": engine_at,
                    "category": category,
                    "symbol": symbol,
                    "side": side,
                    "level": level,
                    "price": price,
                    "size": size,
                    "update_id": update_id,
                    "cross_sequence": cross_sequence,
                }
            )
    if any(right >= left for left, right in zip(prices["bid"], prices["bid"][1:], strict=False)):
        raise DataError("Bybit orderbook bids are not strictly descending")
    if any(right <= left for left, right in zip(prices["ask"], prices["ask"][1:], strict=False)):
        raise DataError("Bybit orderbook asks are not strictly ascending")
    if prices["bid"][0] >= prices["ask"][0]:
        raise DataError("Bybit orderbook is crossed or locked")
    return pl.DataFrame(rows)


def _unique_sorted(
    rows: list[dict[str, object]], timestamp_column: str, label: str
) -> pl.DataFrame:
    frame = pl.DataFrame(rows).sort(timestamp_column)
    if frame[timestamp_column].n_unique() != frame.height:
        raise DataError(f"{label} contains duplicate timestamps")
    return frame
