"""Current operating guidance stays small, navigable, and explicit about invariants.

Historical prose is not an executable specification. Source contracts and behavior tests own
the implementation; this guard checks today's instructions and their local references.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.unit._harness_support import REPO_ROOT as ROOT

RULES = ROOT / ".claude" / "rules"


def _frontmatter_paths(text: str) -> list[str] | None:
    if not text.startswith("---\n"):
        return None
    head = text.split("---\n", 2)[1]
    return [m.group(1) for m in re.finditer(r'^\s*-\s*"([^"]+)"\s*$', head, re.M)]


class TestCurrentManual:
    def test_core_is_small(self) -> None:
        assert sum((ROOT / name).stat().st_size for name in ("CLAUDE.md", "AGENTS.md")) <= 6_000

    def test_local_manual_links_resolve(self) -> None:
        for name in ("AGENTS.md", "CLAUDE.md"):
            for target in re.findall(r"\]\(([^)]+)\)", (ROOT / name).read_text()):
                assert not target.startswith(("https:", "http:")), "manual links are local"
                assert (ROOT / target.split("#", 1)[0]).is_file(), target

    def test_core_keeps_the_invariants(self) -> None:
        core = (ROOT / "CLAUDE.md").read_text()
        for invariant in (
            "alpha_cli",
            "as_of",
            "t+1",
            "immutable",
            "owner",
            "tests/holdout/",
            "uv run python scripts/gate.py full",
            "pyproject.toml",
            "not proof of edge",
        ):
            assert invariant in core


class TestRuleFiles:
    def test_rules_present(self) -> None:
        names = {p.name for p in RULES.glob("*.md")}
        assert {
            "00-karpathy.md",
            "alpha-core.md",
            "alpha-data.md",
            "alpha-strategies.md",
            "alpha-backtest.md",
            "alpha-validation.md",
            "alpha-research.md",
            "alpha-forecast.md",
            "alpha-cli.md",
            "alpha-mcp.md",
            "alpha-web.md",
            "quant.md",
            "tests.md",
            "docs.md",
        } <= names

    @pytest.mark.parametrize("rule", sorted(RULES.glob("*.md")), ids=lambda p: p.name)
    def test_paths_frontmatter_matches_existing_files(self, rule: Path) -> None:
        paths = _frontmatter_paths(rule.read_text())
        if rule.name == "00-karpathy.md":
            assert paths is None, "the Karpathy rule is unscoped (always loaded)"
            return
        assert paths, f"{rule.name} must declare paths: globs"
        for pattern in paths:
            assert "{" not in pattern, "brace expansion is avoided (bounded budget)"
            assert any(ROOT.glob(pattern)), f"{rule.name}: {pattern} matches no file"

    def test_karpathy_rule_mirrors_canonical_skill(self) -> None:
        canonical = (ROOT / ".agents" / "skills" / "karpathy-guidelines" / "SKILL.md").read_text()
        body = canonical.split("---", 2)[2].strip()
        assert body in (RULES / "00-karpathy.md").read_text()

    def test_core_lists_every_rule(self) -> None:
        core = (ROOT / "CLAUDE.md").read_text()
        for rule in RULES.glob("*.md"):
            assert f"`{rule.name}`" in core, f"{rule.name} missing from the CLAUDE.md rules index"

    def test_core_rule_index_references_existing_files(self) -> None:
        core = (ROOT / "CLAUDE.md").read_text()
        rules_section = core.split("## Rules", 1)[1].split("## Architecture DAG", 1)[0]
        indexed_rules = re.findall(r"`([^`/]+\.md)`", rules_section)

        assert indexed_rules, "CLAUDE.md rules index must name its rule files"
        for rule_name in indexed_rules:
            assert (RULES / rule_name).is_file(), f"indexed rule does not exist: {rule_name}"
