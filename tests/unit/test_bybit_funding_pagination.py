"""Caller-supplied synthetic funding pages only; no network or storage."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from alpha_core import DataError
from alpha_data.crypto.providers.bybit import parse_funding_history
from alpha_data.crypto.providers.bybit_funding import FundingPageCollection, collect_funding_pages

NOW = datetime(2026, 9, 1, tzinfo=UTC)
END = int(NOW.timestamp() * 1000)
START = END - 1000


def page(
    *times: int, rate: str = "-0.0001", symbol: str = "BTCUSDT", category: str = "linear"
) -> bytes:
    return json.dumps(
        {
            "retCode": 0,
            "result": {
                "category": category,
                "list": [
                    {"symbol": symbol, "fundingRateTimestamp": str(t), "fundingRate": rate}
                    for t in times
                ],
            },
        }
    ).encode()


def collect(
    pages: list[bytes], *, max_calls: int = 10, max_total_bytes: int = 1_000_000
) -> tuple[FundingPageCollection, list[tuple[dict[str, str | int], int]]]:
    requests: list[tuple[dict[str, str | int], int]] = []
    iterator = iter(pages)

    def supplied(params: dict[str, str | int], max_bytes: int) -> bytes:
        requests.append((params, max_bytes))
        return next(iterator)

    result = collect_funding_pages(
        supplied,
        symbol="BTCUSDT",
        category="linear",
        fetched_at=NOW,
        start_ms=START,
        end_ms=END,
        max_calls=max_calls,
        max_total_bytes=max_total_bytes,
    )
    return result, requests


def test_full_page_progresses_to_exact_lower_boundary_without_fixed_cadence() -> None:
    first = page(*(END - i for i in range(200)))
    result, requests = collect([first, page(START + 1), page(START)])
    assert [p[0]["endTime"] for p in requests] == [END, END - 200, START]
    assert all(p[0]["startTime"] == START and p[0]["limit"] == 200 for p in requests)
    assert result.stop_reason == "lower_bound_reached"
    assert result.next_end_ms is None and result.calls_used == 3
    assert result.observations.height == 202
    assert result.observations["timestamp"].is_sorted()
    assert result.coverage_complete is False


def test_short_page_continues_and_empty_page_stops_without_completeness() -> None:
    result, requests = collect([page(END), page()])
    assert requests[1][0]["endTime"] == END - 1
    assert result.stop_reason == "empty_page" and result.observations.height == 1
    assert result.next_end_ms == END - 1 and result.coverage_complete is False


def test_empty_first_page_retains_empty_legacy_schema() -> None:
    result, _ = collect([page()])
    assert result.observations.columns == ["timestamp", "category", "symbol", "funding_rate"]
    assert result.observations.is_empty() and result.coverage_complete is False


@pytest.mark.parametrize(
    "second,reason", [(page(END), "repeated"), (page(END, rate="0.2"), "conflicting")]
)
def test_cross_page_duplicate_boundaries_are_never_deduplicated(second: bytes, reason: str) -> None:
    with pytest.raises(DataError, match=reason):
        collect([page(END), second])


@pytest.mark.parametrize(
    "raw",
    [
        page(START - 1),
        page(END + 1),
        page(END, END),
        page(END, symbol="ETHUSDT"),
        page(END, category="inverse"),
        page(END, rate="NaN"),
        page(END).replace(str(END).encode(), b"malformed-time"),
        page(*(END - i for i in range(201))),
        page(category="inverse"),
        b"{",
        b'{"retCode":0,"result":{}}',
    ],
)
def test_malformed_identity_bounds_and_values_refused(raw: bytes) -> None:
    with pytest.raises(DataError):
        collect([raw])


def test_new_timestamp_above_current_page_boundary_is_refused() -> None:
    with pytest.raises(DataError, match="boundary"):
        collect([page(END - 10), page(END - 5)])


def test_call_limit_never_makes_an_extra_callback() -> None:
    result, requests = collect([page(END)], max_calls=1)
    assert len(requests) == result.calls_used == 1
    assert result.stop_reason == "call_limit" and result.next_end_ms == END - 1
    assert result.coverage_complete is False


def test_byte_budget_is_given_to_callback_and_exhaustion_stops() -> None:
    raw = page(END)
    result, requests = collect([raw], max_total_bytes=len(raw))
    assert requests[0][1] == len(raw)
    assert result.accepted_payload_bytes == len(raw) and result.stop_reason == "byte_limit"
    with pytest.raises(DataError, match="byte"):
        collect([raw], max_total_bytes=len(raw) - 1)


def test_remaining_allowance_shrinks_across_pages() -> None:
    raw = [page(END), page(END - 10), page()]
    budget = sum(map(len, raw)) + 1
    result, requests = collect(raw, max_total_bytes=budget)
    assert [allowance for _, allowance in requests] == [
        budget,
        budget - len(raw[0]),
        budget - len(raw[0]) - len(raw[1]),
    ]
    assert result.accepted_payload_bytes == budget - 1


def test_non_bytes_supplier_payload_is_refused() -> None:
    def invalid(_params: dict[str, str | int], _max_bytes: int) -> bytes:
        return cast(bytes, "not bytes")  # Deliberately violate the callback contract.

    with pytest.raises(DataError, match="byte allowance"):
        collect_funding_pages(
            invalid, symbol="BTCUSDT", category="linear", fetched_at=NOW, start_ms=START, end_ms=END
        )


@pytest.mark.parametrize("limit", [0, -1, True, 101])
def test_invalid_call_limits_refused_before_callback(limit: int) -> None:
    with pytest.raises(DataError):
        collect([], max_calls=limit)


@pytest.mark.parametrize("limit", [0, -1, True, 32 * 1024 * 1024 + 1])
def test_invalid_byte_limits_refused_before_callback(limit: int) -> None:
    with pytest.raises(DataError):
        collect([], max_total_bytes=limit)


@pytest.mark.parametrize(
    "override",
    [
        {"start_ms": True},
        {"start_ms": END},
        {"end_ms": START - 1},
        {"end_ms": END + 1},
        {"fetched_at": NOW.replace(tzinfo=None)},
        {"symbol": ""},
        {"category": "spot"},
    ],
)
def test_invalid_scope_never_calls_supplier(override: dict[str, Any]) -> None:
    def prohibited(_params: dict[str, str | int], _max_bytes: int) -> bytes:
        pytest.fail("invalid scope reached callback")

    options: dict[str, Any] = dict(
        symbol="BTCUSDT", category="linear", fetched_at=NOW, start_ms=START, end_ms=END
    )
    options.update(override)
    with pytest.raises(DataError):
        collect_funding_pages(prohibited, **options)


def test_callback_failure_is_not_retried() -> None:
    calls = 0

    def failing(_params: dict[str, str | int], _max_bytes: int) -> bytes:
        nonlocal calls
        calls += 1
        raise DataError("synthetic supplier failure")

    with pytest.raises(DataError, match="supplier failure"):
        collect_funding_pages(
            failing, symbol="BTCUSDT", category="linear", fetched_at=NOW, start_ms=START, end_ms=END
        )
    assert calls == 1


@pytest.mark.bias_guard
def test_future_page_poison_refuses_instead_of_returning_partial_results() -> None:
    # Deliberately leaky parser sees the canary; the collector must fail, not hide it.
    latest = parse_funding_history(page(END + 1))["timestamp"].max()
    assert isinstance(latest, datetime) and latest > NOW
    with pytest.raises(DataError, match="knowledge"):
        collect([page(END), page(END + 1)])
