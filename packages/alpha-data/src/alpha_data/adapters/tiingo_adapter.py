"""Tiingo end-of-day adapter with raw-response receipts and explicit actions."""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import UTC, date, datetime
from typing import Literal

import polars as pl
from pydantic import ValidationError

from alpha_core import ActionType, Bar, CorporateAction, DataError
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt, FetchResult

_VERSION = "1"
PARSER_VERSION = "1"
_ENDPOINT = "https://api.tiingo.com/tiingo/daily/{symbol}/prices"


def _number(row: dict[str, object], name: str, index: int, symbol: str) -> float:
    value = row.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError(f"invalid Tiingo row {index} for {symbol}: {name} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise DataError(f"invalid Tiingo row {index} for {symbol}: {name} is not finite")
    return result


def parse_tiingo_eod(
    raw: bytes,
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
    """Parse one Tiingo EOD response while retaining raw, unadjusted OHLCV."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataError(f"Tiingo returned invalid JSON for {symbol}") from exc
    if not isinstance(payload, list) or not payload:
        raise DataError(f"Tiingo returned no data for {symbol} {start}..{end}")

    rows: list[dict[str, object]] = []
    actions: list[CorporateAction] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise DataError(f"invalid Tiingo row {index} for {symbol}: expected an object")
        try:
            timestamp = datetime.fromisoformat(str(item.get("date", "")).replace("Z", "+00:00"))
        except ValueError as exc:
            raise DataError(f"invalid Tiingo row {index} for {symbol}: invalid date") from exc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise DataError(f"invalid Tiingo row {index} for {symbol}: date is timezone-naive")
        timestamp = timestamp.astimezone(UTC)
        if not start <= timestamp.date() <= end:
            raise DataError(
                f"invalid Tiingo row {index} for {symbol}: date outside requested range"
            )
        values = {
            name: _number(item, name, index, symbol)
            for name in ("open", "high", "low", "close", "volume")
        }
        if any(values[name] <= 0.0 for name in ("open", "high", "low", "close")):
            raise DataError(f"invalid Tiingo bar {index} for {symbol}: prices must be positive")
        adjusted = {
            name: _number(item, f"adj{name.capitalize()}", index, symbol)
            for name in ("open", "high", "low", "close")
        }
        if any(value <= 0.0 for value in adjusted.values()):
            raise DataError(
                f"invalid Tiingo bar {index} for {symbol}: adjusted prices must be positive"
            )
        ratios = [adjusted[name] / values[name] for name in ("open", "high", "low", "close")]
        if max(ratios) - min(ratios) > max(1e-9, abs(ratios[0]) * 1e-7):
            raise DataError(f"Tiingo adjustment ratios disagree within row {index} for {symbol}")
        dividend = _number(item, "divCash", index, symbol)
        split = _number(item, "splitFactor", index, symbol)
        if dividend < 0 or split <= 0:
            raise DataError(f"invalid Tiingo actions in row {index} for {symbol}")
        try:
            Bar(
                symbol=symbol,
                ts=timestamp,
                open=values["open"],
                high=values["high"],
                low=values["low"],
                close=values["close"],
                volume=values["volume"],
            )
        except ValidationError as exc:
            raise DataError(f"invalid Tiingo bar {index} for {symbol}: {exc}") from exc
        rows.append({"ts": timestamp, **values})
        if dividend > 0:
            actions.append(
                CorporateAction(
                    symbol=symbol,
                    action_type=ActionType.DIVIDEND,
                    ex_date=timestamp.date(),
                    amount=dividend,
                )
            )
        if split != 1.0:
            actions.append(
                CorporateAction(
                    symbol=symbol,
                    action_type=ActionType.SPLIT,
                    ex_date=timestamp.date(),
                    ratio=split,
                )
            )

    actions.sort(key=lambda action: (action.ex_date, action.action_type.value))
    bars = pl.DataFrame(
        rows,
        schema={
            "ts": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        },
    ).sort("ts")
    identity = DatasetIdentity(
        symbol=symbol,
        provider="tiingo",
        provider_symbol=provider_symbol,
        venue=venue,
        asset_class=asset_class,
        timeframe="1D",
        calendar=calendar,
        currency=currency,
        price_basis="raw",
    )
    response_hash = hashlib.sha256(raw).hexdigest()
    receipt = FetchReceipt.create(
        identity=identity,
        requested_start=start,
        requested_end=end,
        fetched_at=fetched_at,
        adapter_version=_VERSION,
        parser_version=PARSER_VERSION,
        response_sha256=response_hash,
        response_bytes=len(raw),
        row_count=bars.height,
        action_count=len(actions),
        request_metadata={"endpoint": f"/tiingo/daily/{provider_symbol}/prices"},
    )
    return FetchResult(
        symbol=symbol,
        bars=bars,
        actions=actions,
        identity=identity,
        receipt=receipt,
        raw_response=raw,
    )


class TiingoAdapter:
    """Live Tiingo EOD adapter. The API key is sent only in an authorization header."""

    name = "tiingo"
    version = _VERSION
    parser_version = PARSER_VERSION

    def __init__(
        self,
        *,
        api_key: str | None = None,
        canonical_symbol: str | None = None,
        asset_class: Literal["stock", "etf"] = "stock",
        venue: str = "US",
        calendar: str = "XNYS",
        currency: str = "USD",
    ) -> None:
        self._api_key = os.environ.get("ALPHA_TIINGO_API_KEY", "") if api_key is None else api_key
        self._canonical_symbol = canonical_symbol
        self._asset_class = asset_class
        self._venue = venue
        self._calendar = calendar
        self._currency = currency

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        if not self._api_key.strip():
            raise DataError("Tiingo requires a non-empty ALPHA_TIINGO_API_KEY")
        if end < start:
            raise DataError(f"Tiingo end {end} precedes start {start}")
        import urllib.error  # noqa: PLC0415
        import urllib.parse  # noqa: PLC0415
        import urllib.request  # noqa: PLC0415

        provider_symbol = symbol.strip().upper()
        if not provider_symbol or "/" in provider_symbol or ".." in provider_symbol:
            raise DataError(f"invalid Tiingo symbol {symbol!r}")
        canonical_symbol = (self._canonical_symbol or provider_symbol).strip().upper()
        if not canonical_symbol or "/" in canonical_symbol or ".." in canonical_symbol:
            raise DataError(f"invalid canonical symbol {canonical_symbol!r}")
        quoted = urllib.parse.quote(provider_symbol, safe=".-")
        query = urllib.parse.urlencode(
            {"startDate": start.isoformat(), "endDate": end.isoformat(), "resampleFreq": "daily"}
        )
        request = urllib.request.Request(
            f"{_ENDPOINT.format(symbol=quoted)}?{query}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Token {self._api_key}",
                "User-Agent": "Project-ALPHA/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise DataError(f"Tiingo rejected the request with HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise DataError(
                f"Tiingo transport failed: {exc.reason if hasattr(exc, 'reason') else exc}"
            ) from exc
        return parse_tiingo_eod(
            raw,
            symbol=canonical_symbol,
            provider_symbol=provider_symbol,
            asset_class=self._asset_class,
            venue=self._venue,
            calendar=self._calendar,
            currency=self._currency,
            start=start,
            end=end,
            fetched_at=datetime.now(UTC),
        )
