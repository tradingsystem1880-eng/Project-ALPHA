"""Curated lifecycle definitions: mandatory metadata, verified anchors, entity nodes."""

import json
from pathlib import Path

import pytest

from alpha_atlas.core.model import AtlasError
from alpha_atlas.generators.workflow import extract

_LIFECYCLE = "architecture/atlas/definitions/research-lifecycle.json"


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": "wf:research.example",
        "kind": "workflow_node",
        "label": "Example",
        "order": 1,
        "purpose": "example",
        "owner": "agent",
        "created_from": ["ADR-0019"],
        "last_verified_commit": "abc1234",
        "confidence": "high",
        "anchors": [],
    }
    entry.update(overrides)
    return entry


def _write_definitions(tmp_path: Path, entries: list[dict[str, object]]) -> Path:
    root = tmp_path
    defs_dir = root / "architecture/atlas/definitions"
    defs_dir.mkdir(parents=True)
    payload = {"schema_version": 1, "workflow": "research", "nodes": entries, "artifacts": []}
    (defs_dir / "research-lifecycle.json").write_text(json.dumps(payload))
    (defs_dir / "data-lineage.json").write_text(
        json.dumps({"schema_version": 1, "nodes": [], "artifacts": []})
    )
    return root


class TestCuratedMetadata:
    def test_missing_metadata_field_is_rejected(self, tmp_path: Path) -> None:
        entry = _entry()
        del entry["confidence"]
        root = _write_definitions(tmp_path, [entry])
        with pytest.raises(AtlasError, match="confidence"):
            extract(root)

    def test_bogus_anchor_symbol_fails_loud(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text("def real() -> None: ...\n")
        entry = _entry(anchors=[{"path": "mod.py", "symbol": "does_not_exist"}])
        root = _write_definitions(tmp_path, [entry])
        with pytest.raises(AtlasError, match="does_not_exist"):
            extract(root)

    def test_missing_anchor_file_fails_loud(self, tmp_path: Path) -> None:
        entry = _entry(anchors=[{"path": "gone.py", "symbol": "x"}])
        root = _write_definitions(tmp_path, [entry])
        with pytest.raises(AtlasError, match="gone.py"):
            extract(root)

    def test_changed_anchor_hash_flags_reverification(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text("def real() -> None: ...\n")
        entry = _entry(
            anchors=[{"path": "mod.py", "symbol": "real", "sha256": "0" * 64}],
        )
        root = _write_definitions(tmp_path, [entry])
        fragment, _ = extract(root)
        node = next(n for n in fragment.nodes if n.id == "wf:research.example")
        assert node.meta["needs_reverification"] is True


class TestRealLifecycle:
    def test_ten_lifecycle_nodes_in_order(self, repo_root: Path) -> None:
        fragment, inputs = extract(repo_root)
        wf = sorted(
            (n for n in fragment.nodes if n.kind == "workflow_node"),
            key=lambda n: int(str(n.meta["order"])),
        )
        assert len(wf) == 10
        assert wf[0].id == "wf:research.idea"
        assert wf[-1].id == "wf:research.promotion"
        assert _LIFECYCLE in inputs

    def test_d1_node_is_anchored_to_the_runner(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        d1 = next(n for n in fragment.nodes if n.id == "wf:research.d1")
        anchors = d1.meta["verified_anchors"]
        assert any(
            a["path"].endswith("alpha_cli/research_d1.py") and a["symbol"] == "run_deep_research"
            for a in anchors
        )
        assert all(a["line"] > 0 for a in anchors)
        assert d1.evidence.level in {"implemented", "tested"}

    def test_six_research_entity_nodes(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        kinds = {
            "research_case",
            "hypothesis",
            "dataset",
            "experiment",
            "decision",
            "strategy_version",
        }
        entities = [n for n in fragment.nodes if n.kind in kinds]
        assert {n.kind for n in entities} == kinds

    def test_defines_and_produces_edges_are_emitted(self, repo_root: Path) -> None:
        fragment, _ = extract(repo_root)
        types = {e.type for e in fragment.edges}
        assert "defines" in types
        assert "produces" in types
