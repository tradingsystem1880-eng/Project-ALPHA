"""Read-only canonical rule checklist contracts; archive/run contexts are not accepted."""

from datetime import date
from typing import Literal

from pydantic import Field, field_validator

from alpha_web.api.models import StrictModel


class RuleEvaluationRequest(StrictModel):
    rules_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    symbol: str = Field(min_length=1, max_length=120)
    as_of: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("as_of")
    @classmethod
    def valid_date(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value)
        return value

    @field_validator("symbol")
    @classmethod
    def valid_symbol(cls, value: str) -> str:
        if (
            value.startswith(("/", "-"))
            or ".." in value
            or "\\" in value
            or any(c.isspace() for c in value)
        ):
            raise ValueError("symbol must be a canonical stored instrument")
        return value


class RuleConditionEvaluation(StrictModel):
    side: Literal["long", "short"]
    index: int = Field(ge=0)
    label: str
    left: float | None = Field(allow_inf_nan=False)
    right: float | None = Field(allow_inf_nan=False)
    status: Literal["pass", "fail", "unavailable"]
    reason: str | None


class RuleEvaluationResponse(StrictModel):
    schema_version: Literal[1]
    rules_id: str
    rules_sha256: str | None
    symbol: str
    as_of: str | None
    bar_ts: float | None = Field(allow_inf_nan=False)
    signal: Literal[-1, 0, 1] | None
    conditions: list[RuleConditionEvaluation]
    error: str | None
    authority: Literal["none"]
