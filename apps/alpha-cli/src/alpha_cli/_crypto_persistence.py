"""Exact-byte immutable JSON persistence shared by crypto document writers."""

from __future__ import annotations

import json
import os
from pathlib import Path

from alpha_core import DataError


def write_immutable_json(path: Path, payload: dict[str, object], *, collision: str) -> None:
    """Write in an existing parent; retain repeats and reject identity collisions."""
    rendered = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise DataError(collision)
        return
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, path)
