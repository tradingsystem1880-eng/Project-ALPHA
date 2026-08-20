"""Atlas graph model: typed nodes and edges, merge, validation, canonical JSON.

Evidence levels are computed claims, never hand-asserted; every node and edge
carries provenance naming the extractor and repository file that produced it.
The 'observed' level is reserved for the deferred Phase 7 runtime layer and is
rejected by validation in v1.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

EVIDENCE_LEVELS: tuple[str, ...] = (
    "unknown",
    "declared",
    "implemented",
    "connected",
    "tested",
    "observed",
)

NODE_KINDS: frozenset[str] = frozenset(
    {
        "component",
        "module",
        "cli_command",
        "mcp_tool",
        "api_route",
        "screen",
        "panel",
        "workflow_node",
        "test",
        "doc",
        "rule",
        "artifact",
        "contract",
        "research_case",
        "hypothesis",
        "dataset",
        "experiment",
        "decision",
        "strategy_version",
        "runtime_observation",
    }
)

EDGE_TYPES: frozenset[str] = frozenset(
    {
        "depends_on",
        "implements",
        "validates",
        "defines",
        "calls",
        "serves",
        "produces",
        "part_of",
    }
)


class AtlasError(ValueError):
    """A graph inconsistency; generation must stop rather than emit a lie."""


@dataclass(frozen=True)
class Provenance:
    extractor: str
    source: str
    detail: str
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "extractor": self.extractor,
            "source": self.source,
            "detail": self.detail,
        }
        if self.line is not None:
            payload["line"] = self.line
        return payload


@dataclass
class Evidence:
    level: str
    provenance: list[Provenance]

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "provenance": [p.to_dict() for p in self.provenance]}


@dataclass
class Node:
    id: str
    kind: str
    label: str
    evidence: Evidence
    path: str | None = None
    component: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "evidence": self.evidence.to_dict(),
        }
        if self.path is not None:
            payload["path"] = self.path
        if self.component is not None:
            payload["component"] = self.component
        if self.meta:
            payload["meta"] = self.meta
        return payload


@dataclass
class Edge:
    id: str
    type: str
    source: str
    target: str
    evidence: Evidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "evidence": self.evidence.to_dict(),
        }


def edge_id(source: str, target: str, edge_type: str) -> str:
    return f"e:{source}->{target}#{edge_type}"


@dataclass
class Fragment:
    nodes: list[Node]
    edges: list[Edge]


@dataclass
class Graph:
    nodes: dict[str, Node]
    edges: dict[str, Edge]


def _level_rank(level: str) -> int:
    try:
        return EVIDENCE_LEVELS.index(level)
    except ValueError as exc:
        raise AtlasError(f"unknown evidence level: {level!r}") from exc


def _merged_evidence(existing: Evidence, incoming: Evidence) -> Evidence:
    provenance = existing.provenance + [
        p for p in incoming.provenance if p not in existing.provenance
    ]
    level = max(existing.level, incoming.level, key=_level_rank)
    return Evidence(level=level, provenance=provenance)


def merge_fragments(fragments: Iterable[Fragment]) -> Graph:
    """Union fragments by id: provenance accumulates, kinds must agree, max level wins."""
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    for fragment in fragments:
        for node in fragment.nodes:
            existing = nodes.get(node.id)
            if existing is None:
                nodes[node.id] = node
                continue
            if existing.kind != node.kind:
                raise AtlasError(
                    f"conflicting kinds for {node.id}: {existing.kind!r} vs {node.kind!r}"
                )
            nodes[node.id] = Node(
                id=existing.id,
                kind=existing.kind,
                label=existing.label,
                evidence=_merged_evidence(existing.evidence, node.evidence),
                path=existing.path if existing.path is not None else node.path,
                component=existing.component if existing.component is not None else node.component,
                meta={**existing.meta, **node.meta},
            )
        for edge in fragment.edges:
            existing_edge = edges.get(edge.id)
            if existing_edge is None:
                edges[edge.id] = edge
                continue
            edges[edge.id] = Edge(
                id=existing_edge.id,
                type=existing_edge.type,
                source=existing_edge.source,
                target=existing_edge.target,
                evidence=_merged_evidence(existing_edge.evidence, edge.evidence),
            )
    return Graph(nodes=nodes, edges=edges)


def validate_graph(graph: Graph) -> None:
    """Fail loud, naming every offending id, before anything is written."""
    problems: list[str] = []
    for node in graph.nodes.values():
        if node.kind not in NODE_KINDS:
            problems.append(f"node {node.id}: unknown kind {node.kind!r}")
        _check_evidence(f"node {node.id}", node.evidence, problems)
    for edge in graph.edges.values():
        if edge.type not in EDGE_TYPES:
            problems.append(f"edge {edge.id}: unknown type {edge.type!r}")
        for endpoint in (edge.source, edge.target):
            if endpoint not in graph.nodes:
                problems.append(f"edge {edge.id}: dangling endpoint {endpoint}")
        _check_evidence(f"edge {edge.id}", edge.evidence, problems)
    if problems:
        raise AtlasError("invalid atlas graph:\n" + "\n".join(sorted(problems)))


def _check_evidence(owner: str, evidence: Evidence, problems: list[str]) -> None:
    if evidence.level not in EVIDENCE_LEVELS:
        problems.append(f"{owner}: unknown evidence level {evidence.level!r}")
    elif evidence.level == "observed":
        problems.append(f"{owner}: level 'observed' is reserved for the Phase 7 runtime layer")
    if not evidence.provenance:
        problems.append(f"{owner}: evidence without provenance")


def graph_payload(graph: Graph, inputs_hash: str) -> dict[str, Any]:
    nodes = [graph.nodes[node_id].to_dict() for node_id in sorted(graph.nodes)]
    edges = [graph.edges[eid].to_dict() for eid in sorted(graph.edges)]
    kind_counts = Counter(graph.nodes[node_id].kind for node_id in graph.nodes)
    type_counts = Counter(graph.edges[eid].type for eid in graph.edges)
    return {
        "schema_version": SCHEMA_VERSION,
        "inputs_hash": inputs_hash,
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes_by_kind": dict(sorted(kind_counts.items())),
            "edges_by_type": dict(sorted(type_counts.items())),
        },
    }


def dumps_canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
