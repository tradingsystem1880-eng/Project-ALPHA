"""Frontend scan: client.ts method joins (fail-loud), screens, panels, calls edges."""

from pathlib import Path

import pytest

from alpha_atlas.core.model import AtlasError
from alpha_atlas.generators.frontend_scan import extract, join_client_methods


class TestClientJoin:
    def test_client_methods_join_openapi_with_a_floor(self, repo_root: Path) -> None:
        methods = join_client_methods(repo_root)
        assert len(methods) >= 100
        assert methods["runs"] == ("GET", "/api/runs")
        assert methods["candles"] == ("GET", "/api/candles/{symbol}")

    def test_orphan_client_paths_fail_loud(self, tmp_path: Path, repo_root: Path) -> None:
        client = repo_root / "apps/alpha-web/frontend/src/api/client.ts"
        fake_root = tmp_path
        target = fake_root / "apps/alpha-web/frontend/src/api/client.ts"
        target.parent.mkdir(parents=True)
        target.write_text(
            client.read_text(encoding="utf-8").replace(
                "`/api/runs${query}`", "`/api/definitely-not-a-route`"
            ),
            encoding="utf-8",
        )
        spec = repo_root / "apps/alpha-web/frontend/openapi.json"
        (fake_root / "apps/alpha-web/frontend/openapi.json").write_bytes(spec.read_bytes())
        with pytest.raises(AtlasError, match="definitely-not-a-route"):
            join_client_methods(fake_root)


class TestFrontendScan:
    def test_screens_and_panels_from_the_screens_literal(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root)
        explore = next(n for n in fragment.nodes if n.id == "screen:explore")
        assert explore.meta["label"] == "Research"
        assert any(
            e.type == "part_of"
            and e.source == "panel:ResearchCockpit"
            and e.target == "screen:explore"
            for e in fragment.edges
        )
        assert "apps/alpha-web/frontend/src/shell/screens.tsx" in inputs

    def test_panels_are_anchored_to_their_component_file(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        chart = next(n for n in fragment.nodes if n.id == "panel:PriceChart")
        assert chart.evidence.level == "implemented"
        anchor = chart.meta["verified_anchors"][0]
        assert anchor["path"] == "apps/alpha-web/frontend/src/panels/PriceChart.tsx"

    def test_panel_calls_route_via_client_method(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        assert any(
            e.type == "calls"
            and e.source == "panel:PriceChart"
            and e.target == "route:GET /api/candles/{symbol}"
            for e in fragment.edges
        )
