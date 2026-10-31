"""Reopen the existing bulk store from explicit operator storage configuration.

No storage is provisioned and no durability is inferred. A retained config under
control-root/crypto/storage-config.json lets a sanitized supervisor reopen the same
root without copying environment variables or credentials into a research request.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.crypto.root_identity import CloudBulkRootIdentityV1
from alpha_data.crypto.storage import CryptoBulkStore

_SCHEMA = "CryptoBulkStorageConfigV1"


def _configuration_path(root: Path) -> Path:
    path = root.absolute() / "crypto" / "storage-config.json"
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if current.is_symlink():
            raise DataError("crypto bulk storage configuration path is unsafe")
    return path


def _read_config(root: Path) -> dict[str, object] | None:
    path = _configuration_path(root)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 8192:
        raise DataError("crypto bulk storage configuration is invalid or oversized")
    try:
        with path.open("rb") as stream:
            raw = stream.read(8193)
        if len(raw) > 8192:
            raise DataError("crypto bulk storage configuration is oversized")
        value = json.loads(raw)
    except (OSError, ValueError) as error:
        raise DataError("crypto bulk storage configuration is unreadable") from error
    if not isinstance(value, dict):
        raise DataError("crypto bulk storage configuration must be an object")
    return value


def _text(config: dict[str, object], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"crypto bulk storage configuration requires {key}")
    return value


def _integer(config: dict[str, object], key: str) -> int:
    value = config.get(key)
    if type(value) is not int or value < 0:
        raise DataError(f"crypto bulk storage configuration requires nonnegative integer {key}")
    return value


def _from_config(root: Path, config: dict[str, object]) -> CryptoBulkStore:
    if config.get("schema") != _SCHEMA:
        raise DataError("crypto bulk storage configuration schema is unsupported")
    backend = config.get("backend")
    common = {"schema", "backend", "bulk_root"}
    bulk = Path(_text(config, "bulk_root"))
    if backend == "macos_volume_uuid":
        if set(config) != common | {"volume_uuid"}:
            raise DataError("crypto bulk storage configuration fields differ")
        return CryptoBulkStore(
            bulk_root=bulk,
            manifest_root=root / "crypto" / "manifests",
            expected_volume_uuid=_text(config, "volume_uuid"),
        )
    if backend != "cloud_root_identity" or set(config) != common | {
        "control_root",
        "mount_point",
        "device_id",
        "owner_uid",
        "filesystem_type",
        "mount_source",
        "durable_hosting_reference",
    }:
        raise DataError("crypto bulk storage configuration backend/fields differ")
    identity = CloudBulkRootIdentityV1(
        root=bulk,
        mount_point=Path(_text(config, "mount_point")),
        device_id=_integer(config, "device_id"),
        owner_uid=_integer(config, "owner_uid"),
        filesystem_type=_text(config, "filesystem_type"),
        mount_source=_text(config, "mount_source"),
        durable_hosting_reference=_text(config, "durable_hosting_reference"),
    )
    control_root = Path(_text(config, "control_root"))
    try:
        selected_control = root.resolve(strict=True)
    except OSError as error:
        raise DataError("cloud control_root is unavailable") from error
    if control_root != selected_control:
        raise DataError("configured cloud control_root differs from selected canonical data_dir")
    # First portable slice requires the ledger/manifests and public payloads to
    # share one operator-approved durable mount/device/owner. Never certify a
    # disposable control directory merely because the bulk bytes are durable.
    try:
        replace(identity, root=control_root).verify(control_root)
    except (DataError, OSError) as error:
        raise DataError(
            "cloud control_root requires the same approved durable mount/device/owner as bulk: "
            + str(error)
        ) from error
    return CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=root / "crypto" / "manifests",
        cloud_root_identity=identity,
    )


def configured_crypto_bulk_store(
    settings_or_root: AlphaSettings | Path | None = None,
) -> CryptoBulkStore:
    """Construct one configured existing store; no mkdir, mount, or auto-configuration.

    A Path selects only its retained operator config. AlphaSettings uses explicit
    settings, falling back to that file only when no backend identity is configured.
    Conflicting environment and retained configuration fail rather than choose silently.
    """
    if isinstance(settings_or_root, Path):
        root_config = _read_config(settings_or_root)
        if root_config is None:
            raise DataError("crypto bulk storage has no retained operator root configuration")
        return _from_config(settings_or_root, root_config)
    settings = settings_or_root if settings_or_root is not None else AlphaSettings()
    cloud_values = {
        "mount_point": settings.bulk_cloud_mount_point,
        "device_id": settings.bulk_cloud_device_id,
        "owner_uid": settings.bulk_cloud_owner_uid,
        "filesystem_type": settings.bulk_cloud_filesystem_type,
        "mount_source": settings.bulk_cloud_mount_source,
        "durable_hosting_reference": settings.bulk_cloud_durability_reference,
    }
    retained = _read_config(settings.data_dir)
    explicit = (
        settings.bulk_volume_uuid is not None
        or settings.bulk_storage_backend != "macos_volume_uuid"
        or any(value is not None for value in cloud_values.values())
    )
    if not explicit:
        if retained is None:
            raise DataError(
                "crypto bulk volume UUID or explicit cloud root identity is not configured"
            )
        return _from_config(settings.data_dir, retained)
    config: dict[str, object] = {
        "schema": _SCHEMA,
        "backend": settings.bulk_storage_backend,
        "bulk_root": str(settings.bulk_data_dir),
    }
    if settings.bulk_storage_backend == "macos_volume_uuid":
        if any(value is not None for value in cloud_values.values()):
            raise DataError("Mac bulk storage cannot also configure cloud identity fields")
        config["volume_uuid"] = settings.bulk_volume_uuid
    else:
        if settings.bulk_volume_uuid is not None:
            raise DataError("cloud bulk storage cannot also configure a Mac UUID")
        config.update(
            {
                key: str(value) if isinstance(value, Path) else value
                for key, value in cloud_values.items()
            }
        )
        config["control_root"] = str(settings.data_dir.resolve())
    if retained is not None and retained != config:
        raise DataError("explicit and retained crypto bulk storage configurations conflict")
    return _from_config(settings.data_dir, config)
