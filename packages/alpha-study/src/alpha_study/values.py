"""Immutable feature lineage and scalar contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from alpha_core import DataError
from alpha_research import ResearchArtifactRef
from alpha_study._contracts import (
    Scalar,
    ValueType,
    _artifact_from_dict,
    _hash,
    _mapping,
    _parse_datetime,
    _scalar,
    _strict_keys,
    _text,
    _utc_iso,
    canonical_study_sha256,
)

Role = Literal["geometry", "state", "factor"]


@dataclass(frozen=True, slots=True)
class FeatureInputRefV1:
    """Unverified immutable reference to one existing research artifact and snapshot."""

    artifact: ResearchArtifactRef
    input_available_at: datetime
    snapshot_id: str
    snapshot_manifest_sha256: str
    provider: str
    data_family: str
    frequency: str
    venue: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, ResearchArtifactRef):
            raise DataError("artifact must be a ResearchArtifactRef")
        _utc_iso(self.input_available_at, "input_available_at")
        _text("snapshot_id", self.snapshot_id)
        _hash("snapshot_manifest_sha256", self.snapshot_manifest_sha256)
        for name in ("provider", "data_family", "frequency", "venue"):
            _text(name, getattr(self, name))

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "artifact": self.artifact.to_dict(),
            "input_available_at": _utc_iso(self.input_available_at, "input_available_at"),
            "data_family": self.data_family,
            "frequency": self.frequency,
            "lineage_verification": "unverified_reference",
            "provider": self.provider,
            "schema": "FeatureInputRefV1",
            "schema_version": 1,
            "snapshot_id": self.snapshot_id,
            "snapshot_manifest_sha256": self.snapshot_manifest_sha256,
            "venue": self.venue,
        }

    @property
    def content_sha256(self) -> str:
        return canonical_study_sha256(self._semantic_dict())

    def to_dict(self) -> dict[str, object]:
        return {**self._semantic_dict(), "content_sha256": self.content_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> FeatureInputRefV1:
        data = _mapping(value, "FeatureInputRefV1")
        _strict_keys(
            data,
            {
                "artifact",
                "content_sha256",
                "data_family",
                "frequency",
                "input_available_at",
                "lineage_verification",
                "provider",
                "schema",
                "schema_version",
                "snapshot_id",
                "snapshot_manifest_sha256",
                "venue",
            },
            "FeatureInputRefV1",
        )
        if data["schema"] != "FeatureInputRefV1" or data["schema_version"] != 1:
            raise DataError("unsupported FeatureInputRefV1 schema")
        if data["lineage_verification"] != "unverified_reference":
            raise DataError("FeatureInputRefV1 cannot claim verified lineage")
        result = cls(
            artifact=_artifact_from_dict(data["artifact"]),
            input_available_at=_parse_datetime(data["input_available_at"], "input_available_at"),
            snapshot_id=_text("snapshot_id", data["snapshot_id"]),
            snapshot_manifest_sha256=_hash(
                "snapshot_manifest_sha256", data["snapshot_manifest_sha256"]
            ),
            provider=_text("provider", data["provider"]),
            data_family=_text("data_family", data["data_family"]),
            frequency=_text("frequency", data["frequency"]),
            venue=_text("venue", data["venue"]),
        )
        if _hash("content_sha256", data["content_sha256"]) != result.content_sha256:
            raise DataError("FeatureInputRefV1 content_sha256 does not match its semantics")
        return result


@dataclass(frozen=True, slots=True)
class FeatureValueV1:
    """One finite, point-in-time feature value with immutable source lineage."""

    feature_id: str
    role: Role
    value: Scalar
    value_type: ValueType
    observed_at: datetime
    available_at: datetime
    vintage_at: datetime
    vintage_id: str
    sources: tuple[FeatureInputRefV1, ...]
    computation_sha256: str
    unit: str
    venue: str

    def __post_init__(self) -> None:
        _text("feature_id", self.feature_id)
        if not isinstance(self.role, str) or self.role not in {"geometry", "state", "factor"}:
            raise DataError("role must be geometry, state, or factor")
        _scalar("value", self.value, self.value_type)
        _utc_iso(self.observed_at, "observed_at")
        _utc_iso(self.available_at, "available_at")
        if self.available_at < self.observed_at:
            raise DataError("available_at must be at or after observed_at")
        _utc_iso(self.vintage_at, "vintage_at")
        if self.available_at < self.vintage_at:
            raise DataError("available_at must be at or after vintage_at")
        _text("vintage_id", self.vintage_id)
        if (
            not isinstance(self.sources, tuple)
            or not self.sources
            or any(not isinstance(source, FeatureInputRefV1) for source in self.sources)
        ):
            raise DataError("sources must be a non-empty tuple of FeatureInputRefV1")
        sources = tuple(sorted(self.sources, key=lambda source: source.content_sha256))
        if len({source.content_sha256 for source in sources}) != len(sources):
            raise DataError("sources must not contain duplicate lineage references")
        if any(self.available_at < source.input_available_at for source in sources):
            raise DataError("available_at must be at or after every source input_available_at")
        object.__setattr__(self, "sources", sources)
        _hash("computation_sha256", self.computation_sha256)
        _text("unit", self.unit)
        _text("venue", self.venue)
        source_venues = {source.venue for source in sources}
        if self.venue != "not_applicable" and source_venues != {self.venue}:
            raise DataError("feature venue must match every source or be not_applicable")

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "available_at": _utc_iso(self.available_at, "available_at"),
            "computation_sha256": self.computation_sha256,
            "feature_id": self.feature_id,
            "observed_at": _utc_iso(self.observed_at, "observed_at"),
            "role": self.role,
            "lineage_verification": "unverified_reference",
            "schema": "FeatureValueV1",
            "schema_version": 1,
            "sources": [source.to_dict() for source in self.sources],
            "unit": self.unit,
            "value": self.value,
            "value_type": self.value_type,
            "venue": self.venue,
            "vintage_at": _utc_iso(self.vintage_at, "vintage_at"),
            "vintage_id": self.vintage_id,
        }

    @property
    def content_sha256(self) -> str:
        return canonical_study_sha256(self._semantic_dict())

    def to_dict(self) -> dict[str, object]:
        return {**self._semantic_dict(), "content_sha256": self.content_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> FeatureValueV1:
        data = _mapping(value, "FeatureValueV1")
        _strict_keys(
            data,
            {
                "feature_id",
                "role",
                "value",
                "value_type",
                "observed_at",
                "available_at",
                "content_sha256",
                "vintage_at",
                "vintage_id",
                "lineage_verification",
                "sources",
                "computation_sha256",
                "schema",
                "schema_version",
                "unit",
                "venue",
            },
            "FeatureValueV1",
        )
        role = data["role"]
        value_type = data["value_type"]
        if not isinstance(role, str) or role not in {"geometry", "state", "factor"}:
            raise DataError("role must be geometry, state, or factor")
        if not isinstance(value_type, str) or value_type not in {"bool", "int", "float", "str"}:
            raise DataError("value_type is invalid")
        if data["schema"] != "FeatureValueV1" or data["schema_version"] != 1:
            raise DataError("unsupported FeatureValueV1 schema")
        if data["lineage_verification"] != "unverified_reference":
            raise DataError("FeatureValueV1 cannot claim verified lineage")
        sources = data["sources"]
        if not isinstance(sources, list):
            raise DataError("FeatureValueV1.sources must be a JSON array")
        result = cls(
            feature_id=_text("feature_id", data["feature_id"]),
            role=cast(Role, role),
            value=_scalar("value", data["value"], value_type),
            value_type=cast(ValueType, value_type),
            observed_at=_parse_datetime(data["observed_at"], "observed_at"),
            available_at=_parse_datetime(data["available_at"], "available_at"),
            vintage_at=_parse_datetime(data["vintage_at"], "vintage_at"),
            vintage_id=_text("vintage_id", data["vintage_id"]),
            sources=tuple(
                FeatureInputRefV1.from_dict(_mapping(source, "source")) for source in sources
            ),
            computation_sha256=_hash("computation_sha256", data["computation_sha256"]),
            unit=_text("unit", data["unit"]),
            venue=_text("venue", data["venue"]),
        )
        if _hash("content_sha256", data["content_sha256"]) != result.content_sha256:
            raise DataError("FeatureValueV1 content_sha256 does not match its semantics")
        return result
