"""The tests extractor maps test files to lifecycle anchors; tests/holdout is never read."""

from pathlib import Path

from alpha_atlas.generators.tests_map import extract
from alpha_atlas.generators.workflow import extract as extract_workflow


class TestTestsMap:
    def test_test_files_become_nodes_with_categories(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root, workflow_fragment=None)
        tests = [n for n in fragment.nodes if n.kind == "test"]
        assert len(tests) > 300
        categories = {str(n.meta["category"]) for n in tests}
        assert {"unit", "integration", "bias_guards", "oracles"} <= categories
        known = next(n for n in tests if n.id == "test:tests/unit/test_research_d1_executor.py")
        assert known.meta["category"] == "unit"
        assert "alpha_cli.research_d1" in known.meta["targets"]
        assert any(p.startswith("tests/unit/") for p in inputs)

    def test_holdout_is_never_read(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root, workflow_fragment=None)
        assert not any(n.path and n.path.startswith("tests/holdout/") for n in fragment.nodes)
        assert not any(p.startswith("tests/holdout/") for p in inputs)

    def test_lifecycle_nodes_gain_validates_edges(self, repo_root: Path) -> None:
        workflow_fragment, _ = extract_workflow(repo_root)
        fragment, _ = extract(repo_root, workflow_fragment=workflow_fragment)
        d1_edges = [
            e for e in fragment.edges if e.type == "validates" and e.target == "wf:research.d1"
        ]
        assert any(e.source == "test:tests/unit/test_research_d1_executor.py" for e in d1_edges)

    def test_module_targets_gain_validates_edges(self, repo_root: Path) -> None:
        fragment, _ = extract(
            repo_root,
            workflow_fragment=None,
            module_ids={"module:alpha_cli.research_d1"},
        )
        assert any(
            e.type == "validates"
            and e.source == "test:tests/unit/test_research_d1_executor.py"
            and e.target == "module:alpha_cli.research_d1"
            for e in fragment.edges
        )
