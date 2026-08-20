"""Curated workflow/entity definitions -> verified graph nodes.

Definitions live in architecture/atlas/definitions/*.json. Every node entry
must carry the anti-drift metadata (owner, created_from, last_verified_commit,
confidence — confidence rates documentation/provenance quality, never
architectural correctness). Anchors are path+symbol pairs: the file must exist
and the symbol must resolve via AST (its current line is recomputed every run,
so line numbers can never rot). A stored anchor sha256 that no longer matches
the file downgrades the entry to a visible needs_reverification state instead
of silently presenting stale prose. Artifact entries are plain vocabulary
(id/label/description) — they carry no claims, so no metadata block.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from alpha_atlas.core.model import AtlasError, Edge, Evidence, Fragment, Node, Provenance, edge_id
from alpha_atlas.generators._repo import record_input, symbol_line

EXTRACTOR = "workflow"

DEFINITION_FILES = (
    "architecture/atlas/definitions/research-lifecycle.json",
    "architecture/atlas/definitions/data-lineage.json",
)

_REQUIRED_FIELDS = (
    "id",
    "kind",
    "label",
    "purpose",
    "owner",
    "created_from",
    "last_verified_commit",
    "confidence",
    "anchors",
)
_PASSTHROUGH_FIELDS = (
    "purpose",
    "order",
    "inputs",
    "outputs",
    "limitations",
    "safe_change",
    "owner",
    "created_from",
    "last_verified_commit",
    "confidence",
)


def _verify_anchors(
    root: Path, entry_id: str, anchors: list[dict[str, Any]], inputs: dict[str, str]
) -> tuple[list[dict[str, Any]], bool]:
    verified: list[dict[str, Any]] = []
    needs_reverification = False
    for anchor in anchors:
        rel = str(anchor["path"])
        if not (root / rel).is_file():
            raise AtlasError(f"{entry_id}: anchor file does not exist: {rel}")
        raw = record_input(root, rel, inputs)
        symbol = str(anchor.get("symbol", ""))
        line = 1
        if symbol:
            resolved = symbol_line(raw.decode("utf-8"), symbol)
            if resolved is None:
                raise AtlasError(f"{entry_id}: anchor symbol {symbol!r} not found in {rel}")
            line = resolved
        actual = hashlib.sha256(raw).hexdigest()
        expected = anchor.get("sha256")
        if expected is not None and expected != actual:
            needs_reverification = True
        verified.append({"path": rel, "symbol": symbol, "line": line, "sha256": actual})
    return verified, needs_reverification


def _node_from_entry(
    root: Path, source_rel: str, entry: dict[str, Any], inputs: dict[str, str]
) -> tuple[Node, list[Edge]]:
    missing = [field for field in _REQUIRED_FIELDS if field not in entry]
    if missing:
        raise AtlasError(
            f"definition entry {entry.get('id', '?')} in {source_rel} "
            f"is missing required metadata: {', '.join(missing)}"
        )
    entry_id = str(entry["id"])
    verified, needs_reverification = _verify_anchors(root, entry_id, list(entry["anchors"]), inputs)
    provenance = [
        Provenance(extractor=EXTRACTOR, source=source_rel, detail="curated definition")
    ] + [
        Provenance(
            extractor=EXTRACTOR,
            source=a["path"],
            detail=f"anchor symbol {a['symbol'] or a['path']}",
            line=a["line"],
        )
        for a in verified
    ]
    meta: dict[str, Any] = {k: entry[k] for k in _PASSTHROUGH_FIELDS if k in entry}
    meta["verified_anchors"] = verified
    if needs_reverification:
        meta["needs_reverification"] = True
    node = Node(
        id=entry_id,
        kind=str(entry["kind"]),
        label=str(entry["label"]),
        evidence=Evidence(level="implemented" if verified else "declared", provenance=provenance),
        meta=meta,
    )
    edge_evidence = Evidence(level="declared", provenance=[provenance[0]])
    edges = [
        Edge(edge_id(doc, entry_id, "defines"), "defines", doc, entry_id, edge_evidence)
        for doc in entry.get("docs", [])
    ]
    edges += [
        Edge(edge_id(entry_id, out, "produces"), "produces", entry_id, out, edge_evidence)
        for out in entry.get("produces", [])
    ]
    edges += [
        Edge(edge_id(entry_id, dep, "depends_on"), "depends_on", entry_id, dep, edge_evidence)
        for dep in entry.get("depends_on", [])
    ]
    return node, edges


def _artifact_node(source_rel: str, entry: dict[str, Any]) -> Node:
    return Node(
        id=str(entry["id"]),
        kind="artifact",
        label=str(entry["label"]),
        evidence=Evidence(
            level="declared",
            provenance=[
                Provenance(extractor=EXTRACTOR, source=source_rel, detail="curated artifact")
            ],
        ),
        meta={"description": entry.get("description", "")},
    )


def extract(root: Path) -> tuple[Fragment, dict[str, str]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    inputs: dict[str, str] = {}
    for rel in DEFINITION_FILES:
        payload = json.loads(record_input(root, rel, inputs).decode("utf-8"))
        for entry in payload.get("nodes", []):
            node, entry_edges = _node_from_entry(root, rel, entry, inputs)
            nodes.append(node)
            edges.extend(entry_edges)
        nodes.extend(_artifact_node(rel, entry) for entry in payload.get("artifacts", []))
    return Fragment(nodes=nodes, edges=edges), inputs
