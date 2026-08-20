"""Prompt packs: 12 sections in fixed order, tier-aware validation commands."""

import json
from pathlib import Path

import pytest

from alpha_atlas.core.model import AtlasError
from alpha_atlas.core.prompt_pack import SECTIONS, build_prompt_pack, load_rule_globs

_PROV = [{"extractor": "t", "source": "s", "detail": "d"}]


def _graph_with(anchor_path: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "inputs_hash": "x",
        "nodes": [
            {
                "id": "wf:x",
                "kind": "workflow_node",
                "label": "X",
                "evidence": {"level": "implemented", "provenance": _PROV},
                "meta": {
                    "purpose": "p",
                    "owner": "agent",
                    "confidence": "high",
                    "verified_anchors": [{"path": anchor_path, "symbol": "f", "line": 3}],
                },
            }
        ],
        "edges": [],
        "stats": {},
    }


@pytest.fixture(scope="module")
def real_graph(repo_root: Path) -> dict[str, object]:
    return json.loads(
        (repo_root / "architecture/atlas/generated/graph.json").read_text(encoding="utf-8")
    )


class TestPromptPack:
    def test_all_twelve_sections_in_order(
        self, real_graph: dict[str, object], repo_root: Path
    ) -> None:
        pack = build_prompt_pack(real_graph, ["wf:research.d1"], load_rule_globs(repo_root))
        positions = [pack.index(f"## {name}") for name in SECTIONS]
        assert positions == sorted(positions)
        assert len(SECTIONS) == 12

    def test_d1_pack_names_files_docs_and_tests(
        self, real_graph: dict[str, object], repo_root: Path
    ) -> None:
        pack = build_prompt_pack(real_graph, ["wf:research.d1"], load_rule_globs(repo_root))
        assert "apps/alpha-cli/src/alpha_cli/research_d1.py:1078" in pack
        assert "run_deep_research" in pack
        assert "ADR-0025" in pack
        assert "tests/unit/test_research_d1_executor.py" in pack
        assert "alpha-cli" in pack  # the matching .claude/rules file

    def test_quant_anchor_triggers_verify_quant(self, repo_root: Path) -> None:
        graph = _graph_with("packages/alpha-research/src/alpha_research/ic.py")
        pack = build_prompt_pack(graph, ["wf:x"], load_rule_globs(repo_root))
        assert "/verify-quant" in pack

    def test_risk_tier_anchor_triggers_review_gate(self, repo_root: Path) -> None:
        graph = _graph_with("apps/alpha-cli/src/alpha_cli/_gauntlet.py")
        pack = build_prompt_pack(graph, ["wf:x"], load_rule_globs(repo_root))
        assert "/review-gate" in pack

    def test_unknown_node_fails_loud(self, real_graph: dict[str, object], repo_root: Path) -> None:
        with pytest.raises(AtlasError, match="wf:nope"):
            build_prompt_pack(real_graph, ["wf:nope"], load_rule_globs(repo_root))

    def test_evidence_gap_is_reported_as_open_question(self, repo_root: Path) -> None:
        graph = _graph_with("apps/alpha-cli/src/alpha_cli/research_d1.py")
        node = graph["nodes"][0]  # type: ignore[index]
        node["evidence"]["level"] = "declared"  # type: ignore[index]
        node["meta"]["verified_anchors"] = []  # type: ignore[index]
        pack = build_prompt_pack(graph, ["wf:x"], load_rule_globs(repo_root))
        assert "declared" in pack.split("## OPEN QUESTIONS / KNOWN LIMITATIONS")[1]


class TestBackendEndpoint:
    def test_post_prompt_pack(self) -> None:
        from fastapi.testclient import TestClient

        from alpha_atlas.backend.app import create_app

        client = TestClient(create_app())
        response = client.post("/api/prompt-pack", json={"node_ids": ["wf:research.d1"]})
        assert response.status_code == 200
        assert response.json()["markdown"].startswith("# AI CONTEXT")

    def test_unknown_id_is_404(self) -> None:
        from fastapi.testclient import TestClient

        from alpha_atlas.backend.app import create_app

        client = TestClient(create_app())
        assert client.post("/api/prompt-pack", json={"node_ids": ["nope"]}).status_code == 404
