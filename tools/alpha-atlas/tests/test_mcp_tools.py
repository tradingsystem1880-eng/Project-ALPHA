"""MCP extractor: the 62 pinned tools, and argv-literal calls edges to CLI leaves."""

from pathlib import Path

import pytest

from alpha_atlas.generators.cli_tree import extract as extract_cli
from alpha_atlas.generators.mcp_tools import extract


@pytest.fixture(scope="module")
def cli_ids(repo_root: Path) -> set[str]:
    fragment, _ = extract_cli(repo_root)
    return {n.id for n in fragment.nodes}


class TestMcpTools:
    def test_the_pinned_62_tools_are_extracted(self, repo_root: Path, cli_ids: set[str]) -> None:
        fragment, inputs = extract(repo_root, cli_ids=cli_ids)
        tools = [n for n in fragment.nodes if n.kind == "mcp_tool"]
        # The MCP surface is governance-pinned at 62; a drift here is a real finding.
        assert len(tools) == 62
        known = next(n for n in tools if n.id == "mcp:data_pull")
        assert known.evidence.level == "implemented"
        assert "OHLCV" in str(known.meta["doc"])
        assert "apps/alpha-mcp/src/alpha_mcp/server.py" in inputs

    def test_action_tools_call_their_cli_leaf(self, repo_root: Path, cli_ids: set[str]) -> None:
        fragment, _ = extract(repo_root, cli_ids=cli_ids)
        calls = {(e.source, e.target) for e in fragment.edges if e.type == "calls"}
        assert ("mcp:data_pull", "cli:alpha data pull") in calls
        assert ("mcp:backtest_run", "cli:alpha backtest run") in calls
        # server.py currently has exactly nine `args = [...]` action sites; the
        # remaining tools use in-process seams and honestly get no calls edge.
        assert len(calls) >= 9

    def test_calls_edges_only_target_known_cli_ids(
        self, repo_root: Path, cli_ids: set[str]
    ) -> None:
        fragment, _ = extract(repo_root, cli_ids=cli_ids)
        assert all(e.target in cli_ids for e in fragment.edges if e.type == "calls")
