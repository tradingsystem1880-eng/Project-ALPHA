"""Evidence resolver: levels are computed from graph signals, never hand-asserted.

Ordered ladder: unknown < declared < implemented < connected < tested < observed.
- A node with verified curated anchors is `implemented`.
- A discovered code node (code-extractor provenance) is `implemented` only once
  a documentation anchor (incoming `defines` edge) exists; until then it stays
  `unknown` and belongs in the review queue.
- An implemented node participating in a cross-layer calls/serves/implements
  edge is `connected`.
- An incoming `validates` edge promotes an implemented-or-code node to `tested`.
The resolver never emits `observed` (reserved for the Phase 7 runtime layer)
and never lowers a level.
"""

from __future__ import annotations

from alpha_atlas.core.model import EVIDENCE_LEVELS, Graph, Node

_IMPLEMENTED = EVIDENCE_LEVELS.index("implemented")
_CONNECTED = EVIDENCE_LEVELS.index("connected")
_TESTED = EVIDENCE_LEVELS.index("tested")

_CODE_EXTRACTORS = frozenset({"python_modules", "components"})
_CODE_KINDS = frozenset({"module", "component"})
_CROSS_LAYER_TYPES = frozenset({"calls", "serves", "implements"})


def _has_code(node: Node) -> bool:
    """True when an extractor saw actual source for this node (not just prose about it)."""
    if node.meta.get("verified_anchors"):
        return True
    return node.kind in _CODE_KINDS and any(
        p.extractor in _CODE_EXTRACTORS and p.source.endswith((".py", "pyproject.toml"))
        for p in node.evidence.provenance
    )


def _raise_to(node: Node, level_index: int) -> None:
    if EVIDENCE_LEVELS.index(node.evidence.level) < level_index:
        node.evidence.level = EVIDENCE_LEVELS[level_index]


def resolve_levels(graph: Graph) -> None:
    documented: set[str] = set()
    cross_layer: set[str] = set()
    validated: set[str] = set()
    for edge in graph.edges.values():
        if edge.type == "defines":
            documented.add(edge.target)
        elif edge.type in _CROSS_LAYER_TYPES:
            cross_layer.update((edge.source, edge.target))
        elif edge.type == "validates":
            validated.add(edge.target)

    for node in graph.nodes.values():
        if node.meta.get("verified_anchors") or (_has_code(node) and node.id in documented):
            _raise_to(node, _IMPLEMENTED)
        if EVIDENCE_LEVELS.index(node.evidence.level) >= _IMPLEMENTED and node.id in cross_layer:
            _raise_to(node, _CONNECTED)
        if node.id in validated and (
            _has_code(node) or EVIDENCE_LEVELS.index(node.evidence.level) >= _IMPLEMENTED
        ):
            _raise_to(node, _TESTED)
