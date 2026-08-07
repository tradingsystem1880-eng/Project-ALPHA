"""Fail-closed primitives for the future untrusted research acquisition worker.

This module deliberately does not perform network I/O.  A worker must validate every initial and
redirect URL immediately before connecting, then pass the bounded response through this module.
Keeping transport outside this seam prevents a validation helper from being mistaken for a secure
fetcher when DNS pinning and operating-system isolation are not yet active.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit, urlunsplit

from alpha_core import DataError

Resolver = Callable[[str, int], Iterable[str]]

_DEFAULT_MEDIA_TYPES: Final = frozenset(
    {
        "application/json",
        "application/pdf",
        "text/html",
        "text/plain",
    }
)
_PROHIBITED_MAGIC: Final = (
    b"PK\x03\x04",  # ZIP and office containers
    b"\x1f\x8b",  # gzip
    b"Rar!\x1a\x07",  # RAR
    b"7z\xbc\xaf\x27\x1c",  # 7-Zip
    b"\x7fELF",
    b"MZ",
    b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit
    b"\xfe\xed\xfa\xcf",
)


@dataclass(frozen=True, slots=True)
class AcquisitionPolicy:
    """Static acquisition limits; provider hosts must be explicitly selected by the caller."""

    allowed_hosts: frozenset[str]
    allowed_media_types: frozenset[str] = _DEFAULT_MEDIA_TYPES
    max_response_bytes: int = 10 * 1024 * 1024

    def __post_init__(self) -> None:
        if not isinstance(self.allowed_hosts, frozenset) or not self.allowed_hosts:
            raise DataError("research acquisition requires an explicit host allowlist")
        for host in self.allowed_hosts:
            if not isinstance(host, str) or not host or host.endswith(".") or host != host.lower():
                raise DataError("research acquisition hosts must be canonical lowercase names")
            try:
                canonical_host = host.encode("idna").decode("ascii")
            except UnicodeError as exc:
                raise DataError("research acquisition host allowlist is invalid") from exc
            if canonical_host != host:
                raise DataError("research acquisition hosts must use canonical IDNA form")
        if not isinstance(self.allowed_media_types, frozenset) or not self.allowed_media_types:
            raise DataError("research acquisition requires an explicit MIME allowlist")
        if any(
            not isinstance(media_type, str)
            or not media_type
            or media_type != media_type.strip().lower()
            or "/" not in media_type
            or ";" in media_type
            for media_type in self.allowed_media_types
        ):
            raise DataError("research acquisition MIME types must be canonical")
        if (
            isinstance(self.max_response_bytes, bool)
            or not isinstance(self.max_response_bytes, int)
            or self.max_response_bytes < 1
        ):
            raise DataError("research acquisition response limit must be positive")


@dataclass(frozen=True, slots=True)
class SourceResponse:
    """Transport-neutral response supplied only after redirects have been followed manually."""

    final_url: str
    media_type: str
    declared_length: int | None
    chunks: tuple[bytes, ...]


@dataclass(frozen=True, slots=True)
class SourceReceipt:
    """Integrity receipt for untrusted bytes; it grants no authority or execution capability."""

    final_url: str
    media_type: str
    byte_count: int
    sha256: str
    trust_label: str = "UNTRUSTED_SOURCE"


def validate_source_url(url: str, *, policy: AcquisitionPolicy, resolver: Resolver) -> str:
    """Validate one acquisition hop and all of its resolved addresses.

    The worker must call this for the initial URL and again after every redirect.  All returned
    addresses must be globally routable; one private answer fails the entire resolution.
    """

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise DataError("research source URL is malformed") from exc
    if parsed.scheme != "https":
        raise DataError("research source URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise DataError("research source URL must not contain credentials")
    hostname = parsed.hostname
    if hostname is None or hostname.endswith("."):
        raise DataError("research source URL has an invalid hostname")
    try:
        ascii_host = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise DataError("research source URL has an invalid hostname") from exc
    if ascii_host not in policy.allowed_hosts:
        raise DataError("research source hostname is not allowlisted")
    if port not in {None, 443}:
        raise DataError("research source URL uses a prohibited port")
    try:
        addresses = tuple(resolver(ascii_host, 443))
    except OSError as exc:
        raise DataError("research source hostname could not resolve") from exc
    if not addresses:
        raise DataError("research source hostname did not resolve")
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise DataError("research source resolved to an invalid address") from exc
        if not address.is_global:
            raise DataError("research source resolved to a non-public address")
    # Remove a redundant explicit :443 while preserving the exact path/query.  Fragments are not
    # sent to servers and are discarded so receipts cannot disagree over client-only text.
    netloc = ascii_host if port in {None, 443} else parsed.netloc
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


def validate_source_response(
    response: SourceResponse,
    *,
    policy: AcquisitionPolicy,
    resolver: Resolver,
) -> SourceReceipt:
    """Bound MIME and bytes, verify declared length, and create a content receipt."""

    final_url = validate_source_url(response.final_url, policy=policy, resolver=resolver)
    media_type = response.media_type.split(";", maxsplit=1)[0].strip().lower()
    if media_type not in policy.allowed_media_types:
        raise DataError("research source response has a prohibited MIME type")
    declared = response.declared_length
    if declared is not None:
        if isinstance(declared, bool) or not isinstance(declared, int) or declared < 0:
            raise DataError("research source response has an invalid declared length")
        if declared > policy.max_response_bytes:
            raise DataError("research source response exceeds the byte limit")

    digest = hashlib.sha256()
    byte_count = 0
    body = bytearray()
    for chunk in response.chunks:
        if not isinstance(chunk, bytes):
            raise DataError("research source response chunks must be bytes")
        byte_count += len(chunk)
        if byte_count > policy.max_response_bytes:
            raise DataError("research source response exceeds the byte limit")
        digest.update(chunk)
        body.extend(chunk)
    if declared is not None and declared != byte_count:
        raise DataError("research source declared length does not match received bytes")
    raw = bytes(body)
    if any(raw.startswith(signature) for signature in _PROHIBITED_MAGIC):
        raise DataError("research source response contains prohibited executable or archive bytes")
    if media_type != "application/pdf" and raw.startswith(b"%PDF-"):
        raise DataError("research source response MIME does not match PDF bytes")
    if media_type == "application/pdf" and not raw.startswith(b"%PDF-"):
        raise DataError("research source response MIME does not match PDF bytes")
    if media_type == "application/json":
        try:
            json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise DataError("research source response MIME does not match JSON bytes") from exc
    if media_type in {"text/html", "text/plain"}:
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DataError("research source text must be valid UTF-8") from exc
        if "\x00" in decoded:
            raise DataError("research source text must not contain NUL bytes")
    return SourceReceipt(
        final_url=final_url,
        media_type=media_type,
        byte_count=byte_count,
        sha256=digest.hexdigest(),
    )
