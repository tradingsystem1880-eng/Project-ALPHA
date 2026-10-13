"""Bounded transport tests use fake HTTP handlers and never contact a provider."""

from __future__ import annotations

import io
import json
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
    opened = Mock(side_effect=lambda *a, **kw: io.BytesIO(raw))
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a: Mock(open=opened))
    result = TiingoAdapter(api_key="secret").fetch("SPY", DAY, DAY, max_response_bytes=len(raw))
    assert result.raw_response == raw
    assert opened.call_args.kwargs == {"timeout": 30}
    with pytest.raises(DataError, match="response exceeds"):
        TiingoAdapter(api_key="secret").fetch("SPY", DAY, DAY, max_response_bytes=len(raw) - 1)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_is_rejected_before_second_request(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
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
        urllib.request, "build_opener", lambda *handlers: real_build(FakeHTTPS(), *handlers)
    )
    with pytest.raises(DataError, match=f"HTTP {status}"):
        TiingoAdapter(api_key="secret").fetch("SPY", DAY, DAY, max_response_bytes=100)
    assert len(requests) == 1
    assert requests[0].host == "api.tiingo.com"


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
