"""Offline funding-page progression; no transport, persistence or acquisition authority.

Shelved (2026-11-14, triage card B): not wired in, kept for funding-event research; real
downloads wait on the durable acquisition journal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import polars as pl

from alpha_core import DataError

from .bybit import _category, _result_object, parse_funding_page

type StopReason = Literal["lower_bound_reached", "empty_page", "call_limit", "byte_limit"]
type PageSupplier = Callable[[dict[str, str | int], int], bytes]


@dataclass(frozen=True)
class FundingPageCollection:
    """Observed candidates only. The boundary is diagnostic, not a durable resume token."""

    observations: pl.DataFrame
    calls_used: int
    accepted_payload_bytes: int
    next_end_ms: int | None
    stop_reason: StopReason
    coverage_complete: Literal[False] = False


def collect_funding_pages(
    supply_page: PageSupplier,
    *,
    symbol: str,
    category: Literal["linear", "inverse"],
    fetched_at: datetime,
    start_ms: int,
    end_ms: int,
    max_calls: int = 10,
    max_total_bytes: int = 8 * 1024 * 1024,
) -> FundingPageCollection:
    """Walk caller-supplied pages backward over paired inclusive millisecond bounds.

    Each callback receives exact request parameters and its remaining byte allowance.
    It must bound its own allocation/read: returned-byte checks cannot constrain work
    inside an arbitrary callback. No callback is installed by this module. Errors
    discard the collection, never return partial success or retry. A short page still
    progresses; empty/lower-bound/budget stops never establish historical completeness.
    """
    if not isinstance(symbol, str) or not symbol or category not in {"linear", "inverse"}:
        raise DataError("Bybit funding request identity is invalid")
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise DataError("Bybit funding knowledge time must be timezone-aware")
    if type(start_ms) is not int or type(end_ms) is not int or end_ms <= start_ms:
        raise DataError("Bybit funding bounds must be increasing integer milliseconds")
    if end_ms > int(fetched_at.timestamp() * 1000):
        raise DataError("Bybit funding end exceeds the acquisition knowledge time")
    if type(max_calls) is not int or not 1 <= max_calls <= 100:
        raise DataError("Bybit funding call limit must be between 1 and 100")
    if type(max_total_bytes) is not int or not 1 <= max_total_bytes <= 32 * 1024 * 1024:
        raise DataError("Bybit funding byte limit must be between 1 and 32 MiB")

    frames: list[pl.DataFrame] = []
    seen: dict[int, float] = {}
    boundary: int | None = end_ms
    calls = accepted_bytes = 0
    reason: StopReason = "call_limit"
    while calls < max_calls and boundary is not None:
        allowance = min(8 * 1024 * 1024, max_total_bytes - accepted_bytes)
        if allowance == 0:
            reason = "byte_limit"
            break
        params: dict[str, str | int] = {
            "symbol": symbol,
            "category": category,
            "startTime": start_ms,
            "endTime": boundary,
            "limit": 200,
        }
        calls += 1
        payload = supply_page(params, allowance)
        if type(payload) is not bytes or len(payload) > allowance:
            raise DataError("Bybit funding supplied page exceeds its byte allowance")
        result, _ = _result_object(payload)
        _category(result.get("category"), category)
        if result.get("list") == []:
            accepted_bytes += len(payload)
            reason = "empty_page"
            break
        # Original global bounds stay increasing even for the final singleton request.
        frame = parse_funding_page(
            payload,
            symbol=symbol,
            category=category,
            fetched_at=fetched_at,
            start_ms=start_ms,
            end_ms=end_ms,
        )
        oldest = boundary
        for timestamp, rate in frame.select("timestamp", "funding_rate").iter_rows():
            instant = int(timestamp.timestamp() * 1000)
            if instant in seen:
                kind = "repeated" if seen[instant] == rate else "conflicting"
                raise DataError(f"Bybit funding {kind} settlement across pages")
            if instant > boundary:
                raise DataError("Bybit funding page exceeds its backward boundary")
            seen[instant] = rate
            oldest = min(oldest, instant)
        frames.append(frame)
        accepted_bytes += len(payload)
        if oldest == start_ms:
            boundary = None
            reason = "lower_bound_reached"
            break
        boundary = oldest - 1
        if accepted_bytes == max_total_bytes:
            reason = "byte_limit"
            break

    observations = (
        pl.concat(frames).sort("timestamp")
        if frames
        else pl.DataFrame(
            schema={
                "timestamp": pl.Datetime("us", "UTC"),
                "category": pl.String,
                "symbol": pl.String,
                "funding_rate": pl.Float64,
            }
        )
    )
    return FundingPageCollection(observations, calls, accepted_bytes, boundary, reason)
