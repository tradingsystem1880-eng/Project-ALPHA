"""The graph model fails loud: bad kinds, bad edge types, dangling endpoints, reserved levels."""

import json
from pathlib import Path

import pytest

from alpha_atlas.core.model import (
    EDGE_TYPES,
    EVIDENCE_LEVELS,
    NODE_KINDS,
    AtlasError,
    Edge,
    Evidence,
    Fragment,
    Node,
    Provenance,
    dumps_canonical,
    edge_id,
    merge_fragments,
    validate_graph,
)

_PROV = Provenance(extractor="test", source="tests/test_model.py", detail="fixture")


def _node(node_id: str, kind: str = "module", level: str = "implemented") -> Node:
    return Node(
        id=node_id,
        kind=kind,
        label=node_id.split(":", 1)[-1],
        evidence=Evidence(level=level, provenance=[_PROV]),
    )


def _edge(source: str, target: str, edge_type: str = "depends_on") -> Edge:
    return Edge(
        id=edge_id(source, target, edge_type),
        type=edge_type,
        source=source,
        target=target,
        evidence=Evidence(level="implemented", provenance=[_PROV]),
    )


class TestValidation:
    def test_dangling_edge_names_the_offender(self) -> None:
        graph = merge_fragments(
            [Fragment(nodes=[_node("module:a")], edges=[_edge("module:a", "module:missing")])]
        )
        with pytest.raises(AtlasError, match="module:missing"):
            validate_graph(graph)

    def test_unknown_kind_rejected(self) -> None:
        graph = merge_fragments([Fragment(nodes=[_node("x:a", kind="nonsense")], edges=[])])
        with pytest.raises(AtlasError, match="nonsense"):
            validate_graph(graph)

    def test_unknown_edge_type_rejected(self) -> None:
        nodes = [_node("module:a"), _node("module:b")]
        graph = merge_fragments(
            [Fragment(nodes=nodes, edges=[_edge("module:a", "module:b", "touches")])]
        )
        with pytest.raises(AtlasError, match="touches"):
            validate_graph(graph)

    def test_observed_is_reserved_in_v1(self) -> None:
        graph = merge_fragments([Fragment(nodes=[_node("module:a", level="observed")], edges=[])])
        with pytest.raises(AtlasError, match="observed"):
            validate_graph(graph)

    def test_conflicting_kinds_for_one_id_rejected(self) -> None:
        with pytest.raises(AtlasError, match="module:a"):
            merge_fragments(
                [
                    Fragment(nodes=[_node("module:a", kind="module")], edges=[]),
                    Fragment(nodes=[_node("module:a", kind="test")], edges=[]),
                ]
            )

    def test_valid_graph_passes(self) -> None:
        nodes = [_node("module:a"), _node("module:b")]
        graph = merge_fragments([Fragment(nodes=nodes, edges=[_edge("module:a", "module:b")])])
        validate_graph(graph)


class TestMerge:
    def test_duplicate_node_unions_provenance(self) -> None:
        other = Provenance(extractor="other", source="elsewhere.py", detail="second sighting")
        first = _node("module:a")
        second = Node(
            id="module:a",
            kind="module",
            label="a",
            evidence=Evidence(level="declared", provenance=[other]),
        )
        graph = merge_fragments([Fragment(nodes=[first], edges=[]), Fragment([second], [])])
        merged = graph.nodes["module:a"]
        assert [p.extractor for p in merged.evidence.provenance] == ["test", "other"]
        assert merged.evidence.level == "implemented"  # max of the two, resolver refines later


class TestCanonicalJson:
    def test_sorted_keys_trailing_newline(self) -> None:
        text = dumps_canonical({"b": 1, "a": [2, 1]})
        assert text.endswith("\n")
        assert json.loads(text) == {"a": [2, 1], "b": 1}
        assert text.index('"a"') < text.index('"b"')


class TestSchemaDrift:
    """The committed JSON Schema and the model constants must agree exactly."""

    def test_enums_match_schema(self, repo_root: Path) -> None:
        schema = json.loads((repo_root / "architecture/atlas/schema/atlas-schema.json").read_text())
        defs = schema["$defs"]
        assert set(defs["node_kind"]["enum"]) == NODE_KINDS
        assert set(defs["edge_type"]["enum"]) == EDGE_TYPES
        assert tuple(defs["evidence_level"]["enum"]) == EVIDENCE_LEVELS
