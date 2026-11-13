"""Drift guards for the Claude Code skill registration layer.

`.claude/skills/<name>/SKILL.md` stubs exist only for auto-discovery; the
canonical skill body lives in `.agents/skills/<name>/SKILL.md`. These tests
check the 1:1 mapping (a stub with no body would load nothing), frontmatter
integrity, that every skill an agent preloads exists, and the load-bearing
`alpha-research-protocols` library that `alpha_cli` reads and must never be
stubbed. Skill wording is reviewed in the pull request, not pinned here.
"""

from __future__ import annotations

import gate
import pytest

from tests.unit._harness_support import REPO_ROOT

STUB_DIR = REPO_ROOT / ".claude" / "skills"
CANONICAL_DIR = REPO_ROOT / ".agents" / "skills"

# alpha-research-protocols is intentionally absent: its directory layout is
# load-bearing for alpha_cli's protocol library and it is not an agent skill.
NEVER_STUBBED = {"alpha-research-protocols"}


def _stub_names() -> list[str]:
    return sorted(p.name for p in STUB_DIR.iterdir() if p.is_dir())


class TestStubRegistry:
    def test_stubs_exist(self) -> None:
        assert _stub_names(), "no skill stubs registered under .claude/skills"

    def test_every_stub_has_canonical_counterpart(self) -> None:
        for name in _stub_names():
            canonical = CANONICAL_DIR / name / "SKILL.md"
            assert canonical.is_file(), f"stub {name} has no canonical .agents skill"

    def test_stub_points_at_canonical_path(self) -> None:
        for name in _stub_names():
            body = (STUB_DIR / name / "SKILL.md").read_text()
            assert f".agents/skills/{name}/SKILL.md" in body, name

    def test_stub_and_canonical_frontmatter_name_the_skill(self) -> None:
        for name in _stub_names():
            stub = gate._frontmatter((STUB_DIR / name / "SKILL.md").read_text())
            canonical = gate._frontmatter((CANONICAL_DIR / name / "SKILL.md").read_text())
            assert stub.get("name") == name, f"{name}: stub frontmatter name mismatch"
            assert canonical.get("name") == name, f"{name}: canonical frontmatter name mismatch"
            assert stub.get("description"), f"{name}: stub needs a description for discovery"

    @pytest.mark.parametrize("name", sorted(NEVER_STUBBED))
    def test_load_bearing_skills_never_stubbed(self, name: str) -> None:
        assert not (STUB_DIR / name).exists(), f"{name} must not be registered as a stub"

    def test_protocol_library_path_intact(self) -> None:
        protocols = CANONICAL_DIR / "alpha-research-protocols" / "protocols.json"
        assert protocols.is_file(), "load-bearing protocols.json moved — alpha_cli breaks"


def test_every_skill_an_agent_preloads_exists() -> None:
    agents = sorted((REPO_ROOT / ".claude" / "agents").glob("*.md"))
    assert agents
    for agent in agents:
        fields = gate._frontmatter(agent.read_text())
        for name in filter(None, (s.strip() for s in fields.get("skills", "").split(","))):
            assert (STUB_DIR / name / "SKILL.md").is_file(), f"{agent.name} preloads {name}"
