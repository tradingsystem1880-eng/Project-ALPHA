"""Explicit Linux cloud-root identity; operator configuration is not durability proof.

A hosting reference records the operator's durable-storage decision. This module
checks the selected filesystem identity on every access; it does not certify hosting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from alpha_core import DataError

_DISPOSABLE_FILESYSTEMS = frozenset(
    {"tmpfs", "ramfs", "overlay", "aufs", "proc", "sysfs", "devtmpfs"}
)
_DISPOSABLE_ROOTS = (Path("/tmp"), Path("/var/tmp"), Path("/run"), Path("/dev/shm"))


def _unescape_mount(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)


@dataclass(frozen=True)
class CloudRootObservationV1:
    root: Path
    mount_point: Path
    device_id: int
    owner_uid: int
    filesystem_type: str
    mount_source: str


def inspect_cloud_root(root: Path) -> CloudRootObservationV1:
    """Inspect Linux mount metadata without network, credentials, or write probes."""
    if not root.is_absolute() or root == Path("/") or ".." in root.parts:
        raise DataError("cloud bulk root must be an explicit absolute directory")
    current = Path(root.anchor)
    for component in root.parts[1:]:
        current /= component
        if current.is_symlink():
            raise DataError("cloud bulk root contains a symlink")
    if not root.is_dir():
        raise DataError("configured cloud bulk root is unavailable")
    resolved = root.resolve(strict=True)
    if any(resolved.is_relative_to(path) for path in _DISPOSABLE_ROOTS):
        raise DataError("cloud bulk root cannot be a disposable temporary directory")
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
        matches = []
        for line in lines:
            before, after = line.split(" - ", 1)
            prefix, suffix = before.split(), after.split()
            mount = Path(_unescape_mount(prefix[4]))
            if resolved.is_relative_to(mount):
                matches.append((mount, suffix[0], _unescape_mount(suffix[1])))
        if not matches:
            raise DataError("cloud bulk root has no observed Linux mount identity")
        mount, filesystem, source = max(matches, key=lambda item: len(item[0].parts))
        observed = root.stat()
    except (OSError, ValueError, IndexError) as error:
        raise DataError("unable to inspect cloud bulk root mount identity") from error
    if filesystem in _DISPOSABLE_FILESYSTEMS:
        raise DataError("cloud bulk root filesystem is disposable or unsupported")
    return CloudRootObservationV1(
        resolved, mount, observed.st_dev, observed.st_uid, filesystem, source
    )


@dataclass(frozen=True)
class CloudBulkRootIdentityV1:
    root: Path
    mount_point: Path
    device_id: int
    owner_uid: int
    filesystem_type: str
    mount_source: str
    durable_hosting_reference: str

    def __post_init__(self) -> None:
        if (
            not self.root.is_absolute()
            or self.root == Path("/")
            or ".." in self.root.parts
            or not self.mount_point.is_absolute()
            or ".." in self.mount_point.parts
            or not self.root.is_relative_to(self.mount_point)
            or type(self.device_id) is not int
            or self.device_id < 0
            or type(self.owner_uid) is not int
            or self.owner_uid < 0
            or not isinstance(self.filesystem_type, str)
            or not self.filesystem_type.strip()
            or self.filesystem_type in _DISPOSABLE_FILESYSTEMS
            or not isinstance(self.mount_source, str)
            or not self.mount_source.strip()
            or not isinstance(self.durable_hosting_reference, str)
            or not 1 <= len(self.durable_hosting_reference.strip()) <= 1024
        ):
            raise DataError(
                "cloud bulk root requires exact identity and operator durable-hosting decision"
            )

    def verify(self, root: Path) -> None:
        if root != self.root:
            raise DataError("configured cloud bulk root differs from its pinned identity")
        observed = inspect_cloud_root(root)
        if observed != CloudRootObservationV1(
            self.root,
            self.mount_point,
            self.device_id,
            self.owner_uid,
            self.filesystem_type,
            self.mount_source,
        ):
            raise DataError("cloud bulk root mount/device/owner identity does not match")

    def to_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "mount_point": str(self.mount_point),
            "device_id": self.device_id,
            "owner_uid": self.owner_uid,
            "filesystem_type": self.filesystem_type,
            "mount_source": self.mount_source,
            "durable_hosting_reference": self.durable_hosting_reference,
        }
