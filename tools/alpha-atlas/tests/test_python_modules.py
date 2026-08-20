"""Python-module extractor: module nodes, import edges with file:line, part_of."""

from pathlib import Path

from alpha_atlas.generators.python_modules import extract


class TestPythonModules:
    def test_module_nodes_cover_the_workspace(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root)
        modules = [n for n in fragment.nodes if n.kind == "module"]
        assert len(modules) >= 250
        known = next(n for n in modules if n.id == "module:alpha_cli.research_d1")
        assert known.path == "apps/alpha-cli/src/alpha_cli/research_d1.py"
        assert known.component == "alpha-cli"
        assert known.evidence.level == "unknown"  # levels are computed by the resolver
        assert "apps/alpha-cli/src/alpha_cli/research_d1.py" in inputs

    def test_known_cross_package_dependency_edge(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        edge = next(
            e
            for e in fragment.edges
            if e.type == "depends_on"
            and e.source == "module:alpha_cli.research_d1"
            and e.target == "module:alpha_research.ic"
        )
        assert edge.evidence.provenance[0].line is not None

    def test_part_of_edges_join_modules_to_components(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        assert any(
            e.type == "part_of"
            and e.source == "module:alpha_core.types"
            and e.target == "component:alpha-core"
            for e in fragment.edges
        )

    def test_worker_modules_are_included_and_pycache_is_not(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        ids = {n.id for n in fragment.nodes}
        assert "module:literature_worker.discovery" in ids
        assert "module:alpha_qlib_worker.rank_ensemble" in ids
        assert not any("__pycache__" in i for i in ids)
