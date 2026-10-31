"""Pure JSON codec for control-plane storage; owns no database or authority."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence

from alpha_core import DataError

_MAX_JSON_BYTES = 65_536


def _clean_json(value: object, *, label: str, depth: int = 0) -> object:
    if depth > 16:
        raise DataError(f"invalid control {label}: JSON nesting exceeds 16 levels")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DataError(f"invalid control {label}: expected finite JSON values")
        return value
    if isinstance(value, Mapping):
        clean: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or "\x00" in key:
                raise DataError(f"invalid control {label}: JSON keys must be non-empty strings")
            clean[key] = _clean_json(item, label=label, depth=depth + 1)
        return clean
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_clean_json(item, label=label, depth=depth + 1) for item in value]
    raise DataError(f"invalid control {label}: expected finite JSON values")


def _json_object(
    value: Mapping[str, object], label: str, *, max_bytes: int = _MAX_JSON_BYTES
) -> dict[str, object]:
    clean = _clean_json(value, label=label)
    if not isinstance(clean, dict):  # Mapping above makes this defensive branch unreachable.
        raise DataError(f"invalid control {label}: expected a JSON object")
    _canonical_json(clean, label, max_bytes=max_bytes)
    return clean


def _canonical_json(value: object, label: str, *, max_bytes: int = _MAX_JSON_BYTES) -> str:
    try:
        result = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DataError(f"invalid control {label}: expected finite JSON values") from exc
    if len(result.encode("utf-8")) > max_bytes:
        raise DataError(f"invalid control {label}: JSON exceeds {max_bytes} bytes")
    return result


def _decode_json(value: object, label: str) -> object:
    if not isinstance(value, str):
        raise DataError(f"corrupt control store: {label} is not text")
    try:
        result: object = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DataError(f"corrupt control store: invalid {label}") from exc
    return _clean_json(result, label=label)
