"""Subprocess the CLI's research flows (``alpha research compare --json``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json


def compare(*, data_dir: Path, symbol: str, strategies: str = "") -> dict[str, Any]:
    """Rank the registered strategies on ``symbol`` by a full backtest of each."""
    args = ["research", "compare", symbol, "--json"]
    if strategies:
        args += ["--strategies", strategies]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    return result
