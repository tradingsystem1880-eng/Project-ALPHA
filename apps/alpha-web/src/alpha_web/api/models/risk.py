"""Risk reports and their nested contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

from ._base import StrictModel


class RiskScenario(StrictModel):
    name: str
    sharpe: float | None
    annual_vol: float
    max_drawdown: float
    value_at_risk: float
    expected_shortfall: float
    total_return: float


class RiskMetricBasis(StrictModel):
    """Versioned projection conventions; no claim of verified initial capital or flows."""

    schema_version: Annotated[int, Field(strict=True, ge=1, le=1)]
    anchor_kind: Literal["first_recorded_equity"]
    anchor_ts: Annotated[str, Field(strict=True, min_length=1)]
    anchor_value: Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
    anchor_units: Literal["recorded_equity_units"]
    initial_capital_status: Literal["unknown"]
    external_cash_flow_status: Literal["unknown"]
    return_accumulation: Literal["compounded_simple_returns"]
    drawdown_convention: Literal["non_positive_fraction_from_scenario_wealth_peaks"]
    benchmark_adjustment: Literal["none_by_projection"]
    pre_anchor_losses: Literal["not_measured"]

    @field_validator("anchor_ts")
    @classmethod
    def _iso_timestamp(cls, value: str) -> str:
        # Preserve the recorded representation; parsing does not verify UTC,
        # ordering, or that this row was the actual initial-capital observation.
        datetime.fromisoformat(value)
        return value


class RiskProvenance(StrictModel):
    source_run_id: str
    source_command: str | None
    source_artifact: Literal["equity_curve.parquet"]
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str | None
    snapshot_hash: str | None
    research_cutoff: str | None
    as_of: str | None
    timezone: Literal["UTC"]
    derived_projection: Literal[True]
    metric_namespace: Literal["alpha_validation.scenario"]
    periods_per_year: int
    confidence: float
    metric_basis: RiskMetricBasis | None = None


class RiskReport(StrictModel):
    run_id: str
    confidence: float
    scenarios: list[RiskScenario]
    provenance: RiskProvenance
