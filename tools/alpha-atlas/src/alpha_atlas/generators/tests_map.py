"""Map test files to the lifecycle nodes their imports validate.

Tests import their targets with absolute `from alpha_x.y import ...`
statements, so a static import scan resolves each test to source paths; when a
resolved path is the PRIMARY (first) verified anchor of a workflow/entity node,
the test emits a `validates` edge to that node. Secondary anchors never join:
control_store.py anchors six lifecycle nodes, and joining through it would let
any store test "validate" all of them — exactly the overclaiming Atlas exists
to prevent. tests/holdout/ is deliberately never globbed or read — those are
hidden behaviour tests agents must not observe.
"""

from __future__ import annotations

import ast
from pathlib import Path

from alpha_atlas.core.model import Edge, Evidence, Fragment, Node, Provenance, edge_id
from alpha_atlas.generators._repo import module_roots, module_to_path, record_input

EXTRACTOR = "tests_map"

_CATEGORIES = ("unit", "integration", "bias_guards", "oracles", "holdout_seed")


def _imported_modules(source: str) -> list[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return sorted(m for m in modules if m.split(".", 1)[0].startswith("alpha_"))


def _anchor_index(workflow_fragment: Fragment | None) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    if workflow_fragment is None:
        return index
    for node in workflow_fragment.nodes:
        anchors = node.meta.get("verified_anchors", [])
        if anchors:
            index.setdefault(str(anchors[0]["path"]), []).append(node.id)
    return {path: sorted(ids) for path, ids in index.items()}


def extract(
    root: Path,
    *,
    workflow_fragment: Fragment | None,
    module_ids: set[str] | None = None,
) -> tuple[Fragment, dict[str, str]]:
    anchored = _anchor_index(workflow_fragment)
    known_modules = module_ids or set()
    roots = module_roots(root)
    nodes: list[Node] = []
    edges: list[Edge] = []
    inputs: dict[str, str] = {}
    for category in _CATEGORIES:
        for path in sorted((root / "tests" / category).rglob("test_*.py")):
            rel = str(path.relative_to(root))
            source = record_input(root, rel, inputs).decode("utf-8")
            targets = _imported_modules(source)
            evidence = Evidence(
                level="implemented",
                provenance=[Provenance(extractor=EXTRACTOR, source=rel, detail=f"{category} test")],
            )
            test_id = f"test:{rel}"
            nodes.append(
                Node(
                    id=test_id,
                    kind="test",
                    label=path.name,
                    path=rel,
                    evidence=evidence,
                    meta={"category": category, "targets": targets},
                )
            )
            for target in targets:
                module_id = f"module:{target}"
                if module_id in known_modules:
                    edges.append(
                        Edge(
                            id=edge_id(test_id, module_id, "validates"),
                            type="validates",
                            source=test_id,
                            target=module_id,
                            evidence=Evidence(
                                level="implemented",
                                provenance=[
                                    Provenance(
                                        extractor=EXTRACTOR,
                                        source=rel,
                                        detail=f"imports {target}",
                                    )
                                ],
                            ),
                        )
                    )
                resolved = module_to_path(root, target, roots)
                if resolved is None:
                    continue
                for wf_id in anchored.get(resolved, []):
                    edges.append(
                        Edge(
                            id=edge_id(test_id, wf_id, "validates"),
                            type="validates",
                            source=test_id,
                            target=wf_id,
                            evidence=Evidence(
                                level="implemented",
                                provenance=[
                                    Provenance(
                                        extractor=EXTRACTOR,
                                        source=rel,
                                        detail=f"imports {target}",
                                    )
                                ],
                            ),
                        )
                    )
    return Fragment(nodes=nodes, edges=edges), inputs
