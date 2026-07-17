"""``/api/{strategies,commands,symbols}`` — the CLI's catalogs, for the workstation's forms."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from alpha_web import _catalog, _invoke
from alpha_web.api._common import data_dir

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/strategies")
def strategies() -> list[dict[str, Any]]:
    """Registered strategies + their tunable ``--param`` axes."""
    return _catalog.strategies(data_dir=data_dir())


@router.get("/commands")
def commands() -> list[dict[str, Any]]:
    """The CLI command tree, each annotated with the run-type dir it writes (``None`` = no run)."""
    return [
        {**cmd, "run_type": _invoke.RUN_TYPE.get(cmd["id"])}
        for cmd in _catalog.commands(data_dir=data_dir())
    ]


@router.get("/symbols")
def symbols() -> dict[str, list[str]]:
    """Every symbol with stored bars."""
    return _catalog.symbols(data_dir=data_dir())
