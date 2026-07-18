"""Offline guards for the Stooq transport hardening (the headline of the anti-bot fix).

Stooq now gates its free CSV behind a SHA-256 "verify your browser" proof-of-work and a per-IP
"Access denied" quota. The pure parser is covered in test_stooq_parser.py; here we pin the two
load-bearing pieces that previously had no offline coverage: the proof-of-work solver and the
fail-loud classification of a blocked/non-CSV response. The live HTTP path stays network-gated.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from email.message import Message

import pytest

from alpha_core import DataError
from alpha_data.adapters import stooq_adapter
from alpha_data.adapters.stooq_adapter import _csv_or_raise, _fetch_stooq_text, _solve_pow

_VALID_CSV = (
    "Date,Open,High,Low,Close,Volume\n"
    "2020-01-02,100.0,101.0,99.0,100.5,1000\n"
    "2020-01-03,100.5,102.0,100.0,101.5,1200\n"
)
_CHALLENGE_PAGE = (
    "<!DOCTYPE html><html><body><noscript>This site requires JavaScript to verify your "
    'browser.</noscript><script>const c="AAAA",d=4;</script></body></html>'
)


def test_solve_pow_returns_valid_nonce() -> None:
    for difficulty in (1, 2):
        nonce = _solve_pow("challenge-token", difficulty)
        digest = hashlib.sha256(f"challenge-token{nonce}".encode()).hexdigest()
        assert digest.startswith("0" * difficulty)


def test_solve_pow_fails_loud_when_unsolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Cap iterations far below what difficulty 8 (~16^8 hashes) needs → must raise, not hang.
    monkeypatch.setattr(stooq_adapter, "_POW_MAX_ITERS", 5)
    with pytest.raises(DataError, match="proof-of-work unsolved"):
        _solve_pow("challenge-token", 8)


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
