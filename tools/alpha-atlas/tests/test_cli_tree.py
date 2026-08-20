"""CLI extractor: leaves + groups from the committed command cache, calls edges to modules."""

from pathlib import Path

from alpha_atlas.generators.cli_tree import CACHE_REL, extract


class TestCliTree:
    def test_leaves_and_groups_from_cache(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root)
        leaves = [n for n in fragment.nodes if n.kind == "cli_command" and not n.meta.get("group")]
        assert len(leaves) >= 150
        known = next(n for n in leaves if n.id == "cli:alpha backtest cross-sectional")
        assert known.evidence.level == "implemented"
        assert "--lookback" in known.meta["options"]
        assert CACHE_REL in inputs

    def test_leaves_are_part_of_their_group(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        assert any(n.id == "cli:alpha backtest" and n.meta.get("group") for n in fragment.nodes)
        assert any(
            e.type == "part_of"
            and e.source == "cli:alpha backtest cross-sectional"
            and e.target == "cli:alpha backtest"
            for e in fragment.edges
        )

    def test_groups_call_their_cmds_module(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        edge = next(
            e
            for e in fragment.edges
            if e.type == "calls"
            and e.source == "cli:alpha backtest"
            and e.target == "module:alpha_cli.backtest_cmds"
        )
        assert edge.evidence.provenance[0].source == "apps/alpha-cli/src/alpha_cli/main.py"
        assert edge.evidence.provenance[0].line is not None
