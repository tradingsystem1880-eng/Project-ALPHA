"""Injected responses/clocks only; deliberately no network opener."""

from __future__ import annotations

import http.client
import io
import traceback
from asyncio import CancelledError
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest

from alpha_core import DataError
from alpha_data.crypto.funding_ingestion import collect_retained_funding_pages
from alpha_data.crypto.providers.funding_transport import FundingResponseSupplier
from tests.unit.test_bybit_funding_pagination import page as funding_page
from tests.unit.test_funding_raw_retention import dataset, payload, store_at

NOW = datetime(2026, 9, 1, tzinfo=UTC)
END = int(NOW.timestamp() * 1000)
PARAMS: dict[str, str | int] = {
    "symbol": "BTCUSDT",
    "category": "linear",
    "limit": 200,
    "startTime": END - 1000,
    "endTime": END,
}


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class Response:
    def __init__(self, body: bytes, clock: Clock) -> None:
        self.body, self.clock = body, clock
        self.headers = {"Content-Type": "application/json"}
        self.status = 200
        self.url = ""
        self.closed = False
        self.read_sizes: list[int] = []
        self.delay = 0.0
        self.failure: BaseException | None = None
        self.close_failure = False
        self.cleanup_error: BaseException | None = None
        self.close_delay = 0.0

    def geturl(self) -> str:
        return self.url

    def getcode(self) -> int:
        return self.status

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        self.clock.value += self.delay
        if self.failure is not None:
            raise self.failure
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def close(self) -> None:
        self.closed = True
        self.clock.value += self.close_delay
        if self.cleanup_error is not None:
            raise self.cleanup_error
        if self.close_failure:
            raise OSError("SECRET cleanup https://bad.invalid/?key=SECRET")


def supplier(response: Response, clock: Clock, **options: Any) -> FundingResponseSupplier:
    def opening(request: Request, timeout: float) -> Response:
        assert 0 < timeout <= 10
        assert request.get_header("Accept-encoding") == "identity"
        response.url = response.url or request.full_url
        return response

    return FundingResponseSupplier(opening, clock=clock, **options)


def test_exact_cap_and_eof_probe_return_unchanged_bytes_and_close() -> None:
    clock = Clock()
    response = Response(b"abcdef", clock)
    assert supplier(response, clock)(PARAMS, 6) == b"abcdef"
    assert response.closed and response.read_sizes == [7, 1]


def test_streaming_overflow_is_bounded_and_closed() -> None:
    clock = Clock()
    response = Response(b"x" * 100000, clock)
    with pytest.raises(DataError, match="byte"):
        supplier(response, clock)(PARAMS, 10)
    assert response.closed and response.read_sizes == [11]


def test_multi_chunk_success_is_exact_and_bounded() -> None:
    clock = Clock()
    response = Response(b"x" * 70000, clock)
    assert supplier(response, clock)(PARAMS, 70000) == b"x" * 70000
    assert response.closed and max(response.read_sizes) == 65536


@pytest.mark.parametrize(
    "headers,status,url",
    [
        ({"Content-Type": "text/html"}, 200, ""),
        ({"Content-Type": "application/json", "Content-Length": "1000"}, 200, ""),
        ({"Content-Type": "application/json", "Content-Length": "-1"}, 200, ""),
        ({"Content-Type": "application/json", "Content-Encoding": "gzip"}, 200, ""),
        ({"Content-Type": "application/json"}, 302, ""),
        ({"Content-Type": "application/json"}, 403, ""),
        ({"Content-Type": "application/json"}, 200, "https://other.invalid/"),
        ({"Content-Type": "application/json", "content-type": "text/html"}, 200, ""),
    ],
)
def test_invalid_response_metadata_never_reads(
    headers: dict[str, str], status: int, url: str
) -> None:
    clock = Clock()
    response = Response(b"SECRET", clock)
    response.headers, response.status, response.url = headers, status, url
    with pytest.raises(DataError):
        supplier(response, clock)(PARAMS, 10)
    assert response.closed and response.read_sizes == []


def test_partial_declared_body_and_incomplete_read_fail_closed() -> None:
    clock = Clock()
    response = Response(b"x", clock)
    response.headers["Content-Length"] = "2"
    with pytest.raises(DataError, match="length"):
        supplier(response, clock)(PARAMS, 10)
    assert response.closed
    response = Response(b"", clock)
    response.failure = http.client.IncompleteRead(b"SECRET")
    with pytest.raises(DataError) as error:
        supplier(response, clock)(PARAMS, 10)
    assert response.closed and "SECRET" not in "".join(traceback.format_exception(error.value))
    assert error.value.__context__ is None and error.value.__cause__ is None


def test_deadline_checked_after_read_even_when_callback_returns() -> None:
    clock = Clock()
    response = Response(b"ok", clock)
    response.delay = 2
    with pytest.raises(DataError, match="deadline"):
        supplier(response, clock, total_seconds=1)(PARAMS, 10)
    assert response.closed and len(response.read_sizes) == 1


def test_eof_deadline_expiry_is_not_accepted() -> None:
    clock = Clock()
    response = Response(b"ok", clock)
    response.delay = 0.5
    with pytest.raises(DataError, match="deadline"):
        supplier(response, clock, total_seconds=1)(PARAMS, 10)
    assert response.closed and len(response.read_sizes) == 2


def test_read_timeout_closes_and_sanitizes() -> None:
    clock = Clock()
    response = Response(b"", clock)
    response.failure = TimeoutError("SECRET")
    with pytest.raises(DataError) as error:
        supplier(response, clock)(PARAMS, 10)
    assert response.closed and "SECRET" not in str(error.value)


def test_open_deadline_overrun_closes_without_read() -> None:
    clock = Clock()
    response = Response(b"ok", clock)

    def opening(request: Request, timeout: float) -> Response:
        assert timeout == 1
        response.url = request.full_url
        clock.value = 2
        return response

    with pytest.raises(DataError, match="deadline"):
        FundingResponseSupplier(opening, clock=clock, total_seconds=1)(PARAMS, 10)
    assert response.closed and response.read_sizes == []


def test_http_error_response_is_closed_without_exposing_url() -> None:
    body = io.BytesIO(b"SECRET")

    def opening(_request: Request, _timeout: float) -> Response:
        raise HTTPError("https://bad.invalid/?key=SECRET", 403, "SECRET", Message(), body)

    with pytest.raises(DataError) as error:
        FundingResponseSupplier(opening, clock=Clock())(PARAMS, 10)
    assert body.closed and "SECRET" not in "".join(traceback.format_exception(error.value))


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, 301])
def test_invalid_deadlines_never_open(value: float) -> None:
    def prohibited(_request: Request, _timeout: float) -> Response:
        pytest.fail("invalid deadline reached opener")

    with pytest.raises(DataError):
        FundingResponseSupplier(prohibited, clock=Clock(), total_seconds=value)


def test_expired_shared_deadline_prevents_next_open() -> None:
    clock = Clock()
    response = Response(b"ok", clock)
    read = supplier(response, clock, total_seconds=1)
    assert read(PARAMS, 10) == b"ok"
    clock.value = 1
    with pytest.raises(DataError, match="deadline"):
        read(PARAMS, 10)


@pytest.mark.parametrize("failure", [TimeoutError("SECRET"), OSError("SECRET")])
def test_open_errors_redacted_without_chain(failure: Exception) -> None:
    def opening(_request: Request, _timeout: float) -> Response:
        raise failure

    with pytest.raises(DataError) as error:
        FundingResponseSupplier(opening, clock=Clock())(PARAMS, 10)
    assert "SECRET" not in "".join(traceback.format_exception(error.value))
    assert error.value.__context__ is None and error.value.__cause__ is None


def test_close_failure_is_redacted_and_cancellation_is_preserved() -> None:
    clock = Clock()
    response = Response(b"ok", clock)
    response.close_failure = True
    with pytest.raises(DataError) as error:
        supplier(response, clock)(PARAMS, 10)
    assert "SECRET" not in "".join(traceback.format_exception(error.value))
    response = Response(b"", clock)
    response.failure = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        supplier(response, clock)(PARAMS, 10)
    assert response.closed


@pytest.mark.parametrize(
    "cancel",
    [
        KeyboardInterrupt("SECRET"),
        SystemExit("SECRET"),
        CancelledError("SECRET"),
        GeneratorExit("SECRET"),
    ],
)
def test_cancellation_is_fresh_and_sanitized(cancel: BaseException) -> None:
    clock = Clock()
    response = Response(b"", clock)
    response.failure = cancel
    with pytest.raises(type(cancel)) as error:
        supplier(response, clock)(PARAMS, 10)
    assert response.closed and error.value is not cancel
    assert "SECRET" not in "".join(traceback.format_exception(error.value))
    assert error.value.__cause__ is None and error.value.__context__ is None
    if isinstance(error.value, SystemExit):
        assert error.value.code == 1


def test_cleanup_cancellation_takes_precedence_and_is_sanitized() -> None:
    clock = Clock()
    response = Response(b"", clock)
    response.failure = OSError("SECRET read")
    response.cleanup_error = KeyboardInterrupt("SECRET close")
    with pytest.raises(KeyboardInterrupt) as error:
        supplier(response, clock)(PARAMS, 10)
    assert "SECRET" not in "".join(traceback.format_exception(error.value))
    assert error.value.__context__ is None


def test_http_error_cleanup_cancellation_is_sanitized() -> None:
    class Body(io.BytesIO):
        def close(self) -> None:
            if not self.closed:
                super().close()
                raise KeyboardInterrupt("SECRET cleanup")

    body = Body(b"SECRET")

    def opening(_request: Request, _timeout: float) -> Response:
        raise HTTPError("https://bad.invalid/SECRET", 403, "SECRET", Message(), body)

    with pytest.raises(KeyboardInterrupt) as error:
        FundingResponseSupplier(opening, clock=Clock())(PARAMS, 10)
    assert body.closed and "SECRET" not in "".join(traceback.format_exception(error.value))
    assert error.value.__context__ is None


def test_clock_cancellation_is_sanitized_at_construction() -> None:
    def interrupted_clock() -> float:
        raise KeyboardInterrupt("SECRET clock")

    def prohibited(_request: Request, _timeout: float) -> Response:
        pytest.fail("clock cancellation reached opener")

    with pytest.raises(KeyboardInterrupt) as error:
        FundingResponseSupplier(prohibited, clock=interrupted_clock)
    assert "SECRET" not in "".join(traceback.format_exception(error.value))
    assert error.value.__context__ is None


def test_cleanup_time_is_checked_before_accepting_body() -> None:
    clock = Clock()
    response = Response(b"ok", clock)
    response.close_delay = 2
    with pytest.raises(DataError, match="deadline"):
        supplier(response, clock, total_seconds=1)(PARAMS, 10)
    assert response.closed


def test_composes_with_real_raw_retention_before_decode(tmp_path: Path) -> None:
    clock = Clock()
    store = store_at(tmp_path)
    response = Response(payload(), clock)
    result, manifests = collect_retained_funding_pages(
        store,
        supplier(response, clock),
        dataset=dataset(),
        fetched_at=NOW,
        start_ms=END - 1000,
        end_ms=END,
    )
    assert not result.coverage_complete and response.closed
    assert len(manifests) == 1
    assert (store.bulk_root / str(manifests[0]["artifact_key"])).read_bytes() == payload()


def test_failed_read_cannot_publish_partial_raw_evidence(tmp_path: Path) -> None:
    clock = Clock()
    store = store_at(tmp_path)
    response = Response(b"", clock)
    response.failure = http.client.IncompleteRead(b"partial")
    with pytest.raises(DataError):
        collect_retained_funding_pages(
            store,
            supplier(response, clock),
            dataset=dataset(),
            fetched_at=NOW,
            start_ms=END - 1000,
            end_ms=END,
        )
    assert store.inventory() == () and response.closed


def test_completed_malformed_body_is_raw_retained(tmp_path: Path) -> None:
    clock = Clock()
    store = store_at(tmp_path)
    response = Response(b"{", clock)
    with pytest.raises(DataError):
        collect_retained_funding_pages(
            store,
            supplier(response, clock),
            dataset=dataset(),
            fetched_at=NOW,
            start_ms=END - 1000,
            end_ms=END,
        )
    (manifest,) = store.inventory()
    assert (store.bulk_root / str(manifest["artifact_key"])).read_bytes() == b"{"


def test_deadline_between_pages_keeps_first_raw_and_prevents_second_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock()
    store = store_at(tmp_path)
    calls = 0

    def opening(request: Request, _timeout: float) -> Response:
        nonlocal calls
        calls += 1
        response = Response(payload(END), clock)
        response.url = request.full_url
        return response

    publish = store.publish_staging

    def saved(*args: Any, **kwargs: Any) -> dict[str, object]:
        manifest = publish(*args, **kwargs)
        clock.value = 1
        return manifest

    monkeypatch.setattr(store, "publish_staging", saved)
    with pytest.raises(DataError, match="deadline"):
        collect_retained_funding_pages(
            store,
            FundingResponseSupplier(opening, clock=clock, total_seconds=1),
            dataset=dataset(),
            fetched_at=NOW,
            start_ms=END - 1000,
            end_ms=END,
        )
    assert calls == 1 and len(store.inventory()) == 1


def test_composed_full_page_to_singleton_keeps_exact_raw_before_every_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpha_data.crypto.providers import bybit_funding
    from alpha_data.crypto.providers.bybit import _result_object

    clock = Clock()
    store = store_at(tmp_path)
    bodies = [
        funding_page(*(END - i for i in range(200))),
        funding_page(END - 999),
        funding_page(END - 1000),
    ]
    responses: list[Response] = []
    ends: list[int] = []

    def opening(request: Request, _timeout: float) -> Response:
        params = parse_qs(urlsplit(request.full_url).query)
        ends.append(int(params["endTime"][0]))
        assert params["startTime"] == [str(END - 1000)]
        response = Response(bodies[len(responses)], clock)
        response.url = request.full_url
        response.headers["Content-Length"] = str(len(response.body))
        responses.append(response)
        return response

    def decoded(raw: bytes) -> tuple[dict[str, object], int | None]:
        assert responses[-1].closed
        assert raw in {
            (store.bulk_root / str(m["artifact_key"])).read_bytes() for m in store.inventory()
        }
        return _result_object(raw)

    monkeypatch.setattr(bybit_funding, "_result_object", decoded)
    result, manifests = collect_retained_funding_pages(
        store,
        FundingResponseSupplier(opening, clock=clock),
        dataset=dataset(),
        fetched_at=NOW,
        start_ms=END - 1000,
        end_ms=END,
        max_calls=3,
    )
    assert ends == [END, END - 200, END - 1000]
    assert result.stop_reason == "lower_bound_reached" and not result.coverage_complete
    assert result.observations.height == result.observations["timestamp"].n_unique() == 202
    assert result.observations["timestamp"].is_sorted()
    assert all(response.closed for response in responses)
    reopened = store_at(tmp_path)
    assert [
        (
            reopened.bulk_root / str(reopened.verify_manifest(m["manifest_id"])["artifact_key"])
        ).read_bytes()
        for m in manifests
    ] == bodies
    assert len(reopened.inventory()) == 3
    assert all(m["artifact_kind"] == "raw" for m in reopened.inventory())


@pytest.mark.parametrize("kind", ["overflow", "partial", "cancel"])
def test_composed_second_response_failure_keeps_only_first_complete_body(
    tmp_path: Path,
    kind: str,
) -> None:
    class PartialResponse(Response):
        def read(self, size: int) -> bytes:
            if self.read_sizes:
                raise http.client.IncompleteRead(b"SECRET tail")
            return super().read(size)

    clock = Clock()
    store = store_at(tmp_path)
    first = Response(payload(END), clock)
    second = (
        PartialResponse(b"prefix", clock) if kind == "partial" else Response(b"x" * 1001, clock)
    )
    if kind == "cancel":
        second.failure = KeyboardInterrupt("SECRET cancellation")
    responses = [first, second]
    calls = 0

    def opening(request: Request, _timeout: float) -> Response:
        nonlocal calls
        response = responses[calls]
        calls += 1
        response.url = request.full_url
        return response

    with pytest.raises(KeyboardInterrupt if kind == "cancel" else DataError) as error:
        collect_retained_funding_pages(
            store,
            FundingResponseSupplier(opening, clock=clock),
            dataset=dataset(),
            fetched_at=NOW,
            start_ms=END - 1000,
            end_ms=END,
            max_total_bytes=1000,
        )
    assert calls == 2 and first.closed and second.closed
    assert "SECRET" not in "".join(traceback.format_exception(error.value))
    (manifest,) = store.inventory()
    assert manifest["artifact_kind"] == "raw"
    assert (store.bulk_root / str(manifest["artifact_key"])).read_bytes() == payload(END)


def test_composed_second_storage_failure_stops_after_closed_response_before_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpha_data.crypto.providers import bybit_funding
    from alpha_data.crypto.providers.bybit import _result_object

    clock = Clock()
    store = store_at(tmp_path)
    responses: list[Response] = []
    decoded: list[bytes] = []

    def opening(request: Request, _timeout: float) -> Response:
        response = Response(payload(END - len(responses)), clock)
        response.url = request.full_url
        responses.append(response)
        return response

    publish = store._publish_manifest

    def interrupted(body: dict[str, object]) -> dict[str, object]:
        if len(responses) == 2:
            assert responses[-1].closed
            raise OSError("synthetic second publication failure")
        return publish(body)

    def decoding(raw: bytes) -> tuple[dict[str, object], int | None]:
        decoded.append(raw)
        return _result_object(raw)

    monkeypatch.setattr(store, "_publish_manifest", interrupted)
    monkeypatch.setattr(bybit_funding, "_result_object", decoding)
    with pytest.raises(OSError, match="second publication failure"):
        collect_retained_funding_pages(
            store,
            FundingResponseSupplier(opening, clock=clock),
            dataset=dataset(),
            fetched_at=NOW,
            start_ms=END - 1000,
            end_ms=END,
        )
    assert len(responses) == 2 and all(response.closed for response in responses)
    assert decoded == [payload(END)] and len(store.inventory()) == 1
    assert len(list((store.bulk_root / "raw").rglob("funding.json"))) == 2


@pytest.mark.parametrize("stop", ["call_limit", "byte_limit"])
def test_composed_budget_stop_never_opens_another_response(tmp_path: Path, stop: str) -> None:
    clock = Clock()
    store = store_at(tmp_path)
    calls = 0

    def opening(request: Request, _timeout: float) -> Response:
        nonlocal calls
        calls += 1
        assert calls == 1
        response = Response(payload(END), clock)
        response.url = request.full_url
        return response

    options = {"max_calls": 1} if stop == "call_limit" else {"max_total_bytes": len(payload(END))}
    result, manifests = collect_retained_funding_pages(
        store,
        FundingResponseSupplier(opening, clock=clock),
        dataset=dataset(),
        fetched_at=NOW,
        start_ms=END - 1000,
        end_ms=END,
        **options,
    )
    assert calls == result.calls_used == len(manifests) == 1
    assert result.stop_reason == stop and result.next_end_ms == END - 1
    assert not result.coverage_complete


def test_mutated_request_url_cannot_rebind_expected_identity_or_publish_raw(tmp_path: Path) -> None:
    clock = Clock()
    store = store_at(tmp_path)
    response = Response(payload(), clock)

    def opening(request: Request, _timeout: float) -> Response:
        request.full_url = "https://other.invalid/"
        response.url = request.full_url
        return response

    with pytest.raises(DataError, match="redirect"):
        collect_retained_funding_pages(
            store,
            FundingResponseSupplier(opening, clock=clock),
            dataset=dataset(),
            fetched_at=NOW,
            start_ms=END - 1000,
            end_ms=END,
        )
    assert response.closed and response.read_sizes == [] and store.inventory() == ()
