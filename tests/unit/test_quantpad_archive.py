"""Immutable external archive for owner-authorized QuantPad research data."""

from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

import pytest

from alpha_core import DataError
from alpha_data.crypto.storage import Capacity
from alpha_data.quantpad_archive import (
    QuantPadArchiveRequestV1,
    QuantPadArchiveStore,
    fetch_quantpad_archive,
)


def _store(tmp_path: Path) -> QuantPadArchiveStore:
    bulk = tmp_path / "bulk"
    bulk.mkdir(exist_ok=True)
    return QuantPadArchiveStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "internal" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=1_900_000),
        minimum_free_bytes=100,
    )


def test_request_is_content_addressed_and_never_contains_a_key() -> None:
    request = QuantPadArchiveRequestV1(
        endpoint="bars",
        symbol="AAPL",
        start_ms=1_700_000_000_000,
        end_ms=1_700_086_400_000,
        timeframe="1d",
        response_format="csv",
    )
    assert request.request_id == QuantPadArchiveRequestV1.from_dict(request.to_dict()).request_id
    assert "key" not in json.dumps(request.to_dict()).lower()


def test_universe_request_keeps_search_query_and_asset_class_explicit() -> None:
    request = QuantPadArchiveRequestV1(
        endpoint="universe",
        symbol="futures-a",
        response_format="json",
        asset_class="futures",
        limit=50,
    )
    assert request.to_dict()["asset_class"] == "futures"
    assert request.to_dict()["limit"] == 50


def test_archive_publishes_external_bytes_then_internal_manifest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = QuantPadArchiveRequestV1(
        endpoint="ticks",
        symbol="NQ.c.0",
        start_ms=1_700_000_000_000,
        end_ms=1_700_000_060_000,
        schema="trades",
        response_format="arrow",
    )
    manifest = store.publish(request, [b"exact ", b"provider bytes"])
    verified = store.verify(str(manifest["manifest_id"]))
    assert verified == manifest
    assert verified["research_only"] is True
    assert verified["artifact_key"].startswith("raw/quantpad/")
    assert "bulk" not in json.dumps(verified)
    assert store.publish(request, [b"exact provider bytes"]) == manifest


def test_archive_fails_closed_on_volume_substitution_and_tamper(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = QuantPadArchiveRequestV1(
        endpoint="coverage", symbol="AAPL", response_format="json"
    )
    manifest = store.publish(request, [b"{}"])
    artifact = store.bulk_root / str(manifest["artifact_key"])
    artifact.write_bytes(b"tampered")
    with pytest.raises(DataError, match="integrity"):
        store.verify(str(manifest["manifest_id"]))

    wrong = QuantPadArchiveStore(
        bulk_root=store.bulk_root,
        manifest_root=tmp_path / "other",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "OTHER-UUID",
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=1_900_000),
        minimum_free_bytes=100,
    )
    with pytest.raises(DataError, match="UUID"):
        wrong.publish(request, [b"{}"])


@pytest.mark.parametrize(
    "values",
    [
        {"endpoint": "private", "symbol": "AAPL", "response_format": "json"},
        {"endpoint": "ticks", "symbol": "../AAPL", "schema": "trades", "response_format": "arrow"},
        {"endpoint": "ticks", "symbol": "AAPL", "schema": "orders", "response_format": "arrow"},
        {"endpoint": "bars", "symbol": "AAPL", "response_format": "arrow"},
        {
            "endpoint": "universe",
            "symbol": "AAPL",
            "response_format": "json",
            "asset_class": "not-a-class",
        },
    ],
)
def test_request_rejects_unknown_or_unsafe_contracts(values: dict[str, object]) -> None:
    with pytest.raises(DataError):
        QuantPadArchiveRequestV1(**values)  # type: ignore[arg-type]


def test_transport_pins_key_header_host_and_mime(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(
        endpoint="coverage", symbol="AAPL", response_format="json"
    )
    seen: dict[str, object] = {}

    class Response(io.BytesIO):
        headers = {"Content-Type": "application/json; charset=utf-8"}

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

        def geturl(self) -> str:
            return "https://api.quantpad.ai/v1/coverage?symbol=AAPL"

    def opener(wire_request: object, *, timeout: int) -> Response:
        seen["request"] = wire_request
        seen["timeout"] = timeout
        return Response(b'{"ok":true}')

    manifest = fetch_quantpad_archive(
        _store(tmp_path), request, api_key="sentinel-secret", opener=opener
    )
    wire_request = seen["request"]
    assert isinstance(wire_request, urllib.request.Request)
    assert wire_request.get_header("X-api-key") == "sentinel-secret"
    assert "sentinel-secret" not in json.dumps(manifest)
    assert fetch_quantpad_archive(
        _store(tmp_path),
        request,
        api_key="sentinel-secret",
        opener=lambda *_a, **_k: pytest.fail("completed requests must not refetch"),
    ) == manifest


def test_transport_rejects_html_and_cross_host_redirects(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(
        endpoint="coverage", symbol="AAPL", response_format="json"
    )

    class Response(io.BytesIO):
        headers = {"Content-Type": "text/html"}

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

        def geturl(self) -> str:
            return "https://example.com/login"

    with pytest.raises(DataError, match="pinned HTTPS host"):
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="secret", opener=lambda *_a, **_k: Response(b"x")
        )


def test_transport_retries_one_transient_failure_without_publishing_partial_bytes(
    tmp_path: Path,
) -> None:
    request = QuantPadArchiveRequestV1(
        endpoint="coverage", symbol="AAPL", response_format="json"
    )
    calls = 0

    class Response(io.BytesIO):
        headers = {"Content-Type": "application/json"}

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

        def geturl(self) -> str:
            return "https://api.quantpad.ai/v1/coverage?symbol=AAPL"

    def opener(*_args: object, **_kwargs: object) -> Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("network timeout")
        return Response(b"{}")

    result = fetch_quantpad_archive(
        _store(tmp_path), request, api_key="secret", opener=opener, sleep=lambda _: None
    )
    assert calls == 2
    assert result["artifact_bytes"] == 2
