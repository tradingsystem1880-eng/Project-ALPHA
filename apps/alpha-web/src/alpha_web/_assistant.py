"""Thin subprocess projection over the CLI-owned advisory assistant journal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json


def readiness(*, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(["assistant", "readiness", "--json"], data_dir=data_dir)
    return result


def create(context: dict[str, Any], *, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(
        ["assistant", "create", "--context", json.dumps(context), "--json"],
        data_dir=data_dir,
        timeout_seconds=180,
    )
    return result


def show(session_id: str, *, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(
        ["assistant", "show", session_id, "--json"], data_dir=data_dir
    )
    return result


def check(session_id: str, *, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(
        ["assistant", "check", session_id, "--json"], data_dir=data_dir, timeout_seconds=180
    )
    return result
