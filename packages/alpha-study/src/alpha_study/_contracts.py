"""Internal canonical and lineage primitives for alpha-study contracts."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal, cast

from alpha_core import DataError
from alpha_research import ResearchArtifactRef
from alpha_research._canonical import canonical_sha256

Scalar = bool | int | float | str
ValueType = Literal["bool", "int", "float", "str"]
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _utc_iso(value: datetime, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"{name} must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise DataError(f"{name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError(f"{name} must be a valid ISO-8601 timestamp") from exc
    _utc_iso(parsed, name)
    return parsed


def _strict_keys(value: Mapping[str, object], expected: set[str], name: str) -> None:
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing or unknown:
        detail = []
        if missing:
            detail.append(f"missing={sorted(missing)!r}")
        if unknown:
            detail.append(f"unknown={sorted(unknown)!r}")
        raise DataError(f"{name} keys are not exact ({', '.join(detail)})")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise DataError(f"{name} must be a string-keyed mapping")
    return cast(Mapping[str, object], value)


def _text(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise DataError(f"{name} must be non-empty canonical text")
    return value


def _hash(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise DataError(f"{name} must be a lowercase 64-character SHA-256 digest")
    return value


def _scalar(name: str, value: object, value_type: object) -> Scalar:
    if not isinstance(value_type, str) or value_type not in {"bool", "int", "float", "str"}:
        raise DataError("value_type must be one of bool, int, float, str")
    if value_type == "bool":
        if not isinstance(value, bool):
            raise DataError(f"{name} must be bool for value_type='bool'")
        return value
    if value_type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise DataError(f"{name} must be int for value_type='int'")
        return value
    if value_type == "float":
        if isinstance(value, bool) or not isinstance(value, float) or not math.isfinite(value):
            raise DataError(f"{name} must be a finite float for value_type='float'")
        return value
    return _text(name, value)


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return _utc_iso(value, "timestamp")
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DataError("canonical values must contain finite floats")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise DataError("canonical mappings require string keys")
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    raise DataError(f"unsupported canonical value type {type(value).__name__}")


def canonical_study_sha256(value: object) -> str:
    """Use the existing alpha-research canonical JSON/hash convention."""
    return canonical_sha256(_canonical_value(value))


def _artifact_from_dict(value: object) -> ResearchArtifactRef:
    data = _mapping(value, "artifact")
    expected = {
        "artifact_id",
        "content_sha256",
        "kind",
        "media_type",
        "row_count",
        "size_bytes",
    }
    _strict_keys(data, expected, "artifact")
    kind = data["kind"]
    if not isinstance(kind, str) or kind not in {"table", "chart", "report", "manifest"}:
        raise DataError("artifact.kind is invalid")
    size_bytes = data["size_bytes"]
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int):
        raise DataError("artifact.size_bytes must be an integer")
    row_count = data["row_count"]
    if row_count is not None and (isinstance(row_count, bool) or not isinstance(row_count, int)):
        raise DataError("artifact.row_count must be an integer or null")
    return ResearchArtifactRef(
        artifact_id=_text("artifact.artifact_id", data["artifact_id"]),
        kind=cast(Literal["table", "chart", "report", "manifest"], kind),
        media_type=_text("artifact.media_type", data["media_type"]),
        content_sha256=_hash("artifact.content_sha256", data["content_sha256"]),
        size_bytes=size_bytes,
        row_count=row_count,
    )
