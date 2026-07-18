"""Committed and runtime workstation API contracts cannot drift."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.routing import APIRoute

from alpha_web.app import create_app


def test_committed_openapi_matches_runtime() -> None:
    root = Path(__file__).parents[2]
    committed = json.loads((root / "apps/alpha-web/frontend/openapi.json").read_text())
    assert committed == create_app().openapi()


def test_every_stable_json_route_has_a_response_model() -> None:
    unmodeled = []
    for route in create_app().routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        if route.path.endswith("/stream") or route.path.endswith("/tearsheet"):
            continue
        if route.response_model is None:
            unmodeled.append(route.path)
    assert unmodeled == []
