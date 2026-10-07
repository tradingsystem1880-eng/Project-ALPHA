"""Immutable JSON receipts for runs and scoring revisions."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def write_once(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True, default=str)


def bind_manifest(path: Path, value: dict[str, Any], *, resume: bool) -> None:
    if path.exists():
        if not resume:
            raise FileExistsError(f"Existing run: {path}; use --resume or a new name")
        if json.loads(path.read_text()) != value:
            raise ValueError(f"Incompatible resume: {path}")
    else:
        if resume:
            raise ValueError("Cannot resume a legacy or missing run without a bound manifest")
        write_once(path, value)


def revision_path(base: Path, revision: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", revision):
        raise ValueError("Revision must be a simple name, not a path")
    return base / "scoring" / revision
