"""Verify the complete supplied upstream source tree before Python imports any of it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

COMMIT = "484776c211e4fbbeef03e0ec00d6bbee7362a4f4"
ARCHIVE_SHA256 = "4c5d1c792b133d7148bb4d59aea09b8accf4d14deb4a10ffed276ce178dd855c"
SOURCE_SHA256 = "0266b2d63328f88fcaf6f239bf6d67f29c896b8161566f794ef69465b7788707"


def verify_source(root: Path) -> str:
    if root.is_symlink() or not (root / "rdagent").is_dir():
        raise ValueError("expected the pinned complete RD-Agent source tree")
    files = {}
    for path in sorted((root / "rdagent").rglob("*")):
        if path.is_symlink():
            raise ValueError("source symlinks are not supported")
        if path.is_file() and "__pycache__" not in path.parts:
            files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    actual = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if actual != SOURCE_SHA256:
        raise ValueError("pinned RD-Agent source tree mismatch")
    return actual
