"""Lightweight public metadata seam for surface applications."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from alpha_cli._schemas import STRATEGY_PARAM_SCHEMA

COMMAND_RUN_TYPES: dict[str, str] = {
    "backtest run": "runs",
    "backtest oos": "runs",
    "backtest portfolio": "portfolio",
    "backtest cross-sectional": "cross_sectional",
    "validate": "runs",
    "optim grid": "optim",
    "propfirm run": "propfirm",
    "forecast run": "forecast",
    "forecast eval": "forecast",
}

type GenericCommandClass = Literal["empirical", "owner_only", "safe", "unknown"]

_EMPIRICAL_ROOTS = frozenset(
    {"backtest", "validate", "optim", "propfirm", "forecast", "ml", "monte-carlo"}
)
_OWNER_ONLY_ROOTS = frozenset({"project", "suite"})
_SAFE_ROOTS = frozenset({"info", "options", "screener", "risk", "report", "figures"})


def classify_generic_command(argv: list[str]) -> GenericCommandClass:
    """Classify commands exposed by the Workstation's generic launcher.

    This is deliberately conservative for governed project contexts: an unknown command is not
    assumed non-empirical. Research lifecycle mutations stay on their bounded API/CLI surfaces.
    """
    if not argv:
        return "unknown"
    root = argv[0]
    if root == "research":
        return "empirical" if len(argv) > 1 and argv[1] == "compare" else "owner_only"
    if root in _OWNER_ONLY_ROOTS:
        return "owner_only"
    if root == "evidence":
        return "owner_only" if len(argv) < 2 or argv[1] in {"add", "revise"} else "safe"
    if root == "data":
        return (
            "owner_only"
            if len(argv) > 1 and argv[1] in {"repair", "rollback-promotion"}
            else "safe"
        )
    if root == "paper":
        return (
            "safe"
            if len(argv) > 1 and argv[1] in {"sessions", "readiness", "scheduler-status", "show"}
            else "owner_only"
        )
    if root in _EMPIRICAL_ROOTS:
        return "empirical"
    if root in _SAFE_ROOTS:
        return "safe"
    return "unknown"


def known_strategies() -> list[str]:
    """Registered strategy names without importing engine or numerical layers."""
    return sorted(STRATEGY_PARAM_SCHEMA)


def strategy_params(strategy_name: str) -> list[dict[str, Any]]:
    return [asdict(spec) for spec in STRATEGY_PARAM_SCHEMA[strategy_name]]
