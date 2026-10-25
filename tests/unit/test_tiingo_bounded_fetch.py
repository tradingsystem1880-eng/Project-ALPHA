"""Tiingo transport tests use fake responses and never contact a provider."""

from __future__ import annotations

import http.client
import io
import json
import os
import urllib.error
import urllib.request
from datetime import date
from email.message import Message
from typing import Any
from unittest.mock import Mock

import pytest

from alpha_core import DataError
from alpha_data.adapters.tiingo_adapter import TiingoAdapter

DAY = date(2024, 1, 2)


def _payload() -> bytes:
    return json.dumps(
        [
            dict(
                date="2024-01-02T00:00:00Z",
                open=10,
                high=10,
                low=10,
                close=10,
                volume=1,
                adjOpen=10,
                adjHigh=10,
                adjLow=10,
                adjClose=10,
                divCash=0,
                splitFactor=1,
            )
        ]
    ).encode()


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, 32 * 1024 * 1024 + 1])
def test_invalid_limit_fails_before_network(monkeypatch: pytest.MonkeyPatch, limit: Any) -> None:
    opener = Mock()
    monkeypatch.setattr(urllib.request, "build_opener", opener)
    with pytest.raises(DataError, match="max_response_bytes"):
        TiingoAdapter(api_key="secret").fetch("SPY", DAY, DAY, max_response_bytes=limit)
    opener.assert_not_called()


def test_exact_byte_limit_and_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _payload()

    class TrackingResponse:
        def __init__(self) -> None:
            self.closed = False
            self.read_sizes: list[int] = []

        def __enter__(self) -> TrackingResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            self.closed = True

        def read(self, size: int = -1) -> bytes:
            self.read_sizes.append(size)
            return raw if size < 0 else raw[:size]

    responses: list[TrackingResponse] = []

    def open_response(*_args: object, **_kwargs: object) -> TrackingResponse:
        response = TrackingResponse()
        responses.append(response)
        return response

    opened = Mock(side_effect=open_response)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a: Mock(open=opened))
    result = TiingoAdapter(api_key="secret").fetch("SPY", DAY, DAY, max_response_bytes=len(raw))
    assert result.raw_response == raw
    assert opened.call_args.kwargs == {"timeout": 30}
    with pytest.raises(DataError, match="response exceeds"):
        TiingoAdapter(api_key="secret").fetch("SPY", DAY, DAY, max_response_bytes=len(raw) - 1)
    assert [response.read_sizes for response in responses] == [[len(raw) + 1], [len(raw)]]
    assert all(response.closed for response in responses)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_is_rejected_before_second_request(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    # The transport is wholly synthetic; inherited cloud proxy routing must not
    # mutate its Request before FakeHTTPS observes the original target.
    monkeypatch.setenv("https_proxy", "http://fixture-proxy.invalid:8080")
    monkeypatch.setenv("no_proxy", "")
    requests: list[urllib.request.Request] = []

    class FakeHTTPS(urllib.request.HTTPSHandler):
        def https_open(self, request: urllib.request.Request) -> Any:
            requests.append(request)
            headers = Message()
            headers["Location"] = "https://elsewhere.invalid/steal"
            response = urllib.response.addinfourl(
                io.BytesIO(b""), headers, request.full_url, status
            )
            response.msg = "Found"  # type: ignore[attr-defined]
            return response

    real_build = urllib.request.build_opener
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: real_build(urllib.request.ProxyHandler({}), FakeHTTPS(), *handlers),
    )
    with pytest.raises(DataError, match=f"HTTP {status}"):
        TiingoAdapter(api_key="secret").fetch("SPY", DAY, DAY, max_response_bytes=100)
    assert len(requests) == 1
    assert requests[0].host == "api.tiingo.com"
    assert os.environ["https_proxy"] == "http://fixture-proxy.invalid:8080"
    assert os.environ["no_proxy"] == ""


@pytest.mark.parametrize(
    "failure",
    [urllib.error.URLError("secret-token-from-proxy"), TimeoutError("secret-token-from-proxy")],
)
def test_bounded_transport_error_does_not_disclose_exception_details(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    opened = Mock(side_effect=failure)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a: Mock(open=opened))
    with pytest.raises(DataError) as error:
        TiingoAdapter(api_key="secret").fetch("SPY", DAY, DAY, max_response_bytes=100)
    assert "secret-token" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("bounded", [False, True], ids=["unbounded", "bounded"])
@pytest.mark.parametrize(
    "failure_kind",
    ["urlerror", "timeout", "incomplete-read", "connection-reset", "oserror"],
)
def test_transport_failures_are_redacted_and_response_reads_are_cleaned_up(
    monkeypatch: pytest.MonkeyPatch, bounded: bool, failure_kind: str
) -> None:
    secret = "synthetic-secret-from-transport"
    failures: dict[str, Exception] = {
        "urlerror": urllib.error.URLError(secret),
        "timeout": TimeoutError(secret),
        "incomplete-read": http.client.IncompleteRead(partial=secret.encode(), expected=100),
        "connection-reset": ConnectionResetError(secret),
        "oserror": OSError(secret),
    }
    failure = failures[failure_kind]
    fails_during_read = failure_kind in {
        "incomplete-read",
        "connection-reset",
        "oserror",
    }

    class InterruptedResponse:
        def __init__(self) -> None:
            self.closed = False
            self.read_sizes: list[int] = []

        def __enter__(self) -> InterruptedResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            self.closed = True

        def read(self, size: int = -1) -> bytes:
            self.read_sizes.append(size)
            raise failure

    response = InterruptedResponse() if fails_during_read else None

    def open_request(*_args: object, **_kwargs: object) -> InterruptedResponse:
        if response is None:
            raise failure
        return response

    if bounded:
        monkeypatch.setattr(urllib.request, "build_opener", lambda *_args: Mock(open=open_request))
        request_options: dict[str, int] = {"max_response_bytes": 128}
    else:
        monkeypatch.setattr(urllib.request, "urlopen", open_request)
        request_options = {}

    with pytest.raises(DataError) as error:
        TiingoAdapter(api_key="synthetic-api-key").fetch("SPY", DAY, DAY, **request_options)

    assert str(error.value) == f"Tiingo transport failed: {type(failure).__name__}"
    assert secret not in str(error.value)
    assert error.value.__suppress_context__
    if response is not None:
        assert response.closed
        assert response.read_sizes == [129 if bounded else -1]
