"""Canonical JSON identity helpers for immutable research contracts."""

from __future__ import annotations

import hashlib
import json


def canonical_sha256(value: object) -> str:
    """Hash one JSON-compatible value with stable key and whitespace conventions."""
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
