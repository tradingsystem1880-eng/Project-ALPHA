"""Offline request-bound funding validation; no provider or storage access."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import polars as pl
import pytest

from alpha_cli._crypto_acquisition import AcquisitionPlan, bybit_plan
from alpha_core import DataError
from alpha_data.crypto.providers.bybit import parse_funding_history, parse_funding_page

NOW = datetime(2026, 9, 1, tzinfo=UTC)
END = int(NOW.timestamp() * 1000)
START = END - 86_400_000


def payload(*times: int, symbol: str = "BTCUSDT", category: str = "linear") -> bytes:
    return json.dumps(
        {
            "retCode": 0,
            "result": {
                "category": category,
                "list": [
                    {"symbol": symbol, "fundingRateTimestamp": str(t), "fundingRate": "-0.0001"}
                    for t in times
                ],
            },
        }
    ).encode()


def parse(raw: bytes, **overrides: Any) -> pl.DataFrame:
    # Deliberately malformed request values exercise the runtime boundary below.
    options: dict[str, Any] = dict(
        symbol="BTCUSDT", category="linear", fetched_at=NOW, start_ms=START, end_ms=END
    )
    options.update(overrides)
    return parse_funding_page(raw, **options)


def test_inclusive_bounds_and_irregular_settlements_preserve_legacy_frame() -> None:
    raw = payload(END, START, START + 3_600_000)
    assert parse(raw).equals(parse_funding_history(raw))
    assert parse(raw)["timestamp"].to_list() == [
        NOW - timedelta(days=1),
        NOW - timedelta(hours=23),
        NOW,
    ]
    assert "available_at" not in parse(raw).columns


def test_aware_non_utc_cutoff_preserves_the_inclusive_instant() -> None:
    cutoff = NOW.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert parse(payload(END), fetched_at=cutoff).equals(parse(payload(END)))


def test_inverse_identity_preserves_native_rate_and_legacy_schema() -> None:
    raw = payload(START, symbol="BTCUSD", category="inverse")
    assert parse(raw, symbol="BTCUSD", category="inverse").equals(parse_funding_history(raw))


def test_full_unbounded_page_preserves_legacy_compatibility() -> None:
    raw = payload(*(START + i for i in range(200)))
    assert parse(raw, start_ms=None, end_ms=None).equals(parse_funding_history(raw))


@pytest.mark.parametrize("symbol,category", [("ETHUSDT", "linear"), ("BTCUSDT", "inverse")])
def test_wrong_identity_is_refused(symbol: str, category: str) -> None:
    with pytest.raises(DataError, match="identity"):
        parse(payload(START, symbol=symbol, category=category))


@pytest.mark.parametrize("timestamp", [START - 1, END + 1])
def test_outside_inclusive_range_is_refused(timestamp: int) -> None:
    with pytest.raises(DataError):
        parse(payload(timestamp))


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_ms": None},
        {"end_ms": None},
        {"start_ms": True},
        {"end_ms": START},
        {"fetched_at": NOW.replace(tzinfo=None)},
        {"end_ms": END + 1},
        {"category": "spot"},
        {"symbol": ""},
    ],
)
def test_invalid_request_contract_is_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(DataError):
        parse(payload(START), **overrides)


@pytest.mark.parametrize(
    "raw", [payload(), payload(START, START), b"{", payload(START).replace(b'"-0.0001"', b'"NaN"')]
)
def test_empty_duplicate_and_malformed_pages_are_refused(raw: bytes) -> None:
    with pytest.raises(DataError):
        parse(raw)


def test_payload_and_row_caps() -> None:
    with pytest.raises(DataError, match="byte"):
        parse(b" " * (8 * 1024 * 1024 + 1))
    with pytest.raises(DataError, match="200"):
        parse(payload(*(START + i for i in range(201))))


@pytest.mark.bias_guard
def test_future_poison_is_refused_even_without_requested_range() -> None:
    raw = payload(START, END + 1)
    # Deliberately leaky legacy parser demonstrates that this canary is observable.
    latest = parse_funding_history(raw)["timestamp"].max()
    assert isinstance(latest, datetime) and latest > NOW
    with pytest.raises(DataError, match="knowledge"):
        parse(raw, start_ms=None, end_ms=None)


def plan(*, bounded: bool = True) -> AcquisitionPlan:
    return bybit_plan(
        "funding",
        "BTCUSDT",
        base="BTC",
        quote="USDT",
        category="linear",
        frequency="1h",
        fetched_at=NOW,
        start="2026-08-31T00:00:00Z" if bounded else None,
        end="2026-09-01T00:00:00Z" if bounded else None,
    )


def test_plan_binds_request_identity_and_cutoff() -> None:
    bound = plan()
    assert bound.dataset.frequency == "funding_interval"
    assert bound.expected_cadence_seconds is None
    assert bound.availability_column is None
    with pytest.raises(DataError, match="identity"):
        bound.parser(payload(START, symbol="ETHUSDT"))
    with pytest.raises(DataError, match="knowledge"):
        plan(bounded=False).parser(payload(END + 1))


def test_full_bounded_page_still_refuses_and_short_page_makes_no_coverage_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpha_cli import crypto_data_cmds

    raw = payload(*(START + i for i in range(200)))
    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", lambda *_a, **_k: raw)
    with pytest.raises(DataError, match="fills one provider page"):
        crypto_data_cmds._fetch_bybit_pages(plan(), follow_cursors=True)
    raw = payload(START)
    pages = crypto_data_cmds._fetch_bybit_pages(plan(), follow_cursors=True)
    assert len(pages) == 1
    assert pages[0][0] == raw
