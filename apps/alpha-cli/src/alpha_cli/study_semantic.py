"""Verified, read-only composition of the alpha-study semantic projection."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from alpha_core import DataError
from alpha_study import (
    BlindSemanticProjectionV1,
    canonical_study_sha256,
)

_RUN_ID_RE: Final = re.compile(r"[0-9a-f]{16}")
_HASH_RE: Final = re.compile(r"[0-9a-f]{64}")


def _strict_keys(value: Mapping[str, object], expected: set[str], name: str) -> None:
    actual = set(value)
    if actual != expected:
        raise DataError(
            f"{name} keys are not exact (missing={sorted(expected - actual)!r}, "
            f"unknown={sorted(actual - expected)!r})"
        )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise DataError(f"{name} must be a string-keyed mapping")
    return value


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
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise DataError(f"{name} must be a lowercase 64-character SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class VerifiedBlindSemanticReadV1:
    """Server-verified, non-authoritative envelope around one blind projection."""

    run_id: str
    projection: BlindSemanticProjectionV1
    content_sha256: str | None = None
    source_verification: str = "verified_completed_d0_recomputation"
    authority: str = "none"

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or _RUN_ID_RE.fullmatch(self.run_id) is None:
            raise DataError("run_id must be lowercase 16-character hex")
        if not isinstance(self.projection, BlindSemanticProjectionV1):
            raise DataError("projection must be BlindSemanticProjectionV1")
        if self.projection.run_id != self.run_id:
            raise DataError("run_id must match the blind semantic projection")
        if self.source_verification != "verified_completed_d0_recomputation":
            raise DataError("source_verification is fixed")
        if self.authority != "none":
            raise DataError("verified blind semantic read has no authority")
        expected = canonical_study_sha256(self._semantic_dict())
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected)
        elif _hash("content_sha256", self.content_sha256) != expected:
            raise DataError("content_sha256 does not match verified blind semantic read")

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "authority": self.authority,
            "projection": self.projection.to_dict(),
            "run_id": self.run_id,
            "schema": "VerifiedBlindSemanticReadV1",
            "schema_version": 1,
            "source_verification": self.source_verification,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._semantic_dict(), "content_sha256": self.content_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> VerifiedBlindSemanticReadV1:
        data = _mapping(value, "VerifiedBlindSemanticReadV1")
        _strict_keys(data, set(cls._keys()), "VerifiedBlindSemanticReadV1")
        if data["schema"] != "VerifiedBlindSemanticReadV1" or data["schema_version"] != 1:
            raise DataError("unsupported VerifiedBlindSemanticReadV1 schema")
        projection_raw = _mapping(data["projection"], "projection")
        return cls(
            run_id=_text("run_id", data["run_id"]),
            projection=BlindSemanticProjectionV1.from_dict(projection_raw),
            content_sha256=_hash("content_sha256", data["content_sha256"]),
            source_verification=_text("source_verification", data["source_verification"]),
            authority=_text("authority", data["authority"]),
        )

    @staticmethod
    def _keys() -> tuple[str, ...]:
        return (
            "authority",
            "content_sha256",
            "projection",
            "run_id",
            "schema",
            "schema_version",
            "source_verification",
        )


__all__ = ["VerifiedBlindSemanticReadV1"]
