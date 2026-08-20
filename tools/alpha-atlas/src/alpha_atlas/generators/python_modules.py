"""Extract Python modules and their import dependencies from the source tree.

Modules are emitted at level `unknown` — discovery proves a file exists, not
that a feature does. The resolver promotes a module only when a documentation
anchor, cross-layer edge, or validating test supplies the evidence. Import
edges carry the importing file and line so every `depends_on` claim is
checkable.
"""

from __future__ import annotations

import ast
from pathlib import Path

from alpha_atlas.core.model import Edge, Evidence, Fragment, Node, Provenance, edge_id
from alpha_atlas.generators._repo import record_input, source_roots

EXTRACTOR = "python_modules"


def _dotted(pkg: str, rel_to_src: Path) -> str:
    parts = list(rel_to_src.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([pkg, *parts]) if parts else pkg


def _imports(source: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            out.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.append((node.module, node.lineno))
    return out


def extract(root: Path) -> tuple[Fragment, dict[str, str]]:
    roots = source_roots(root)
    nodes: list[Node] = []
    edges: list[Edge] = []
    inputs: dict[str, str] = {}

    def known_module(dotted: str) -> str | None:
        """Longest known module prefix of a dotted import, as a node id."""
        top = dotted.split(".", 1)[0]
        entry = roots.get(top)
        if entry is None:
            return None
        src_dir, _ = entry
        parts = dotted.split(".")
        while parts:
            stem = "/".join([src_dir, *parts[1:]]) if len(parts) > 1 else src_dir
            if (root / f"{stem}.py").is_file() or (root / stem / "__init__.py").is_file():
                return f"module:{'.'.join(parts)}"
            parts = parts[:-1]
        return None

    for pkg, (src_dir, component) in sorted(roots.items()):
        for path in sorted((root / src_dir).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = str(path.relative_to(root))
            source = record_input(root, rel, inputs).decode("utf-8")
            module_id = f"module:{_dotted(pkg, path.relative_to(root / src_dir))}"
            nodes.append(
                Node(
                    id=module_id,
                    kind="module",
                    label=module_id.removeprefix("module:"),
                    path=rel,
                    component=component,
                    evidence=Evidence(
                        level="unknown",
                        provenance=[
                            Provenance(extractor=EXTRACTOR, source=rel, detail="python module")
                        ],
                    ),
                )
            )
            edges.append(
                Edge(
                    id=edge_id(module_id, f"component:{component}", "part_of"),
                    type="part_of",
                    source=module_id,
                    target=f"component:{component}",
                    evidence=Evidence(
                        level="declared",
                        provenance=[
                            Provenance(extractor=EXTRACTOR, source=rel, detail="source location")
                        ],
                    ),
                )
            )
            for imported, lineno in _imports(source):
                target_id = known_module(imported)
                if target_id is None or target_id == module_id:
                    continue
                edges.append(
                    Edge(
                        id=edge_id(module_id, target_id, "depends_on"),
                        type="depends_on",
                        source=module_id,
                        target=target_id,
                        evidence=Evidence(
                            level="declared",
                            provenance=[
                                Provenance(
                                    extractor=EXTRACTOR,
                                    source=rel,
                                    line=lineno,
                                    detail=f"imports {imported}",
                                )
                            ],
                        ),
                    )
                )
    return Fragment(nodes=nodes, edges=edges), inputs
