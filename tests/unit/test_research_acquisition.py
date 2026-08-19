"""Fail-closed boundaries for future research-source acquisition workers."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from alpha_cli.research_acquisition import (
    AcquisitionPolicy,
    SourceResponse,
    validate_source_response,
    validate_source_url,
)
from alpha_core import DataError


def _resolve(*addresses: str) -> Iterable[str]:
    return addresses


def test_source_url_requires_allowlisted_https_global_address() -> None:
    policy = AcquisitionPolicy(allowed_hosts=frozenset({"api.openalex.org"}))

    assert (
        validate_source_url(
            "https://api.openalex.org/works?search=double-bottom",
            policy=policy,
            resolver=lambda _host, _port: _resolve("104.20.1.1", "2606:4700::1"),
        )
        == "https://api.openalex.org/works?search=double-bottom"
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"allowed_hosts": frozenset()},
        {"allowed_hosts": frozenset({"API.OPENALEX.ORG"})},
        {"allowed_hosts": frozenset({"api.openalex.org."})},
        {"allowed_hosts": frozenset({"api.openalex.org"}), "max_response_bytes": True},
        {"allowed_hosts": frozenset({"api.openalex.org"}), "max_response_bytes": 1.5},
        {"allowed_hosts": frozenset({"api.openalex.org"}), "allowed_media_types": frozenset()},
        {
            "allowed_hosts": frozenset({"api.openalex.org"}),
            "allowed_media_types": frozenset({"Application/JSON"}),
        },
    ],
)
def test_acquisition_policy_requires_canonical_bounded_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(DataError):
        AcquisitionPolicy(**kwargs)  # type: ignore[arg-type]


def test_acquisition_policy_rejects_invalid_unicode_and_noncanonical_idna() -> None:
    with pytest.raises(DataError, match="allowlist is invalid"):
        AcquisitionPolicy(allowed_hosts=frozenset({"\ud800.example"}))
    with pytest.raises(DataError, match="canonical IDNA"):
        AcquisitionPolicy(allowed_hosts=frozenset({"tést.example"}))


@pytest.mark.parametrize(
    ("url", "addresses", "message"),
    [
        ("http://api.openalex.org/works", ("104.20.1.1",), "HTTPS"),
        ("https://evil.example/works", ("104.20.1.1",), "allowlisted"),
        ("https://user:secret@api.openalex.org/works", ("104.20.1.1",), "credentials"),
        ("https://api.openalex.org:8443/works", ("104.20.1.1",), "port"),
        ("https://api.openalex.org./works", ("104.20.1.1",), "hostname"),
        ("https://api.openalex.org/works", ("127.0.0.1",), "non-public"),
        ("https://api.openalex.org/works", ("169.254.169.254",), "non-public"),
        ("https://api.openalex.org/works", ("10.0.0.3",), "non-public"),
        ("https://api.openalex.org/works", (), "resolve"),
    ],
)
def test_source_url_rejects_ssrf_and_ambiguous_targets(
    url: str, addresses: tuple[str, ...], message: str
) -> None:
    policy = AcquisitionPolicy(allowed_hosts=frozenset({"api.openalex.org"}))
    with pytest.raises(DataError, match=message):
        validate_source_url(
            url,
            policy=policy,
            resolver=lambda _host, _port: _resolve(*addresses),
        )


def test_source_url_rejects_malformed_unicode_dns_and_address_answers() -> None:
    policy = AcquisitionPolicy(allowed_hosts=frozenset({"api.openalex.org"}))
    with pytest.raises(DataError, match="malformed"):
        validate_source_url(
            "https://api.openalex.org:not-a-port/works",
            policy=policy,
            resolver=lambda _host, _port: _resolve("104.20.1.1"),
        )
    unicode_policy = AcquisitionPolicy(allowed_hosts=frozenset({"xn--test-9ta.example"}))
    with pytest.raises(DataError, match="invalid hostname"):
        validate_source_url(
            "https://\ud800.example/works",
            policy=unicode_policy,
            resolver=lambda _host, _port: _resolve("104.20.1.1"),
        )

    def failed_resolution(_host: str, _port: int) -> Iterable[str]:
        raise OSError("simulated DNS outage")

    with pytest.raises(DataError, match="could not resolve"):
        validate_source_url(
            "https://api.openalex.org/works",
            policy=policy,
            resolver=failed_resolution,
        )
    with pytest.raises(DataError, match="invalid address"):
        validate_source_url(
            "https://api.openalex.org/works",
            policy=policy,
            resolver=lambda _host, _port: _resolve("not-an-ip-address"),
        )


def test_source_response_is_bounded_and_receipted() -> None:
    policy = AcquisitionPolicy(allowed_hosts=frozenset({"api.openalex.org"}), max_response_bytes=12)
    receipt = validate_source_response(
        SourceResponse(
            final_url="https://api.openalex.org/works/W1",
            media_type="application/json; charset=utf-8",
            declared_length=8,
            chunks=(b'{"id":', b"1}"),
        ),
        policy=policy,
        resolver=lambda _host, _port: _resolve("104.20.1.1"),
    )

    assert receipt.byte_count == 8
    assert receipt.media_type == "application/json"
    assert receipt.sha256 == "037c9214eef74cc3887f3a4f085b4e17d76280dafd273b0ee160c09c4ba1cfd4"
    assert receipt.trust_label == "UNTRUSTED_SOURCE"


@pytest.mark.parametrize(
    "response",
    [
        SourceResponse(
            final_url="https://api.openalex.org/a.zip",
            media_type="application/zip",
            declared_length=3,
            chunks=(b"zip",),
        ),
        SourceResponse(
            final_url="https://api.openalex.org/works",
            media_type="application/json",
            declared_length=99,
            chunks=(b"{}",),
        ),
        SourceResponse(
            final_url="https://api.openalex.org/works",
            media_type="application/json",
            declared_length=None,
            chunks=(b"123456", b"123456", b"x"),
        ),
        SourceResponse(
            final_url="https://api.openalex.org/works",
            media_type="application/json",
            declared_length=1,
            chunks=(b"{}",),
        ),
        SourceResponse(
            final_url="https://api.openalex.org/works",
            media_type="application/json",
            declared_length=2.0,  # type: ignore[arg-type]
            chunks=(b"{}",),
        ),
        SourceResponse(
            final_url="https://api.openalex.org/paper.pdf",
            media_type="application/pdf",
            declared_length=8,
            chunks=(b"PK\x03\x04evil",),
        ),
        SourceResponse(
            final_url="https://api.openalex.org/works",
            media_type="application/json",
            declared_length=9,
            chunks=(b"not-json!",),
        ),
        SourceResponse(
            final_url="https://api.openalex.org/paper.txt",
            media_type="text/plain",
            declared_length=3,
            chunks=(b"a\x00b",),
        ),
        SourceResponse(
            final_url="https://api.openalex.org/not-really-text",
            media_type="text/plain",
            declared_length=9,
            chunks=(b"%PDF-fake",),
        ),
    ],
)
def test_source_response_rejects_mime_oversize_and_length_mismatch(
    response: SourceResponse,
) -> None:
    policy = AcquisitionPolicy(allowed_hosts=frozenset({"api.openalex.org"}), max_response_bytes=12)
    with pytest.raises(DataError):
        validate_source_response(
            response,
            policy=policy,
            resolver=lambda _host, _port: _resolve("104.20.1.1"),
        )


@pytest.mark.parametrize(
    "response",
    [
        SourceResponse(
            final_url="https://api.openalex.org/works",
            media_type="application/json",
            declared_length=None,
            chunks=("not-bytes",),  # type: ignore[arg-type]
        ),
        SourceResponse(
            final_url="https://api.openalex.org/paper.pdf",
            media_type="application/pdf",
            declared_length=7,
            chunks=(b"not-pdf",),
        ),
        SourceResponse(
            final_url="https://api.openalex.org/paper.txt",
            media_type="text/plain",
            declared_length=1,
            chunks=(b"\xff",),
        ),
    ],
)
def test_source_response_rejects_nonbytes_false_pdf_and_invalid_utf8(
    response: SourceResponse,
) -> None:
    policy = AcquisitionPolicy(allowed_hosts=frozenset({"api.openalex.org"}))
    with pytest.raises(DataError):
        validate_source_response(
            response,
            policy=policy,
            resolver=lambda _host, _port: _resolve("104.20.1.1"),
        )


def test_arxiv_landing_page_cannot_be_mislabeled_as_pdf() -> None:
    policy = AcquisitionPolicy(allowed_hosts=frozenset({"arxiv.org"}))
    with pytest.raises(DataError, match="landing-page URL"):
        validate_source_response(
            SourceResponse(
                final_url="https://arxiv.org/abs/1234.5678",
                media_type="application/pdf",
                declared_length=None,
                chunks=(b"%PDF-1.7\nvalid-looking bytes",),
            ),
            policy=policy,
            resolver=lambda _host, _port: _resolve("151.101.1.42"),
        )
