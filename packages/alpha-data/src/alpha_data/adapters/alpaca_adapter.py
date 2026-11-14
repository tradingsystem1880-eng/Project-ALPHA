"""Alpaca SIP raw time bars, replayable receipts and split cross-checks."""

from __future__ import annotations

import base64
import binascii
import hashlib
import http.client
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

import polars as pl
from pydantic import ValidationError

from alpha_core import ActionType, Bar, CorporateAction, DataError
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt, FetchResult
from alpha_data.timeframe import DAILY, BarTimeframe, parse_timeframe

_VERSION = "1"
PARSER_VERSION = "1"
_HOST = "https://data.alpaca.markets"
FEED = "sip"
_BARS = "/v2/stocks/bars"
_ACTIONS = "/v1/corporate-actions"
_MAX_PAGES = 200
_MAX_BYTES = 32 * 1024 * 1024
_NY = ZoneInfo("America/New_York")
_SERIES = ("bars_raw", "bars_split", "actions")
_ACTION_TYPES = "forward_split,reverse_split,cash_dividend,stock_dividend,spin_off,unit_split"
# Per corporate-action group: the fields that may name the queried symbol, and its date field
# (Alpaca's schemas: spin-offs name source_symbol/new_symbol; unit splits old/new/alternate
# symbols and an effective_date; a reverse split may carry the post-split new_symbol).
_ACTION_FIELDS: dict[str, tuple[tuple[str, ...], str]] = {
    "forward_splits": (("symbol",), "ex_date"),
    "reverse_splits": (("symbol", "new_symbol"), "ex_date"),
    "cash_dividends": (("symbol",), "ex_date"),
    "stock_dividends": (("symbol",), "ex_date"),
    "spin_offs": (("source_symbol", "new_symbol"), "ex_date"),
    "unit_splits": (("old_symbol", "new_symbol", "alternate_symbol"), "effective_date"),
}
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})")
# Query values every stored page must carry, so a replayed envelope proves what was asked for.
_FIXED_QUERY: dict[str, dict[str, str]] = {
    "bars_raw": {"timeframe": "1Day", "adjustment": "raw", "feed": FEED, "currency": "USD"},
    "bars_split": {"timeframe": "1Day", "adjustment": "split", "feed": FEED, "currency": "USD"},
    "actions": {"types": _ACTION_TYPES},
}
type Transport = Callable[[str, Mapping[str, str], float], tuple[int, Mapping[str, str], bytes]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _transport(
    url: str, headers: Mapping[str, str], timeout: float
) -> tuple[int, Mapping[str, str], bytes]:
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read(_MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        with error:
            return error.code, dict(error.headers), error.read(_MAX_BYTES + 1)


def _json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise DataError("Alpaca returned invalid JSON") from None
    if not isinstance(value, dict):
        raise DataError("Alpaca JSON must be an object")
    return value


def _token(body: dict[str, Any]) -> str | None:
    if "next_page_token" not in body or (
        body["next_page_token"] is not None and not isinstance(body["next_page_token"], str)
    ):
        raise DataError("Alpaca next_page_token must be a string or null")
    return body["next_page_token"] or None


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError(f"Alpaca {field} must be numeric")
    try:
        result = float(value)
    except OverflowError:
        raise DataError(f"Alpaca {field} must be finite") from None
    if not math.isfinite(result):
        raise DataError(f"Alpaca {field} must be finite")
    return result


def _date(value: object, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise DataError(f"Alpaca {field} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise DataError(f"Alpaca {field} must be a valid date") from None


def _bar_query(
    symbol: str, start: date, end: date, timeframe: BarTimeframe, *, adjustment: str
) -> dict[str, str]:
    if timeframe.is_daily:
        lower, upper = str(start), str(end)
    else:
        lower = (
            datetime.combine(start, datetime.min.time(), tzinfo=_NY)
            .astimezone(UTC)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        upper = (
            datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=_NY).astimezone(
                UTC
            )
            - timedelta(seconds=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "symbols": symbol,
        "timeframe": timeframe.alpaca,
        "start": lower,
        "end": upper,
        "adjustment": adjustment,
        "feed": FEED,
        "asof": str(end),
        "currency": "USD",
        "limit": "10000",
        "sort": "asc",
    }


def _envelope_timeframe(payload: dict[str, Any]) -> BarTimeframe:
    if payload.get("schema") == "alpha.alpaca.daily.v1":
        return DAILY
    if payload.get("schema") == "alpha.alpaca.bars.v1":
        value = payload.get("timeframe")
        if not isinstance(value, str):
            raise DataError("invalid Alpaca envelope timeframe")
        timeframe = parse_timeframe(value)
        if not timeframe.is_daily and payload["timeframe"] == timeframe.alpaca:
            return timeframe
    raise DataError("invalid Alpaca envelope schema")


def _pages(
    envelope: bytes, provider_symbol: str, start: date, end: date, timeframe: BarTimeframe
) -> dict[str, list[dict[str, Any]]]:
    payload = _json(envelope)
    if _envelope_timeframe(payload) != timeframe or not isinstance(payload.get("pages"), list):
        raise DataError("invalid Alpaca envelope schema")
    groups: dict[str, list[dict[str, Any]]] = {series: [] for series in _SERIES}
    expected: dict[str, str | None] = dict.fromkeys(_SERIES)
    seen: dict[str, set[str]] = {series: set() for series in _SERIES}
    position = 0
    for page in payload["pages"]:
        if (
            not isinstance(page, dict)
            or not isinstance(page.get("series"), str)
            or page["series"] not in groups
        ):
            raise DataError("invalid Alpaca envelope page series")
        series = page["series"]
        index = _SERIES.index(series)
        if index < position:
            raise DataError("invalid Alpaca envelope series order")
        position = index
        if page.get("status") != 200 or page.get("path") != (
            _ACTIONS if series == "actions" else _BARS
        ):
            raise DataError("invalid Alpaca envelope page status or path")
        query = page.get("query")
        if not isinstance(query, list) or any(
            not isinstance(pair, list)
            or len(pair) != 2
            or any(not isinstance(value, str) for value in pair)
            for pair in query
        ):
            raise DataError("invalid Alpaca envelope query")
        params = dict(query)
        if len(params) != len(query):
            raise DataError("Alpaca continuation query has duplicate keys")
        fixed = {**_FIXED_QUERY[series], "symbols": provider_symbol, "start": str(start)}
        if series != "actions":
            fixed.update(end=str(end), asof=str(end))
            if not timeframe.is_daily:
                fixed = _bar_query(
                    provider_symbol,
                    start,
                    end,
                    timeframe,
                    adjustment="raw" if series == "bars_raw" else "split",
                )
                if set(params) - {"page_token"} != set(fixed):
                    raise DataError(
                        f"Alpaca envelope query for {series} is not the adapter's request"
                    )
        else:
            fixed["end"] = str(end + timedelta(days=90))
        if any(params.get(name) != value for name, value in fixed.items()):
            raise DataError(f"Alpaca envelope query for {series} is not the adapter's request")
        if params.get("page_token") != expected[series] or (
            groups[series] and expected[series] is None
        ):
            raise DataError("Alpaca continuation token mismatch")
        encoded = page.get("body_b64")
        if not isinstance(encoded, str):
            raise DataError("invalid Alpaca envelope body encoding")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise DataError("invalid Alpaca envelope body encoding") from None
        if len(raw) > _MAX_BYTES:
            raise DataError("Alpaca page exceeds 32 MiB")
        if hashlib.sha256(raw).hexdigest() != page.get("body_sha256"):
            raise DataError("Alpaca body hash mismatch")
        body = _json(raw)
        token = _token(body)
        if token in seen[series]:
            raise DataError("Alpaca repeated continuation token")
        if token is not None:
            seen[series].add(token)
        expected[series] = token
        groups[series].append(body)
        if len(groups[series]) > _MAX_PAGES:
            raise DataError("Alpaca exceeded 200 pages per series")
    if any(not group for group in groups.values()):
        raise DataError("Alpaca envelope missing series")
    if any(expected.values()):
        raise DataError("Alpaca continuation token has no final page")
    return groups


def _bars(
    pages: list[dict[str, Any]],
    symbol: str,
    provider_symbol: str,
    start: date,
    end: date,
    timeframe: BarTimeframe,
) -> list[Bar]:
    rows: list[Bar] = []
    for page in pages:
        if "currency" in page and page["currency"] != "USD":
            raise DataError("Alpaca bars currency must be USD")
        bars = page.get("bars")
        if not isinstance(bars, dict):
            raise DataError("Alpaca bars must be an object")
        if set(bars) - {provider_symbol}:
            raise DataError("Alpaca bars contain another symbol")
        items = bars.get(provider_symbol, [])
        if not isinstance(items, list):
            raise DataError("Alpaca symbol bars must be a list")
        for item in items:
            if not isinstance(item, dict):
                raise DataError("Alpaca bar must be an object")
            stamp = item.get("t")
            if not isinstance(stamp, str) or not _TIMESTAMP.fullmatch(stamp):
                raise DataError("Alpaca t must be RFC 3339 with an offset")
            try:
                timestamp = datetime.fromisoformat(stamp.upper().replace("Z", "+00:00"))
            except ValueError:
                raise DataError("Alpaca t must be valid RFC 3339") from None
            # datetime truncates fractional seconds beyond six digits; reject nonzero
            # fractions explicitly so submicrosecond times cannot become midnight.
            fraction = re.search(r"\.(\d+)", stamp)
            if (
                timeframe.is_daily
                and fraction is not None
                and any(digit != "0" for digit in fraction.group(1))
            ):
                raise DataError("Alpaca t must be exactly midnight in America/New_York")
            local = timestamp.astimezone(_NY)
            if timeframe.is_daily:
                if (local.hour, local.minute, local.second, local.microsecond) != (0, 0, 0, 0):
                    raise DataError("Alpaca t must be exactly midnight in America/New_York")
            else:
                if fraction is not None or timestamp.second != 0:
                    raise DataError("Alpaca t must use whole minutes (second == 0, no fraction)")
                if not timeframe.is_aligned(timestamp):
                    raise DataError(f"Alpaca t must be timeframe-aligned: {stamp}")
            session = local.date()
            if not start <= session <= end:
                raise DataError("Alpaca session outside requested range")
            ts = (
                datetime.combine(session, datetime.min.time(), tzinfo=UTC)
                if timeframe.is_daily
                else timestamp.astimezone(UTC)
            )
            if rows and ts <= rows[-1].ts:
                raise DataError("Alpaca duplicate or descending session dates")
            values = {
                name: _number(item.get(key), name)
                for name, key in (
                    ("open", "o"),
                    ("high", "h"),
                    ("low", "l"),
                    ("close", "c"),
                    ("volume", "v"),
                )
            }
            if any(values[name] <= 0 for name in ("open", "high", "low", "close")):
                raise DataError("Alpaca bar prices must be positive")
            try:
                rows.append(Bar(symbol=symbol, ts=ts, **values))
            except ValidationError:
                raise DataError("invalid Alpaca bar OHLC or volume") from None
    return rows


def _actions(
    pages: list[dict[str, Any]], symbol: str, provider_symbol: str, start: date, end: date
) -> list[CorporateAction]:
    actions: dict[tuple[date, ActionType], CorporateAction] = {}
    seen_ids: dict[str, dict[str, Any]] = {}
    supported = {"forward_splits", "reverse_splits", "cash_dividends"}
    unsupported = {"stock_dividends", "spin_offs", "unit_splits"}
    for page in pages:
        groups = page.get("corporate_actions")
        if not isinstance(groups, dict):
            raise DataError("Alpaca corporate_actions must be an object")
        for kind, entries in groups.items():
            if kind not in supported | unsupported or not isinstance(entries, list):
                raise DataError("invalid Alpaca corporate action group")
            for item in entries:
                if not isinstance(item, dict):
                    raise DataError("Alpaca action must be an object")
                symbol_fields, date_field = _ACTION_FIELDS[kind]
                symbols = [item.get(field) for field in symbol_fields]
                if provider_symbol not in symbols:
                    raise DataError("Alpaca action contains another symbol")
                ex_date = _date(item.get(date_field), date_field)
                if not start <= ex_date <= end:
                    continue
                if kind == "spin_offs" and item.get("source_symbol") != provider_symbol:
                    continue  # the queried symbol is the new company; its prices are unaffected
                # One record per Alpaca id (else per identical content): a record repeated,
                # e.g. across pages, counts once; one id with two different bodies fails.
                action_id = item.get("id")
                identity_key = (
                    f"id:{action_id}"
                    if isinstance(action_id, str) and action_id
                    else "body:" + json.dumps(item, sort_keys=True)
                )
                if identity_key in seen_ids:
                    if seen_ids[identity_key] != item:
                        raise DataError(f"Alpaca action {action_id} listed twice, differently")
                    continue
                seen_ids[identity_key] = item
                if kind in unsupported:
                    raise DataError(
                        f"Alpaca {kind} on {ex_date}: ALPHA cannot adjust it; symbol refused"
                    )
                record = (
                    _date(item["record_date"], "record_date")
                    if item.get("record_date") is not None
                    else None
                )
                pay = (
                    _date(item["payable_date"], "payable_date")
                    if item.get("payable_date") is not None
                    else None
                )
                ratio = amount = None
                if kind == "cash_dividends":
                    action_type = ActionType.DIVIDEND
                    if item.get("currency") not in (None, "USD"):
                        raise DataError("Alpaca dividend currency must be USD or null")
                    amount = _number(item.get("rate"), "dividend rate")
                    if amount <= 0:
                        raise DataError("Alpaca dividend rate must be positive")
                    prior = actions.get((ex_date, action_type))
                    if prior is not None:
                        # Two distinct records (e.g. regular plus special) on one ex-date: sum.
                        assert prior.amount is not None
                        if (prior.record_date, prior.pay_date) != (record, pay):
                            raise DataError(
                                f"Alpaca dividends on {ex_date} disagree on record or pay date"
                            )
                        amount += prior.amount
                else:
                    action_type = ActionType.SPLIT
                    old = _number(item.get("old_rate"), "old_rate")
                    new = _number(item.get("new_rate"), "new_rate")
                    if old <= 0 or new <= 0:
                        raise DataError("Alpaca split rates must be positive")
                    ratio = new / old
                    if not math.isfinite(ratio) or ratio <= 0 or ratio == 1:
                        raise DataError("Alpaca split ratio must be finite, positive and not 1")
                    if (ex_date, action_type) in actions:
                        raise DataError(f"Alpaca two splits on {ex_date}")
                try:
                    actions[ex_date, action_type] = CorporateAction(
                        symbol=symbol,
                        action_type=action_type,
                        ex_date=ex_date,
                        record_date=record,
                        pay_date=pay,
                        ratio=ratio,
                        amount=amount,
                    )
                except ValidationError:
                    raise DataError("invalid Alpaca corporate action") from None
    return sorted(actions.values(), key=lambda action: (action.ex_date, action.action_type.value))


def parse_alpaca_daily(
    envelope: bytes,
    *,
    symbol: str,
    provider_symbol: str,
    asset_class: Literal["stock", "etf"],
    venue: str,
    calendar: str,
    currency: str,
    start: date,
    end: date,
    fetched_at: datetime,
) -> FetchResult:
    """Rebuild raw bars, actions and their receipt from the envelope alone."""
    if currency != "USD" or asset_class not in {"stock", "etf"}:
        raise DataError("Alpaca supports only USD stock or etf datasets")
    timeframe = _envelope_timeframe(_json(envelope))
    groups = _pages(envelope, provider_symbol, start, end, timeframe)
    raw = _bars(groups["bars_raw"], symbol, provider_symbol, start, end, timeframe)
    split = _bars(groups["bars_split"], symbol, provider_symbol, start, end, timeframe)
    if [bar.ts for bar in raw] != [bar.ts for bar in split]:
        raise DataError("Alpaca raw and split session dates differ")
    if not raw:
        raise DataError(f"Alpaca returned no bars for {symbol} {start}..{end}")
    actions = _actions(groups["actions"], symbol, provider_symbol, start, end)
    last_factor = raw[-1].close / split[-1].close
    for raw_bar, split_bar in zip(raw, split, strict=True):
        session = raw_bar.ts.date() if timeframe.is_daily else raw_bar.ts.astimezone(_NY).date()
        expected = math.prod(
            action.ratio
            for action in actions
            if action.action_type == ActionType.SPLIT
            and action.ratio is not None
            and action.ex_date > session
        )
        factor = raw_bar.close / split_bar.close
        relative = factor / last_factor if last_factor > 0 else math.inf
        if (
            not math.isfinite(relative)
            or not math.isfinite(expected)
            # Alpaca rounds adjusted prices (about four decimals): allow that rounding on top.
            or not math.isclose(relative, expected, rel_tol=1e-3 + 1e-4 / split_bar.close)
        ):
            raise DataError(
                f"Alpaca split cross-check failed for {symbol} on {session}: "
                f"bar factor {relative}, action factor {expected}"
            )
    bars = pl.DataFrame(
        [
            {
                "ts": bar.ts,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in raw
        ],
        schema={
            "ts": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        },
    )
    identity = DatasetIdentity(
        symbol=symbol,
        provider="alpaca",
        provider_symbol=provider_symbol,
        venue=venue,
        asset_class=asset_class,
        timeframe=timeframe.canonical,
        calendar=calendar,
        currency=currency,
        price_basis="raw",
    )
    receipt = FetchReceipt.create(
        identity=identity,
        requested_start=start,
        requested_end=end,
        fetched_at=fetched_at,
        adapter_version=_VERSION,
        parser_version=PARSER_VERSION,
        response_sha256=hashlib.sha256(envelope).hexdigest(),
        response_bytes=len(envelope),
        row_count=bars.height,
        action_count=len(actions),
        request_metadata={
            "endpoint_bars": _BARS,
            "endpoint_actions": _ACTIONS,
            "feed": FEED,
            "adjustment": "raw; split used as cross-check",
            "asof": end.isoformat(),
            "pages": str(sum(len(pages) for pages in groups.values())),
            **(
                {
                    "timeframe": timeframe.canonical,
                    "timestamp_convention": "interval_start_utc",
                    "session_scope": "all hours Alpaca returns: pre-market, regular, after-hours",
                }
                if not timeframe.is_daily
                else {}
            ),
        },
    )
    return FetchResult(
        symbol=symbol,
        bars=bars,
        actions=actions,
        identity=identity,
        receipt=receipt,
        raw_response=envelope,
    )


class AlpacaAdapter:
    """Bounded SIP bar acquisition; credentials are resolved only at fetch time."""

    name = "alpaca"
    version = _VERSION
    parser_version = PARSER_VERSION

    def __init__(
        self,
        *,
        timeframe: BarTimeframe = DAILY,
        asset_class: Literal["stock", "etf"] = "stock",
        venue: str = "US",
        calendar: str = "XNYS",
        currency: str = "USD",
        api_key_id: str | None = None,
        api_secret_key: str | None = None,
        transport: Transport = _transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if currency != "USD" or asset_class not in {"stock", "etf"}:
            raise DataError("Alpaca supports only USD stock or etf datasets")
        self._timeframe = timeframe
        self._asset_class = asset_class
        self._venue = venue
        self._calendar = calendar
        self._currency = currency
        self._key = api_key_id
        self._secret = api_secret_key
        self._transport = transport
        self._sleep = sleep
        self._clock = clock
        self._requested = False

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise DataError("Alpaca clock must be aware UTC")
        return now

    def _wait(self, headers: Mapping[str, str], attempt: int) -> float:
        lowered = {key.lower(): value for key, value in headers.items()}
        retry = lowered.get("retry-after", "")
        if re.fullmatch(r"[0-9]+", retry):
            return float(min(int(retry), 60))
        reset = lowered.get("x-ratelimit-reset", "")
        if re.fullmatch(r"[0-9]+", reset):
            remaining = int(reset) - self._now().timestamp()
            if remaining > 0:
                return min(remaining, 60.0)
        return float(2**attempt)

    def _request(self, url: str, headers: Mapping[str, str], secrets: tuple[str, str]) -> bytes:
        for attempt in range(3):
            if self._requested:
                self._sleep(0.35)
            self._requested = True
            try:
                status, response_headers, body = self._transport(url, headers, 30)
            except (
                ValueError,
                http.client.HTTPException,
                urllib.error.URLError,
                TimeoutError,
                OSError,
                http.client.IncompleteRead,
            ) as exc:
                if attempt == 2:
                    raise DataError(f"Alpaca transport failed: {type(exc).__name__}") from None
                self._sleep(float(2**attempt))
                continue
            if len(body) > _MAX_BYTES:
                raise DataError(f"Alpaca page exceeds 32 MiB (HTTP {status})")
            if status == 200:
                # Never persist a response that reflects authentication headers.
                if any(secret.encode() in body for secret in secrets):
                    raise DataError("Alpaca response contains a credential")
                return body
            if status == 429 or 500 <= status <= 599:
                if attempt < 2:
                    self._sleep(self._wait(response_headers, attempt))
                    continue
                if status == 429:
                    raise DataError("Alpaca rate limit (HTTP 429) persisted after 3 attempts")
                raise DataError(f"Alpaca HTTP {status} persisted after 3 attempts")
            if status == 401:
                raise DataError("Alpaca rejected the key with HTTP 401; check both key variables")
            if status == 403:
                try:
                    payload = json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    payload = None
                message = payload.get("message") if isinstance(payload, dict) else None
                detail = message if isinstance(message, str) else "no provider message"
                for secret in secrets:
                    detail = detail.replace(secret, "[redacted]")
                raise DataError(
                    f"Alpaca refused the request with HTTP 403: {detail[:200]}; "
                    "the free plan may not cover it"
                )
            raise DataError(f"Alpaca rejected the request with HTTP {status}")
        raise AssertionError("unreachable Alpaca attempt loop")

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        key = os.environ.get("APCA_API_KEY_ID", "") if self._key is None else self._key
        secret = os.environ.get("APCA_API_SECRET_KEY", "") if self._secret is None else self._secret
        key, secret = key.strip(), secret.strip()
        if not key or not secret:
            raise DataError(
                "Alpaca requires APCA_API_KEY_ID and APCA_API_SECRET_KEY: "
                "create a free Alpaca account, generate a key, and set both variables "
                "in your own terminal; see docs/operations/alpaca-stock-data.md"
            )
        for name, value in (("APCA_API_KEY_ID", key), ("APCA_API_SECRET_KEY", secret)):
            if not re.fullmatch(r"[\x21-\x7e]+", value):
                raise DataError(
                    f"{name} holds characters a key cannot contain (spaces, line breaks or "
                    "non-ASCII); set it again from Alpaca's dashboard"
                )
        if end < start:
            raise DataError(f"Alpaca end {end} precedes start {start}")
        if start < date(2016, 1, 1):
            raise DataError("Alpaca history starts in 2016; start must be >= 2016-01-01")
        latest = self._now().astimezone(_NY).date() - timedelta(days=1)
        if end > latest:
            raise DataError(f"Alpaca requires completed sessions; latest allowed end is {latest}")
        symbol = symbol.strip().upper()
        if not re.fullmatch(r"[A-Z0-9.\-]+", symbol):
            raise DataError("invalid Alpaca symbol; use only A-Z0-9.-")
        headers = {
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json",
            "User-Agent": "Project-ALPHA/1.0",
        }
        pages: list[dict[str, Any]] = []
        for series in _SERIES:
            path = _ACTIONS if series == "actions" else _BARS
            if series == "actions":
                query = {
                    "symbols": symbol,
                    "types": _ACTION_TYPES,
                    "start": str(start),
                    # Filtered on process date (a dividend's is its pay date, weeks after the
                    # ex-date), so look 90 days past the end; ex-dates after `end` are dropped.
                    "end": str(end + timedelta(days=90)),
                    "limit": "1000",
                    "sort": "asc",
                }
            else:
                query = _bar_query(
                    symbol,
                    start,
                    end,
                    self._timeframe,
                    adjustment="raw" if series == "bars_raw" else "split",
                )
            seen: set[str] = set()
            for _ in range(_MAX_PAGES):
                raw = self._request(
                    f"{_HOST}{path}?{urllib.parse.urlencode(query)}", headers, (key, secret)
                )
                body = _json(raw)
                pages.append(
                    {
                        "series": series,
                        "path": path,
                        "query": list(query.items()),
                        "status": 200,
                        "body_sha256": hashlib.sha256(raw).hexdigest(),
                        "body_b64": base64.b64encode(raw).decode("ascii"),
                    }
                )
                token = _token(body)
                if token is None:
                    break
                if token in seen:
                    raise DataError("Alpaca repeated continuation token")
                seen.add(token)
                query["page_token"] = token
            else:
                raise DataError("Alpaca exceeded 200 pages per series")
        envelope = json.dumps(
            {"schema": "alpha.alpaca.daily.v1", "pages": pages}
            if self._timeframe.is_daily
            else {
                "schema": "alpha.alpaca.bars.v1",
                "timeframe": self._timeframe.alpaca,
                "pages": pages,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
        return parse_alpaca_daily(
            envelope,
            symbol=symbol,
            provider_symbol=symbol,
            asset_class=self._asset_class,
            venue=self._venue,
            calendar=self._calendar,
            currency=self._currency,
            start=start,
            end=end,
            fetched_at=self._now(),
        )
