"""Public, authority-free assistant inputs. Browser supplies identifiers, never evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssistantContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=80, pattern=r"^\^?[A-Za-z0-9][A-Za-z0-9/_.:=-]*$")
    as_of: datetime
    snapshot_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")
    manifest_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")
    run_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")
    project_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")
    rules_name: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    rules_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_context(self) -> AssistantContext:
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must include a timezone")
        if self.rules_sha256 is not None and self.rules_name is None:
            raise ValueError("rules_sha256 requires rules_name")
        if self.rules_name:
            day_end = self.as_of.astimezone(UTC)
            if (day_end.hour, day_end.minute, day_end.second) != (23, 59, 59):
                raise ValueError("Rule explanations require an explicit UTC end-of-day cutoff")
            # The public rule evaluator accepts a date and includes the entire final second.
            self.as_of = day_end.replace(microsecond=999999)
        if self.snapshot_id and self.manifest_id:
            raise ValueError("choose canonical snapshot or archive manifest")
        if self.manifest_id and self.run_id:
            raise ValueError("archive data cannot substitute for a recorded run snapshot")
        if self.manifest_id and self.rules_name:
            raise ValueError("archive data is not admitted for rule execution")
        return self


class AssistantTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "explain_chart", "explain_signal", "challenge_thesis", "explain_results", "draft_rules"
    ]
    message: str = Field(default="", max_length=4000)


class AssistantSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: AssistantContext


class AssistantAttachment(BaseModel):
    ref: str
    label: str
    content_hash: str


class AssistantAnswer(BaseModel):
    text: str
    citations: list[str]
    rule_draft: dict[str, object] | None


class AssistantTurn(BaseModel):
    turn_id: str
    action: str
    message: str
    status: Literal["running", "completed", "failed", "cancelled", "interrupted"]
    context_hash: str
    answer: AssistantAnswer | None
    error: str | None


class AssistantSession(BaseModel):
    session_id: str
    context: AssistantContext
    context_hash: str
    attachments: list[AssistantAttachment]
    turns: list[AssistantTurn]
    authority: Literal["none"]
    created_at: str
    active_job_id: str | None = None


class AssistantReadiness(BaseModel):
    available: bool
    reason: str | None
    model: str
    isolation_verified: bool


class AssistantContextCheck(BaseModel):
    valid: Literal[True]
    context_hash: str
