"""Shared strict bases, regexes and validators."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


_LOWER_HEX_16 = re.compile(r"^[0-9a-f]{16}$")
_LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_utc_z(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{6})?Z", value
    ):
        raise ValueError("must be a canonical UTC-Z timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("must be a canonical UTC-Z timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("must be a canonical UTC-Z timestamp")
    canonical = parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if parsed.microsecond == 0:
        canonical = parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    if value != canonical:
        raise ValueError("must be a canonical UTC-Z timestamp")
    return value


def _canonical_point_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("point_id must be non-empty canonical text")
    return value


class _FrozenSemanticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
