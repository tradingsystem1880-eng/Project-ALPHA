"""Lightweight public metadata seam for surface applications."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from alpha_cli._schemas import STRATEGY_PARAM_SCHEMA

COMMAND_RUN_TYPES: dict[str, str] = {
    "backtest run": "runs",
    "backtest portfolio": "portfolio",
    "backtest cross-sectional": "cross_sectional",
    "validate": "runs",
    "optim grid": "optim",
    "propfirm run": "propfirm",
    "forecast run": "forecast",
    "forecast eval": "forecast",
}


def known_strategies() -> list[str]:
    """Registered strategy names without importing engine or numerical layers."""
    return sorted(STRATEGY_PARAM_SCHEMA)


def strategy_params(strategy_name: str) -> list[dict[str, Any]]:
    return [asdict(spec) for spec in STRATEGY_PARAM_SCHEMA[strategy_name]]
