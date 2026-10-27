"""Strict opt-in HTTP budgets; all transport responses are synthetic and offline."""

from __future__ import annotations

import http.client
import io
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from urllib.response import addinfourl

import pytest
from typer.testing import CliRunner

from alpha_core import DataError
from alpha_data.crypto.providers._wire import RequestBudget, fetch_bounded

HOST = "https://api.binance.com/api/v3/"


def fetch(budget: RequestBudget, *, retry: bool = False, cap: int = 16) -> bytes:
    return fetch_bounded(
        HOST + "klines",
        provider="test",
        host_prefix=HOST,
        content_types=frozenset({"application/json"}),
        max_bytes=cap,
        timeout_seconds=1,
        retry_429=retry,
        budget=budget,
    )


def transport(monkeypatch: pytest.MonkeyPatch, responses: list[object]) -> list[str]:
    calls: list[str] = []

    def open_fake(_handler: object, request: urllib.request.Request) -> object:
        calls.append(request.full_url)
        value = responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fake)
    monkeypatch.setattr(urllib.request.HTTPHandler, "http_open", open_fake)
    monkeypatch.setattr("time.sleep", lambda _: None)
    return calls


class SyntheticResponse(addinfourl):
    msg = "synthetic"


def response(body: bytes = b"{}", code: int = 200) -> addinfourl:
    headers = Message()
    headers["Content-Type"] = "application/json"
    headers["Location"] = HOST + "redirected"
    result = SyntheticResponse(io.BytesIO(body), headers, HOST + "klines", code)
    return result


def test_budget_shared_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = transport(monkeypatch, [response(), response()])
    budget = RequestBudget(1, 10)
    assert fetch(budget) == b"{}"
    with pytest.raises(DataError, match="request budget"):
        fetch(budget)
    assert len(calls) == budget.requests_used == 1
    assert budget.bytes_read == 2


def test_initial_host_rejected_before_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = transport(monkeypatch, [])
    budget = RequestBudget(1, 100)
    with pytest.raises(DataError, match="request host"):
        fetch_bounded(
            "https://unapproved.invalid/klines",
            provider="test",
            host_prefix=HOST,
            content_types=frozenset({"application/json"}),
            max_bytes=16,
            timeout_seconds=1,
            budget=budget,
        )
    assert not calls and budget.requests_used == budget.bytes_read == 0


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_redirect_never_reaches_second_target(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    calls = transport(monkeypatch, [response(code=code)])
    budget = RequestBudget(2, 100)
    with pytest.raises(DataError):
        fetch(budget)
    assert len(calls) == budget.requests_used == 1


def test_429_retry_is_charged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = transport(monkeypatch, [response(code=429), response()])
    budget = RequestBudget(1, 100)
    with pytest.raises(DataError, match="request budget"):
        fetch(budget, retry=True)
    assert len(calls) == budget.requests_used == 1


def test_allowed_retry_closes_error_response(monkeypatch: pytest.MonkeyPatch) -> None:
    first = response(code=429)
    calls = transport(monkeypatch, [first, response()])
    budget = RequestBudget(2, 100)
    assert fetch(budget, retry=True) == b"{}"
    assert first.closed
    assert len(calls) == budget.requests_used == 2


def test_http_error_consumes_attempt_and_closes_body(monkeypatch: pytest.MonkeyPatch) -> None:
    first = response(code=500)
    calls = transport(monkeypatch, [first])
    budget = RequestBudget(1, 100)
    with pytest.raises(DataError):
        fetch(budget)
    with pytest.raises(DataError, match="request budget"):
        fetch(budget)
    assert first.closed and len(calls) == 1


@pytest.mark.parametrize(
    "error", [TimeoutError(), urllib.error.URLError("synthetic"), OSError(), KeyboardInterrupt()]
)
def test_failed_attempt_is_not_refunded(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    calls = transport(monkeypatch, [error])
    budget = RequestBudget(1, 100)
    with pytest.raises((DataError, OSError, KeyboardInterrupt)):
        fetch(budget)
    with pytest.raises(DataError):
        fetch(budget)
    assert len(calls) == budget.requests_used == 1


def test_aggregate_body_limit_counts_previous_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = transport(monkeypatch, [response(b"abc"), response(b"defghi")])
    budget = RequestBudget(3, 5)
    assert fetch(budget) == b"abc"
    with pytest.raises(DataError, match="byte budget"):
        fetch(budget)
    assert budget.bytes_read == 5
    with pytest.raises(DataError):
        fetch(budget)
    assert len(calls) == 2


def test_per_response_overflow_probe_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    transport(monkeypatch, [response(b"x" * 20)])
    budget = RequestBudget(2, 100)
    with pytest.raises(DataError, match="byte limit"):
        fetch(budget, cap=16)
    assert budget.bytes_read == 17


def test_exact_aggregate_boundary_fails_without_extra_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport(monkeypatch, [response(b"abc")])
    budget = RequestBudget(1, 3)
    with pytest.raises(DataError, match="byte budget"):
        fetch(budget)
    assert budget.bytes_read == 3


@pytest.mark.parametrize("requests,body_bytes", [(0, 10), (True, 10), (1, 0), (1, False)])
def test_invalid_budget(requests: int, body_bytes: int) -> None:
    with pytest.raises(DataError):
        RequestBudget(requests, body_bytes)


@pytest.mark.parametrize(
    "error", [OSError("synthetic"), http.client.IncompleteRead(b"xy", 4), KeyboardInterrupt()]
)
def test_interrupted_body_aborts_remaining_budget(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    class BrokenBody(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            if self.tell() == 0:
                return super().read(2)
            raise error

    body = BrokenBody(b"abcd")
    headers = Message()
    headers["Content-Type"] = "application/json"
    reply = SyntheticResponse(body, headers, HOST + "klines", 200)
    calls = transport(monkeypatch, [reply])
    budget = RequestBudget(3, 100)
    with pytest.raises((OSError, http.client.IncompleteRead, KeyboardInterrupt)):
        fetch(budget)
    assert budget.bytes_read == (4 if isinstance(error, http.client.IncompleteRead) else 2)
    assert budget.failed and body.closed
    with pytest.raises(DataError, match="aborted"):
        fetch(budget)
    assert len(calls) == 1


def klines(start: int, count: int) -> bytes:
    return json.dumps(
        [
            [
                start + i * 86400000,
                "100",
                "102",
                "99",
                "101",
                "10",
                start + (i + 1) * 86400000 - 1,
                "1010",
                3,
                "5",
                "505",
                "0",
            ]
            for i in range(count)
        ]
    ).encode()


def test_pagination_budget_counts_failed_second_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    from alpha_cli.crypto_data_cmds import _fetch_binance_tail_pages

    start = 1577836800000
    calls = transport(monkeypatch, [response(klines(start, 1000))])
    budget = RequestBudget(1, 1_000_000)
    with pytest.raises(DataError, match="request budget"):
        _fetch_binance_tail_pages(
            category="spot",
            symbol="BTCUSDT",
            frequency="1d",
            start_ms=start,
            end_ms=start + 1096 * 86400000 - 1,
            budget=budget,
        )
    assert len(calls) == budget.requests_used == 1


def test_repeated_page_fails_without_third_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    from alpha_cli.crypto_data_cmds import _fetch_binance_tail_pages

    start = 1577836800000
    calls = transport(monkeypatch, [response(klines(start, 1000)), response(klines(start, 1000))])
    budget = RequestBudget(3, 1_000_000)
    with pytest.raises(DataError):
        _fetch_binance_tail_pages(
            category="spot",
            symbol="BTCUSDT",
            frequency="1d",
            start_ms=start,
            end_ms=start + 1096 * 86400000 - 1,
            budget=budget,
        )
    assert len(calls) == budget.requests_used == 2


def test_short_partial_page_does_not_spend_another_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from alpha_cli.crypto_data_cmds import _fetch_binance_tail_pages

    start = 1577836800000
    calls = transport(monkeypatch, [response(klines(start, 1))])
    budget = RequestBudget(1, 10000)
    pages = _fetch_binance_tail_pages(
        category="spot",
        symbol="BTCUSDT",
        frequency="1d",
        start_ms=start,
        end_ms=start + 7 * 86400000 - 1,
        budget=budget,
    )
    assert len(pages) == len(calls) == 1
    # A short page terminates existing pagination; this is not proof of full window coverage.


@pytest.mark.parametrize(
    "options",
    [
        ["--max-requests", "1"],
        ["--max-total-bytes", "100"],
        ["--max-requests", "0", "--max-total-bytes", "100"],
    ],
)
def test_budget_pair_validated_before_storage(
    monkeypatch: pytest.MonkeyPatch, options: list[str]
) -> None:
    from alpha_cli import crypto_data_cmds
    from alpha_cli.main import app

    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: pytest.fail("storage touched"))
    result = CliRunner().invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "binance",
            "market_bars",
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "spot",
            "--frequency",
            "1d",
            "--start",
            "2020-01-01T00:00:00Z",
            "--end",
            "2022-12-31T23:59:59.999Z",
            *options,
        ],
    )
    assert result.exit_code != 0
    assert "budgets" in result.output


@pytest.mark.parametrize(
    "provider,extra",
    [
        ("bybit", []),
        ("binance", ["--period", "2020-01"]),
        ("binance", ["--frequency", "1h"]),
        ("binance", ["--category", "linear"]),
    ],
)
def test_unsupported_scope_rejected_before_storage(
    monkeypatch: pytest.MonkeyPatch, provider: str, extra: list[str]
) -> None:
    from alpha_cli import crypto_data_cmds
    from alpha_cli.main import app

    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: pytest.fail("storage touched"))
    result = CliRunner().invoke(
        app,
        [
            "crypto-data",
            "acquire",
            provider,
            "market_bars",
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "spot",
            "--frequency",
            "1d",
            "--start",
            "2020-01-01T00:00:00Z",
            "--end",
            "2022-12-31T23:59:59.999Z",
            "--max-requests",
            "2",
            "--max-total-bytes",
            "1000000",
            *extra,
        ],
    )
    assert result.exit_code != 0
    assert "strict budgets require" in result.output


@pytest.mark.parametrize(
    "max_requests,max_total_bytes,expected_error",
    [(1, 1_000_000, "request budget"), (2, 1_000_000, None), (2, 100_000, "byte budget")],
)
def test_cli_budget_reaches_actual_opener_and_prevents_partial_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    max_requests: int,
    max_total_bytes: int,
    expected_error: str | None,
) -> None:
    from alpha_cli import crypto_data_cmds
    from alpha_cli.main import app
    from alpha_data.crypto.storage import Capacity, CryptoBulkStore

    bulk = tmp_path / "bulk"
    bulk.mkdir()
    manifests = tmp_path / "manifests"
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=manifests,
        expected_volume_uuid="SYNTHETIC",
        volume_uuid=lambda _: "SYNTHETIC",
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: datetime(2023, 1, 2, tzinfo=UTC))
    start = 1577836800000
    assert len(klines(start, 1000)) < 100_000
    assert len(klines(start, 1096)) > 100_000
    calls = transport(
        monkeypatch, [response(klines(start, 1000)), response(klines(start + 1000 * 86400000, 96))]
    )
    result = CliRunner().invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "binance",
            "market_bars",
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "spot",
            "--frequency",
            "1d",
            "--start",
            "2020-01-01T00:00:00Z",
            "--end",
            "2022-12-31T23:59:59.999Z",
            "--max-requests",
            str(max_requests),
            "--max-total-bytes",
            str(max_total_bytes),
            "--json",
        ],
    )
    assert (result.exit_code == 0) == (expected_error is None), result.output
    assert len(calls) == max_requests
    if expected_error is None:
        receipt = json.loads(result.stdout)
        assert receipt["raw_page_count"] == 2
        store.verify_manifest(receipt["normalized_manifest_id"])
    else:
        assert expected_error in result.output
        assert not list(manifests.rglob("*.json"))
