"""Immutable external archive for owner-authorized QuantPad research data."""

from __future__ import annotations

import email.message
import io
import json
import urllib.error
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


def _headers(values: dict[str, str]) -> email.message.Message:
    """urllib hands HTTPError a real ``Message``; mirror that instead of a dict."""
    message = email.message.Message()
    for key, value in values.items():
        message[key] = value
    return message


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
    assert str(verified["artifact_key"]).startswith("raw/quantpad/")
    assert "bulk" not in json.dumps(verified)
    assert store.publish(request, [b"exact provider bytes"]) == manifest


def test_archive_fails_closed_on_volume_substitution_and_tamper(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
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
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
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
    assert (
        fetch_quantpad_archive(
            _store(tmp_path),
            request,
            api_key="sentinel-secret",
            opener=lambda *_a, **_k: pytest.fail("completed requests must not refetch"),
        )
        == manifest
    )


def test_transport_rejects_html_and_cross_host_redirects(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")

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
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
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


def test_transport_honours_bounded_rate_limit_retry_after(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
    calls = 0
    sleeps: list[float] = []

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
            raise urllib.error.HTTPError(
                "https://api.quantpad.ai/v1/coverage?symbol=AAPL",
                429,
                "rate limited",
                _headers({"Retry-After": "4"}),
                None,
            )
        return Response(b"{}")

    assert (
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="secret", opener=opener, sleep=sleeps.append
        )["artifact_bytes"]
        == 2
    )
    assert calls == 2
    assert sleeps == [4.0]


def _response(
    body: bytes, *, content_type: str = "application/json", url: str | None = None
) -> io.BytesIO:
    """One stand-in for the four hand-rolled Response classes the transport tests need."""

    class Response(io.BytesIO):
        headers = {"Content-Type": content_type}

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

        def geturl(self) -> str:
            return url or "https://api.quantpad.ai/v1/coverage?symbol=AAPL"

    return Response(body)


@pytest.mark.parametrize(
    "values",
    [
        # every fail-loud contract branch, one case each
        {"endpoint": "bars", "symbol": "A", "response_format": "csv", "compression": "gzip"},
        {"endpoint": "bars", "symbol": "A", "response_format": "csv", "roll_adjust": "forward"},
        {"endpoint": "bars", "symbol": "A", "response_format": "json", "timeframe": "1d"},
        {"endpoint": "bars", "symbol": "A", "response_format": "csv"},
        {"endpoint": "ticks", "symbol": "A", "schema": "trades", "response_format": "csv"},
        {
            "endpoint": "ticks",
            "symbol": "A",
            "schema": "trades",
            "timeframe": "1d",
            "response_format": "arrow",
        },
        {"endpoint": "coverage", "symbol": "A", "response_format": "json", "timeframe": "1d"},
        {"endpoint": "coverage", "symbol": "A", "response_format": "json", "limit": 10},
        {"endpoint": "universe", "symbol": "A", "response_format": "json", "limit": 10},
        {
            "endpoint": "universe",
            "symbol": "A",
            "response_format": "json",
            "limit": 50,
            "start_ms": 1,
        },
        {
            "endpoint": "bars",
            "symbol": "A",
            "response_format": "csv",
            "timeframe": "1d",
            "start_ms": 5,
            "end_ms": 5,
        },
        {
            "endpoint": "bars",
            "symbol": "A",
            "response_format": "csv",
            "timeframe": "1d",
            "start_ms": -1,
            "end_ms": 5,
        },
        {
            "endpoint": "bars",
            "symbol": "A",
            "response_format": "csv",
            "timeframe": "1d",
            "start_ms": True,
            "end_ms": 5,
        },
        {
            "endpoint": "bars",
            "symbol": "A",
            "response_format": "csv",
            "timeframe": "1d",
            "start_ms": 1,
            "end_ms": None,
        },
        {"endpoint": "coverage", "symbol": "A", "response_format": "xml"},
    ],
)
def test_request_rejects_every_malformed_contract(values: dict[str, object]) -> None:
    with pytest.raises(DataError):
        QuantPadArchiveRequestV1(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 2, "endpoint": "coverage", "symbol": "A", "response_format": "json"},
        {"schema_version": 1, "endpoint": "coverage", "symbol": "A", "not_a_field": 1},
    ],
)
def test_from_dict_rejects_a_foreign_payload(payload: dict[str, object]) -> None:
    with pytest.raises(DataError):
        QuantPadArchiveRequestV1.from_dict(payload)


def test_store_requires_a_configured_volume_uuid(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="volume UUID"):
        QuantPadArchiveStore(bulk_root=tmp_path, manifest_root=tmp_path, expected_volume_uuid="   ")


def test_store_reads_real_free_space_when_no_capacity_probe_is_injected(tmp_path: Path) -> None:
    """The default probe is the one that runs in production; exercise it, not the double."""
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    store = QuantPadArchiveStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        reserve_fraction=0.0,
        minimum_free_bytes=1,
    )
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    assert store.publish(request, [b"{}"])["artifact_bytes"] == 2


def test_publish_fails_closed_when_the_volume_is_absent_or_too_full(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    missing = QuantPadArchiveStore(
        bulk_root=tmp_path / "never-mounted",
        manifest_root=tmp_path / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=10, free_bytes=10),
    )
    with pytest.raises(DataError, match="not mounted"):
        missing.publish(request, [b"{}"])

    bulk = tmp_path / "bulk"
    bulk.mkdir()
    full = QuantPadArchiveStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=1_000, free_bytes=10),
        minimum_free_bytes=100,
    )
    with pytest.raises(DataError, match="free-space reserve"):
        full.publish(request, [b"{}"])


def test_publish_rejects_a_symlinked_staging_directory(tmp_path: Path) -> None:
    store = _store(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    staging = store.bulk_root / "staging"
    staging.mkdir(parents=True)
    (staging / "quantpad").symlink_to(elsewhere, target_is_directory=True)
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    with pytest.raises(DataError, match="staging path is unsafe"):
        store.publish(request, [b"{}"])


@pytest.mark.parametrize("chunks", [[b"ok", ""], [b"ok", b""], []])
def test_publish_rejects_an_invalid_or_empty_stream(tmp_path: Path, chunks: list[object]) -> None:
    store = _store(tmp_path)
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    with pytest.raises(DataError):
        store.publish(request, chunks)  # type: ignore[arg-type]
    staging = store.bulk_root / "staging" / "quantpad"
    assert not list(staging.glob("*.part")), "a rejected stream must leave no partial file"


def test_publish_detects_a_tampered_artifact_or_manifest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    manifest = store.publish(request, [b"{}"])

    artifact = store.bulk_root / str(manifest["artifact_key"])
    artifact.write_bytes(b"[]")  # same length, different bytes
    with pytest.raises(DataError, match="external artifact identity collision"):
        store.publish(request, [b"{}"])

    artifact.write_bytes(b"{}")
    record = store.manifest_root / f"{manifest['manifest_id']}.json"
    record.write_text(record.read_text().replace('"research_only": true', '"research_only": 1'))
    with pytest.raises(DataError, match="internal manifest identity collision"):
        store.publish(request, [b"{}"])


def test_verify_rejects_a_missing_renamed_or_unsafe_manifest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    manifest = store.publish(request, [b"{}"])
    manifest_id = str(manifest["manifest_id"])

    with pytest.raises(DataError, match="unavailable or corrupt"):
        store.verify("0" * 64)

    (store.manifest_root / "renamed.json").write_text(
        (store.manifest_root / f"{manifest_id}.json").read_text()
    )
    with pytest.raises(DataError, match="identity is invalid"):
        store.verify("renamed")

    body = json.loads((store.manifest_root / f"{manifest_id}.json").read_text())
    body["artifact_key"] = "../escape.json"
    (store.manifest_root / f"{manifest_id}.json").write_text(json.dumps(body))
    with pytest.raises(DataError, match="integrity failure"):
        store.verify(manifest_id)


def test_verify_rejects_an_artifact_key_that_escapes_the_volume(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    manifest = dict(store.publish(request, [b"{}"]))
    body = {k: v for k, v in manifest.items() if k != "manifest_id"}
    body["artifact_key"] = "/etc/passwd"
    import hashlib as _h

    forged = _h.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    (store.manifest_root / f"{forged}.json").write_text(json.dumps({**body, "manifest_id": forged}))
    with pytest.raises(DataError, match="artifact key is invalid"):
        store.verify(forged)


def test_find_request_is_none_when_nothing_matches_and_loud_when_corrupt(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.find_request("no-such-request") is None  # manifest root does not exist yet
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    store.publish(request, [b"{}"])
    assert store.find_request("no-such-request") is None
    (store.manifest_root / "junk.json").write_text("not json")
    with pytest.raises(DataError, match="unavailable or corrupt"):
        store.find_request("no-such-request")


def test_fetch_requires_an_injected_key(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    with pytest.raises(DataError, match="Keychain injection"):
        fetch_quantpad_archive(_store(tmp_path), request, api_key="")


def test_fetch_builds_the_documented_query_for_every_endpoint(tmp_path: Path) -> None:
    seen: list[str] = []

    def opener(wire_request: object, *, timeout: int) -> io.BytesIO:
        assert isinstance(wire_request, urllib.request.Request)
        seen.append(wire_request.full_url)
        fmt = "arrow" if "format=arrow" in wire_request.full_url else "json"
        content_type = (
            "application/vnd.apache.arrow.stream" if fmt == "arrow" else "application/json"
        )
        return _response(b"payload", content_type=content_type, url=wire_request.full_url)

    for request in (
        QuantPadArchiveRequestV1(
            endpoint="universe",
            symbol="ES",
            response_format="json",
            asset_class="futures",
            limit=50,
        ),
        QuantPadArchiveRequestV1(
            endpoint="bars",
            symbol="ES.c.0",
            response_format="arrow",
            timeframe="1d",
            compression="zstd",
            roll_adjust="back",
            start_ms=1,
            end_ms=2,
        ),
        QuantPadArchiveRequestV1(
            endpoint="ticks",
            symbol="ES.c.0",
            response_format="arrow",
            schema="mbp-1",
            start_ms=1,
            end_ms=2,
        ),
    ):
        fetch_quantpad_archive(_store(tmp_path), request, api_key="k", opener=opener)

    universe, bars, ticks = seen
    assert "q=ES" in universe and "limit=50" in universe and "asset_class=futures" in universe
    assert "timeframe=1d" in bars and "roll_adjust=back" in bars and "compression=zstd" in bars
    assert "schema=mbp-1" in ticks and "roll_adjust" not in ticks


def test_fetch_rejects_a_mime_that_contradicts_the_requested_format(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(
        endpoint="bars",
        symbol="A",
        response_format="csv",
        timeframe="1d",
        start_ms=1,
        end_ms=2,
    )
    with pytest.raises(DataError, match="MIME does not match"):
        fetch_quantpad_archive(
            _store(tmp_path),
            request,
            api_key="k",
            opener=lambda *_a, **_k: _response(b"a,b", content_type="application/json"),
        )


def test_fetch_does_not_retry_a_client_rejection(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    calls = 0

    def opener(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            "https://api.quantpad.ai/v1/coverage", 404, "missing", _headers({}), None
        )

    with pytest.raises(DataError, match="was rejected"):
        fetch_quantpad_archive(_store(tmp_path), request, api_key="k", opener=opener)
    assert calls == 1, "a 404 is final; retrying it just burns quota"


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.HTTPError(
            "https://api.quantpad.ai/v1/coverage", 503, "down", _headers({}), None
        ),
        TimeoutError("network timeout"),
    ],
)
def test_fetch_gives_up_after_three_transient_failures(tmp_path: Path, failure: Exception) -> None:
    calls = 0

    def opener(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise failure

    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    with pytest.raises(DataError, match="retry the bounded request"):
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="k", opener=opener, sleep=lambda _: None
        )
    assert calls == 3


def test_fetch_falls_back_when_retry_after_is_not_a_number(tmp_path: Path) -> None:
    sleeps: list[float] = []
    calls = 0

    def opener(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                "https://api.quantpad.ai/v1/coverage",
                429,
                "slow down",
                _headers({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
                None,
            )
        return _response(b"{}")

    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="A", response_format="json")
    fetch_quantpad_archive(
        _store(tmp_path), request, api_key="k", opener=opener, sleep=sleeps.append
    )
    assert sleeps == [1.0], "an unparseable Retry-After must fall back to the bounded default"


def _response_class(headers: dict[str, str]) -> type[io.BytesIO]:
    class Response(io.BytesIO):
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

        def geturl(self) -> str:
            return "https://api.quantpad.ai/v1/coverage?symbol=AAPL"

    Response.headers = headers  # type: ignore[attr-defined]
    return Response


def test_truncated_stream_fails_loud_after_bounded_retries(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
    Response = _response_class({"Content-Type": "application/json", "Content-Length": "5"})
    calls = 0
    sleeps: list[float] = []

    def opener(*_args: object, **_kwargs: object) -> io.BytesIO:
        nonlocal calls
        calls += 1
        return Response(b"{}")  # 2 bytes delivered, 5 declared

    with pytest.raises(DataError, match="truncated: expected 5 bytes, got 2"):
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="secret", opener=opener, sleep=sleeps.append
        )
    assert calls == 3
    assert sleeps == [1.0, 2.0]
    assert _store(tmp_path).find_request(request.request_id) is None


def test_over_long_stream_fails_loud(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
    Response = _response_class({"Content-Type": "application/json", "Content-Length": "1"})

    def opener(*_args: object, **_kwargs: object) -> io.BytesIO:
        return Response(b"{}")

    with pytest.raises(DataError, match="longer than declared"):
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="secret", opener=opener, sleep=lambda _: None
        )


def test_truncated_stream_recovers_on_retry(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
    Short = _response_class({"Content-Type": "application/json", "Content-Length": "5"})
    Good = _response_class({"Content-Type": "application/json", "Content-Length": "2"})
    calls = 0

    def opener(*_args: object, **_kwargs: object) -> io.BytesIO:
        nonlocal calls
        calls += 1
        return Short(b"{}") if calls == 1 else Good(b"{}")

    result = fetch_quantpad_archive(
        _store(tmp_path), request, api_key="secret", opener=opener, sleep=lambda _: None
    )
    assert calls == 2
    assert result["artifact_bytes"] == 2


def test_server_error_reason_is_surfaced(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")

    def opener(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            "https://api.quantpad.ai/v1/coverage?symbol=AAPL",
            503,
            "unavailable",
            _headers({}),
            io.BytesIO(b'{"error": "quota exhausted"}'),
        )

    with pytest.raises(DataError, match=r"reason: quota exhausted"):
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="secret", opener=opener, sleep=lambda _: None
        )


def test_unparsable_content_length_fails_loud(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
    Response = _response_class({"Content-Type": "application/json", "Content-Length": "abc"})

    def opener(*_args: object, **_kwargs: object) -> io.BytesIO:
        return Response(b"{}")

    with pytest.raises(DataError, match="unparsable Content-Length"):
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="secret", opener=opener, sleep=lambda _: None
        )
    assert _store(tmp_path).find_request(request.request_id) is None


def test_http_error_message_never_echoes_response_body(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")

    def opener(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            "https://api.quantpad.ai/v1/coverage?symbol=AAPL",
            429,
            "slow down",
            _headers({}),
            io.BytesIO(b'{"error": "X-API-Key sk-secret-value rejected by the gateway"}'),
        )

    with pytest.raises(DataError) as failure:
        fetch_quantpad_archive(
            _store(tmp_path),
            request,
            api_key="sk-secret-value",
            opener=opener,
            sleep=lambda _: None,
        )
    assert "sk-secret-value" not in str(failure.value)
