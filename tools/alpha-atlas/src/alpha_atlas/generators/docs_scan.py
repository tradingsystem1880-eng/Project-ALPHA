"""Extract ADRs and specs into doc nodes.

ADR headers are uniform across the repo (`# ADR-NNNN: title`, `**Status:**`,
`**Date:**`, `**Deciders:**`); 15 ADRs additionally carry an
`## Implementation anchors` section whose file paths are harvested into meta.
Doc nodes are always `declared` — a document never proves implementation.
"""

from __future__ import annotations

import re
from pathlib import Path

from alpha_atlas.core.model import Evidence, Fragment, Node, Provenance
from alpha_atlas.generators._repo import record_input

EXTRACTOR = "docs_scan"

_ADR_TITLE_RE = re.compile(r"^#\s+ADR-(\d{4}):\s*(.+?)\s*$", re.MULTILINE)
_HEADER_RE = re.compile(r"^\*\*(Status|Date|Deciders):\*\*\s*(.+?)\s*$", re.MULTILINE)
_PATHLIKE_RE = re.compile(r"[\w][\w./_-]*\.(?:py|md|toml|json|yml|yaml)")
_FIRST_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _anchor_section(text: str) -> list[str]:
    lines = text.splitlines()
    collected: set[str] = set()
    capturing = False
    for line in lines:
        if line.lower().startswith("## implementation anchors"):
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing:
            collected.update(_PATHLIKE_RE.findall(line))
    return sorted(collected)


def _adr_node(rel: str, text: str) -> Node:
    title_match = _ADR_TITLE_RE.search(text)
    number = rel.split("/")[-1][:4]
    label = title_match.group(2) if title_match else Path(rel).stem
    meta: dict[str, object] = {"doc_type": "adr"}
    for field, value in _HEADER_RE.findall(text):
        meta[field.lower()] = value
    anchors = _anchor_section(text)
    if anchors:
        meta["implementation_anchors"] = anchors
    return Node(
        id=f"doc:ADR-{number}",
        kind="doc",
        label=label,
        path=rel,
        evidence=Evidence(
            level="declared",
            provenance=[Provenance(extractor=EXTRACTOR, source=rel, detail="ADR header", line=1)],
        ),
        meta=meta,
    )


def _spec_node(rel: str, text: str) -> Node:
    heading = _FIRST_HEADING_RE.search(text)
    return Node(
        id=f"doc:{rel}",
        kind="doc",
        label=heading.group(1) if heading else Path(rel).stem,
        path=rel,
        evidence=Evidence(
            level="declared",
            provenance=[Provenance(extractor=EXTRACTOR, source=rel, detail="spec", line=1)],
        ),
        meta={"doc_type": "spec"},
    )


def extract(root: Path) -> tuple[Fragment, dict[str, str]]:
    nodes: list[Node] = []
    inputs: dict[str, str] = {}
    for path in sorted((root / "docs/adr").glob("0*.md")):
        rel = str(path.relative_to(root))
        nodes.append(_adr_node(rel, record_input(root, rel, inputs).decode("utf-8")))
    for path in sorted((root / "docs/superpowers/specs").glob("*.md")):
        rel = str(path.relative_to(root))
        nodes.append(_spec_node(rel, record_input(root, rel, inputs).decode("utf-8")))
    return Fragment(nodes=nodes, edges=[]), inputs
