"""Pure, byte-bound server-masked blind semantic-read contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

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

_RUN_ID_RE: Final = re.compile(r"[0-9a-f]{16}")
_EVENT_IDENTITY_KEYS: Final = frozenset(
    {
        "first_trough_index",
        "second_trough_index",
        "confirmation_index",
        "first_trough_at",
        "second_trough_at",
        "confirmed_at",
    }
)
_RAW_EVENT_KEYS: Final = frozenset(
    {*_EVENT_IDENTITY_KEYS, "neckline", "trough_difference", "rebound"}
)
_ACCEPTANCE_KEYS: Final = frozenset(
    {
        "schema",
        "schema_version",
        "run_id",
        "project_id",
        "research_contract_id",
        "contract_hash",
        "dataset_hash",
        "execution_fingerprint",
        "d0_operator_fingerprint",
        "fixture_id",
        "fixture_version",
        "evidence_zone",
        "real_market_evidence",
        "eligible_for_holdout_or_execution",
        "measurements",
    }
)
_CHART_KEYS: Final = frozenset(
    {
        "artifact_id",
        "artifact_sha256",
        "caveat",
        "chart_id",
        "dataset_sha256",
        "evidence_phase",
        "effective_sample_size",
        "events",
        "plain_language_answer",
        "protocol_sha256",
        "question",
        "run_id",
        "sample_size",
        "schema_version",
        "series",
        "title",
        "uncertainty",
        "watermark",
        "x_label",
        "y_label",
    }
)


def _index(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DataError(f"{name} must be a non-negative integer")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise DataError(f"{name} must be finite")
    return float(value)


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, float) or not math.isfinite(value):
        raise DataError(f"{name} must be a finite float")
    return value


@dataclass(frozen=True, slots=True)
class SemanticEventIdentityV1:
    """Identity and causal clocks of one registered D0 planted event."""

    first_trough_index: int
    second_trough_index: int
    confirmation_index: int
    first_trough_at: datetime
    second_trough_at: datetime
    confirmed_at: datetime

    def __post_init__(self) -> None:
        for name in ("first_trough_index", "second_trough_index", "confirmation_index"):
            _index(name, getattr(self, name))
        if self.first_trough_index >= self.second_trough_index:
            raise DataError("event identity requires first trough before second trough")
        if self.confirmation_index <= self.second_trough_index:
            raise DataError("event identity requires confirmation after second trough")
        for name in ("first_trough_at", "second_trough_at", "confirmed_at"):
            value = getattr(self, name)
            _utc_iso(value, name)
            object.__setattr__(self, name, value.astimezone(UTC))
        if not self.first_trough_at <= self.second_trough_at <= self.confirmed_at:
            raise DataError("event clocks are not causal")

    @classmethod
    def from_raw(cls, value: Mapping[str, object], *, name: str) -> SemanticEventIdentityV1:
        data = _mapping(value, name)
        _strict_keys(data, set(_RAW_EVENT_KEYS), name)
        for field in ("neckline", "trough_difference", "rebound"):
            _finite(f"{name}.{field}", data[field])
        return cls(
            first_trough_index=_index("first_trough_index", data["first_trough_index"]),
            second_trough_index=_index("second_trough_index", data["second_trough_index"]),
            confirmation_index=_index("confirmation_index", data["confirmation_index"]),
            first_trough_at=_parse_datetime(data["first_trough_at"], "first_trough_at"),
            second_trough_at=_parse_datetime(data["second_trough_at"], "second_trough_at"),
            confirmed_at=_parse_datetime(data["confirmed_at"], "confirmed_at"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "confirmed_at": _utc_iso(self.confirmed_at, "confirmed_at"),
            "confirmation_index": self.confirmation_index,
            "first_trough_at": _utc_iso(self.first_trough_at, "first_trough_at"),
            "first_trough_index": self.first_trough_index,
            "second_trough_at": _utc_iso(self.second_trough_at, "second_trough_at"),
            "second_trough_index": self.second_trough_index,
        }


def normalize_semantic_event(value: Mapping[str, object]) -> SemanticEventIdentityV1:
    """Normalize a complete event payload without executing or consulting a detector."""
    return SemanticEventIdentityV1.from_raw(value, name="semantic event")


@dataclass(frozen=True, slots=True)
class SemanticPointV1:
    """One chart point derived from a published chart-data artifact."""

    point_id: str
    available_at: datetime
    value: float

    def __post_init__(self) -> None:
        _text("point_id", self.point_id)
        _utc_iso(self.available_at, "available_at")
        object.__setattr__(self, "available_at", self.available_at.astimezone(UTC))
        _finite_float("value", self.value)

    def to_dict(self) -> dict[str, object]:
        return {
            "available_at": _utc_iso(self.available_at, "available_at"),
            "point_id": self.point_id,
            "value": self.value,
        }


def _json_bytes(name: str, value: bytes) -> tuple[object, str]:
    if not isinstance(value, bytes):
        raise DataError(f"{name} must be complete JSON bytes")
    digest = hashlib.sha256(value).hexdigest()

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise DataError(f"{name} contains duplicate JSON key {key!r}")
            result[key] = item
        return result

    def reject_constant(constant: str) -> object:
        raise DataError(f"{name} contains non-finite JSON constant {constant}")

    try:
        parsed = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except DataError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f"{name} is not valid UTF-8 JSON") from exc
    return parsed, digest


def _artifact_event_list(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, list):
        raise DataError(f"{name} must be an event JSON array")
    if len(value) != 1:
        raise DataError(f"{name} must contain exactly one event")
    return _mapping(value[0], f"{name} event")


def _acceptance_event(value: object) -> tuple[Mapping[str, object], str]:
    data = _mapping(value, "d0_acceptance.json")
    _strict_keys(data, set(_ACCEPTANCE_KEYS), "d0_acceptance.json")
    if data["schema"] != "ResearchD0AcceptanceV1" or data["schema_version"] != 1:
        raise DataError("d0_acceptance.json schema is unsupported")
    run_id = data["run_id"]
    if not isinstance(run_id, str) or _RUN_ID_RE.fullmatch(run_id) is None:
        raise DataError("d0_acceptance.json run_id is invalid")
    if data["evidence_zone"] != "D0":
        raise DataError("d0_acceptance.json evidence_zone must be D0")
    if (
        data["real_market_evidence"] is not False
        or data["eligible_for_holdout_or_execution"] is not False
    ):
        raise DataError("d0_acceptance.json cannot grant market or execution authority")
    for name in (
        "contract_hash",
        "dataset_hash",
        "execution_fingerprint",
        "d0_operator_fingerprint",
    ):
        _hash(f"d0_acceptance.json {name}", data[name])
    measurements = _mapping(data["measurements"], "d0_acceptance.json measurements")
    _strict_keys(
        measurements,
        {
            "planted_events",
            "monotonic_event_count",
            "single_trough_event_count",
            "topology",
            "power",
        },
        "d0_acceptance.json measurements",
    )
    planted = measurements["planted_events"]
    for name in ("monotonic_event_count", "single_trough_event_count"):
        count = measurements[name]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DataError(f"d0_acceptance.json measurements.{name} must be a count")
    _mapping(measurements["topology"], "d0_acceptance.json measurements.topology")
    _mapping(measurements["power"], "d0_acceptance.json measurements.power")
    return _artifact_event_list(
        planted, name="d0_acceptance.json measurements.planted_events"
    ), run_id


def _chart_points(value: Mapping[str, object]) -> tuple[SemanticPointV1, ...]:
    series = value["series"]
    if not isinstance(series, list) or not series:
        raise DataError("chart-data.json series must be a non-empty array")
    points: list[SemanticPointV1] = []
    series_ids: set[str] = set()
    for item in series:
        data = _mapping(item, "chart series")
        _strict_keys(data, {"label", "points", "series_id", "unit"}, "chart series")
        series_id = _text("chart series_id", data["series_id"])
        if series_id in series_ids:
            raise DataError("chart-data.json series_id values must be unique")
        series_ids.add(series_id)
        raw_points = data["points"]
        if not isinstance(raw_points, list) or not raw_points:
            raise DataError("chart series points must be a non-empty array")
        previous_at: datetime | None = None
        for index, raw_point in enumerate(raw_points):
            point = _mapping(raw_point, "chart point")
            _strict_keys(point, {"ts", "value"}, "chart point")
            available_at = _parse_datetime(point["ts"], "chart point ts")
            if previous_at is not None and available_at <= previous_at:
                raise DataError("chart series timestamps must be strictly increasing")
            previous_at = available_at
            points.append(
                SemanticPointV1(
                    point_id=f"{series_id}:{index}",
                    available_at=available_at,
                    value=_finite_float("chart point value", point["value"]),
                )
            )
    return tuple(
        sorted(
            points, key=lambda item: (_utc_iso(item.available_at, "available_at"), item.point_id)
        )
    )


@dataclass(frozen=True, slots=True)
class BlindSemanticProjectionV1:
    """Immutable, non-authoritative masked semantic-read response."""

    run_id: str
    acceptance_artifact_sha256: str
    events_artifact_sha256: str
    chart_data_artifact_sha256: str
    cutoff_confirmed_at: datetime
    visible_points: tuple[SemanticPointV1, ...]
    masked_count: int
    content_sha256: str | None = None
    authority: str = "none"
    cutoff_source: str = "d0_acceptance_measurement_reference"
    lineage_verification: str = "not_checked"
    semantic_status: str = "unfrozen"

    def __post_init__(self) -> None:
        if _RUN_ID_RE.fullmatch(self.run_id) is None:
            raise DataError("run_id must be lowercase 16-character hex")
        for name in (
            "acceptance_artifact_sha256",
            "events_artifact_sha256",
            "chart_data_artifact_sha256",
        ):
            _hash(f"{name} artifact sha256", getattr(self, name))
        _utc_iso(self.cutoff_confirmed_at, "cutoff_confirmed_at")
        object.__setattr__(self, "cutoff_confirmed_at", self.cutoff_confirmed_at.astimezone(UTC))
        if (
            isinstance(self.masked_count, bool)
            or not isinstance(self.masked_count, int)
            or self.masked_count < 0
        ):
            raise DataError("masked_count must be a non-negative integer")
        if not isinstance(self.visible_points, tuple):
            raise DataError("visible_points must be a tuple of SemanticPointV1")
        if not all(isinstance(point, SemanticPointV1) for point in self.visible_points):
            raise DataError("visible_points must contain only SemanticPointV1 children")
        if any(point.available_at > self.cutoff_confirmed_at for point in self.visible_points):
            raise DataError("visible points must be available by the acceptance cutoff")
        point_ids = [point.point_id for point in self.visible_points]
        if len(point_ids) != len(set(point_ids)):
            raise DataError("visible point IDs must be unique")
        expected_order = tuple(
            sorted(
                self.visible_points,
                key=lambda point: (_utc_iso(point.available_at, "available_at"), point.point_id),
            )
        )
        if self.visible_points != expected_order:
            raise DataError("visible_points must use canonical availability and ID order")
        if (
            self.authority,
            self.cutoff_source,
            self.lineage_verification,
            self.semantic_status,
        ) != ("none", "d0_acceptance_measurement_reference", "not_checked", "unfrozen"):
            raise DataError("blind semantic projection has fixed non-authoritative status")
        expected = canonical_study_sha256(self._semantic_dict())
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected)
        elif _hash("content_sha256", self.content_sha256) != expected:
            raise DataError("content_sha256 does not match blind semantic projection")

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "acceptance_artifact_sha256": self.acceptance_artifact_sha256,
            "authority": self.authority,
            "chart_data_artifact_sha256": self.chart_data_artifact_sha256,
            "cutoff_confirmed_at": _utc_iso(self.cutoff_confirmed_at, "cutoff_confirmed_at"),
            "cutoff_source": self.cutoff_source,
            "events_artifact_sha256": self.events_artifact_sha256,
            "lineage_verification": self.lineage_verification,
            "masked_count": self.masked_count,
            "points": [point.to_dict() for point in self.visible_points],
            "run_id": self.run_id,
            "schema": "BlindSemanticProjectionV1",
            "schema_version": 1,
            "semantic_status": self.semantic_status,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._semantic_dict(), "content_sha256": self.content_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> BlindSemanticProjectionV1:
        data = _mapping(value, "BlindSemanticProjectionV1")
        _strict_keys(data, set(cls._keys()), "BlindSemanticProjectionV1")
        if data["schema"] != "BlindSemanticProjectionV1" or data["schema_version"] != 1:
            raise DataError("unsupported BlindSemanticProjectionV1 schema")
        if (
            data["authority"],
            data["cutoff_source"],
            data["lineage_verification"],
            data["semantic_status"],
        ) != ("none", "d0_acceptance_measurement_reference", "not_checked", "unfrozen"):
            raise DataError("blind semantic projection has fixed non-authoritative status")
        points = data["points"]
        if not isinstance(points, list):
            raise DataError("points must be a JSON array")
        parsed_points: list[SemanticPointV1] = []
        for item in points:
            point = _mapping(item, "point")
            _strict_keys(point, {"available_at", "point_id", "value"}, "point")
            parsed_points.append(
                SemanticPointV1(
                    point_id=_text("point_id", point["point_id"]),
                    available_at=_parse_datetime(point["available_at"], "available_at"),
                    value=_finite_float("value", point["value"]),
                )
            )
        return cls(
            run_id=_text("run_id", data["run_id"]),
            acceptance_artifact_sha256=_hash(
                "acceptance artifact sha256", data["acceptance_artifact_sha256"]
            ),
            events_artifact_sha256=_hash("events artifact sha256", data["events_artifact_sha256"]),
            chart_data_artifact_sha256=_hash(
                "chart-data artifact sha256", data["chart_data_artifact_sha256"]
            ),
            cutoff_confirmed_at=_parse_datetime(data["cutoff_confirmed_at"], "cutoff_confirmed_at"),
            visible_points=tuple(parsed_points),
            masked_count=data["masked_count"] if isinstance(data["masked_count"], int) else -1,
            content_sha256=_hash("content_sha256", data["content_sha256"]),
        )

    @staticmethod
    def _keys() -> tuple[str, ...]:
        return (
            "acceptance_artifact_sha256",
            "authority",
            "chart_data_artifact_sha256",
            "content_sha256",
            "cutoff_confirmed_at",
            "cutoff_source",
            "events_artifact_sha256",
            "lineage_verification",
            "masked_count",
            "points",
            "run_id",
            "schema",
            "schema_version",
            "semantic_status",
        )


def project_blind_semantic_read(
    *, acceptance_bytes: bytes, events_bytes: bytes, chart_data_bytes: bytes
) -> BlindSemanticProjectionV1:
    """Build a masked response from the complete, byte-bound D0 artifacts."""
    acceptance_raw, acceptance_hash = _json_bytes("d0_acceptance.json", acceptance_bytes)
    events_raw, events_hash = _json_bytes("events.json", events_bytes)
    chart_raw, chart_hash = _json_bytes("chart-data.json", chart_data_bytes)
    acceptance_event_raw, run_id = _acceptance_event(acceptance_raw)
    events_event = _artifact_event_list(events_raw, name="events.json")
    chart = _mapping(chart_raw, "chart-data.json")
    _strict_keys(chart, set(_CHART_KEYS), "chart-data.json")
    if (
        chart["schema_version"] != 1
        or chart["evidence_phase"] != "exploratory"
        or chart["watermark"] != "EXPLORATORY"
    ):
        raise DataError("chart-data.json is not an exploratory chart artifact")
    if chart["run_id"] != run_id:
        raise DataError("chart-data.json run_id does not match d0_acceptance.json")
    _hash("chart-data.json dataset_sha256", chart["dataset_sha256"])
    _hash("chart-data.json protocol_sha256", chart["protocol_sha256"])
    acceptance_data = _mapping(acceptance_raw, "d0_acceptance.json")
    if chart["dataset_sha256"] != acceptance_data["dataset_hash"]:
        raise DataError("chart-data.json dataset provenance does not match d0_acceptance.json")
    if chart["protocol_sha256"] != acceptance_data["contract_hash"]:
        raise DataError("chart-data.json protocol provenance does not match d0_acceptance.json")
    series = chart["series"]
    if not isinstance(series, list) or not series:
        raise DataError("chart-data.json series must be a non-empty array")
    _hash("chart-data.json artifact_sha256", chart["artifact_sha256"])
    if len(series) != 1 or chart["artifact_sha256"] != canonical_study_sha256(series[0]):
        raise DataError("chart-data.json artifact_sha256 does not match its series")
    chart_event = _artifact_event_list(chart["events"], name="chart-data.json.events")
    acceptance_event = SemanticEventIdentityV1.from_raw(
        acceptance_event_raw, name="acceptance event"
    )
    if SemanticEventIdentityV1.from_raw(events_event, name="events event") != acceptance_event:
        raise DataError("events event identity or clocks do not match acceptance event")
    if SemanticEventIdentityV1.from_raw(chart_event, name="chart-data event") != acceptance_event:
        raise DataError("chart-data event identity or clocks do not match acceptance event")
    points = _chart_points(chart)
    masked_count = sum(point.available_at > acceptance_event.confirmed_at for point in points)
    visible_points = tuple(
        point for point in points if point.available_at <= acceptance_event.confirmed_at
    )
    return BlindSemanticProjectionV1(
        run_id=run_id,
        acceptance_artifact_sha256=acceptance_hash,
        events_artifact_sha256=events_hash,
        chart_data_artifact_sha256=chart_hash,
        cutoff_confirmed_at=acceptance_event.confirmed_at,
        visible_points=visible_points,
        masked_count=masked_count,
    )


blind_semantic_projection = project_blind_semantic_read

__all__ = [
    "BlindSemanticProjectionV1",
    "SemanticEventIdentityV1",
    "SemanticPointV1",
    "blind_semantic_projection",
    "normalize_semantic_event",
    "project_blind_semantic_read",
]
