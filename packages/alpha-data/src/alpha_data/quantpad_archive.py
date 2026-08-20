"""Owner-authorized, research-only archive of exact QuantPad REST responses.

The external artifact is published before its internal manifest.  Credentials are
transport inputs only and can never enter either identity.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from alpha_core import DataError
from alpha_data.crypto.contracts import canonical_bytes
from alpha_data.crypto.storage import Capacity, macos_volume_uuid, sha256_file

_SYMBOL: Final = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
_ENDPOINTS: Final = frozenset({"bars", "ticks", "coverage", "universe"})
_TICK_SCHEMAS: Final = frozenset(
    {
        "trades",
        "mbp-1",
        "mbp-10",
        "cmbp-1",
        "tcbbo",
        "cbbo-1s",
        "cbbo-1m",
        "definition",
        "statistics",
        "status",
    }
)
_BASE_URL: Final = "https://api.quantpad.ai"


class _TruncatedStream(DataError):
    """Body length disagreed with ``Content-Length``; a bounded retry is allowed."""


_SAFE_REASON: Final = re.compile(r"^[A-Za-z0-9 ._-]{1,80}$")


def _http_error_reason(exc: urllib.error.HTTPError, api_key: str) -> str:
    """A short allowlisted provider reason, else the status; the body is never echoed."""
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except OSError as error:
        raise DataError(
            f"QuantPad archive error body could not be read (status: {exc.code})"
        ) from error
    try:
        payload = json.loads(body)
    except ValueError:
        return str(exc.code)
    if isinstance(payload, dict):
        reason = payload.get("error")
        if isinstance(reason, str) and _SAFE_REASON.match(reason) and api_key not in reason:
            return reason
    return str(exc.code)


def _capacity(path: Path) -> Capacity:
    usage = shutil.disk_usage(path)
    return Capacity(total_bytes=usage.total, free_bytes=usage.free)


@dataclass(frozen=True)
class QuantPadArchiveRequestV1:
    endpoint: str
    symbol: str
    response_format: str
    start_ms: int | None = None
    end_ms: int | None = None
    timeframe: str | None = None
    schema: str | None = None
    compression: str = "none"
    roll_adjust: str = "none"
    asset_class: str | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.endpoint not in _ENDPOINTS or _SYMBOL.fullmatch(self.symbol) is None:
            raise DataError("unsupported or unsafe QuantPad archive request")
        if self.response_format not in {"json", "csv", "arrow"}:
            raise DataError("unsupported QuantPad archive response format")
        if self.compression not in {"none", "zstd", "lz4"}:
            raise DataError("unsupported QuantPad archive compression")
        if self.roll_adjust not in {"none", "back", "ratio"}:
            raise DataError("unsupported QuantPad futures roll adjustment")
        if self.endpoint == "bars":
            if not self.timeframe or self.schema is not None or self.response_format == "json":
                raise DataError("QuantPad bars archive requires timeframe and Arrow or CSV")
        elif self.endpoint == "ticks":
            if self.schema not in _TICK_SCHEMAS or self.timeframe is not None:
                raise DataError("QuantPad ticks archive requires a supported schema")
            if self.response_format != "arrow":
                raise DataError("QuantPad ticks archive requires Arrow")
        elif self.endpoint == "universe":
            if (
                any(
                    value is not None
                    for value in (self.start_ms, self.end_ms, self.timeframe, self.schema)
                )
                or self.asset_class not in {"futures", "equity", "option", None}
                or self.limit != 50
                or (self.compression, self.roll_adjust) != ("none", "none")
            ):
                raise DataError(
                    "QuantPad universe archive requires a query, optional asset class, and limit 50"
                )
        elif any(
            value is not None for value in (self.start_ms, self.end_ms, self.timeframe, self.schema)
        ) or (self.compression, self.roll_adjust, self.asset_class, self.limit) != (
            "none",
            "none",
            None,
            None,
        ):
            raise DataError("QuantPad coverage archive accepts only a symbol")
        if self.endpoint not in {"coverage", "universe"} and (
            not isinstance(self.start_ms, int)
            or isinstance(self.start_ms, bool)
            or not isinstance(self.end_ms, int)
            or isinstance(self.end_ms, bool)
            or self.start_ms < 0
            or self.end_ms <= self.start_ms
        ):
            raise DataError("QuantPad archive requires an ordered epoch-ms interval")

    @property
    def request_id(self) -> str:
        return hashlib.sha256(canonical_bytes(self.to_dict())).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": 1, **asdict(self)}

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> QuantPadArchiveRequestV1:
        raw = dict(value)
        if raw.pop("schema_version", None) != 1:
            raise DataError("unsupported QuantPad archive request version")
        try:
            return cls(**raw)  # type: ignore[arg-type]
        except TypeError as exc:
            raise DataError("invalid QuantPad archive request") from exc


class QuantPadArchiveStore:
    """Publish exact public response bytes externally and receipts internally."""

    def __init__(
        self,
        *,
        bulk_root: Path,
        manifest_root: Path,
        expected_volume_uuid: str,
        volume_uuid: Callable[[Path], str] = macos_volume_uuid,
        capacity: Callable[[Path], Capacity] = _capacity,
        reserve_fraction: float = 0.15,
        minimum_free_bytes: int = 100_000_000_000,
    ) -> None:
        self.bulk_root = Path(bulk_root)
        self.manifest_root = Path(manifest_root)
        self.expected_volume_uuid = expected_volume_uuid.strip().upper()
        self._volume_uuid = volume_uuid
        self._capacity = capacity
        self.reserve_fraction = reserve_fraction
        self.minimum_free_bytes = minimum_free_bytes
        if not self.expected_volume_uuid:
            raise DataError("bulk volume UUID must be configured")

    def _verify_ready(self, required_bytes: int = 0) -> None:
        if not self.bulk_root.is_dir() or self.bulk_root.is_symlink():
            raise DataError("configured QuantPad bulk volume is not mounted")
        if self._volume_uuid(self.bulk_root).strip().upper() != self.expected_volume_uuid:
            raise DataError("configured QuantPad bulk volume UUID does not match")
        capacity = self._capacity(self.bulk_root)
        reserve = max(int(capacity.total_bytes * self.reserve_fraction), self.minimum_free_bytes)
        if capacity.free_bytes - required_bytes < reserve:
            raise DataError("QuantPad archive would violate the free-space reserve")

    def publish(
        self, request: QuantPadArchiveRequestV1, chunks: Iterable[bytes]
    ) -> dict[str, object]:
        self._verify_ready()
        staging = self.bulk_root / "staging" / "quantpad"
        staging.mkdir(parents=True, exist_ok=True)
        if staging.is_symlink():
            raise DataError("QuantPad staging path is unsafe")
        partial = staging / f"{request.request_id}.part"
        digest = hashlib.sha256()
        size = 0
        try:
            with partial.open("wb") as stream:
                for chunk in chunks:
                    if not isinstance(chunk, bytes) or not chunk:
                        raise DataError("QuantPad archive stream contains an invalid chunk")
                    self._verify_ready(len(chunk))
                    stream.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        if size == 0:
            partial.unlink(missing_ok=True)
            raise DataError("QuantPad archive response is empty")
        response_hash = digest.hexdigest()
        suffix = {"json": "json", "csv": "csv", "arrow": "arrow"}[request.response_format]
        artifact_key = f"raw/quantpad/{request.request_id}/{response_hash}.{suffix}"
        artifact = self.bulk_root / artifact_key
        artifact.parent.mkdir(parents=True, exist_ok=True)
        if artifact.exists():
            if artifact.stat().st_size != size or sha256_file(artifact) != response_hash:
                raise DataError("QuantPad external artifact identity collision")
            partial.unlink(missing_ok=True)
        else:
            os.replace(partial, artifact)
        body: dict[str, object] = {
            "schema_version": 1,
            "artifact_kind": "quantpad_raw",
            "artifact_key": artifact_key,
            "artifact_sha256": response_hash,
            "artifact_bytes": size,
            "provider": "quantpad",
            "request": request.to_dict(),
            "request_id": request.request_id,
            "research_only": True,
        }
        manifest_id = hashlib.sha256(canonical_bytes(body)).hexdigest()
        manifest = {**body, "manifest_id": manifest_id}
        self.manifest_root.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n"
        path = self.manifest_root / f"{manifest_id}.json"
        if path.exists() and path.read_text(encoding="utf-8") != rendered:
            raise DataError("QuantPad internal manifest identity collision")
        if not path.exists():
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.manifest_root, delete=False
            ) as stream:
                stream.write(rendered)
                temporary = Path(stream.name)
            os.replace(temporary, path)
        return manifest

    def verify(self, manifest_id: str) -> dict[str, object]:
        try:
            raw = json.loads((self.manifest_root / f"{manifest_id}.json").read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise DataError("QuantPad archive manifest is unavailable or corrupt") from exc
        if not isinstance(raw, dict) or raw.get("manifest_id") != manifest_id:
            raise DataError("QuantPad archive manifest identity is invalid")
        body = {key: value for key, value in raw.items() if key != "manifest_id"}
        if hashlib.sha256(canonical_bytes(body)).hexdigest() != manifest_id:
            raise DataError("QuantPad archive manifest integrity failure")
        key = raw.get("artifact_key")
        if not isinstance(key, str) or key.startswith("/") or ".." in key.split("/"):
            raise DataError("QuantPad archive artifact key is invalid")
        artifact = self.bulk_root / key
        if (
            not artifact.is_file()
            or artifact.is_symlink()
            or artifact.stat().st_size != raw.get("artifact_bytes")
            or sha256_file(artifact) != raw.get("artifact_sha256")
        ):
            raise DataError("QuantPad external artifact integrity failure")
        return raw

    def find_request(self, request_id: str) -> dict[str, object] | None:
        """Return a verified completed request so interrupted plans resume without refetching."""
        if not self.manifest_root.exists():
            return None
        for path in sorted(self.manifest_root.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise DataError("QuantPad archive manifest is unavailable or corrupt") from exc
            if isinstance(raw, dict) and raw.get("request_id") == request_id:
                return self.verify(path.stem)
        return None


def fetch_quantpad_archive(
    store: QuantPadArchiveStore,
    request: QuantPadArchiveRequestV1,
    *,
    api_key: str,
    opener: Callable[..., object] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Stream one closed QuantPad request into immutable storage."""
    if not api_key:
        raise DataError("QuantPad archive requires scoped Keychain injection")
    existing = store.find_request(request.request_id)
    if existing is not None:
        return existing
    params: dict[str, object] = {"symbol": request.symbol}
    if request.endpoint == "universe":
        params = {"q": request.symbol, "limit": 50}
        if request.asset_class is not None:
            params["asset_class"] = request.asset_class
    if request.endpoint != "coverage":
        params.update({"start": request.start_ms, "end": request.end_ms})
    if request.timeframe is not None:
        params["timeframe"] = request.timeframe
    if request.schema is not None:
        params["schema"] = request.schema
    if request.endpoint in {"bars", "ticks"}:
        params["format"] = request.response_format
        params["compression"] = request.compression
    if request.endpoint == "bars":
        params["roll_adjust"] = request.roll_adjust
    url = f"{_BASE_URL}/v1/{request.endpoint}?{urllib.parse.urlencode(params)}"
    accept = {
        "json": "application/json",
        "csv": "text/csv",
        "arrow": "application/vnd.apache.arrow.stream, application/octet-stream",
    }[request.response_format]
    wire_request = urllib.request.Request(url, headers={"X-API-Key": api_key, "Accept": accept})
    for attempt in range(3):
        try:
            response = opener(wire_request, timeout=120)
            with response:  # type: ignore[attr-defined]
                final_url = response.geturl()  # type: ignore[attr-defined]
                parsed = urllib.parse.urlparse(final_url)
                if parsed.scheme != "https" or parsed.hostname != "api.quantpad.ai":
                    raise DataError("QuantPad archive redirect left the pinned HTTPS host")
                expected_bytes: int | None = None
                declared = response.headers.get("Content-Length")  # type: ignore[attr-defined]
                if declared is not None:
                    try:
                        expected_bytes = int(declared)
                    except (TypeError, ValueError) as error:
                        raise DataError(
                            "QuantPad archive declared an unparsable Content-Length"
                        ) from error
                content_type = (
                    str(response.headers.get("Content-Type", ""))  # type: ignore[attr-defined]
                    .split(";", 1)[0]
                    .lower()
                )
                allowed_types = {
                    "json": {"application/json"},
                    "csv": {"text/csv", "application/csv"},
                    "arrow": {"application/vnd.apache.arrow.stream", "application/octet-stream"},
                }[request.response_format]
                if content_type not in allowed_types:
                    raise DataError("QuantPad archive response MIME does not match the request")

                reader = response.read  # type: ignore[attr-defined]

                def chunks(
                    reader: Callable[[int], bytes] = reader,
                    expected_bytes: int | None = expected_bytes,
                ) -> Iterable[bytes]:
                    downloaded = 0
                    while chunk := reader(1024 * 1024):
                        downloaded += len(chunk)
                        if expected_bytes is not None and downloaded > expected_bytes:
                            raise _TruncatedStream(
                                "QuantPad archive stream is longer than declared bytes "
                                f"({downloaded} > {expected_bytes})"
                            )
                        yield chunk
                    if expected_bytes is not None and downloaded != expected_bytes:
                        raise _TruncatedStream(
                            "QuantPad archive stream is truncated: "
                            f"expected {expected_bytes} bytes, got {downloaded}"
                        )

                return store.publish(request, chunks())
        except _TruncatedStream:
            if attempt == 2:
                raise
            sleep(float(attempt + 1))
        except DataError:
            raise
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and not 500 <= exc.code < 600:
                raise DataError("QuantPad archive request was rejected") from exc
            if attempt == 2:
                raise DataError(
                    "QuantPad archive request failed; retry the bounded request "
                    f"(reason: {_http_error_reason(exc, api_key)})"
                ) from exc
            delay = float(attempt + 1)
            if exc.code == 429:
                with suppress(TypeError, ValueError):
                    delay = float(exc.headers.get("Retry-After", delay))
            sleep(min(max(delay, 1.0), 60.0))
        except (OSError, TimeoutError) as exc:
            if attempt == 2:
                raise DataError(
                    "QuantPad archive request failed; retry the bounded request"
                ) from exc
            sleep(float(attempt + 1))
    raise AssertionError("unreachable")


__all__ = ["QuantPadArchiveRequestV1", "QuantPadArchiveStore", "fetch_quantpad_archive"]
