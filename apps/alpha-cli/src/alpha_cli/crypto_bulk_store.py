"""Reopen the existing bulk store from explicit operator storage configuration.

No storage is provisioned and no durability is inferred. A retained config under
control-root/crypto/storage-config.json lets a sanitized supervisor reopen the same
root without copying environment variables or credentials into a research request.

An optional ``free_space_reserve`` object (schema ``OwnerStorageReserveV1``, ADR-0043) carries
the owner's explicit reserve for this root. Without it the ADR-0032 default applies unchanged,
so existing settings files keep their bytes, hash and meaning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.crypto.root_identity import CloudBulkRootIdentityV1
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

_SCHEMA = "CryptoBulkStorageConfigV1"
_RESERVE_KEY = "free_space_reserve"

# ADR-0032 default, applied whenever the owner has set nothing: the larger of 15% of the
# volume and 100 GB (CryptoBulkStore's own defaults). ADR-0043 lets the owner replace it per
# storage root with an explicit, attributed value, never below this hard floor.
DEFAULT_RESERVE_FRACTION = 0.15
DEFAULT_MINIMUM_FREE_BYTES = 100_000_000_000
RESERVE_FLOOR_BYTES = 10_000_000_000
OWNER_RESERVE_SCHEMA = "OwnerStorageReserveV1"
_OWNER_RESERVE_FIELDS = frozenset(
    {
        "schema",
        "minimum_free_bytes",
        "advisory_free_bytes",
        "decided_by",
        "decided_on",
        "decision_record",
    }
)


def _gigabytes(value: int) -> str:
    return f"{value / 1_000_000_000:.1f} GB"


@dataclass(frozen=True)
class OwnerStorageReserveV1:
    """An owner-supplied free-space reserve for one storage root (ADR-0043).

    This validates what the owner wrote into the retained storage settings. It never creates
    or implies an approval, and no value below ``RESERVE_FLOOR_BYTES`` is accepted.
    """

    minimum_free_bytes: int
    advisory_free_bytes: int
    decided_by: str
    decided_on: str
    decision_record: str

    def __post_init__(self) -> None:
        prefix = "crypto bulk storage configuration owner reserve"
        for name in ("minimum_free_bytes", "advisory_free_bytes"):
            value = getattr(self, name)
            if type(value) is not int or value < RESERVE_FLOOR_BYTES:
                raise DataError(
                    f"{prefix} {name} must be an integer of at least "
                    f"{RESERVE_FLOOR_BYTES} bytes (the hard floor)"
                )
        if self.advisory_free_bytes < self.minimum_free_bytes:
            raise DataError(f"{prefix} advisory threshold must not be below the reserve")
        for name in ("decided_by", "decided_on", "decision_record"):
            value = getattr(self, name)
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= 512:
                raise DataError(f"{prefix} requires {name}")
        try:
            date.fromisoformat(self.decided_on)
        except ValueError as error:
            raise DataError(f"{prefix} decided_on must be an ISO date") from error

    @classmethod
    def from_dict(cls, value: object) -> OwnerStorageReserveV1:
        if (
            not isinstance(value, dict)
            or set(value) != _OWNER_RESERVE_FIELDS
            or value.get("schema") != OWNER_RESERVE_SCHEMA
        ):
            raise DataError("crypto bulk storage configuration owner reserve fields differ")
        return cls(
            minimum_free_bytes=value["minimum_free_bytes"],
            advisory_free_bytes=value["advisory_free_bytes"],
            decided_by=value["decided_by"],
            decided_on=value["decided_on"],
            decision_record=value["decision_record"],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": OWNER_RESERVE_SCHEMA,
            "minimum_free_bytes": self.minimum_free_bytes,
            "advisory_free_bytes": self.advisory_free_bytes,
            "decided_by": self.decided_by,
            "decided_on": self.decided_on,
            "decision_record": self.decision_record,
        }


class ConfiguredCryptoBulkStore(CryptoBulkStore):
    """The existing store reopened from retained settings, with the reserve's provenance.

    Enforcement is unchanged: ``verify_ready`` still refuses before any write when free
    space minus the request would fall below the reserve; this only explains the refusal.
    """

    def __init__(
        self,
        *,
        bulk_root: Path,
        manifest_root: Path,
        owner_reserve: OwnerStorageReserveV1 | None,
        expected_volume_uuid: str | None = None,
        cloud_root_identity: CloudBulkRootIdentityV1 | None = None,
    ) -> None:
        # The owner's explicit value replaces the default formula exactly; otherwise the
        # ADR-0032 default is passed through unchanged.
        super().__init__(
            bulk_root=bulk_root,
            manifest_root=manifest_root,
            expected_volume_uuid=expected_volume_uuid,
            cloud_root_identity=cloud_root_identity,
            reserve_fraction=DEFAULT_RESERVE_FRACTION if owner_reserve is None else 0.0,
            minimum_free_bytes=(
                DEFAULT_MINIMUM_FREE_BYTES
                if owner_reserve is None
                else owner_reserve.minimum_free_bytes
            ),
        )
        self.owner_reserve = owner_reserve

    def reserve_bytes(self, capacity: Capacity) -> int:
        return max(int(capacity.total_bytes * self.reserve_fraction), self.minimum_free_bytes)

    def reserve_source(self) -> str:
        if self.owner_reserve is None:
            return "default reserve: the larger of 15% and 100 GB (ADR-0032)"
        reserve = self.owner_reserve
        return (
            f"owner-set reserve {_gigabytes(reserve.minimum_free_bytes)}, decided by "
            f"{reserve.decided_by} on {reserve.decided_on} ({reserve.decision_record})"
        )

    def low_space_advisory(self, capacity: Capacity) -> str | None:
        """Advisory only (never a refusal): free space is under the owner's threshold."""
        if self.owner_reserve is None:
            return None
        return low_space_advisory(
            capacity.free_bytes,
            reserve_bytes=self.reserve_bytes(capacity),
            advisory_bytes=self.owner_reserve.advisory_free_bytes,
        )

    def verify_ready(self, *, required_bytes: int) -> Capacity:
        try:
            return super().verify_ready(required_bytes=required_bytes)
        except DataError as error:
            if "free-space reserve" not in str(error):
                raise
            capacity = self._capacity(self.bulk_root)
            raise DataError(
                f"{error}: {_gigabytes(capacity.free_bytes)} free, "
                f"{_gigabytes(required_bytes)} requested, "
                f"{_gigabytes(self.reserve_bytes(capacity))} must stay free "
                f"({self.reserve_source()}). Refused before writing, so work cannot fail "
                "mid-run on a full disk; free disk space, or the owner may set a different "
                "reserve (ADR-0043)."
            ) from error


def low_space_advisory(free_bytes: int, *, reserve_bytes: int, advisory_bytes: int) -> str | None:
    """The shared low-space wording used by the storage command and the doctor."""
    if free_bytes >= advisory_bytes:
        return None
    return (
        f"LOW DISK SPACE: {_gigabytes(free_bytes)} free, below the owner's advisory threshold "
        f"of {_gigabytes(advisory_bytes)}. A data-storage write needing more than "
        f"{_gigabytes(max(free_bytes - reserve_bytes, 0))} is refused (reserve "
        f"{_gigabytes(reserve_bytes)}). Free disk space or revisit ADR-0043."
    )


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


def _from_config(root: Path, config: dict[str, object]) -> ConfiguredCryptoBulkStore:
    if config.get("schema") != _SCHEMA:
        raise DataError("crypto bulk storage configuration schema is unsupported")
    owner_reserve = (
        OwnerStorageReserveV1.from_dict(config[_RESERVE_KEY]) if _RESERVE_KEY in config else None
    )
    config = {key: value for key, value in config.items() if key != _RESERVE_KEY}
    backend = config.get("backend")
    common = {"schema", "backend", "bulk_root"}
    bulk = Path(_text(config, "bulk_root"))
    if backend == "macos_volume_uuid":
        if set(config) != common | {"volume_uuid"}:
            raise DataError("crypto bulk storage configuration fields differ")
        return ConfiguredCryptoBulkStore(
            bulk_root=bulk,
            manifest_root=root / "crypto" / "manifests",
            expected_volume_uuid=_text(config, "volume_uuid"),
            owner_reserve=owner_reserve,
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
    return ConfiguredCryptoBulkStore(
        bulk_root=bulk,
        manifest_root=root / "crypto" / "manifests",
        cloud_root_identity=identity,
        owner_reserve=owner_reserve,
    )


def configured_crypto_bulk_store(
    settings_or_root: AlphaSettings | Path | None = None,
) -> ConfiguredCryptoBulkStore:
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
    if retained is not None:
        # The reserve is only ever a retained owner setting; environment identity never sets it.
        comparable = {key: value for key, value in retained.items() if key != _RESERVE_KEY}
        if comparable != config:
            raise DataError("explicit and retained crypto bulk storage configurations conflict")
        if _RESERVE_KEY in retained:
            config[_RESERVE_KEY] = retained[_RESERVE_KEY]
    return _from_config(settings.data_dir, config)
