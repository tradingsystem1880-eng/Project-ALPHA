"""Shared bounded fetch, decode and validation vocabulary for the crypto providers.

Every helper is parameterised by the calling provider's own constants and message noun:
host prefixes, MIME sets, byte caps, timeouts and 429 policy stay owned by each provider.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import Message
from typing import Any, Final, cast
from urllib.request import HTTPRedirectHandler, Request

from alpha_core import DataError

type EndpointTable = Mapping[str, tuple[str, frozenset[str]]]

_JSON_HEADERS: Final = {"Accept": "application/json", "User-Agent": "Project-ALPHA/1.0"}
_EARLIEST_INSTANT: Final = datetime(2010, 1, 1, tzinfo=UTC)
_LATEST_INSTANT: Final = datetime(2100, 1, 1, tzinfo=UTC)


def resolve_endpoint[ValueT](
    endpoints: EndpointTable,
    endpoint: str,
    params: Mapping[str, ValueT],
    *,
    provider: str,
    param_message: str | None = None,
    max_params: int | None = None,
) -> tuple[str, list[tuple[str, ValueT]]]:
    """Resolve one allowlisted endpoint path and its deterministically ordered parameters."""
    definition = endpoints.get(endpoint)
    if definition is None:
        raise DataError(f"unsupported {provider} endpoint {endpoint!r}")
    path, allowed = definition
    if set(params) - allowed:
        raise DataError(param_message or f"unsupported {provider} query parameters")
    if max_params is not None and (
        len(params) > max_params
        or any(
            isinstance(value, bool) or not isinstance(value, str | int) for value in params.values()
        )
    ):
        raise DataError(f"{provider} query contains an unsupported value")
    return path, sorted(params.items())


def _retry_after_delay(headers: Message | None, attempt: int) -> float:
    raw = headers.get("Retry-After") if headers is not None else None
    provider_delay: float = 0.0
    if raw is not None:
        try:
            provider_delay = float(str(raw))
        except ValueError:
            provider_delay = 0.0
    backoff: float = 2.1 * (2**attempt)
    return min(10.0, max(backoff, provider_delay))


@dataclass
class RequestBudget:
    """One invocation's HTTP attempts and application body bytes, never socket traffic."""

    max_requests: int
    max_bytes: int
    requests_used: int = field(default=0, init=False)
    bytes_read: int = field(default=0, init=False)
    failed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value <= 0 for value in (self.max_requests, self.max_bytes)
        ):
            raise DataError("request and byte budgets must be positive integers")

    def reserve_request(self) -> None:
        if self.failed:
            raise DataError("request budget aborted after transport failure")
        if self.requests_used >= self.max_requests:
            raise DataError("total request budget exhausted")
        if self.bytes_read >= self.max_bytes:
            raise DataError("total response byte budget exhausted")
        self.requests_used += 1


class _NoBudgetRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _read_budgeted(response: Any, budget: RequestBudget, max_bytes: int) -> bytes:
    import http.client  # noqa: PLC0415

    chunks: list[bytes] = []
    size = 0
    while True:
        remaining = budget.max_bytes - budget.bytes_read
        if remaining <= 0:
            raise DataError("total response byte budget exhausted before EOF")
        try:
            chunk = bytes(response.read(min(65536, remaining, max_bytes + 1 - size)))
        except http.client.IncompleteRead as exc:
            budget.bytes_read += len(exc.partial)
            raise
        budget.bytes_read += len(chunk)
        size += len(chunk)
        if size > max_bytes:
            raise DataError("response exceeds the byte limit")
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def fetch_bounded(
    request_or_url: str | Request,
    *,
    provider: str,
    host_prefix: str | tuple[str, ...],
    content_types: frozenset[str],
    max_bytes: int,
    timeout_seconds: int,
    mime_message: str = "response MIME is not JSON",
    report_http_code: bool = False,
    retry_429: bool = False,
    budget: RequestBudget | None = None,
) -> bytes:
    """Read one bounded response, revalidating the redirect host, the MIME and the byte cap."""
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    request = (
        Request(request_or_url, headers=dict(_JSON_HEADERS))
        if isinstance(request_or_url, str)
        else request_or_url
    )
    max_attempts = 4 if retry_429 else 1
    if budget is not None and not request.full_url.startswith(host_prefix):
        raise DataError(f"{provider} request host is invalid")
    opener = urllib.request.build_opener(_NoBudgetRedirect()) if budget is not None else None
    payload: bytes | None = None
    for attempt in range(max_attempts):
        if budget is not None:
            budget.reserve_request()
        try:
            context = (
                urllib.request.urlopen(request, timeout=timeout_seconds)  # noqa: S310
                if opener is None
                else opener.open(request, timeout=timeout_seconds)
            )
            with context as response:
                if not str(response.geturl()).startswith(host_prefix):
                    raise DataError(f"{provider} redirect host is invalid")
                content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0]
                if content_type not in content_types:
                    raise DataError(f"{provider} {mime_message}")
                payload = (
                    bytes(response.read(max_bytes + 1))
                    if budget is None
                    else _read_budgeted(response, budget, max_bytes)
                )
            break
        except urllib.error.HTTPError as exc:
            if budget is not None:
                exc.close()
            if retry_429 and exc.code == 429 and attempt < max_attempts - 1:
                if budget is not None and budget.requests_used >= budget.max_requests:
                    raise DataError("total request budget exhausted") from exc
                time.sleep(_retry_after_delay(exc.headers, attempt))
                continue
            if report_http_code:
                raise DataError(f"{provider} request failed with HTTP {exc.code}") from exc
            raise DataError(f"{provider} request failed") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if budget is not None:
                budget.failed = True
            raise DataError(f"{provider} request failed") from exc
        except BaseException:
            if budget is not None:
                budget.failed = True
            raise
    if payload is None:
        raise DataError(f"{provider} request failed")
    if len(payload) > max_bytes:
        raise DataError(f"{provider} response exceeds the byte limit")
    return payload


def _loads(payload: bytes, provider: str) -> object:
    try:
        return json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f"{provider} response is malformed") from exc


def decode_json_object(
    payload: bytes, *, provider: str, shape_message: str = "must be an object"
) -> dict[str, object]:
    """Decode one JSON payload that must be a top-level object."""
    raw = _loads(payload, provider)
    if not isinstance(raw, dict):
        raise DataError(f"{provider} response {shape_message}")
    return cast(dict[str, object], raw)


def decode_json_list(payload: bytes, *, provider: str) -> list[dict[str, object]]:
    """Decode one JSON payload that must be a top-level list of objects."""
    raw = _loads(payload, provider)
    if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
        raise DataError(f"{provider} response must be a list of objects")
    return list(raw)


def finite_float(value: object, label: str, *, allow_text: bool = True) -> float:
    """Return one finite float, rejecting booleans, unparseable text and non-finite values."""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise DataError(f"{label} is invalid")
    if isinstance(value, str) and not allow_text:
        raise DataError(f"{label} is invalid")
    try:
        number = float(value)
    except ValueError as exc:
        raise DataError(f"{label} is invalid") from exc
    if not math.isfinite(number):
        raise DataError(f"{label} is not finite")
    return number


def epoch_ms_to_utc(
    raw: str | int | float,
    label: str,
    *,
    range_label: str | None = None,
    allow_microseconds: bool = False,
    enforce_window: bool = False,
    allow_future: bool = False,
) -> datetime:
    """Decode one epoch-millisecond instant.

    ``enforce_window`` opts into the 2010-2100 sanity window that catches a seconds-resolution
    column silently decoding to 1970; Bybit keeps it off because its records are already bounded
    against the fetch clock and pre-2010 sentinels there fail on their own field checks first.
    """
    bound = range_label or label
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise DataError(f"{label} is invalid") from exc
    divisor = 1_000_000 if allow_microseconds and value >= 1_000_000_000_000_000 else 1_000
    try:
        instant = datetime.fromtimestamp(value / divisor, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise DataError(f"{bound} is outside the supported range") from exc
    if enforce_window and (
        instant < _EARLIEST_INSTANT or (not allow_future and instant > _LATEST_INSTANT)
    ):
        raise DataError(f"{bound} is outside the supported range")
    return instant


def validate_book_sides(
    bids: list[float], asks: list[float], *, provider: str, crossed_message: str
) -> None:
    """Reject a book whose sides are not strictly monotonic or whose top of book is crossed."""
    if any(right >= left for left, right in zip(bids, bids[1:], strict=False)):
        raise DataError(f"{provider} bids are not strictly descending")
    if any(right <= left for left, right in zip(asks, asks[1:], strict=False)):
        raise DataError(f"{provider} asks are not strictly ascending")
    if bids[0] >= asks[0]:
        raise DataError(crossed_message)
