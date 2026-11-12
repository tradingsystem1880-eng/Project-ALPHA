"""Invocation-local artifact hashing limits, never provider or durable quota accounting."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from alpha_core import DataError

_CHUNK_BYTES = 1024 * 1024


def _identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


@dataclass
class ArtifactVerificationBudget:
    """Bound returned artifact bytes across hashes, including repeated reads.

    Metadata JSON, kernel read-ahead and physical disk traffic are outside this
    counter. Reservations are local, remain charged on failure and have no authority
    over HTTP usage, retries, campaigns or another invocation/process.
    """

    max_bytes: int
    reserved_bytes: int = field(default=0, init=False)
    bytes_read: int = field(default=0, init=False)
    failed: bool = field(default=False, init=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.max_bytes) is not int or self.max_bytes <= 0:
            raise DataError("artifact verification byte limit must be a positive integer")

    def _reserve(self, size: int) -> None:
        with self._lock:
            if self.failed:
                raise DataError("artifact verification budget aborted after failure")
            if type(size) is not int or size < 0:
                self.failed = True
                raise DataError("artifact verification length is invalid")
            if size > self.max_bytes - self.reserved_bytes:
                self.failed = True
                raise DataError("artifact verification byte budget exhausted")
            self.reserved_bytes += size

    def _abort(self) -> None:
        with self._lock:
            self.failed = True

    def hash_file(self, path: Path, *, expected_bytes: int, expected_sha256: str) -> str:
        """Reserve before open; hash exactly the declared regular file without an EOF probe."""
        self._reserve(expected_bytes)
        try:
            flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags)
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode) or before.st_size != expected_bytes:
                    raise DataError("crypto artifact size or file type changed before verification")
                digest = hashlib.sha256()
                remaining = expected_bytes
                while remaining:
                    chunk = os.read(descriptor, min(_CHUNK_BYTES, remaining))
                    with self._lock:
                        self.bytes_read += len(chunk)
                    if not chunk:
                        raise DataError("crypto artifact ended before its declared size")
                    digest.update(chunk)
                    remaining -= len(chunk)
                after = os.fstat(descriptor)
                actual = digest.hexdigest()
                if _identity(before) != _identity(after) or actual != expected_sha256:
                    raise DataError("crypto artifact integrity failure during bounded verification")
            finally:
                os.close(descriptor)
        except OSError as exc:
            self._abort()
            raise DataError("crypto artifact could not be read for bounded verification") from exc
        except BaseException:
            self._abort()
            raise
        return actual


# New inspection-only engineering ceiling, matching the existing normalized-read
# magnitude. It is not a provider quota and does not alter legacy verifier defaults.
DEFAULT_METADATA_READ_BYTES = 32 * 1024 * 1024
DEFAULT_METADATA_JSON_DEPTH = 64


@dataclass
class MetadataVerificationBudget:
    """Aggregate manifest/retirement JSON bytes for one optional inspection.

    Repeated reads count repeatedly. This bounds input bodies, not decoded-object
    overhead, serialization work, filesystem read-ahead, config/identity queries or
    wall time. No authority, persistent accounting, refund or history reset.
    """

    max_bytes: int
    max_depth: int = DEFAULT_METADATA_JSON_DEPTH
    reserved_bytes: int = field(default=0, init=False)
    bytes_read: int = field(default=0, init=False)
    failed: bool = field(default=False, init=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in (self.max_bytes, self.max_depth)):
            raise DataError("metadata verification limits must be positive")

    def _reserve(self, size: int) -> None:
        with self._lock:
            if self.failed:
                raise DataError("metadata verification aborted after failure")
            if size > self.max_bytes - self.reserved_bytes:
                self.failed = True
                raise DataError("metadata verification byte limit exhausted")
            self.reserved_bytes += size

    def _abort(self) -> None:
        with self._lock:
            self.failed = True

    def read_json(self, path: Path) -> object:
        """Reserve before open; read exactly one stable regular file, then decode."""
        import json  # noqa: PLC0415
        from typing import cast  # noqa: PLC0415

        try:
            named_before = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(named_before.st_mode):
                raise DataError("crypto metadata must be a regular file")
            self._reserve(named_before.st_size)
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                before = os.fstat(fd)
                if not stat.S_ISREG(before.st_mode) or _identity(before) != _identity(named_before):
                    raise DataError("crypto metadata changed before reading")
                chunks: list[bytes] = []
                remaining = before.st_size
                while remaining:
                    chunk = os.read(fd, min(_CHUNK_BYTES, remaining))
                    with self._lock:
                        self.bytes_read += len(chunk)
                    if not chunk:
                        raise DataError("crypto metadata ended before its reserved size")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                after = os.fstat(fd)
                named_after = path.stat(follow_symlinks=False)
                if _identity(before) != _identity(after) or _identity(after) != _identity(
                    named_after
                ):
                    raise DataError("crypto metadata changed during reading")
            finally:
                os.close(fd)
            payload = b"".join(chunks)
            text = payload.decode("utf-8")  # match existing UTF-8 metadata readers
            depth = 0
            in_string = escaped = False
            for char in payload:
                if in_string:
                    if escaped:
                        escaped = False
                    elif char == 92:
                        escaped = True
                    elif char == 34:
                        in_string = False
                elif char == 34:
                    in_string = True
                elif char in (91, 123):
                    depth += 1
                    if depth > self.max_depth:
                        raise DataError("crypto metadata JSON nesting limit exhausted")
                elif char in (93, 125):
                    depth -= 1
            return cast(object, json.loads(text))
        except OSError:
            self._abort()
            raise DataError("crypto metadata could not be read safely") from None
        except (ValueError, RecursionError):
            self._abort()
            raise DataError("crypto metadata JSON is unavailable or malformed") from None
        except BaseException:
            self._abort()
            raise
