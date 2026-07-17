"""Subprocess the CLI's risk scenarios (``alpha risk scenario --from-run … --json``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json


def scenario(*, data_dir: Path, run_id: str, confidence: float) -> dict[str, Any]:
    """Stress scenarios (vol scaling + tail shocks) for a stored run's return stream."""
    args = ["risk", "scenario", "--from-run", run_id, "--confidence", str(confidence), "--json"]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    return result
