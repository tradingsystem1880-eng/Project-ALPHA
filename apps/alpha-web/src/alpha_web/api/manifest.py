"""``/api/apps`` — the declarative panel manifest (OpenBB-style) the shell renders from.

Each panel names its component id, whether it subscribes to the linked symbol/date context, and the
data endpoints it reads. Later modules append entries here (and a component in the frontend
``panels/registry``) to add panels with no shell change.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["manifest"])

_MANIFEST: dict[str, Any] = {
    "panels": [
        {
            "id": "run-browser",
            "title": "Run Browser",
            "component": "RunBrowser",
            "linked": False,
            "data": [{"endpoint": "/api/runs", "method": "GET"}],
            "params": [],
        },
        {
            "id": "run-detail",
            "title": "Run Detail",
            "component": "RunDetail",
            "linked": False,
            "data": [{"endpoint": "/api/runs/{run_id}", "method": "GET"}],
            "params": [{"name": "run_id", "type": "run", "default": None}],
        },
        {
            "id": "strategy-lab",
            "title": "Strategy Lab",
            "component": "StrategyLab",
            "linked": False,
            "data": [
                {"endpoint": "/api/strategies", "method": "GET"},
                {"endpoint": "/api/commands", "method": "GET"},
            ],
            "params": [],
        },
        {
            "id": "price-chart",
            "title": "Price",
            "component": "PriceChart",
            "linked": True,
            "data": [{"endpoint": "/api/candles/{symbol}", "method": "GET"}],
            "params": [{"name": "symbol", "type": "symbol", "default": None}],
        },
        {
            "id": "data-explorer",
            "title": "Data Explorer",
            "component": "DataExplorer",
            "linked": False,
            "data": [{"endpoint": "/api/symbols", "method": "GET"}],
            "params": [],
        },
        {
            "id": "ai-console",
            "title": "AI Console",
            "component": "AiConsole",
            "linked": False,
            "data": [{"endpoint": "/api/jobs", "method": "POST"}],
            "params": [],
        },
        {
            "id": "workspaces",
            "title": "Workspaces",
            "component": "Workspaces",
            "linked": False,
            "data": [{"endpoint": "/api/workspaces", "method": "GET"}],
            "params": [],
        },
        {
            "id": "options",
            "title": "Options",
            "component": "OptionsGreeks",
            "linked": False,
            "data": [
                {"endpoint": "/api/options/greeks", "method": "GET"},
                {"endpoint": "/api/options/curve", "method": "GET"},
            ],
            "params": [],
        },
        {
            "id": "risk",
            "title": "Risk",
            "component": "RiskMonitor",
            "linked": True,
            "data": [{"endpoint": "/api/risk/scenario", "method": "GET"}],
            "params": [{"name": "run_id", "type": "run", "default": None}],
        },
    ],
    "commands": "/api/commands",
    "strategies": "/api/strategies",
}


@router.get("/apps")
def apps() -> dict[str, Any]:
    """The panel catalog + the endpoints that drive the new-run form."""
    return _MANIFEST
