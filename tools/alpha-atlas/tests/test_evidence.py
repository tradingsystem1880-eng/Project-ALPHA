"""The minimal S2 evidence resolver: anchors raise declared->implemented, validates->tested."""

from alpha_atlas.core.evidence import resolve_levels
from alpha_atlas.core.model import (
    Edge,
    Evidence,
    Fragment,
    Node,
    Provenance,
    edge_id,
    merge_fragments,
)

_PROV = Provenance(extractor="test", source="tests/test_evidence.py", detail="fixture")


def _node(node_id: str, kind: str, level: str, **meta: object) -> Node:
    return Node(
        id=node_id,
        kind=kind,
        label=node_id,
        evidence=Evidence(level=level, provenance=[_PROV]),
        meta=dict(meta),
    )


def test_anchored_workflow_node_is_implemented_and_tested_when_validated() -> None:
    wf = _node("wf:x", "workflow_node", "declared", verified_anchors=[{"path": "a.py"}])
    unanchored = _node("wf:y", "workflow_node", "declared")
    test = _node("test:tests/unit/test_x.py", "test", "implemented")
    edge = Edge(
        id=edge_id(test.id, wf.id, "validates"),
        type="validates",
        source=test.id,
        target=wf.id,
        evidence=Evidence(level="implemented", provenance=[_PROV]),
    )
    graph = merge_fragments([Fragment(nodes=[wf, unanchored, test], edges=[edge])])
    resolve_levels(graph)
    assert graph.nodes["wf:x"].evidence.level == "tested"
    assert graph.nodes["wf:y"].evidence.level == "declared"
    assert graph.nodes["test:tests/unit/test_x.py"].evidence.level == "implemented"


def test_resolver_never_raises_to_observed() -> None:
    wf = _node("wf:x", "workflow_node", "declared", verified_anchors=[{"path": "a.py"}])
    graph = merge_fragments([Fragment(nodes=[wf], edges=[])])
    resolve_levels(graph)
    assert graph.nodes["wf:x"].evidence.level != "observed"
