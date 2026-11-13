"""Read-only caller-grid projection; no source completeness or admission authority."""

from __future__ import annotations

from datetime import timedelta
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from .models import StrictModel


class RetainedCoverageRequest(StrictModel):
    coverage_start: AwareDatetime
    coverage_end: AwareDatetime
    as_of: AwareDatetime
    expected_cadence_seconds: Literal[86400]
    max_verify_artifact_bytes: int = Field(strict=True, ge=1, le=2**63 - 1)
    max_input_bytes: int = Field(default=32 * 1024 * 1024, strict=True, ge=1, le=32 * 1024 * 1024)
    max_rows: int = Field(default=50000, strict=True, ge=1, le=50000)
    max_missing_ranges: int = Field(default=1000, strict=True, ge=1, le=1000)
    max_verify_metadata_bytes: int = Field(
        default=32 * 1024 * 1024, strict=True, ge=1, le=32 * 1024 * 1024
    )

    @model_validator(mode="after")
    def closed_grid(self) -> Self:
        duration = self.coverage_end - self.coverage_start
        if (
            duration <= timedelta(0)
            or duration % timedelta(days=1)
            or self.coverage_end > self.as_of
        ):
            raise ValueError("Declare whole daily periods with exclusive end at or before as_of")
        return self


class RetainedMissingRange(StrictModel):
    start: str
    end: str
    slots: int = Field(strict=True, ge=1)


class RetainedCoverageRows(StrictModel):
    grid_basis: Literal["caller_declared_start_and_native_daily_cadence"]
    start: AwareDatetime
    end_exclusive: AwareDatetime
    as_of: AwareDatetime
    cadence_seconds: Literal[86400]
    expected_slots: int = Field(strict=True, ge=1)
    covered_slots: int = Field(strict=True, ge=0)
    missing_slots: int = Field(strict=True, ge=0)
    missing_ranges: list[RetainedMissingRange] = Field(max_length=1000)
    missing_range_count: int = Field(strict=True, ge=0)
    missing_ranges_truncated: bool
    row_count: int = Field(strict=True, ge=0)
    in_window_rows: int = Field(strict=True, ge=0)
    outside_window_rows: int = Field(strict=True, ge=0)
    invalid_timestamp_rows: int = Field(strict=True, ge=0)
    invalid_close_timestamp_rows: int = Field(strict=True, ge=0)
    off_grid_rows: int = Field(strict=True, ge=0)
    invalid_numeric_rows: int = Field(strict=True, ge=0)
    duplicate_timestamp_groups: int = Field(strict=True, ge=0)
    duplicate_extra_rows: int = Field(strict=True, ge=0)
    conflicting_duplicate_groups: int = Field(strict=True, ge=0)
    identical_duplicate_groups: int = Field(strict=True, ge=0)
    failures: list[str]
    warnings: list[str]
    audited_columns: list[str]
    declared_grid_satisfied: bool
    provider_history_complete: Literal[False]
    point_in_time_eligibility: Literal[False]
    execution_authority: Literal[False]


class RetainedCoverageLimits(StrictModel):
    normalized_payload_bytes: int
    payload_read_bytes: int
    returned_rows: int
    missing_ranges: int
    artifact_hash_bytes: int
    metadata_bytes: int


class RetainedStoredQuality(StrictModel):
    state: Literal["qualified", "warning", "quarantined", "unavailable"]
    row_count: int
    method_version: str
    unchanged: Literal[True]


class RetainedCoverageResponse(StrictModel):
    manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_state: Literal["inspected", "unavailable"]
    reason: Literal["RETAINED_GRID_INSPECTED", "RETAINED_BAR_AUDIT_UNAVAILABLE"]
    row_audit: RetainedCoverageRows | None
    stored_quality: RetainedStoredQuality | None
    limits: RetainedCoverageLimits | None
    hash_bytes_reserved: int = 0
    hash_bytes_read: int = 0
    metadata_bytes_reserved: int = 0
    metadata_bytes_read: int = 0
    source_retrieved_after_as_of: bool | None = None
    provider_history_complete: Literal[False]
    point_in_time_eligibility: Literal[False]
    execution_authority: Literal[False]
    inspection_provider_calls: Literal[0]

    @model_validator(mode="after")
    def diagnostic_state(self) -> Self:
        if self.audit_state == "inspected":
            if self.row_audit is None or self.stored_quality is None or self.limits is None:
                raise ValueError("Inspected coverage requires its exact row and resource evidence")
            if self.reason != "RETAINED_GRID_INSPECTED":
                raise ValueError("Inspected reason differs")
        elif self.row_audit is not None or self.reason != "RETAINED_BAR_AUDIT_UNAVAILABLE":
            raise ValueError("Unavailable coverage cannot expose a successful row audit")
        return self
