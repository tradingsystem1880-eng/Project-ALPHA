"""API-route extractor: openapi operations + router AST anchors + serves edges."""

import json
from pathlib import Path

from alpha_atlas.generators.api_routes import extract


class TestApiRoutes:
    def test_every_openapi_operation_becomes_a_route_node(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root)
        routes = [n for n in fragment.nodes if n.kind == "api_route"]
        spec = json.loads(
            (repo_root / "apps/alpha-web/frontend/openapi.json").read_text(encoding="utf-8")
        )
        operations = sum(
            1
            for methods in spec["paths"].values()
            for m in methods
            if m in ("get", "post", "put", "delete")
        )
        assert len(routes) == operations >= 190
        assert "apps/alpha-web/frontend/openapi.json" in inputs
        assert "docs/governance/openapi-operation-classification.json" in inputs

    def test_known_route_is_anchored_and_classified(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        route = next(n for n in fragment.nodes if n.id == "route:GET /api/activity/stream")
        assert route.evidence.level == "implemented"
        anchor = route.meta["verified_anchors"][0]
        assert anchor["path"] == "apps/alpha-web/src/alpha_web/api/activity.py"
        assert anchor["line"] > 0
        assert route.meta["classification"] == "fixture_backed"

    def test_path_converter_decorators_still_anchor(self, repo_root: Path) -> None:
        # candles.py declares "/candles/{symbol:path}"; openapi says "/api/candles/{symbol}".
        fragment, _ = extract(repo_root)
        route = next(n for n in fragment.nodes if n.id == "route:GET /api/candles/{symbol}")
        assert route.evidence.level == "implemented"

    def test_routes_serve_their_router_module(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        assert any(
            e.type == "serves"
            and e.source == "route:GET /api/activity/stream"
            and e.target == "module:alpha_web.api.activity"
            for e in fragment.edges
        )
