"""CLI extractor: leaves + groups from the committed command cache, calls edges to modules."""

import ast
from pathlib import Path

import pytest

from alpha_atlas.generators.cli_tree import CACHE_REL, MAIN_REL, _typer_registrations, extract


def _registry(repo_root: Path) -> set[tuple[str, str]]:
    """The (group, module) pairs of main.py's GROUPS literal, read independently."""
    tree = ast.parse((repo_root / MAIN_REL).read_text())
    value = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign | ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "GROUPS"
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        )
    )
    assert value is not None
    return {(name, module) for name, module, _ in ast.literal_eval(value)}


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

    def test_every_registry_group_calls_its_module(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        registry = _registry(repo_root)
        assert len(registry) == 24
        calls = {
            (e.source.removeprefix("cli:alpha "), e.target.removeprefix("module:"))
            for e in fragment.edges
            if e.type == "calls" and e.source.startswith("cli:alpha ")
        }
        assert calls == registry
        assert all(
            e.evidence.provenance[0].source == MAIN_REL
            for e in fragment.edges
            if e.type == "calls" and e.source.startswith("cli:alpha ")
        )

    def test_a_malformed_registry_fails_loudly(self) -> None:
        with pytest.raises(ValueError, match="GROUPS"):
            _typer_registrations('GROUPS = (("data", "alpha_cli.data_cmds"),)\n')
