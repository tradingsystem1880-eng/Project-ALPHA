"""Subprocess the CLI's JSON catalogs (strategies, commands, symbols) — the source of truth.

The strategy + command catalogs are static (they describe the code, not the store), so they are
cached after the first call; symbols depend on the store and are read fresh each time.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

_ALPHA_BIN = "alpha"

#: Bounded wall-clock ceiling for every synchronous ``alpha`` projection. A hung CLI child must
#: surface as a typed error (the routers' 422) instead of pinning the request thread forever;
#: genuinely long launch-style calls pass an explicit larger — still finite — value.
DEFAULT_TIMEOUT_SECONDS = 60.0

# Typer/Rich decorate CLI output with terminal escapes (CSI such as ``\x1b[2m`` plus OSC
# sequences terminated by BEL or ST). Strip both before output lands in an HTTP error detail.
_ANSI_CSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_ANSI_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def _strip_ansi(text: str) -> str:
    """Remove ANSI CSI/OSC escapes (and any stray ESC bytes), keeping the semantic text intact."""
    return _ANSI_CSI.sub("", _ANSI_OSC.sub("", text)).replace("\x1b", "")


def _command(args: list[str]) -> list[str]:
    """The argv to spawn (seam: tests monkeypatch this with a fake command)."""
    return [_ALPHA_BIN, *args]


def _run_json(
    args: list[str], *, data_dir: Path, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
) -> Any:
    env = {**os.environ, "ALPHA_DATA_DIR": str(data_dir)}
    try:
        proc = subprocess.run(
            _command(args),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"alpha {' '.join(args)} timed out after {timeout_seconds:g} seconds"
        ) from exc
    if proc.returncode != 0:
        stderr = _strip_ansi(proc.stderr).strip()
        stdout = _strip_ansi(proc.stdout).strip()
        raise RuntimeError(stderr or stdout or f"alpha {args} failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        # e.g. an option-shaped argument makes the CLI print help with exit 0; the routers
        # map RuntimeError to a typed 4xx, never a 500.
        raise RuntimeError(f"alpha {' '.join(args)} did not return valid JSON") from exc


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
