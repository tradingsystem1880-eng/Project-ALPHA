"""Drift guards for the Claude Code skill registration layer.

`.claude/skills/<name>/SKILL.md` stubs exist only for auto-discovery; the
canonical skill body lives in `.agents/skills/<name>/SKILL.md`. These tests
pin the 1:1 mapping, frontmatter integrity, description sync, and the
load-bearing `alpha-research-protocols` path that must never be stubbed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STUB_DIR = REPO_ROOT / ".claude" / "skills"
CANONICAL_DIR = REPO_ROOT / ".agents" / "skills"

# alpha-research-protocols is intentionally absent: its directory layout is
# load-bearing for alpha_cli's protocol library and it is not an agent skill.
NEVER_STUBBED = {"alpha-research-protocols"}


def _frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    block = text.split("---", 2)[1]
    fields: dict[str, str] = {}
    for line in block.strip().splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


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

    def test_stub_frontmatter_matches_canonical(self) -> None:
        for name in _stub_names():
            stub = _frontmatter((STUB_DIR / name / "SKILL.md").read_text())
            canonical = _frontmatter((CANONICAL_DIR / name / "SKILL.md").read_text())
            assert stub.get("name") == name, f"{name}: stub frontmatter name mismatch"
            assert canonical.get("name") == name, f"{name}: canonical frontmatter name mismatch"
            assert stub.get("description") == canonical.get("description"), (
                f"{name}: stub description drifted from canonical — regenerate the stub"
            )

    @pytest.mark.parametrize("name", sorted(NEVER_STUBBED))
    def test_load_bearing_skills_never_stubbed(self, name: str) -> None:
        assert not (STUB_DIR / name).exists(), f"{name} must not be registered as a stub"

    def test_protocol_library_path_intact(self) -> None:
        protocols = CANONICAL_DIR / "alpha-research-protocols" / "protocols.json"
        assert protocols.is_file(), "load-bearing protocols.json moved — alpha_cli breaks"


class TestNewCanonicalSkills:
    @pytest.mark.parametrize("name", ["quant-source-verification", "alpha-feature-workflow"])
    def test_canonical_exists_with_frontmatter(self, name: str) -> None:
        text = (CANONICAL_DIR / name / "SKILL.md").read_text()
        fields = _frontmatter(text)
        assert fields.get("name") == name
        assert fields.get("description")

    def test_quant_skill_names_the_primary_sources(self) -> None:
        body = (CANONICAL_DIR / "quant-source-verification" / "SKILL.md").read_text()
        for anchor in ("Bailey", "White", "Hansen", "Politis", "Efron", "Holm"):
            assert anchor in body, f"quant-source-verification lost its {anchor} citation"
        assert "attest --kind quant" in body

    def test_feature_workflow_names_the_pipeline(self) -> None:
        body = (CANONICAL_DIR / "alpha-feature-workflow" / "SKILL.md").read_text()
        for anchor in ("/plan-feature", "/review-gate", "/verify-quant", "bias_guard"):
            assert anchor in body, f"alpha-feature-workflow lost its {anchor} step"
