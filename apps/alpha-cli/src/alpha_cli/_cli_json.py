"""Shared CLI JSON output and object options."""

from __future__ import annotations

import json
from typing import cast

import typer


def emit(value: object, *, json_out: bool, fallback: str) -> None:
    if json_out:
        typer.echo(json.dumps(value, sort_keys=True, allow_nan=False))
    else:
        typer.echo(fallback)


def json_object_option(raw: str, label: str) -> dict[str, object]:
    try:
        value: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{label} must be a valid JSON object") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise typer.BadParameter(f"{label} must be a valid JSON object")
    return cast(dict[str, object], value)
