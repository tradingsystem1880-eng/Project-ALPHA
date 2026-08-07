"""Immutable, canonical research artifact and chart-data contracts."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from alpha_core import DataError
from alpha_research._canonical import canonical_sha256

ArtifactKind = Literal["table", "chart", "report", "manifest"]
ChartEvidencePhase = Literal["exploratory", "confirmatory"]
ChartWatermark = Literal["EXPLORATORY", "REGISTERED CONFIRMATORY"]
_ARTIFACT_KINDS = {"table", "chart", "report", "manifest"}
_CHART_PHASES = {"exploratory", "confirmatory"}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"{name} must be non-empty")


def _hash(name: str, value: object) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise DataError(f"{name} must be a lowercase 64-character SHA-256 digest")


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataError("chart timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ResearchArtifactRef:
    artifact_id: str
    kind: ArtifactKind
    media_type: str
    content_sha256: str
    size_bytes: int
    row_count: int | None = None

    def __post_init__(self) -> None:
        _text("artifact_id", self.artifact_id)
        _text("media_type", self.media_type)
        if self.kind not in _ARTIFACT_KINDS:
            raise DataError(f"unsupported research artifact kind {self.kind!r}")
        _hash("content_sha256", self.content_sha256)
        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes < 0
        ):
            raise DataError("size_bytes must be a non-negative integer")
        if self.row_count is not None and (
            isinstance(self.row_count, bool)
            or not isinstance(self.row_count, int)
            or self.row_count < 0
        ):
            raise DataError("row_count must be a non-negative integer when supplied")

    def to_dict(self) -> dict[str, int | str | None]:
        return {
            "artifact_id": self.artifact_id,
            "content_sha256": self.content_sha256,
            "kind": self.kind,
            "media_type": self.media_type,
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
        }

    @property
    def contract_hash(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ResearchChartPoint:
    ts: datetime
    value: float

    def __post_init__(self) -> None:
        _utc_iso(self.ts)
        if not math.isfinite(self.value):
            raise DataError("ResearchChartPoint.value must be finite")

    def to_dict(self) -> dict[str, float | str]:
        return {"ts": _utc_iso(self.ts), "value": self.value}


@dataclass(frozen=True, slots=True)
class ResearchChartSeries:
    series_id: str
    label: str
    unit: str
    points: tuple[ResearchChartPoint, ...]

    def __post_init__(self) -> None:
        for name in ("series_id", "label", "unit"):
            _text(name, getattr(self, name))
        if not isinstance(self.points, tuple) or not self.points:
            raise DataError("ResearchChartSeries requires a non-empty tuple of points")
        if any(
            current.ts <= previous.ts
            for previous, current in zip(self.points, self.points[1:], strict=False)
        ):
            raise DataError("ResearchChartSeries timestamps must be strictly increasing")

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "points": [point.to_dict() for point in self.points],
            "series_id": self.series_id,
            "unit": self.unit,
        }


@dataclass(frozen=True, slots=True)
class ResearchChartData:
    chart_id: str
    title: str
    x_label: str
    y_label: str
    evidence_phase: ChartEvidencePhase
    dataset_sha256: str
    protocol_sha256: str
    question: str
    plain_language_answer: str
    sample_size: int
    effective_sample_size: float
    uncertainty: str
    caveat: str
    run_id: str
    artifact_id: str
    artifact_sha256: str
    series: tuple[ResearchChartSeries, ...]

    def __post_init__(self) -> None:
        for name in (
            "chart_id",
            "title",
            "x_label",
            "y_label",
            "question",
            "plain_language_answer",
            "uncertainty",
            "caveat",
            "run_id",
            "artifact_id",
        ):
            _text(name, getattr(self, name))
        if self.evidence_phase not in _CHART_PHASES:
            raise DataError(f"unsupported chart evidence phase {self.evidence_phase!r}")
        _hash("dataset_sha256", self.dataset_sha256)
        _hash("protocol_sha256", self.protocol_sha256)
        _hash("artifact_sha256", self.artifact_sha256)
        if (
            isinstance(self.sample_size, bool)
            or not isinstance(self.sample_size, int)
            or self.sample_size < 1
        ):
            raise DataError("sample_size must be an integer >= 1")
        if (
            not math.isfinite(self.effective_sample_size)
            or not 0.0 < self.effective_sample_size <= self.sample_size
        ):
            raise DataError("effective_sample_size must be finite in (0, sample_size]")
        if not isinstance(self.series, tuple) or not self.series:
            raise DataError("ResearchChartData requires a non-empty tuple of series")
        series_ids = [item.series_id for item in self.series]
        if len(series_ids) != len(set(series_ids)):
            raise DataError("ResearchChartData series_id values must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_sha256": self.artifact_sha256,
            "caveat": self.caveat,
            "chart_id": self.chart_id,
            "dataset_sha256": self.dataset_sha256,
            "evidence_phase": self.evidence_phase,
            "effective_sample_size": self.effective_sample_size,
            "plain_language_answer": self.plain_language_answer,
            "protocol_sha256": self.protocol_sha256,
            "question": self.question,
            "run_id": self.run_id,
            "sample_size": self.sample_size,
            "schema_version": 1,
            "series": [
                item.to_dict() for item in sorted(self.series, key=lambda item: item.series_id)
            ],
            "title": self.title,
            "uncertainty": self.uncertainty,
            "watermark": self.watermark,
            "x_label": self.x_label,
            "y_label": self.y_label,
        }

    @property
    def watermark(self) -> ChartWatermark:
        if self.evidence_phase == "exploratory":
            return "EXPLORATORY"
        return "REGISTERED CONFIRMATORY"

    @property
    def contract_hash(self) -> str:
        return canonical_sha256(self.to_dict())
