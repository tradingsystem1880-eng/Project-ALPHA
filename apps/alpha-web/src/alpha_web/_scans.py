"""Rule scans and their alert log via the CLI (``alpha scan … --json``).

Every call subprocesses the audited CLI; the web layer never evaluates a rule or touches the alert
log itself. Saving/deleting a scan touches the owner's ``data_dir/scans/`` files only;
``authority: none`` throughout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json


def list_scans(*, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(["scan", "list", "--json"], data_dir=data_dir)
    return result


def show(name: str, *, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(["scan", "show", name, "--json"], data_dir=data_dir)
    return result


def save(name: str, rules: str, symbols: list[str] | None, *, data_dir: Path) -> dict[str, Any]:
    args = ["scan", "save", name, "--rules", rules, "--json"]
    if symbols:
        args += ["--symbols", ",".join(symbols)]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    return result


def delete(name: str, *, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(["scan", "delete", name, "--json"], data_dir=data_dir)
    return result


def run(name: str, as_of: str | None, *, data_dir: Path) -> dict[str, Any]:
    args = ["scan", "run", name, "--json"]
    if as_of:
        args += ["--as-of", as_of]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir, timeout_seconds=600.0)
    return result


def check(name: str | None, *, data_dir: Path) -> dict[str, Any]:
    args = ["scan", "check", *([name] if name else []), "--json"]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir, timeout_seconds=600.0)
    return result


def alerts(limit: int, *, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(
        ["scan", "alerts", "--limit", str(limit), "--json"], data_dir=data_dir
    )
    return result
