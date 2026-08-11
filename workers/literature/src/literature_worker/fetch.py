"""Validated document acquisition: every hop and every byte through the primitives.

The transport is injected so tests exercise the complete redirect/validation loop
offline. The default transport uses urllib with redirects disabled — the loop itself
re-validates every redirect target against the allowlist before reconnecting.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from literature_worker._acquisition import (
    AcquisitionPolicy,
    SourceReceipt,
    SourceResponse,
    validate_source_response,
    validate_source_url,
)
from literature_worker._errors import DataError

Resolver = Callable[[str, int], Iterable[str]]


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """One hop's transport result; redirects are surfaced, never auto-followed."""

    status: int
    location: str | None
    media_type: str
    declared_length: int | None
    body: bytes


Transport = Callable[[str], TransportResponse]

_MAX_REDIRECTS = 5


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def default_resolver(host: str, port: int) -> list[str]:
    return sorted(
        {str(info[4][0]) for info in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)}
    )


def urllib_transport(url: str) -> TransportResponse:
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(  # noqa: S310 - callers validate every hop first
        url, headers={"User-Agent": "alpha-literature-worker/0.1 (research; contact: owner)"}
    )
    try:
        with opener.open(request, timeout=30) as response:
            return TransportResponse(
                status=int(response.status),
                location=None,
                media_type=str(response.headers.get("Content-Type", "")),
                declared_length=(
                    int(response.headers["Content-Length"])
                    if response.headers.get("Content-Length", "").isdigit()
                    else None
                ),
                body=response.read(),
            )
    except urllib.error.HTTPError as error:
        if 300 <= error.code < 400:
            return TransportResponse(
                status=error.code,
                location=error.headers.get("Location"),
                media_type="",
                declared_length=None,
                body=b"",
            )
        raise DataError(f"literature fetch failed with HTTP {error.code}") from error
    except OSError as exc:
        raise DataError(f"literature fetch transport failed: {exc}") from exc


def fetch_validated(
    url: str,
    *,
    policy: AcquisitionPolicy,
    resolver: Resolver,
    transport: Transport,
) -> tuple[bytes, SourceReceipt]:
    """Fetch one document, re-validating the URL before every hop (fail-closed)."""
    current = validate_source_url(url, policy=policy, resolver=resolver)
    for _ in range(_MAX_REDIRECTS + 1):
        hop = transport(current)
        if 300 <= hop.status < 400:
            if not hop.location:
                raise DataError("literature redirect carried no Location header")
            current = validate_source_url(
                urljoin(current, hop.location), policy=policy, resolver=resolver
            )
            continue
        if hop.status != 200:
            raise DataError(f"literature fetch returned HTTP {hop.status}")
        if len(hop.body) > policy.max_response_bytes:
            raise DataError("research source response exceeds the byte limit")
        receipt = validate_source_response(
            SourceResponse(
                final_url=current,
                media_type=hop.media_type,
                declared_length=hop.declared_length,
                chunks=(hop.body,),
            ),
            policy=policy,
            resolver=resolver,
        )
        return hop.body, receipt
    raise DataError("literature fetch exceeded the redirect limit")


def store_object(raw: bytes, receipt: SourceReceipt, objects_dir: Path) -> dict[str, str]:
    """Content-address the bytes and persist the UNTRUSTED_SOURCE receipt beside them."""
    objects_dir.mkdir(parents=True, exist_ok=True)
    object_path = objects_dir / receipt.sha256
    object_path.write_bytes(raw)
    receipt_path = objects_dir / f"{receipt.sha256}.receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "final_url": receipt.final_url,
                "media_type": receipt.media_type,
                "byte_count": receipt.byte_count,
                "sha256": receipt.sha256,
                "trust_label": receipt.trust_label,
            },
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"object_path": str(object_path), "receipt_path": str(receipt_path)}


def verify_object(object_path: Path, receipt_path: Path) -> None:
    """Tamper detection: the stored bytes must still hash to the receipt's digest."""
    import hashlib

    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("literature object receipt is unreadable") from exc
    expected = receipt.get("sha256") if isinstance(receipt, dict) else None
    if not isinstance(expected, str):
        raise DataError("literature object receipt has no digest")
    actual = hashlib.sha256(object_path.read_bytes()).hexdigest()
    if actual != expected:
        raise DataError(f"literature object {object_path.name} does not match its receipt digest")


__all__ = [
    "Transport",
    "TransportResponse",
    "default_resolver",
    "fetch_validated",
    "store_object",
    "urllib_transport",
    "verify_object",
]
