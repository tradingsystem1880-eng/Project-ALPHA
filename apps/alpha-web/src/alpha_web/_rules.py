"""Owner rule strategies via the CLI (``alpha rules … --json``): list, show, save, validate, delete.

Every call is a subprocess of the audited CLI; the web layer never parses a rule itself. Saving
and deleting touch only the owner's ``data_dir/rules/`` files and confer no authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json


def list_rules(*, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(["rules", "list", "--json"], data_dir=data_dir)
    return result


def show(name: str, *, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(["rules", "show", name, "--json"], data_dir=data_dir)
    return result


def save(name: str, spec: dict[str, Any], *, data_dir: Path) -> dict[str, Any]:
    args = ["rules", "save", name, "--spec", json.dumps(spec), "--json"]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    return result


def validate(spec: dict[str, Any], *, data_dir: Path) -> dict[str, Any]:
    """A validation *report*: an invalid spec is ``valid: false`` with the CLI's defect text."""
    try:
        result: dict[str, Any] = _run_json(
            ["rules", "validate", "--spec", json.dumps(spec), "--json"], data_dir=data_dir
        )
    except RuntimeError as exc:
        return {"valid": False, "error": str(exc)}
    return {**result, "error": None}


def delete(name: str, *, data_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = _run_json(["rules", "delete", name, "--json"], data_dir=data_dir)
    return result
