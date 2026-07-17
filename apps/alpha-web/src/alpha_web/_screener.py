"""Subprocess the CLI's screener (``alpha screener quote/news --json``; needs a finnhub key)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json


def quote(*, data_dir: Path, symbol: str) -> dict[str, Any]:
    """A live quote for ``symbol`` (raises ``RuntimeError`` if the key/network is missing)."""
    result: dict[str, Any] = _run_json(["screener", "quote", symbol, "--json"], data_dir=data_dir)
    return result


def news(*, data_dir: Path, symbol: str, days: int, limit: int) -> dict[str, Any]:
    """Recent company news for ``symbol``."""
    args = ["screener", "news", symbol, "--days", str(days), "--limit", str(limit), "--json"]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    return result
