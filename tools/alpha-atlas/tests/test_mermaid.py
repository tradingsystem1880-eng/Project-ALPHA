"""Mermaid docs: five files, generated header, node caps, id comments, fallbacks."""

import json
from pathlib import Path

import pytest

from alpha_atlas.core.mermaid import DOC_PATHS, GENERATED_HEADER, MAX_DIAGRAM_NODES, _diagram
from alpha_atlas.core.model import AtlasError
from alpha_atlas.generate import GRAPH_PATH, build_outputs


@pytest.fixture(scope="module")
def outputs(repo_root: Path) -> dict[str, str]:
    return build_outputs(repo_root)


class TestDiagramHelper:
    def test_node_cap_is_enforced(self) -> None:
        nodes = [(f"id{i}", f"label {i}") for i in range(MAX_DIAGRAM_NODES + 1)]
        with pytest.raises(AtlasError, match="diagram"):
            _diagram(nodes, [])

    def test_diagram_carries_id_comment_fence_and_fallback(self) -> None:
        text = _diagram([("a:1", "A"), ("b:2", "B")], [("a:1", "b:2", "")])
        assert "<!-- nodes: a:1|b:2 -->" in text
        assert "```mermaid" in text
        assert "<details>" in text


class TestDocs:
    def test_all_five_docs_emitted_with_header(self, outputs: dict[str, str]) -> None:
        assert set(DOC_PATHS) == {
            "docs/atlas/system-map.md",
            "docs/atlas/research-flow.md",
            "docs/atlas/data-lineage.md",
            "docs/atlas/frontend-flow.md",
            "docs/atlas/cli-flow.md",
        }
        for path in DOC_PATHS:
            assert outputs[path].startswith(GENERATED_HEADER), path

    def test_every_diagram_id_exists_in_the_graph(self, outputs: dict[str, str]) -> None:
        graph_ids = {n["id"] for n in json.loads(outputs[GRAPH_PATH])["nodes"]}
        for path in DOC_PATHS:
            for line in outputs[path].splitlines():
                if line.startswith("<!-- nodes: "):
                    ids = line.removeprefix("<!-- nodes: ").removesuffix(" -->").split("|")
                    missing = [i for i in ids if i not in graph_ids]
                    assert not missing, f"{path}: {missing}"

    def test_research_flow_lists_the_lifecycle_in_order(self, outputs: dict[str, str]) -> None:
        text = outputs["docs/atlas/research-flow.md"]
        positions = [
            text.index(marker)
            for marker in ("wf:research.idea", "wf:research.d0", "wf:research.promotion")
        ]
        assert positions == sorted(positions)
        assert "research_d1.py" in text

    def test_unknowns_queue_is_surfaced(self, outputs: dict[str, str]) -> None:
        assert "Unknowns" in outputs["docs/atlas/system-map.md"]
