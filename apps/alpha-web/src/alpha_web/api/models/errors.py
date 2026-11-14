"""API error responses."""

from __future__ import annotations

from typing import Literal

from ._base import StrictModel


class ApiFieldErrorV1(StrictModel):
    field: str
    message: str


class ApiErrorV1(StrictModel):
    schema_version: Literal[1] = 1
    code: str
    message: str
    recovery_action: str
    field_errors: list[ApiFieldErrorV1]
    request_id: str
