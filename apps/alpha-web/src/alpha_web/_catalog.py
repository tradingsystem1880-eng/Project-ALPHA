"""Subprocess the CLI's JSON catalogs (strategies, commands, symbols) — the source of truth.

The strategy + command catalogs are static (they describe the code, not the store), so they are
cached after the first call; symbols depend on the store and are read fresh each time.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

_ALPHA_BIN = "alpha"


def _command(args: list[str]) -> list[str]:
    """The argv to spawn (seam: tests monkeypatch this with a fake command)."""
    return [_ALPHA_BIN, *args]


def _run_json(args: list[str], *, data_dir: Path) -> Any:
    env = {**os.environ, "ALPHA_DATA_DIR": str(data_dir)}
    proc = subprocess.run(_command(args), capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"alpha {args} failed")
    return json.loads(proc.stdout)


_STRATEGIES_CACHE: list[dict[str, Any]] | None = None
_COMMANDS_CACHE: list[dict[str, Any]] | None = None


def strategies(*, data_dir: Path) -> list[dict[str, Any]]:
    """The registered strategies + their tunable ``--param`` axes (cached; store-independent)."""
    global _STRATEGIES_CACHE
    if _STRATEGIES_CACHE is None:
        _STRATEGIES_CACHE = _run_json(["info", "strategies", "--json"], data_dir=data_dir)
    return _STRATEGIES_CACHE


def commands(*, data_dir: Path) -> list[dict[str, Any]]:
    """The CLI command tree (flags + defaults) for the new-run form (cached; store-independent)."""
    global _COMMANDS_CACHE
    if _COMMANDS_CACHE is None:
        _COMMANDS_CACHE = _run_json(["info", "commands", "--json"], data_dir=data_dir)
    return _COMMANDS_CACHE


def symbols(*, data_dir: Path) -> dict[str, list[str]]:
    """Every symbol with stored bars (read fresh — it changes as data is pulled)."""
    result: dict[str, list[str]] = _run_json(["data", "symbols", "--json"], data_dir=data_dir)
    return result


def providers(*, data_dir: Path) -> list[dict[str, Any]]:
    """Provider capability/configuration registry (fresh so credential presence can change)."""
    result: list[dict[str, Any]] = _run_json(["info", "providers", "--json"], data_dir=data_dir)
    return result


def system(*, data_dir: Path) -> dict[str, Any]:
    """Local system readiness (fresh because store, disk, and opt-in state can change)."""
    result: dict[str, Any] = _run_json(["info", "system", "--json"], data_dir=data_dir)
    return result
