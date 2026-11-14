"""Verified and blind semantic reads."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ._base import (
    _LOWER_HEX_16,
    _LOWER_HEX_64,
    _canonical_point_id,
    _canonical_utc_z,
    _FrozenSemanticModel,
)


class SemanticPointV1(_FrozenSemanticModel):
    point_id: str
    available_at: str
    value: float

    _point_id = field_validator("point_id", mode="before")(_canonical_point_id)
    _available_at = field_validator("available_at", mode="before")(_canonical_utc_z)

    @field_validator("value", mode="before")
    @classmethod
    def _finite_float(cls, value: object) -> float:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("value must be a finite float")
        return value


class BlindSemanticProjectionV1(_FrozenSemanticModel):
    schema_: Literal["BlindSemanticProjectionV1"] = Field(
        alias="schema", serialization_alias="schema"
    )
    schema_version: Literal[1]
    run_id: str
    acceptance_artifact_sha256: str
    events_artifact_sha256: str
    chart_data_artifact_sha256: str
    cutoff_confirmed_at: str
    points: list[SemanticPointV1]
    masked_count: int
    authority: Literal["none"]
    cutoff_source: Literal["d0_acceptance_measurement_reference"]
    lineage_verification: Literal["not_checked"]
    semantic_status: Literal["unfrozen"]
    content_sha256: str

    _cutoff_confirmed_at = field_validator("cutoff_confirmed_at", mode="before")(_canonical_utc_z)

    @field_validator("run_id")
    @classmethod
    def _run_id(cls, value: str) -> str:
        if _LOWER_HEX_16.fullmatch(value) is None:
            raise ValueError("run_id must be lowercase 16-character hex")
        return value

    @field_validator(
        "acceptance_artifact_sha256",
        "events_artifact_sha256",
        "chart_data_artifact_sha256",
        "content_sha256",
    )
    @classmethod
    def _sha256(cls, value: str) -> str:
        if _LOWER_HEX_64.fullmatch(value) is None:
            raise ValueError("value must be lowercase 64-character SHA-256 hex")
        return value

    @field_validator("masked_count", mode="before")
    @classmethod
    def _nonnegative_count(cls, value: object) -> int:
        if type(value) is not int or value < 0:
            raise ValueError("masked_count must be a non-negative integer")
        return value


class VerifiedBlindSemanticReadV1(_FrozenSemanticModel):
    schema_: Literal["VerifiedBlindSemanticReadV1"] = Field(
        alias="schema", serialization_alias="schema"
    )
    schema_version: Literal[1]
    source_verification: Literal["verified_completed_d0_recomputation"]
    authority: Literal["none"]
    run_id: str
    projection: BlindSemanticProjectionV1
    content_sha256: str

    @field_validator("run_id")
    @classmethod
    def _run_id(cls, value: str) -> str:
        if _LOWER_HEX_16.fullmatch(value) is None:
            raise ValueError("run_id must be lowercase 16-character hex")
        return value

    @field_validator("content_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if _LOWER_HEX_64.fullmatch(value) is None:
            raise ValueError("content_sha256 must be lowercase 64-character SHA-256 hex")
        return value

    @model_validator(mode="after")
    def _matching_run_id(self) -> VerifiedBlindSemanticReadV1:
        if self.projection.run_id != self.run_id:
            raise ValueError("run_id must match the blind semantic projection")
        return self
