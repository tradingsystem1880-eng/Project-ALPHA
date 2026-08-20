"""The docs extractor parses the uniform ADR headers and spec files into doc nodes."""

from pathlib import Path

from alpha_atlas.generators.docs_scan import extract


class TestDocsScan:
    def test_every_adr_becomes_a_doc_node(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root)
        adrs = [n for n in fragment.nodes if n.meta.get("doc_type") == "adr"]
        assert len(adrs) == len(list((repo_root / "docs/adr").glob("0*.md")))
        assert len(adrs) >= 34
        assert all(n.evidence.level == "declared" for n in adrs)
        assert any(p.startswith("docs/adr/") for p in inputs)

    def test_adr_header_fields_are_parsed(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        by_id = {n.id: n for n in fragment.nodes}
        adr = by_id["doc:ADR-0025"]
        assert str(adr.meta["status"]).startswith("Accepted")
        assert adr.meta["date"].count("-") == 2
        assert "d1" in adr.label.lower() or "D1" in adr.label
        assert adr.path == "docs/adr/0025-empirical-d1-research-runner-admission.md"

    def test_implementation_anchor_paths_are_harvested(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        by_id = {n.id: n for n in fragment.nodes}
        anchors = by_id["doc:ADR-0025"].meta.get("implementation_anchors", [])
        assert any("research" in a for a in anchors)

    def test_specs_become_doc_nodes(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        spec_path = "docs/superpowers/specs/2026-08-07-research-first-workstation-design.md"
        by_id = {n.id: n for n in fragment.nodes}
        spec = by_id[f"doc:{spec_path}"]
        assert spec.meta["doc_type"] == "spec"
        assert spec.label
