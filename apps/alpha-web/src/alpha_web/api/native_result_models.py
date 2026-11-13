"""Versioned read-only native-job response, never a canonical run or scientific admission."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StrictBool,
    StrictInt,
    model_validator,
)

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identity = Annotated[str, Field(min_length=1, max_length=200)]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)


class NativeDispatch(_Closed):
    job_id: UUID
    reservation_id: Identity
    owner_id: Identity
    spec_sha256: Digest
    profile_sha256: Digest


class NativeProvenance(_Closed):
    receipt_sha256: Digest | None = None
    trace_sha256: Digest | None = None
    checkpoint_sha256: Digest | None = None
    owner_receipt_match: Literal["verified", "mismatch", "unavailable"]


class NativeRequest(_Closed):
    schema_: Literal["StockRDLoopFixtureRequestV1"] = Field(alias="schema")
    job_id: UUID
    reservation_id: Identity
    owner_id: Identity
    spec_sha256: Digest
    manifest_sha256: Digest
    loop_steps: Annotated[StrictInt, Field(ge=5, le=5)]
    model_calls: Annotated[StrictInt, Field(ge=2, le=2)]
    tool_calls: Annotated[StrictInt, Field(ge=2, le=2)]
    cpu_milliseconds: Annotated[StrictInt, Field(ge=1, le=60000)]
    mode: Literal["resume"]


class NativeReceipt(_Closed):
    schema_: Literal["StockRDLoopReceiptV1"] = Field(alias="schema")
    request: NativeRequest
    source_sha256: Literal["0266b2d63328f88fcaf6f239bf6d67f29c896b8161566f794ef69465b7788707"]
    trace_sha256: Digest
    checkpoint_sha256: Digest
    charged_stages: tuple[
        Literal["direct_exp_gen"],
        Literal["coding"],
        Literal["running"],
        Literal["feedback"],
        Literal["record"],
    ]
    fake_model_attempts: Annotated[StrictInt, Field(ge=2, le=2)]
    fake_tool_attempts: Annotated[StrictInt, Field(ge=2, le=2)]
    actual_model_calls: Annotated[StrictInt, Field(ge=0, le=0)]
    resumed_without_repeating: StrictBool
    checkpoint_unchanged: StrictBool
    replay_rejected: StrictBool
    routes_enabled: StrictBool
    scientific_acceptance: Literal["not_admitted"]

    @model_validator(mode="after")
    def fixed_fixture(self) -> NativeReceipt:
        if (
            self.routes_enabled
            or not self.resumed_without_repeating
            or not self.checkpoint_unchanged
            or not self.replay_rejected
        ):
            raise ValueError("native receipt fixture bounds differ")
        return self


class NativeResult(_Closed):
    synthetic_score: FiniteFloat
    unit: Literal["fixture_only"]


class NativeFeedback(_Closed):
    decision: StrictBool
    acceptable: StrictBool

    @model_validator(mode="after")
    def unaccepted(self) -> NativeFeedback:
        if self.decision or self.acceptable:
            raise ValueError("native fixture feedback cannot admit research")
        return self


class NativeJobResultV1(_Closed):
    schema_: Literal["NativeStockOperatorResultV1"] = Field(alias="schema")
    operation: Literal["recover_native_stock_result"]
    classification: Literal["synthetic_only_unqualified"]
    status: Literal["completed", "invalid", "unavailable"]
    reason: Annotated[str, Field(max_length=256)]
    dispatch: NativeDispatch | None = None
    provenance: NativeProvenance | None = None
    receipt: NativeReceipt | None = None
    result: NativeResult | None = None
    feedback: NativeFeedback | None = None
    resume_allowed: StrictBool
    scientific_acceptance: Literal["not_admitted"]

    @model_validator(mode="after")
    def no_promotion(self) -> NativeJobResultV1:
        if self.resume_allowed:
            raise ValueError("native result read cannot grant resume")
        values = {"receipt", "result", "feedback"} & self.model_fields_set
        if self.status != "completed":
            if values:
                raise ValueError("incomplete native result cannot expose values")
            return self
        if (
            values != {"receipt", "result", "feedback"}
            or self.receipt is None
            or self.result is None
            or self.feedback is None
            or self.dispatch is None
            or self.provenance is None
            or self.provenance.owner_receipt_match != "verified"
        ):
            raise ValueError("completed native result requires verified bindings")
        request = self.receipt.request
        if (
            request.job_id != self.dispatch.job_id
            or request.reservation_id != self.dispatch.reservation_id
            or request.owner_id != self.dispatch.owner_id
            or request.spec_sha256 != self.dispatch.spec_sha256
            or self.receipt.trace_sha256 != self.provenance.trace_sha256
            or self.receipt.checkpoint_sha256 != self.provenance.checkpoint_sha256
            or self.provenance.receipt_sha256 is None
        ):
            raise ValueError("completed native result identities differ")
        return self
