"""Minimal v1 evidence resolver: levels are computed, never hand-asserted.

Rules (v1, extended in later slices): a node with at least one verified code
anchor is `implemented`; an implemented-or-better node with an incoming
`validates` edge is `tested`. The resolver never emits `observed` (reserved
for the Phase 7 runtime layer) and never lowers a level.
"""

from __future__ import annotations

from alpha_atlas.core.model import EVIDENCE_LEVELS, Graph

_IMPLEMENTED = EVIDENCE_LEVELS.index("implemented")
_TESTED = EVIDENCE_LEVELS.index("tested")


def resolve_levels(graph: Graph) -> None:
    for node in graph.nodes.values():
        if (
            node.meta.get("verified_anchors")
            and EVIDENCE_LEVELS.index(node.evidence.level) < _IMPLEMENTED
        ):
            node.evidence.level = "implemented"
    validated = {edge.target for edge in graph.edges.values() if edge.type == "validates"}
    for node_id in validated:
        target = graph.nodes.get(node_id)
        if target is None:
            continue
        rank = EVIDENCE_LEVELS.index(target.evidence.level)
        if _IMPLEMENTED <= rank < _TESTED:
            target.evidence.level = "tested"
