"""Shared immutable D1/D2 artifact publication and canonical JSON reads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alpha_cli import _artifacts
from alpha_core import DataError


def publish_bytes(path: Path, content: bytes) -> None:
    def write(target: Path) -> None:
        target.write_bytes(content)

    _artifacts.publish_artifact(path, write)


def publish_text(path: Path, content: str) -> None:
    publish_bytes(path, content.encode("utf-8"))


def estimate_record(estimate: Any) -> dict[str, object]:
    return {
        "estimate": float(estimate.estimate),
        "ci_lower": float(estimate.ci_lower),
        "ci_upper": float(estimate.ci_upper),
        "p_value": float(estimate.p_value),
        "confidence": float(estimate.confidence),
        "sample_size": int(estimate.sample_size),
        "effective_event_count": int(estimate.effective_event_count),
        "low_cluster_count": bool(estimate.low_cluster_count),
    }


def read_canonical_json(path: Path, label: str, *, max_bytes: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise DataError(f"{label} is not a regular immutable file")
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise DataError(f"{label} exceeds the bounded JSON size")
    try:
        parsed: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise DataError(f"{label} must contain a JSON object")
    try:
        canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DataError(f"{label} must contain finite JSON values") from exc
    if raw != canonical.encode("utf-8"):
        raise DataError(f"{label} must use canonical JSON bytes")
    return parsed
