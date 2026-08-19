"""Validated context attached by the Workstation to empirical child processes."""

from __future__ import annotations

import json
import os
from typing import cast

from alpha_core import DataError

RUN_CONTEXT_ENV = "ALPHA_RUN_CONTEXT_JSON"
STANDALONE_UNQUALIFIED = "STANDALONE_UNQUALIFIED"
LEGACY_CONTEXT_UNKNOWN = "LEGACY_CONTEXT_UNKNOWN"


def run_context_from_environment() -> dict[str, object] | None:
    """Return a validated V1 run context, or ``None`` for historical/direct CLI runs."""
    text = os.environ.get(RUN_CONTEXT_ENV)
    if text is None:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataError("invalid Workstation run context JSON") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise DataError("invalid Workstation run context: expected an object")
    context = cast(dict[str, object], value)
    kind = context.get("kind")
    if context.get("schema_version") != 1:
        raise DataError("invalid Workstation run context schema version")
    if kind == "standalone_sandbox":
        expected = {"schema_version", "kind", "watermark"}
        if set(context) != expected or context.get("watermark") != STANDALONE_UNQUALIFIED:
            raise DataError("invalid standalone Workstation run context")
    elif kind == "governed_project":
        required = {"schema_version", "kind", "project_id", "research_gate_state"}
        allowed = required | {"watermark"}
        project_id = context.get("project_id")
        gate_state = context.get("research_gate_state")
        if (
            not required.issubset(context)
            or not set(context).issubset(allowed)
            or not isinstance(project_id, str)
            or not project_id
            or gate_state not in {"passed", "not_required", "overridden"}
        ):
            raise DataError("invalid governed-project Workstation run context")
        expected_watermark = "EXPLORATORY" if gate_state == "overridden" else None
        if context.get("watermark") != expected_watermark:
            raise DataError("invalid governed-project Workstation run context watermark")
    else:
        raise DataError("invalid Workstation run context kind")
    return context
