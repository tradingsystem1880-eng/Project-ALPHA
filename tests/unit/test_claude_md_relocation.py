"""Zero-loss drift test for the CLAUDE.md restructure.

The pre-v2 CLAUDE.md is frozen at ``tests/fixtures/claude_md_v1.md``. Every
heading, table row, and bullet of that file must still be present verbatim in
the union of the core ``CLAUDE.md``, ``.claude/rules/*.md``, and
``docs/BUILD-STATUS.md``. The core file must stay small enough to be read, and
every rule file must declare ``paths`` globs that match at least one file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "claude_md_v1.md"
RULES = ROOT / ".claude" / "rules"
CORE_MAX_LINES = 200
CORE_MAX_BYTES = 35_000
_LOAD_BEARING = re.compile(r"^\s*(#|\||- |\+ )")


def _load_bearing_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if _LOAD_BEARING.match(line)]


def _union_lines() -> set[str]:
    docs = [ROOT / "CLAUDE.md", ROOT / "docs" / "BUILD-STATUS.md", *sorted(RULES.glob("*.md"))]
    union: set[str] = set()
    for doc in docs:
        union.update(line.strip() for line in doc.read_text().splitlines())
    return union


def _frontmatter_paths(text: str) -> list[str] | None:
    if not text.startswith("---\n"):
        return None
    head = text.split("---\n", 2)[1]
    return [m.group(1) for m in re.finditer(r'^\s*-\s*"([^"]+)"\s*$', head, re.M)]


class TestZeroLoss:
    def test_every_load_bearing_line_survives(self) -> None:
        union = _union_lines()
        missing = [line for line in _load_bearing_lines(FIXTURE.read_text()) if line not in union]
        assert missing == [], f"{len(missing)} CLAUDE.md v1 line(s) lost:\n" + "\n".join(
            missing[:20]
        )

    def test_core_is_small(self) -> None:
        core = (ROOT / "CLAUDE.md").read_text()
        assert core.count("\n") < CORE_MAX_LINES
        assert len(core.encode()) < CORE_MAX_BYTES

    def test_core_keeps_the_invariants(self) -> None:
        core = (ROOT / "CLAUDE.md").read_text()
        for heading in (
            "## Architecture DAG",
            "## Golden rules",
            "## Commands",
            "## Where do I add X?",
            "## Claude Code harness",
            "## Rules (path-scoped",
        ):
            assert heading in core


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
            "alpha-analytics.md",
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
