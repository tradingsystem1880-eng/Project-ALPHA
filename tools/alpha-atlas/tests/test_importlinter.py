"""The import-linter extractor captures all 14 contracts with their module lists."""

from pathlib import Path

import pytest

from alpha_atlas.generators.importlinter import extract


class TestImportLinterExtractor:
    def test_all_fourteen_contracts_become_nodes(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root)
        contracts = [n for n in fragment.nodes if n.kind == "contract"]
        assert len(contracts) == 14
        assert fragment.edges == []
        assert "pyproject.toml" in inputs

    def test_contract_carries_full_module_lists(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        by_id = {n.id: n for n in fragment.nodes}
        core = by_id["contract:alpha-core-imports-nothing-internal"]
        assert core.label == "alpha_core imports nothing internal"
        assert core.meta["source_modules"] == ["alpha_core"]
        assert "alpha_cli" in core.meta["forbidden_modules"]
        assert core.evidence.level == "declared"
        assert core.evidence.provenance[0].source == "pyproject.toml"

    def test_ignore_imports_exemptions_are_preserved(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        exemptions = [
            n.meta["ignore_imports"] for n in fragment.nodes if n.meta.get("ignore_imports")
        ]
        # ADR-0030 owner-auth seam is the single sanctioned exemption today.
        assert any("alpha_web.api.owner_auth" in " ".join(e) for e in exemptions)

    def test_missing_section_fails_loud(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        with pytest.raises(Exception, match="importlinter"):
            extract(tmp_path)
