"""The agent manual stays navigable and keeps its research-integrity invariants.

Process wording (which command to run, where files live) is not pinned here: it changes with
the tooling and is checked by the links. What must not silently disappear are the research rules.
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


@pytest.mark.parametrize("name", ["AGENTS.md", "CLAUDE.md"])
def test_local_manual_links_resolve(name: str) -> None:
    for target in re.findall(r"\]\(([^)]+)\)", (ROOT / name).read_text()):
        assert not target.startswith(("https:", "http:")), "manual links are local"
        assert (ROOT / target.split("#", 1)[0]).is_file(), target


def test_manual_keeps_the_research_integrity_invariants() -> None:
    core = (ROOT / "CLAUDE.md").read_text()
    for invariant in (
        "as_of",  # point-in-time reads
        "future-poison",  # look-ahead guards
        "t+1",  # decide at close, fill next open
        "not proof of edge",
        "owner confirmation",
        "no-live-capital",
    ):
        assert invariant in core, invariant


@pytest.mark.parametrize("rule", sorted(RULES.glob("*.md")), ids=lambda p: p.name)
def test_rule_paths_frontmatter_matches_existing_files(rule: Path) -> None:
    paths = _frontmatter_paths(rule.read_text())
    if rule.name == "00-karpathy.md":
        assert paths is None, "the Karpathy rule is unscoped (always loaded)"
        return
    assert paths, f"{rule.name} must declare paths: globs"
    for pattern in paths:
        assert any(ROOT.glob(pattern)), f"{rule.name}: {pattern} matches no file"
