"""The validated fetch loop: every hop through the allowlist, every byte bounded."""

from __future__ import annotations

from pathlib import Path

import pytest

from literature_worker._acquisition import AcquisitionPolicy
from literature_worker._errors import DataError
from literature_worker.fetch import (
    TransportResponse,
    fetch_validated,
    store_object,
    verify_object,
)

_POLICY = AcquisitionPolicy(allowed_hosts=frozenset({"export.arxiv.org", "arxiv.org"}))


def _resolver(host: str, port: int) -> list[str]:
    del host, port
    return ["93.184.216.34"]


def test_redirects_are_revalidated_per_hop_and_offsite_hops_fail_closed() -> None:
    hops: list[str] = []

    def transport(url: str) -> TransportResponse:
        hops.append(url)
        if url == "https://export.arxiv.org/pdf/1":
            return TransportResponse(302, "https://arxiv.org/pdf/1", "", None, b"")
        return TransportResponse(200, None, "application/pdf", 9, b"%PDF-1.7\n")

    raw, receipt = fetch_validated(
        "https://export.arxiv.org/pdf/1",
        policy=_POLICY,
        resolver=_resolver,
        transport=transport,
    )
    assert raw.startswith(b"%PDF-")
    assert receipt.final_url == "https://arxiv.org/pdf/1"
    assert receipt.trust_label == "UNTRUSTED_SOURCE"
    assert hops == ["https://export.arxiv.org/pdf/1", "https://arxiv.org/pdf/1"]

    def hostile_transport(url: str) -> TransportResponse:
        del url
        return TransportResponse(302, "https://evil.example.com/payload", "", None, b"")

    with pytest.raises(DataError, match="not allowlisted"):
        fetch_validated(
            "https://export.arxiv.org/pdf/1",
            policy=_POLICY,
            resolver=_resolver,
            transport=hostile_transport,
        )


def test_redirect_loops_and_non_200_statuses_fail_closed() -> None:
    def looping(url: str) -> TransportResponse:
        del url
        return TransportResponse(302, "https://arxiv.org/pdf/loop", "", None, b"")

    with pytest.raises(DataError, match="redirect limit"):
        fetch_validated(
            "https://arxiv.org/pdf/loop",
            policy=_POLICY,
            resolver=_resolver,
            transport=looping,
        )

    def missing(url: str) -> TransportResponse:
        del url
        return TransportResponse(404, None, "text/plain", None, b"gone")

    with pytest.raises(DataError, match="HTTP 404"):
        fetch_validated(
            "https://arxiv.org/pdf/x",
            policy=_POLICY,
            resolver=_resolver,
            transport=missing,
        )


def test_store_and_verify_detect_tampering(tmp_path: Path) -> None:
    def transport(url: str) -> TransportResponse:
        del url
        return TransportResponse(200, None, "text/plain", None, b"benign text")

    raw, receipt = fetch_validated(
        "https://arxiv.org/abs/x",
        policy=_POLICY,
        resolver=_resolver,
        transport=transport,
    )
    stored = store_object(raw, receipt, tmp_path / "objects")
    object_path = Path(stored["object_path"])
    receipt_path = Path(stored["receipt_path"])
    verify_object(object_path, receipt_path)
    object_path.write_bytes(b"tampered bytes")
    with pytest.raises(DataError, match="does not match its receipt digest"):
        verify_object(object_path, receipt_path)
