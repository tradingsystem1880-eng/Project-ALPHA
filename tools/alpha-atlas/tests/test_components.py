"""Components extractor: workspace dirs, rule nodes, MODULE MAP responsibilities."""

from pathlib import Path

from alpha_atlas.generators.components import extract


class TestComponents:
    def test_every_workspace_dir_is_a_component(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root)
        components = {n.id for n in fragment.nodes if n.kind == "component"}
        assert {
            "component:alpha-core",
            "component:alpha-cli",
            "component:alpha-web",
            "component:literature",
            "component:qlib",
        } <= components
        assert len(components) == 16  # 11 packages + 3 apps + 2 workers
        assert any(p.endswith("pyproject.toml") for p in inputs)

    def test_rules_attach_component_responsibility_and_defines_edges(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        core = next(n for n in fragment.nodes if n.id == "component:alpha-core")
        assert "domain types" in str(core.meta["responsibility"])
        rule_id = "rule:.claude/rules/alpha-core.md"
        assert any(n.id == rule_id and n.kind == "rule" for n in fragment.nodes)
        assert any(
            e.type == "defines" and e.source == rule_id and e.target == "component:alpha-core"
            for e in fragment.edges
        )

    def test_module_map_rows_become_declared_stubs(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        stub = next(n for n in fragment.nodes if n.id == "module:alpha_data.adapters.base")
        assert stub.kind == "module"
        assert stub.evidence.level == "declared"
        assert stub.meta["responsibility"]
        assert any(
            e.type == "defines"
            and e.source == "rule:.claude/rules/alpha-data.md"
            and e.target == stub.id
            for e in fragment.edges
        )

    def test_multi_module_rows_split(self, repo_root: Path) -> None:
        # alpha-cli.md packs several modules into one row: `a.py` · `b.py`
        fragment, _ = extract(repo_root)
        ids = {n.id for n in fragment.nodes}
        assert "module:alpha_cli.research_d1" in ids
        assert "module:alpha_cli.research_analysis_plan" in ids

    def test_paragraph_style_module_map_is_parsed(self, repo_root: Path) -> None:
        # alpha-patterns.md introduces its MODULE MAP with a paragraph, not a ### heading.
        fragment, _ = extract(repo_root)
        patterns = next(n for n in fragment.nodes if n.id == "component:alpha-patterns")
        assert patterns.evidence.level == "declared"
        assert "geometry" in str(patterns.meta["responsibility"])
        assert any(n.id == "module:alpha_patterns.swings" for n in fragment.nodes)

    def test_worker_components_without_rules_stay_unknown(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        worker = next(n for n in fragment.nodes if n.id == "component:literature")
        assert worker.evidence.level == "unknown"
