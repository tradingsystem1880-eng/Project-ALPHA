"""Offline guards for the Stooq transport hardening (the headline of the anti-bot fix).

Stooq now gates its free CSV behind a SHA-256 "verify your browser" proof-of-work and a per-IP
"Access denied" quota. The pure parser is covered in test_stooq_parser.py; here we pin the two
load-bearing pieces: refusal of browser verification and the
fail-loud classification of a blocked/non-CSV response. The live HTTP path stays network-gated.
"""

from __future__ import annotations

import http.client
import io
import urllib.error
import urllib.request
from email.message import Message
from types import SimpleNamespace

import pytest

from alpha_core import DataError
from alpha_data.adapters.stooq_adapter import _csv_or_raise, _fetch_stooq_text

_VALID_CSV = (
    "Date,Open,High,Low,Close,Volume\n"
    "2020-01-02,100.0,101.0,99.0,100.5,1000\n"
    "2020-01-03,100.5,102.0,100.0,101.5,1200\n"
)
_CHALLENGE_PAGE = (
    "<!DOCTYPE html><html><body><noscript>This site requires JavaScript to verify your "
    'browser.</noscript><script>const c="AAAA",d=4;</script></body></html>'
)


@pytest.mark.parametrize("page", [_CHALLENGE_PAGE, "VERIFY YOUR BROWSER"])
def test_fetch_refuses_challenge_after_one_generic_get(
    monkeypatch: pytest.MonkeyPatch, page: str
) -> None:
    requests = []

    class Opener:
        def open(self, request: urllib.request.Request, timeout: int) -> io.BytesIO:
            requests.append(request)
            return io.BytesIO(page.encode())

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(DataError, match="anti-bot") as caught:
        _fetch_stooq_text("https://stooq.com/q/d/l/?s=spy.us")
    message = str(caught.value)
    assert "browser verification check" in message
    assert "does not get past bot checks" in message
    assert "download is refused" in message
    assert "data already stored stays readable" in message
    assert "yfinance" not in message.lower()
    assert len(requests) == 1
    assert requests[0].get_method() == "GET"
    assert requests[0].get_header("User-agent") == "Project-ALPHA/1.0"


@pytest.mark.parametrize(
    "body", ["Access denied", _CHALLENGE_PAGE, "<html>blocked</html>", "   ", "No data"]
)
def test_csv_or_raise_blocked_messages_do_not_recommend_yfinance(body: str) -> None:
    with pytest.raises(DataError) as caught:
        _csv_or_raise(body, "spy.us", "2020-01-01..2020-01-31")
    assert "yfinance" not in str(caught.value).lower()
    assert "anti-bot" in str(caught.value)


def test_csv_or_raise_parses_valid_csv() -> None:
    result = _csv_or_raise(_VALID_CSV, "spy.us", "2020-01-01..2020-01-31")
    assert result.bars.height == 2
    assert result.actions == []  # Stooq carries no separate corporate actions


def test_csv_or_raise_fails_loud_on_access_denied() -> None:
    with pytest.raises(DataError, match="anti-bot challenge"):
        _csv_or_raise("Access denied", "spy.us", "2020-01-01..2020-01-31")


def test_csv_or_raise_fails_loud_on_leftover_challenge_page() -> None:
    with pytest.raises(DataError, match="anti-bot challenge"):
        _csv_or_raise(_CHALLENGE_PAGE, "spy.us", "2020-01-01..2020-01-31")


def test_csv_or_raise_fails_loud_on_html_body() -> None:
    with pytest.raises(DataError, match="anti-bot challenge"):
        _csv_or_raise("<html><body>nope</body></html>", "spy.us", "2020-01-01..2020-01-31")


def test_csv_or_raise_fails_loud_on_empty_and_no_data() -> None:
    with pytest.raises(DataError, match="returned no data"):
        _csv_or_raise("   ", "spy.us", "2020-01-01..2020-01-31")
    with pytest.raises(DataError, match="returned no data"):
        _csv_or_raise("No data", "spy.us", "2020-01-01..2020-01-31")


def test_fetch_wraps_provider_http_rejection_as_data_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BlockedOpener:
        def open(self, request: urllib.request.Request, timeout: int) -> object:
            del timeout
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", Message(), None)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: BlockedOpener())

    with pytest.raises(DataError, match="anti-bot/transport.*HTTP 403"):
        _fetch_stooq_text("https://stooq.com/q/d/l/?s=spy.us")


@pytest.mark.parametrize(
    "error", [ConnectionResetError("synthetic reset"), http.client.IncompleteRead(b"partial", 30)]
)
def test_fetch_wraps_interrupted_body_and_closes_response(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    closed = []

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            closed.append(True)

        def read(self) -> bytes:
            raise error

    class Opener:
        def open(self, request: urllib.request.Request, timeout: int) -> Response:
            return Response()

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(DataError, match="Stooq transport failed") as caught:
        _fetch_stooq_text("https://stooq.com/q/d/l/?s=spy.us")
    assert caught.value.__cause__ is error
    assert closed == [True]


def test_fetch_returns_complete_csv_and_closes_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = io.BytesIO(_VALID_CSV.encode())
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *args: SimpleNamespace(open=lambda request, timeout: response),
    )
    assert _fetch_stooq_text("https://stooq.com/q/d/l/?s=spy.us") == _VALID_CSV
    assert response.closed
