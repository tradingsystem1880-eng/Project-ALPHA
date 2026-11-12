"""Shared bounded fetch, decode and validation vocabulary for the crypto providers.

Every helper is parameterised by the calling provider's own constants and message noun:
host prefixes, MIME sets, byte caps, timeouts and 429 policy stay owned by each provider.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import Message
from typing import Any, Final, Literal, Protocol, cast
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


@dataclass(frozen=True)
class CompleteHttpResponse:
    """Local transport evidence, NOT authentication, raw admission or replay authority.

    Emitted only after a bounded identity-encoded Content-Length body, EOF probe and
    context cleanup succeed. Construction alone cannot establish source provenance.
    """

    request_hash: str
    status_code: Literal[200, 429]
    content_length: int
    body: bytes
    basis: Literal["identity_content_length_and_eof"] = "identity_content_length_and_eof"
    schema_version: Literal[1] = 1

    @property
    def actual_bytes(self) -> int:
        return len(self.body)

    @property
    def body_sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


def _read_complete_identity(
    response: Any, budget: RequestBudget | None, max_bytes: int, *, expected_status: int = 200
) -> bytes:
    """Strict supported framing subset; missing/chunked/encoded framing is refused."""
    import http.client  # noqa: PLC0415

    # urllib already bounds HTTP headers; independently bound the accepted fixture metadata.
    headers: dict[str, str] = {}
    for index, (key, value) in enumerate(response.headers.items()):
        if (
            index >= 128
            or type(key) is not str
            or type(value) is not str
            or len(key) > 1024
            or len(value) > 8192
        ):
            raise DataError("complete response headers exceed bounds")
        name = key.lower()
        if name in headers:
            raise DataError("complete response duplicate header")
        headers[name] = value.strip()
    declared = headers.get("content-length", "")
    status = response.getcode()
    if (
        type(status) is not int
        or status != expected_status
        or not declared.isascii()
        or not declared.isdecimal()
        or len(declared) > 10
        or headers.get("content-encoding", "identity").lower() != "identity"
        or "transfer-encoding" in headers
    ):
        raise DataError("complete response requires status200 identity Content-Length framing")
    length = int(declared)
    if length > max_bytes:
        raise DataError("complete response declared byte limit exceeded")
    chunks: list[bytes] = []
    size = 0
    while True:
        requested = min(65536, length - size + 1)
        if budget is not None:
            remaining = budget.max_bytes - budget.bytes_read
            if remaining <= 0:
                raise DataError("complete response byte budget exhausted before EOF")
            requested = min(requested, remaining)
        try:
            chunk = response.read(requested)
        except http.client.IncompleteRead as error:
            if budget is not None:
                budget.bytes_read += len(error.partial)
            raise
        if type(chunk) is not bytes or len(chunk) > requested:
            raise DataError("complete response read contract invalid")
        if budget is not None:
            budget.bytes_read += len(chunk)
        size += len(chunk)
        if size > length:
            raise DataError("complete response exceeds declared length")
        if not chunk:
            if size != length:
                raise DataError("complete response truncated before declared length")
            return b"".join(chunks)
        chunks.append(chunk)


class HttpAttemptHook(Protocol):
    """Trusted injected boundary around ONE explicit open/read/close attempt.

    Identity hashes method+exact URL; no headers or raw URL are passed to accounting.
    The implementation must return the supplied operation's bytes or raise. It cannot
    confer live admission. Redirects are refused whenever this hook is installed.
    """

    def __call__(
        self, request_hash: str, retry_ordinal: int, send: Callable[[], bytes], /
    ) -> bytes: ...


def http_request_hash(request: Request) -> str:
    return hashlib.sha256(
        json.dumps([request.get_method(), request.full_url], separators=(",", ":")).encode()
    ).hexdigest()


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
    attempt_hook: HttpAttemptHook | None = None,
    response_evidence: Callable[[CompleteHttpResponse], None] | None = None,
    error_response_evidence: Callable[[CompleteHttpResponse], None] | None = None,
) -> bytes:
    """Read one bounded response, revalidating the redirect host, the MIME and the byte cap."""
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    request = (
        Request(request_or_url, headers=dict(_JSON_HEADERS))
        if isinstance(request_or_url, str)
        else request_or_url
    )
    if error_response_evidence is not None and response_evidence is None:
        raise DataError("error evidence requires complete response evidence")
    strict = response_evidence is not None
    expected_url, expected_method = request.full_url, request.get_method()
    request_hash = http_request_hash(request) if attempt_hook is not None or strict else None
    if (attempt_hook is not None or strict) and (
        request.get_method() != "GET" or request.data is not None
    ):
        raise DataError("accounted HTTP transport requires a body-free GET")
    max_attempts = 4 if retry_429 else 1
    if (
        budget is not None or attempt_hook is not None or strict
    ) and not request.full_url.startswith(host_prefix):
        raise DataError(f"{provider} request host is invalid")
    opener = (
        urllib.request.build_opener(_NoBudgetRedirect())
        if budget is not None or attempt_hook is not None or strict
        else None
    )
    payload: bytes | None = None
    for attempt in range(max_attempts):
        called = False
        if budget is not None and attempt_hook is None:
            budget.reserve_request()

        def send() -> bytes:
            nonlocal called
            if called:
                raise DataError("HTTP attempt operation already called")
            called = True
            if budget is not None and attempt_hook is not None:
                budget.reserve_request()
            opened = False
            try:
                if strict and (
                    request.full_url != expected_url
                    or request.get_method() != expected_method
                    or request.data is not None
                ):
                    raise DataError("complete response identity changed before open")
                context = (
                    urllib.request.urlopen(request, timeout=timeout_seconds)  # noqa: S310
                    if opener is None
                    else opener.open(request, timeout=timeout_seconds)
                )
                opened = True
                with context as response:
                    if strict and (
                        response.geturl() != expected_url
                        or request.full_url != expected_url
                        or request.get_method() != expected_method
                        or request.data is not None
                    ):
                        raise DataError("complete response exact request identity changed")
                    if not str(response.geturl()).startswith(host_prefix):
                        raise DataError(f"{provider} redirect host is invalid")
                    content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0]
                    if content_type not in content_types:
                        raise DataError(f"{provider} {mime_message}")
                    body = (
                        _read_complete_identity(response, budget, max_bytes)
                        if strict
                        else bytes(response.read(max_bytes + 1))
                        if budget is None
                        else _read_budgeted(response, budget, max_bytes)
                    )
                    if attempt_hook is not None and len(body) > max_bytes:
                        raise DataError(f"{provider} response exceeds the byte limit")
                if response_evidence is not None:
                    if (
                        request.full_url != expected_url
                        or request.get_method() != expected_method
                        or request.data is not None
                        or response.geturl() != expected_url
                    ):
                        raise DataError("complete response request identity changed during cleanup")
                    assert request_hash is not None
                    response_evidence(
                        CompleteHttpResponse(
                            request_hash=request_hash,
                            status_code=200,
                            content_length=len(body),
                            body=body,
                        )
                    )
                return body
            except urllib.error.HTTPError as error:
                if error_response_evidence is not None:
                    try:
                        if (
                            opened
                            or error.code != 429
                            or error.geturl() != expected_url
                            or request.full_url != expected_url
                            or request.get_method() != expected_method
                            or request.data is not None
                        ):
                            raise DataError("complete error response identity or status invalid")
                        error_body = _read_complete_identity(
                            error, budget, max_bytes, expected_status=429
                        )
                    finally:
                        error.close()
                    if (
                        error.geturl() != expected_url
                        or request.full_url != expected_url
                        or request.get_method() != expected_method
                        or request.data is not None
                    ):
                        raise DataError(
                            "complete error response identity changed during cleanup"
                        ) from None
                    assert request_hash is not None
                    error_response_evidence(
                        CompleteHttpResponse(
                            request_hash=request_hash,
                            status_code=429,
                            content_length=len(error_body),
                            body=error_body,
                        )
                    )
                elif attempt_hook is not None or strict:
                    error.close()
                    if opened:
                        raise DataError("accounted HTTP response read or close failed") from None
                raise

        try:
            if attempt_hook is None:
                payload = send()
            else:
                assert request_hash is not None
                payload = attempt_hook(request_hash, attempt, send)
            if attempt_hook is not None and (not called or type(payload) is not bytes):
                raise DataError("HTTP attempt hook did not execute the operation")
            break
        except urllib.error.HTTPError as exc:
            if budget is not None and attempt_hook is None and not strict:
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
