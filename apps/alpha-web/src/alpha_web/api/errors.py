"""Stable, redacted API errors shared by JSON and SSE entry points."""

from __future__ import annotations

import os
import re
import secrets
from collections.abc import Sequence
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from alpha_web.api.models import ApiErrorV1, ApiFieldErrorV1

_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
_PRIVATE_PATH = re.compile(r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\(?:[^\\\s]+\\)+[^\\\s]+")
_IBKR_ACCOUNT = re.compile(r"\bDU\d{4,}\b", re.IGNORECASE)


def request_id(request: Request) -> str:
    current = getattr(request.state, "request_id", None)
    if isinstance(current, str) and current:
        return current
    current = secrets.token_hex(16)
    request.state.request_id = current
    return current


def safe_message(value: object, *, fallback: str) -> str:
    """Remove terminal, traceback, path, credential, account, and raw-response content."""
    if not isinstance(value, str):
        return fallback
    text = _ANSI.sub("", value).strip()
    if not text or "traceback" in text.casefold() or text.startswith(("{", "[", "<")):
        return fallback
    for name, secret in os.environ.items():
        upper = name.upper()
        if (
            any(marker in upper for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
            and len(secret) >= 4
        ):
            text = text.replace(secret, "[redacted]")
    text = _IBKR_ACCOUNT.sub("DU…", text)
    text = _PRIVATE_PATH.sub("[redacted-path]", text)
    text = " ".join(text.split())
    return text[:500] or fallback


def error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "request_invalid",
        429: "rate_limited",
        503: "service_unavailable",
    }.get(status_code, "request_failed" if status_code < 500 else "internal_error")


def recovery_action(status_code: int) -> str:
    if status_code == 404:
        return "Refresh the current workspace and select an available record."
    if status_code == 409:
        return "Refresh the current project state, resolve the blocker, and retry."
    if status_code == 422:
        return "Review the highlighted fields or blocker and submit a supported value."
    if status_code >= 500:
        return "Retry once; if the failure persists, inspect the local Workstation logs."
    return "Review the request and try again."


def api_error_response(
    request: Request,
    *,
    status_code: int,
    message: object,
    field_errors: list[ApiFieldErrorV1] | None = None,
) -> JSONResponse:
    fallback = (
        "The Workstation could not complete this request."
        if status_code >= 500
        else "The request could not be completed."
    )
    rid = request_id(request)
    body = ApiErrorV1(
        code=error_code(status_code),
        message=safe_message(message, fallback=fallback),
        recovery_action=recovery_action(status_code),
        field_errors=field_errors or [],
        request_id=rid,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
        headers={"x-request-id": rid},
    )


def validation_field_errors(errors: Sequence[Any]) -> list[ApiFieldErrorV1]:
    result: list[ApiFieldErrorV1] = []
    for error in errors[:50]:
        if not isinstance(error, dict):
            continue
        location = error.get("loc", ())
        parts = [str(part) for part in location if part not in {"body", "query", "path"}]
        result.append(
            ApiFieldErrorV1(
                field=".".join(parts) or "request",
                message=safe_message(error.get("msg"), fallback="invalid value"),
            )
        )
    return result
