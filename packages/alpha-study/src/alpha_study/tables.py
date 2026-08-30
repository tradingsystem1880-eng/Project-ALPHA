"""Immutable event and factor observation tables for generic study projections."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from alpha_core import DataError
from alpha_study._contracts import (
    _hash,
    _mapping,
    _parse_datetime,
    _strict_keys,
    _text,
    _utc_iso,
    canonical_study_sha256,
)
from alpha_study.values import FeatureValueV1

AssetClass = Literal["equity", "etf", "future", "option", "fx", "crypto", "macro", "other"]
_ASSET_CLASSES = {"equity", "etf", "future", "option", "fx", "crypto", "macro", "other"}
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def _optional_text(name: str, value: object) -> str | None:
    return None if value is None else _text(name, value)


def _canonical_strings(name: str, values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise DataError(f"{name} must be a list or tuple")
    result = tuple(_text(f"{name} item", item) for item in values)
    if len(result) != len(set(result)):
        raise DataError(f"{name} must not contain duplicates")
    return tuple(sorted(result))


def _feature_tuple(value: object) -> tuple[FeatureValueV1, ...]:
    if not isinstance(value, (list, tuple)):
        raise DataError("features must be a list or tuple")
    features = tuple(value)
    if any(not isinstance(feature, FeatureValueV1) for feature in features):
        raise DataError("features must contain FeatureValueV1 values")
    if len({feature.feature_id for feature in features}) != len(features):
        raise DataError("features must have unique feature_id values")
    return tuple(sorted(features, key=lambda feature: (feature.feature_id, feature.role)))


@dataclass(frozen=True, slots=True)
class EventRowV1:
    study_id: str
    entity_id: str
    asset_class: AssetClass
    instrument_id: str
    venue: str
    event_start: datetime
    event_end: datetime
    printed_at: datetime
    confirmed_at: datetime
    available_at: datetime
    direction: int
    operator_id: str
    operator_version: str
    operator_code_sha256: str
    parameter_sha256: str
    features: tuple[FeatureValueV1, ...]
    overlap_cluster_id: str | None
    diagnostic_flags: tuple[str, ...]
    parent_event_ids: tuple[str, ...]
    content_sha256: str | None = None
    event_id: str | None = None

    def __post_init__(self) -> None:
        _text("study_id", self.study_id)
        _text("entity_id", self.entity_id)
        if not isinstance(self.asset_class, str) or self.asset_class not in _ASSET_CLASSES:
            raise DataError("asset_class is not supported")
        _text("instrument_id", self.instrument_id)
        _text("venue", self.venue)
        for name, value in (
            ("event_start", self.event_start),
            ("event_end", self.event_end),
            ("printed_at", self.printed_at),
            ("confirmed_at", self.confirmed_at),
            ("available_at", self.available_at),
        ):
            _utc_iso(value, name)
        if not (
            self.event_end >= self.event_start
            and self.printed_at >= self.event_end
            and self.confirmed_at >= self.printed_at
            and self.available_at >= self.confirmed_at
        ):
            raise DataError(
                "event clocks must be event_start <= event_end <= printed <= confirmed <= available"
            )
        if (
            isinstance(self.direction, bool)
            or not isinstance(self.direction, int)
            or self.direction not in {-1, 0, 1}
        ):
            raise DataError("direction must be exactly -1, 0, or 1")
        _text("operator_id", self.operator_id)
        if (
            not isinstance(self.operator_version, str)
            or _SEMVER.fullmatch(self.operator_version) is None
        ):
            raise DataError("operator_version must be a strict x.y.z version")
        _hash("operator_code_sha256", self.operator_code_sha256)
        _hash("parameter_sha256", self.parameter_sha256)
        features = _feature_tuple(self.features)
        if any(feature.available_at > self.available_at for feature in features):
            raise DataError("every feature must be available by event.available_at")
        flags = _canonical_strings("diagnostic_flags", self.diagnostic_flags)
        parents = _canonical_strings("parent_event_ids", self.parent_event_ids)
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "diagnostic_flags", flags)
        object.__setattr__(self, "parent_event_ids", parents)
        expected = canonical_study_sha256(self._semantic_dict())
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected)
        elif _hash("content_sha256", self.content_sha256) != expected:
            raise DataError("content_sha256 does not match event content")
        expected_id = f"ev_{expected}"
        if self.event_id is None:
            object.__setattr__(self, "event_id", expected_id)
        elif self.event_id != expected_id:
            raise DataError("event_id does not match event content")

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "asset_class": self.asset_class,
            "authority": "none",
            "available_at": _utc_iso(self.available_at, "available_at"),
            "confirmed_at": _utc_iso(self.confirmed_at, "confirmed_at"),
            "diagnostic_flags": list(self.diagnostic_flags),
            "direction": self.direction,
            "entity_id": self.entity_id,
            "event_end": _utc_iso(self.event_end, "event_end"),
            "event_start": _utc_iso(self.event_start, "event_start"),
            "features": [feature.to_dict() for feature in self.features],
            "instrument_id": self.instrument_id,
            "lineage_verification": "unverified_reference",
            "operator_code_sha256": self.operator_code_sha256,
            "operator_id": self.operator_id,
            "operator_version": self.operator_version,
            "overlap_cluster_id": self.overlap_cluster_id,
            "parameter_sha256": self.parameter_sha256,
            "parent_event_ids": list(self.parent_event_ids),
            "printed_at": _utc_iso(self.printed_at, "printed_at"),
            "schema": "EventRowV1",
            "schema_version": 1,
            "study_id": self.study_id,
            "venue": self.venue,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_dict(),
            "content_sha256": self.content_sha256,
            "event_id": self.event_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> EventRowV1:
        data = _mapping(value, "EventRowV1")
        _strict_keys(data, set(cls._keys()), "EventRowV1")
        if data["schema"] != "EventRowV1" or data["schema_version"] != 1:
            raise DataError("unsupported EventRowV1 schema")
        if data["authority"] != "none" or data["lineage_verification"] != "unverified_reference":
            raise DataError("EventRowV1 cannot claim authority or verified lineage")
        features = data["features"]
        if not isinstance(features, list):
            raise DataError("features must be a list")
        return cls(
            study_id=_text("study_id", data["study_id"]),
            entity_id=_text("entity_id", data["entity_id"]),
            asset_class=cast(AssetClass, data["asset_class"]),
            instrument_id=_text("instrument_id", data["instrument_id"]),
            venue=_text("venue", data["venue"]),
            event_start=_parse_datetime(data["event_start"], "event_start"),
            event_end=_parse_datetime(data["event_end"], "event_end"),
            printed_at=_parse_datetime(data["printed_at"], "printed_at"),
            confirmed_at=_parse_datetime(data["confirmed_at"], "confirmed_at"),
            available_at=_parse_datetime(data["available_at"], "available_at"),
            direction=data["direction"] if isinstance(data["direction"], int) else 9,
            operator_id=_text("operator_id", data["operator_id"]),
            operator_version=_text("operator_version", data["operator_version"]),
            operator_code_sha256=_hash("operator_code_sha256", data["operator_code_sha256"]),
            parameter_sha256=_hash("parameter_sha256", data["parameter_sha256"]),
            features=tuple(
                FeatureValueV1.from_dict(_mapping(item, "feature")) for item in features
            ),
            overlap_cluster_id=_optional_text("overlap_cluster_id", data["overlap_cluster_id"]),
            diagnostic_flags=_canonical_strings("diagnostic_flags", data["diagnostic_flags"]),
            parent_event_ids=_canonical_strings("parent_event_ids", data["parent_event_ids"]),
            content_sha256=_hash("content_sha256", data["content_sha256"]),
            event_id=_text("event_id", data["event_id"]),
        )

    @staticmethod
    def _keys() -> tuple[str, ...]:
        return (
            "asset_class",
            "authority",
            "available_at",
            "confirmed_at",
            "content_sha256",
            "diagnostic_flags",
            "direction",
            "entity_id",
            "event_end",
            "event_id",
            "event_start",
            "features",
            "instrument_id",
            "lineage_verification",
            "operator_code_sha256",
            "operator_id",
            "operator_version",
            "overlap_cluster_id",
            "parameter_sha256",
            "parent_event_ids",
            "printed_at",
            "schema",
            "schema_version",
            "study_id",
            "venue",
        )


@dataclass(frozen=True, slots=True)
class EventTableV1:
    study_id: str
    rows: tuple[EventRowV1, ...]
    content_sha256: str | None = None

    def __post_init__(self) -> None:
        _text("study_id", self.study_id)
        if not isinstance(self.rows, tuple) or any(
            not isinstance(row, EventRowV1) for row in self.rows
        ):
            raise DataError("rows must be a tuple of EventRowV1")
        if any(row.study_id != self.study_id for row in self.rows):
            raise DataError("all event rows must have the table study_id")
        ordered = tuple(sorted(self.rows, key=lambda row: cast(str, row.event_id)))
        if len({row.event_id for row in ordered}) != len(ordered):
            raise DataError("event rows must have unique event_id values")
        object.__setattr__(self, "rows", ordered)
        expected = canonical_study_sha256(self._semantic_dict())
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected)
        elif _hash("content_sha256", self.content_sha256) != expected:
            raise DataError("content_sha256 does not match event table")

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "authority": "none",
            "lineage_verification": "unverified_reference",
            "rows": [row.to_dict() for row in self.rows],
            "schema": "EventTableV1",
            "schema_version": 1,
            "study_id": self.study_id,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._semantic_dict(), "content_sha256": self.content_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> EventTableV1:
        data = _mapping(value, "EventTableV1")
        _strict_keys(
            data,
            {
                "authority",
                "content_sha256",
                "lineage_verification",
                "rows",
                "schema",
                "schema_version",
                "study_id",
            },
            "EventTableV1",
        )
        if data["schema"] != "EventTableV1" or data["schema_version"] != 1:
            raise DataError("unsupported EventTableV1 schema")
        if data["authority"] != "none" or data["lineage_verification"] != "unverified_reference":
            raise DataError("EventTableV1 cannot claim authority or verified lineage")
        rows = data["rows"]
        if not isinstance(rows, list):
            raise DataError("rows must be a list")
        return cls(
            study_id=_text("study_id", data["study_id"]),
            rows=tuple(EventRowV1.from_dict(_mapping(row, "event row")) for row in rows),
            content_sha256=_hash("content_sha256", data["content_sha256"]),
        )


@dataclass(frozen=True, slots=True)
class FactorObservationV1:
    study_id: str
    entity_id: str
    instrument_id: str
    factor_id: str
    cross_section_at: datetime
    observed_at: datetime
    available_at: datetime
    universe_snapshot_id: str
    universe_snapshot_sha256: str
    universe_available_at: datetime
    value: FeatureValueV1
    content_sha256: str | None = None
    observation_id: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("study_id", self.study_id),
            ("entity_id", self.entity_id),
            ("instrument_id", self.instrument_id),
            ("factor_id", self.factor_id),
            ("universe_snapshot_id", self.universe_snapshot_id),
        ):
            _text(name, value)
        _hash("universe_snapshot_sha256", self.universe_snapshot_sha256)
        for clock_name, clock_value in (
            ("cross_section_at", self.cross_section_at),
            ("observed_at", self.observed_at),
            ("available_at", self.available_at),
            ("universe_available_at", self.universe_available_at),
        ):
            _utc_iso(clock_value, clock_name)
        if not (self.cross_section_at <= self.observed_at <= self.available_at):
            raise DataError(
                "factor clocks must satisfy cross_section_at <= observed_at <= available_at"
            )
        if self.universe_available_at > self.available_at:
            raise DataError("factor availability cannot precede universe availability")
        if not isinstance(self.value, FeatureValueV1):
            raise DataError("value must be a FeatureValueV1")
        if self.value.role != "factor" or self.value.feature_id != self.factor_id:
            raise DataError("factor value must have role='factor' and feature_id == factor_id")
        if (
            self.value.observed_at != self.observed_at
            or self.value.available_at != self.available_at
        ):
            raise DataError("factor value clocks must equal factor observation clocks")
        expected = canonical_study_sha256(self._semantic_dict())
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected)
        elif _hash("content_sha256", self.content_sha256) != expected:
            raise DataError("content_sha256 does not match factor observation")
        expected_id = f"fo_{expected}"
        if self.observation_id is None:
            object.__setattr__(self, "observation_id", expected_id)
        elif self.observation_id != expected_id:
            raise DataError("observation_id does not match factor observation")

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "authority": "none",
            "available_at": _utc_iso(self.available_at, "available_at"),
            "cross_section_at": _utc_iso(self.cross_section_at, "cross_section_at"),
            "entity_id": self.entity_id,
            "factor_id": self.factor_id,
            "instrument_id": self.instrument_id,
            "lineage_verification": "unverified_reference",
            "observed_at": _utc_iso(self.observed_at, "observed_at"),
            "schema": "FactorObservationV1",
            "schema_version": 1,
            "study_id": self.study_id,
            "universe_snapshot_id": self.universe_snapshot_id,
            "universe_snapshot_sha256": self.universe_snapshot_sha256,
            "universe_available_at": _utc_iso(self.universe_available_at, "universe_available_at"),
            "value": self.value.to_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_dict(),
            "content_sha256": self.content_sha256,
            "observation_id": self.observation_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> FactorObservationV1:
        data = _mapping(value, "FactorObservationV1")
        _strict_keys(data, set(cls._keys()), "FactorObservationV1")
        if data["schema"] != "FactorObservationV1" or data["schema_version"] != 1:
            raise DataError("unsupported FactorObservationV1 schema")
        if data["authority"] != "none" or data["lineage_verification"] != "unverified_reference":
            raise DataError("FactorObservationV1 cannot claim authority or verified lineage")
        return cls(
            study_id=_text("study_id", data["study_id"]),
            entity_id=_text("entity_id", data["entity_id"]),
            instrument_id=_text("instrument_id", data["instrument_id"]),
            factor_id=_text("factor_id", data["factor_id"]),
            cross_section_at=_parse_datetime(data["cross_section_at"], "cross_section_at"),
            observed_at=_parse_datetime(data["observed_at"], "observed_at"),
            available_at=_parse_datetime(data["available_at"], "available_at"),
            universe_snapshot_id=_text("universe_snapshot_id", data["universe_snapshot_id"]),
            universe_snapshot_sha256=_hash(
                "universe_snapshot_sha256", data["universe_snapshot_sha256"]
            ),
            universe_available_at=_parse_datetime(
                data["universe_available_at"], "universe_available_at"
            ),
            value=FeatureValueV1.from_dict(_mapping(data["value"], "value")),
            content_sha256=_hash("content_sha256", data["content_sha256"]),
            observation_id=_text("observation_id", data["observation_id"]),
        )

    @staticmethod
    def _keys() -> tuple[str, ...]:
        return (
            "available_at",
            "authority",
            "content_sha256",
            "cross_section_at",
            "entity_id",
            "factor_id",
            "instrument_id",
            "lineage_verification",
            "observation_id",
            "observed_at",
            "schema",
            "schema_version",
            "study_id",
            "universe_snapshot_id",
            "universe_snapshot_sha256",
            "universe_available_at",
            "value",
        )


@dataclass(frozen=True, slots=True)
class FactorObservationTableV1:
    study_id: str
    rows: tuple[FactorObservationV1, ...]
    content_sha256: str | None = None

    def __post_init__(self) -> None:
        _text("study_id", self.study_id)
        if not isinstance(self.rows, tuple) or any(
            not isinstance(row, FactorObservationV1) for row in self.rows
        ):
            raise DataError("rows must be a tuple of FactorObservationV1")
        if any(row.study_id != self.study_id for row in self.rows):
            raise DataError("all factor rows must have the table study_id")
        ordered = tuple(sorted(self.rows, key=lambda row: cast(str, row.observation_id)))
        if len({row.observation_id for row in ordered}) != len(ordered):
            raise DataError("factor rows must have unique observation_id values")
        economic_keys = {
            (row.factor_id, row.entity_id, _utc_iso(row.cross_section_at, "cross_section_at"))
            for row in ordered
        }
        if len(economic_keys) != len(ordered):
            raise DataError("factor rows must have unique factor/entity/cross-section keys")
        object.__setattr__(self, "rows", ordered)
        expected = canonical_study_sha256(self._semantic_dict())
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected)
        elif _hash("content_sha256", self.content_sha256) != expected:
            raise DataError("content_sha256 does not match factor table")

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "authority": "none",
            "lineage_verification": "unverified_reference",
            "rows": [row.to_dict() for row in self.rows],
            "schema": "FactorObservationTableV1",
            "schema_version": 1,
            "study_id": self.study_id,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._semantic_dict(), "content_sha256": self.content_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> FactorObservationTableV1:
        data = _mapping(value, "FactorObservationTableV1")
        _strict_keys(
            data,
            {
                "authority",
                "content_sha256",
                "lineage_verification",
                "rows",
                "schema",
                "schema_version",
                "study_id",
            },
            "FactorObservationTableV1",
        )
        if data["schema"] != "FactorObservationTableV1" or data["schema_version"] != 1:
            raise DataError("unsupported FactorObservationTableV1 schema")
        if data["authority"] != "none" or data["lineage_verification"] != "unverified_reference":
            raise DataError("FactorObservationTableV1 cannot claim authority or verified lineage")
        rows = data["rows"]
        if not isinstance(rows, list):
            raise DataError("rows must be a list")
        return cls(
            study_id=_text("study_id", data["study_id"]),
            rows=tuple(FactorObservationV1.from_dict(_mapping(row, "factor row")) for row in rows),
            content_sha256=_hash("content_sha256", data["content_sha256"]),
        )
