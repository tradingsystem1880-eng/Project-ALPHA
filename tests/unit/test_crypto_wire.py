from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_data.crypto.providers._wire import (
    decode_json_object,
    epoch_ms_to_utc,
    fetch_bounded,
    finite_float,
    resolve_endpoint,
    validate_book_sides,
)

_HOST = "https://api.example.test/v1/"
_ENDPOINTS = {"quotes": ("/quotes", frozenset({"symbol"}))}


class _Response:
    def __init__(self, payload: bytes, mime: str = "application/json", url: str = _HOST) -> None:
        self.payload = payload
        self.headers = {"Content-Type": mime}
        self.url = url

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return self.payload

    def geturl(self) -> str:
        return self.url


def _fetch(response: _Response, monkeypatch: pytest.MonkeyPatch) -> bytes:
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: response)
    return fetch_bounded(
        _HOST + "quotes",
        provider="Example",
        host_prefix=_HOST,
        content_types=frozenset({"application/json"}),
        max_bytes=16,
        timeout_seconds=5,
    )


def test_fetch_rejects_a_redirect_to_another_host(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(DataError, match="Example redirect host is invalid"):
        _fetch(_Response(b"{}", url="https://attacker.invalid/v1/"), monkeypatch)


def test_fetch_rejects_a_non_json_mime(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(DataError, match="Example response MIME is not JSON"):
        _fetch(_Response(b"{}", mime="text/html"), monkeypatch)


def test_fetch_rejects_a_body_over_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(DataError, match="Example response exceeds the byte limit"):
        _fetch(_Response(b"x" * 17), monkeypatch)


def test_resolve_endpoint_rejects_an_unsupported_parameter() -> None:
    with pytest.raises(DataError, match="unsupported Example query parameters"):
        resolve_endpoint(_ENDPOINTS, "quotes", {"api_key": "leak"}, provider="Example")
    with pytest.raises(DataError, match="Example query contains an unsupported value"):
        resolve_endpoint(_ENDPOINTS, "quotes", {"symbol": True}, provider="Example", max_params=4)


def test_decode_json_object_rejects_a_non_object_payload() -> None:
    with pytest.raises(DataError, match="Example response must be an object"):
        decode_json_object(b"[]", provider="Example")


def test_finite_float_rejects_non_finite_and_unwanted_text() -> None:
    with pytest.raises(DataError, match="Example price is not finite"):
        finite_float("nan", "Example price")
    with pytest.raises(DataError, match="Example price is invalid"):
        finite_float("1.0", "Example price", allow_text=False)


def test_epoch_ms_bounds_are_opt_in() -> None:
    assert epoch_ms_to_utc(1, "Example timestamp").year == 1970
    with pytest.raises(DataError, match="Example timestamp is outside the supported range"):
        epoch_ms_to_utc(1, "Example timestamp", enforce_window=True)


def test_validate_book_sides_rejects_a_crossed_book() -> None:
    with pytest.raises(DataError, match="Example book is crossed"):
        validate_book_sides(
            [2.0], [1.0], provider="Example book", crossed_message="Example book is crossed"
        )
