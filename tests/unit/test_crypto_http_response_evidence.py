"""Strict framing evidence only, synthetic responses; no network admission or replay."""

from __future__ import annotations

import io
from typing import Any
from urllib.request import Request

import pytest

from alpha_core import DataError
from alpha_data.crypto.providers._wire import (
    CompleteHttpResponse,
    RequestBudget,
    fetch_bounded,
    http_request_hash,
)

URL = "https://api.bybit.com/v5/market/test"


class Response:
    def __init__(
        self,
        body: bytes = b"{}",
        *,
        length: str | None = "2",
        encoding: str | None = None,
        status: int = 200,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.url = URL
        self.body = io.BytesIO(body)
        self.headers = {"Content-Type": "application/json"}
        if length is not None:
            self.headers["Content-Length"] = length
        if encoding is not None:
            self.headers["Content-Encoding"] = encoding
        self.status = status
        self.closed = False
        self.requests: list[int] = []
        self.chunks = iter(chunks) if chunks is not None else None

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.closed = True

    def geturl(self) -> str:
        return self.url

    def getcode(self) -> int:
        return self.status

    def read(self, size: int) -> bytes:
        self.requests.append(size)
        return self.body.read(size) if self.chunks is None else next(self.chunks, b"")


def fetch(
    response: Response,
    monkeypatch: pytest.MonkeyPatch,
    evidence: list[CompleteHttpResponse],
    **kwargs: Any,
) -> bytes:
    class Opener:
        def open(self, *args: object, **kwargs: object) -> Response:
            return response

    monkeypatch.setattr("urllib.request.build_opener", lambda *args: Opener())
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *args, **kwargs: pytest.fail("no legacy opener")
    )
    return fetch_bounded(
        URL,
        provider="synthetic",
        host_prefix="https://api.bybit.com/v5/",
        content_types=frozenset({"application/json"}),
        max_bytes=100_000,
        timeout_seconds=1,
        response_evidence=evidence.append,
        **kwargs,
    )


def test_bounded_chunks_eof_close_then_exact_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Response(length="6", chunks=[b"ab", b"cdef", b""])
    evidence: list[CompleteHttpResponse] = []
    assert fetch(response, monkeypatch, evidence) == b"abcdef"
    assert response.closed and response.requests == [7, 5, 1]
    item = evidence[0]
    assert item.request_hash == http_request_hash(Request(URL)) and item.status_code == 200
    assert item.body == b"abcdef" and item.content_length == 6 and item.actual_bytes == 6
    assert item.body_sha256 == "bef57ec7f53a6d40beb640a780a639c83bc29ac8a9816f1fc6c5c6dcd93c4721"
    assert item.basis == "identity_content_length_and_eof"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"length": None},
        {"length": "invalid"},
        {"length": "100001"},
        {"length": "-1"},
        {"length": "3"},
        {"length": "1"},
        {"encoding": "gzip"},
        {"status": 206},
        {"length": "2", "chunks": [b"{}extra"]},
    ],
)
def test_missing_ambiguous_oversize_or_truncated_bodies_never_emit_evidence(
    monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, Any]
) -> None:
    response = Response(**kwargs)
    evidence: list[CompleteHttpResponse] = []
    with pytest.raises(DataError):
        fetch(response, monkeypatch, evidence)
    assert response.closed and evidence == []


@pytest.mark.parametrize("phase", ["read", "close"])
def test_interruption_does_not_emit_evidence(monkeypatch: pytest.MonkeyPatch, phase: str) -> None:
    class Broken(Response):
        def read(self, size: int) -> bytes:
            if phase == "read":
                raise TimeoutError("synthetic")
            return super().read(size)

        def __exit__(self, *args: object) -> None:
            self.closed = True
            if phase == "close":
                raise OSError("synthetic")

    response = Broken()
    evidence: list[CompleteHttpResponse] = []
    with pytest.raises((DataError, OSError)):
        fetch(response, monkeypatch, evidence)
    assert response.closed and evidence == []


def test_eof_probe_and_application_budget_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Response()
    evidence: list[CompleteHttpResponse] = []
    budget = RequestBudget(1, 3)
    assert fetch(response, monkeypatch, evidence, budget=budget) == b"{}"
    assert budget.requests_used == 1 and budget.bytes_read == 2 and response.requests == [3, 1]
    assert len(evidence) == 1


def test_empty_identity_body_is_complete_bytes_not_valid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Response(body=b"", length="0")
    evidence: list[CompleteHttpResponse] = []
    assert fetch(response, monkeypatch, evidence) == b""
    assert evidence[0].actual_bytes == 0 and response.requests == [1]


def test_strict_same_host_different_url_has_no_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Response()
    response.url = URL + "other"
    evidence: list[CompleteHttpResponse] = []
    with pytest.raises(DataError):
        fetch(response, monkeypatch, evidence)
    assert response.closed and not evidence


def test_strict_request_mutation_cannot_change_accounting_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Response()
    evidence: list[CompleteHttpResponse] = []
    accounted = []

    class Opener:
        def open(self, request: Request, **kwargs: object) -> Response:
            request.full_url = URL + "mutated"
            response.url = request.full_url
            return response

    monkeypatch.setattr("urllib.request.build_opener", lambda *a: Opener())

    def hook(request_hash: str, ordinal: int, send: Any) -> bytes:
        accounted.append(request_hash)
        result = send()
        assert isinstance(result, bytes)
        return result

    with pytest.raises(DataError):
        fetch_bounded(
            URL,
            provider="synthetic",
            host_prefix="https://api.bybit.com/v5/",
            content_types=frozenset({"application/json"}),
            max_bytes=1000,
            timeout_seconds=1,
            attempt_hook=hook,
            response_evidence=evidence.append,
        )
    assert accounted == [http_request_hash(Request(URL))] and not evidence and response.closed


@pytest.mark.parametrize(
    "extra",
    [{"content-length": "2"}, {"Transfer-Encoding": "chunked"}, {"Content-Encoding": "gzip"}],
)
def test_duplicate_or_ambiguous_framing_never_emits_complete_evidence(
    monkeypatch: pytest.MonkeyPatch, extra: dict[str, str]
) -> None:
    response = Response()
    response.headers.update(extra)
    evidence: list[CompleteHttpResponse] = []
    with pytest.raises(DataError):
        fetch(response, monkeypatch, evidence)
    assert response.closed and not evidence and response.requests == []


def test_header_bound_prevents_read_and_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Response()
    response.headers.update({f"X-{i}": "v" for i in range(129)})
    evidence: list[CompleteHttpResponse] = []
    with pytest.raises(DataError):
        fetch(response, monkeypatch, evidence)
    assert response.closed and not evidence and not response.requests
