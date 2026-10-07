"""Drift guards between the tree and the agent-facing docs.

Awareness that is remembered rots; awareness that is derived does not. Each
test here derives a fact from the tree (ADR files, package modules, CLI
sub-apps, MCP tools, agents, commands) and asserts the docs still say so.
"""

from __future__ import annotations

import re
from pathlib import Path

import harness_awareness
import pytest
from repo_orientation import orientation

from tests.unit._harness_support import REPO_ROOT as ROOT

RULES = ROOT / ".claude" / "rules"
DOC_UNION = [ROOT / "CLAUDE.md", *sorted(RULES.glob("*.md"))]


def _docs_text() -> str:
    return "\n".join(p.read_text() for p in DOC_UNION)


class TestAdrAwareness:
    def test_every_adr_is_referenced(self) -> None:
        assert harness_awareness.adr_drift(ROOT) == []

    def test_adr_0029_is_referenced(self) -> None:
        # The concrete omission that motivated this guard.
        assert 29 in harness_awareness.referenced_adr_ids(_docs_text())


class TestModuleMapAwareness:
    @pytest.mark.parametrize(
        "src",
        sorted(
            p for p in [*ROOT.glob("packages/*/src/*"), *ROOT.glob("apps/*/src/*")] if p.is_dir()
        ),
        ids=lambda p: p.name,
    )
    def test_top_level_modules_have_a_row(self, src: Path) -> None:
        """Current modules are discoverable without a duplicated handwritten module map."""
        index = orientation(ROOT, component=src.name.replace("_", "-"))
        paths = {row["path"] for row in index["modules"]}
        missing = [
            py.name
            for py in sorted(src.glob("*.py"))
            if not py.name.startswith("_") and str(py.relative_to(ROOT)) not in paths
        ]
        assert missing == [], f"{src.name}: modules absent from source index: {missing}"


class TestCliAwareness:
    def test_every_typer_subapp_is_documented(self) -> None:
        main = (ROOT / "apps/alpha-cli/src/alpha_cli/main.py").read_text()
        names = re.findall(r'add_typer\([^,]+,\s*name="([^"]+)"', main)
        docs = _docs_text()
        missing = [n for n in names if f"`alpha {n}" not in docs and f"`{n}`" not in docs]
        assert missing == [], f"undocumented CLI sub-apps: {missing}"


class TestMcpAwareness:
    def test_tool_count_pin_matches_server(self) -> None:
        server = (ROOT / "apps/alpha-mcp/src/alpha_mcp/server.py").read_text()
        decorated = len(re.findall(r"@mcp\.tool", server))
        pin = (ROOT / "tests/integration/test_research_mcp.py").read_text()
        match = re.search(r"assert len\(names\) == (\d+)", pin)
        assert match is not None
        assert decorated == int(match.group(1))
        assert "capability-authority-matrix.md" in (ROOT / "CLAUDE.md").read_text()


class TestHarnessAwareness:
    def test_rules_paths_point_at_existing_dirs(self) -> None:
        for rule in RULES.glob("*.md"):
            text = rule.read_text()
            for pattern in re.findall(
                r'^\s*-\s*"([^"]+)"', text.split("---")[1] if text.startswith("---") else "", re.M
            ):
                anchor = ROOT / pattern.split("*")[0].rstrip("/")
                assert anchor.exists(), f"{rule.name}: {pattern} anchors at a missing path"
