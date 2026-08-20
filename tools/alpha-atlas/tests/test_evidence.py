"""The evidence resolver: levels are computed from signals, never hand-asserted.

unknown < declared < implemented < connected < tested; observed is never emitted.
A discovered code node needs a documentation anchor (incoming defines edge) to
reach implemented; cross-layer participation reaches connected; an incoming
validates edge reaches tested.
"""

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
_CODE_PROV = Provenance(extractor="python_modules", source="pkg/x.py", detail="fixture")


def _node(node_id: str, kind: str, level: str, *, code: bool = False, **meta: object) -> Node:
    return Node(
        id=node_id,
        kind=kind,
        label=node_id,
        evidence=Evidence(level=level, provenance=[_CODE_PROV if code else _PROV]),
        meta=dict(meta),
    )


def _edge(source: str, target: str, edge_type: str) -> Edge:
    return Edge(
        id=edge_id(source, target, edge_type),
        type=edge_type,
        source=source,
        target=target,
        evidence=Evidence(level="declared", provenance=[_PROV]),
    )


def _resolved(nodes: list[Node], edges: list[Edge]) -> dict[str, str]:
    graph = merge_fragments([Fragment(nodes=nodes, edges=edges)])
    resolve_levels(graph)
    return {node_id: node.evidence.level for node_id, node in graph.nodes.items()}


def test_anchored_workflow_node_is_implemented_and_tested_when_validated() -> None:
    wf = _node("wf:x", "workflow_node", "declared", verified_anchors=[{"path": "a.py"}])
    unanchored = _node("wf:y", "workflow_node", "declared")
    test = _node("test:tests/unit/test_x.py", "test", "implemented")
    levels = _resolved([wf, unanchored, test], [_edge(test.id, wf.id, "validates")])
    assert levels["wf:x"] == "tested"
    assert levels["wf:y"] == "declared"
    assert levels["test:tests/unit/test_x.py"] == "implemented"


def test_undocumented_untested_unlinked_module_stays_unknown() -> None:
    levels = _resolved([_node("module:x.y", "module", "unknown", code=True)], [])
    assert levels["module:x.y"] == "unknown"


def test_documented_code_module_is_implemented() -> None:
    mod = _node("module:x.y", "module", "unknown", code=True)
    rule = _node("rule:.claude/rules/x.md", "rule", "declared")
    levels = _resolved([mod, rule], [_edge(rule.id, mod.id, "defines")])
    assert levels["module:x.y"] == "implemented"


def test_declared_stub_without_code_stays_declared() -> None:
    stub = _node("module:x.gone", "module", "declared")
    rule = _node("rule:.claude/rules/x.md", "rule", "declared")
    levels = _resolved([stub, rule], [_edge(rule.id, stub.id, "defines")])
    assert levels["module:x.gone"] == "declared"


def test_validated_code_module_is_tested() -> None:
    mod = _node("module:x.y", "module", "unknown", code=True)
    test = _node("test:tests/unit/test_y.py", "test", "implemented")
    levels = _resolved([mod, test], [_edge(test.id, mod.id, "validates")])
    assert levels["module:x.y"] == "tested"


def test_cross_layer_edge_promotes_implemented_to_connected() -> None:
    mod = _node("module:x.y", "module", "unknown", code=True)
    rule = _node("rule:.claude/rules/x.md", "rule", "declared")
    cli = _node("cli:alpha x", "cli_command", "declared")
    levels = _resolved(
        [mod, rule, cli],
        [_edge(rule.id, mod.id, "defines"), _edge(cli.id, mod.id, "calls")],
    )
    assert levels["module:x.y"] == "connected"


def test_undocumented_code_module_with_cross_layer_edge_is_connected() -> None:
    mod = _node("module:x.y", "module", "unknown", code=True)
    cli = _node("cli:alpha x", "cli_command", "implemented")
    levels = _resolved([mod, cli], [_edge(cli.id, mod.id, "calls")])
    assert levels["module:x.y"] == "connected"


def test_resolver_never_raises_to_observed() -> None:
    wf = _node("wf:x", "workflow_node", "declared", verified_anchors=[{"path": "a.py"}])
    test = _node("test:tests/unit/test_x.py", "test", "implemented")
    levels = _resolved([wf, test], [_edge(test.id, wf.id, "validates")])
    assert "observed" not in levels.values()
