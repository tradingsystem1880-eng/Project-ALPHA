"""Fail-closed external public-bulk storage with internal completion manifests."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from alpha_core import DataError

from .contracts import (
    CryptoAcquisitionScopeV1,
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
)

_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class Capacity:
    total_bytes: int
    free_bytes: int


@dataclass(frozen=True)
class StagingHandle:
    staging_id: str
    provider: str
    receipt_id: str
    logical_name: str
    expected_bytes: int
    bytes_written: int


def _disk_capacity(path: Path) -> Capacity:
    usage = shutil.disk_usage(path)
    return Capacity(total_bytes=usage.total, free_bytes=usage.free)


def _containing_mount_point(path: Path) -> Path:
    candidate = path.resolve(strict=True)
    while not os.path.ismount(candidate):
        parent = candidate.parent
        if parent == candidate:
            raise DataError("unable to resolve crypto bulk volume mount point")
        candidate = parent
    return candidate


def macos_volume_uuid(path: Path) -> str:
    """Read a mounted volume UUID without parsing localized human output."""
    try:
        mount_point = _containing_mount_point(path)
        completed = subprocess.run(
            ["diskutil", "info", "-plist", str(mount_point)],
            check=True,
            capture_output=True,
            timeout=10,
        )
        raw = plistlib.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException) as exc:
        raise DataError("unable to verify bulk volume UUID") from exc
    value = raw.get("VolumeUUID") if isinstance(raw, dict) else None
    if not isinstance(value, str) or not value:
        raise DataError("bulk volume has no stable UUID")
    return value.upper()


def _safe_component(value: str, label: str) -> str:
    if not isinstance(value, str) or _SAFE.fullmatch(value) is None or value in {".", ".."}:
        raise DataError(f"invalid crypto storage {label}")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class CryptoBulkStore:
    """Coordinate external content publication and internal immutable manifests."""

    def __init__(
        self,
        *,
        bulk_root: Path,
        manifest_root: Path,
        expected_volume_uuid: str,
        volume_uuid: Callable[[Path], str] = macos_volume_uuid,
        capacity: Callable[[Path], Capacity] = _disk_capacity,
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
        if not 0 <= reserve_fraction < 1:
            raise DataError("bulk reserve fraction must be between zero and one")
        if minimum_free_bytes < 0:
            raise DataError("bulk minimum free bytes must be non-negative")

    @property
    def staging_root(self) -> Path:
        return self.bulk_root / "staging"

    def verify_ready(self, *, required_bytes: int) -> Capacity:
        if (
            not isinstance(required_bytes, int)
            or isinstance(required_bytes, bool)
            or required_bytes < 0
        ):
            raise DataError("required bulk bytes must be a non-negative integer")
        if not self.bulk_root.is_dir() or self.bulk_root.is_symlink():
            raise DataError("configured crypto bulk volume is not mounted")
        actual = self._volume_uuid(self.bulk_root).strip().upper()
        if actual != self.expected_volume_uuid:
            raise DataError("configured crypto bulk volume UUID does not match")
        capacity = self._capacity(self.bulk_root)
        reserve = max(int(capacity.total_bytes * self.reserve_fraction), self.minimum_free_bytes)
        if capacity.free_bytes - required_bytes < reserve:
            raise DataError("crypto bulk acquisition would violate the free-space reserve")
        try:
            with tempfile.NamedTemporaryFile(dir=self.bulk_root, prefix=".alpha-write-probe-"):
                pass
        except OSError as exc:
            raise DataError("configured crypto bulk volume is not writable") from exc
        return capacity

    def begin_staging(
        self, *, provider: str, receipt_id: str, logical_name: str, expected_bytes: int
    ) -> StagingHandle:
        self.verify_ready(required_bytes=expected_bytes)
        provider = _safe_component(provider, "provider")
        receipt_id = _safe_component(receipt_id, "receipt id")
        logical_name = _safe_component(logical_name, "logical name")
        seed = _canonical(
            {
                "provider": provider,
                "receipt_id": receipt_id,
                "logical_name": logical_name,
                "expected_bytes": expected_bytes,
            }
        )
        staging_id = hashlib.sha256(seed).hexdigest()
        root = self.staging_root / staging_id
        metadata = root / "staging.json"
        payload = root / "payload.part"
        expected = {
            "schema_version": 1,
            "staging_id": staging_id,
            "provider": provider,
            "receipt_id": receipt_id,
            "logical_name": logical_name,
            "expected_bytes": expected_bytes,
        }
        root.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(expected, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if metadata.exists() and metadata.read_text(encoding="utf-8") != rendered:
            raise DataError("crypto staging identity collision")
        if not metadata.exists():
            temporary = root / "staging.json.tmp"
            temporary.write_text(rendered, encoding="utf-8")
            os.replace(temporary, metadata)
        payload.touch(exist_ok=True)
        return self.resume_staging(staging_id)

    def _staging_path(self, staging_id: str) -> Path:
        return self.staging_root / _safe_component(staging_id, "staging id")

    def resume_staging(self, staging_id: str) -> StagingHandle:
        root = self._staging_path(staging_id)
        try:
            raw = json.loads((root / "staging.json").read_text(encoding="utf-8"))
            size = (root / "payload.part").stat().st_size
        except (OSError, json.JSONDecodeError) as exc:
            raise DataError("crypto staging metadata is unavailable or corrupt") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise DataError("crypto staging metadata has an unsupported schema")
        try:
            handle = StagingHandle(
                staging_id=raw["staging_id"],
                provider=raw["provider"],
                receipt_id=raw["receipt_id"],
                logical_name=raw["logical_name"],
                expected_bytes=raw["expected_bytes"],
                bytes_written=size,
            )
        except (KeyError, TypeError) as exc:
            raise DataError("crypto staging metadata is invalid") from exc
        expected_id = hashlib.sha256(
            _canonical(
                {
                    "provider": handle.provider,
                    "receipt_id": handle.receipt_id,
                    "logical_name": handle.logical_name,
                    "expected_bytes": handle.expected_bytes,
                }
            )
        ).hexdigest()
        if handle.staging_id != staging_id or expected_id != staging_id:
            raise DataError("crypto staging metadata identity does not match")
        if (
            not isinstance(handle.expected_bytes, int)
            or isinstance(handle.expected_bytes, bool)
            or handle.expected_bytes < 0
            or size > handle.expected_bytes
        ):
            raise DataError("crypto staging bytes do not match the bounded contract")
        return handle

    def append_staging(self, handle: StagingHandle, data: bytes) -> StagingHandle:
        current = self.resume_staging(handle.staging_id)
        if current != handle:
            raise DataError("crypto staging offset is stale; resume before appending")
        if not isinstance(data, bytes) or not data:
            raise DataError("crypto staging append requires non-empty bytes")
        if current.bytes_written + len(data) > current.expected_bytes:
            raise DataError("crypto staging append exceeds expected bytes")
        with (self._staging_path(handle.staging_id) / "payload.part").open("ab") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return self.resume_staging(handle.staging_id)

    def resume_payload(self, handle: StagingHandle, payload: bytes) -> StagingHandle:
        """Resume from an exact verified prefix; never splice different provider bytes."""
        current = self.resume_staging(handle.staging_id)
        if current != handle:
            raise DataError("crypto staging offset is stale; resume before appending")
        if not isinstance(payload, bytes) or len(payload) != current.expected_bytes:
            raise DataError("crypto resumed payload does not match the bounded byte count")
        staged = (self._staging_path(handle.staging_id) / "payload.part").read_bytes()
        if payload[: current.bytes_written] != staged:
            raise DataError("crypto resumed payload prefix does not match staged bytes")
        if current.bytes_written == current.expected_bytes:
            return current
        return self.append_staging(current, payload[current.bytes_written :])

    def publish_staging(
        self,
        handle: StagingHandle,
        *,
        expected_sha256: str,
        receipt: CryptoRawReceiptV1 | None = None,
    ) -> dict[str, object]:
        current = self.resume_staging(handle.staging_id)
        if current.bytes_written != current.expected_bytes:
            raise DataError("crypto staging payload is incomplete")
        source = self._staging_path(handle.staging_id) / "payload.part"
        actual_hash = _sha256(source)
        if actual_hash != expected_sha256:
            raise DataError("crypto staging payload hash does not match")
        artifact_key = f"raw/{current.provider}/{current.receipt_id}/{current.logical_name}"
        destination = self.bulk_root / artifact_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if _sha256(destination) != actual_hash:
                raise DataError("crypto external artifact identity collision")
        else:
            temporary = destination.with_name(f".{destination.name}.{current.staging_id}.tmp")
            try:
                os.link(source, temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        body = {
            "schema_version": 1,
            "artifact_kind": "raw",
            "artifact_key": artifact_key,
            "artifact_sha256": actual_hash,
            "artifact_bytes": current.expected_bytes,
            "provider": current.provider,
            "receipt_id": current.receipt_id,
        }
        if receipt is not None:
            if (
                receipt.receipt_id != current.receipt_id
                or receipt.dataset.provider != current.provider
                or receipt.response_sha256 != actual_hash
                or receipt.response_bytes != current.expected_bytes
            ):
                raise DataError("crypto raw receipt does not match staged provider bytes")
            body["receipt"] = receipt.to_dict()
        manifest = self._publish_manifest(body)
        shutil.rmtree(self._staging_path(handle.staging_id))
        return manifest

    def _publish_manifest(self, body: dict[str, object]) -> dict[str, object]:
        manifest_id = hashlib.sha256(_canonical(body)).hexdigest()
        manifest = {**body, "manifest_id": manifest_id}
        try:
            self.manifest_root.mkdir(parents=True, exist_ok=True)
            manifest_path = self.manifest_root / f"{manifest_id}.json"
            rendered = json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n"
            if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != rendered:
                raise DataError("crypto internal manifest identity collision")
            if not manifest_path.exists():
                temporary = manifest_path.with_suffix(".json.tmp")
                temporary.write_text(rendered, encoding="utf-8")
                os.replace(temporary, manifest_path)
        except OSError as exc:
            raise DataError("crypto internal manifest publication failed") from exc
        return manifest

    def publish_normalized(
        self,
        payload: bytes,
        *,
        dataset: CryptoDatasetIdentityV1,
        input_manifest_ids: tuple[str, ...],
        quality: CryptoQualityReportV1,
        acquisition_scope: CryptoAcquisitionScopeV1 | None = None,
    ) -> dict[str, object]:
        """Publish exact normalized bytes only after every raw input re-verifies."""
        if not isinstance(payload, bytes) or not payload:
            raise DataError("crypto normalized publication requires non-empty bytes")
        if dataset.family in {"derivative_trades", "derivative_book_snapshots"}:
            if acquisition_scope is None:
                raise DataError("high-frequency derivative capture requires a research-case scope")
        elif acquisition_scope is not None:
            raise DataError("research-case acquisition scope is limited to derivative event data")
        artifact_hash = hashlib.sha256(payload).hexdigest()
        if quality.dataset_sha256 != artifact_hash:
            raise DataError("crypto normalized bytes do not match the quality report")
        if not input_manifest_ids or len(set(input_manifest_ids)) != len(input_manifest_ids):
            raise DataError("crypto normalized publication requires unique raw input manifests")
        for manifest_id in input_manifest_ids:
            try:
                raw_manifest = self.verify_manifest(manifest_id)
            except DataError as exc:
                raise DataError("crypto normalized raw input manifest failed verification") from exc
            artifact_kind = raw_manifest.get("artifact_kind")
            artifact_key = raw_manifest.get("artifact_key")
            if artifact_kind != "raw" and not (
                artifact_kind is None
                and isinstance(artifact_key, str)
                and artifact_key.startswith("raw/")
            ):
                raise DataError("crypto normalized input manifest is not raw provider data")
        self.verify_ready(required_bytes=len(payload))
        artifact_key = (
            f"normalized/{dataset.family}/{dataset.content_sha256}/{artifact_hash}.parquet"
        )
        destination = self.bulk_root / artifact_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.stat().st_size != len(payload) or _sha256(destination) != artifact_hash:
                raise DataError("crypto normalized artifact identity collision")
        else:
            temporary = destination.with_name(f".{destination.name}.tmp")
            try:
                with temporary.open("wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        body: dict[str, object] = {
            "schema_version": 1,
            "artifact_kind": "normalized",
            "artifact_key": artifact_key,
            "artifact_sha256": artifact_hash,
            "artifact_bytes": len(payload),
            "provider": dataset.provider,
            "dataset": dataset.to_dict(),
            "input_manifest_ids": list(input_manifest_ids),
            "quality": quality.to_dict(),
        }
        if acquisition_scope is not None:
            body["acquisition_scope"] = acquisition_scope.to_dict()
        return self._publish_manifest(body)

    def verify_manifest(self, manifest_id: object) -> dict[str, object]:
        if not isinstance(manifest_id, str):
            raise DataError("invalid crypto manifest id")
        _safe_component(manifest_id, "manifest id")
        path = self.manifest_root / f"{manifest_id}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DataError("crypto manifest is unavailable or corrupt") from exc
        if not isinstance(raw, dict) or raw.get("manifest_id") != manifest_id:
            raise DataError("crypto manifest identity is invalid")
        body = {key: value for key, value in raw.items() if key != "manifest_id"}
        if hashlib.sha256(_canonical(body)).hexdigest() != manifest_id:
            raise DataError("crypto manifest integrity failure")
        artifact_key = raw.get("artifact_key")
        artifact_hash = raw.get("artifact_sha256")
        artifact_bytes = raw.get("artifact_bytes")
        if (
            not isinstance(artifact_key, str)
            or artifact_key.startswith("/")
            or ".." in artifact_key.split("/")
        ):
            raise DataError("crypto manifest artifact key is invalid")
        artifact = self.bulk_root / artifact_key
        if (
            not artifact.is_file()
            or not isinstance(artifact_hash, str)
            or not isinstance(artifact_bytes, int)
            or isinstance(artifact_bytes, bool)
            or artifact.stat().st_size != artifact_bytes
            or _sha256(artifact) != artifact_hash
        ):
            raise DataError("crypto external artifact integrity failure")
        return raw

    def inventory(self) -> tuple[dict[str, object], ...]:
        if not self.manifest_root.exists():
            return ()
        return tuple(
            self.verify_manifest(path.stem) for path in sorted(self.manifest_root.glob("*.json"))
        )

    def clean_cache(self) -> int:
        """Delete only the explicitly disposable cache tree and return removed bytes."""
        total = self.cache_size()
        cache = self.bulk_root / "cache"
        if not cache.exists():
            return 0
        shutil.rmtree(cache)
        return total

    def cache_size(self) -> int:
        """Return removable cache bytes without touching immutable or staged data."""
        cache = self.bulk_root / "cache"
        if not cache.exists():
            return 0
        return sum(path.stat().st_size for path in cache.rglob("*") if path.is_file())
