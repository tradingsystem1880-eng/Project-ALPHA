"""Extract workspace components and the .claude/rules MODULE MAP layer.

Components are the packages/apps/workers directories (one pyproject.toml each).
The path-scoped rules carry the drift-tested MODULE MAP: a heading per package
with a responsibility one-liner, and a table row per module. Rows become
declared-level module stubs with `defines` edges — the documentation anchor the
evidence resolver requires before a discovered module may claim `implemented`.
A component no rule documents (the workers today) stays `unknown` and lands in
the review queue rather than being silently promoted.
"""

from __future__ import annotations

import re
from pathlib import Path

from alpha_atlas.core.model import Edge, Evidence, Fragment, Node, Provenance, edge_id
from alpha_atlas.generators._repo import record_input

EXTRACTOR = "components"

_COMPONENT_GLOBS = ("packages/*", "apps/*", "workers/*")

# ### `alpha_core` (`packages/alpha-core/src/alpha_core/`) — one-liner
# (alpha-patterns.md writes the same shape as a paragraph, without the ### prefix)
_HEADING_RE = re.compile(r"^(?:#{2,3} )?`(?P<pkg>\w+)` \(`(?P<dir>[^`]+?)/?`\) — (?P<desc>.+)$")
# | `a.py` · `b.py` | responsibility | symbols |
_ROW_RE = re.compile(r"^\|(?P<modules>[^|]+)\|(?P<resp>[^|]+)\|")
_MODULE_TOKEN_RE = re.compile(r"`([\w./]+\.py)`")


def _dotted(pkg: str, rel: str) -> str:
    parts = rel.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([pkg, *parts]) if parts else pkg


def extract(root: Path) -> tuple[Fragment, dict[str, str]]:
    inputs: dict[str, str] = {}
    components: dict[str, Node] = {}
    for glob in _COMPONENT_GLOBS:
        for path in sorted(root.glob(glob)):
            if not (path / "pyproject.toml").is_file():
                continue
            rel = str(path.relative_to(root))
            record_input(root, f"{rel}/pyproject.toml", inputs)
            components[rel] = Node(
                id=f"component:{path.name}",
                kind="component",
                label=path.name,
                path=rel,
                evidence=Evidence(
                    level="unknown",
                    provenance=[
                        Provenance(
                            extractor=EXTRACTOR,
                            source=f"{rel}/pyproject.toml",
                            detail="workspace directory with a pyproject.toml",
                        )
                    ],
                ),
                meta={},
            )
    nodes: list[Node] = []
    edges: list[Edge] = []
    for rule_path in sorted((root / ".claude/rules").glob("*.md")):
        rel = f".claude/rules/{rule_path.name}"
        text = record_input(root, rel, inputs).decode("utf-8", errors="replace")
        rule_id = f"rule:{rel}"
        nodes.append(
            Node(
                id=rule_id,
                kind="rule",
                label=rule_path.name,
                path=rel,
                evidence=Evidence(
                    level="declared",
                    provenance=[
                        Provenance(extractor=EXTRACTOR, source=rel, detail="path-scoped rule file")
                    ],
                ),
            )
        )
        current: tuple[str, str] | None = None  # (pkg import name, component dir)
        for lineno, line in enumerate(text.splitlines(), start=1):
            heading = _HEADING_RE.match(line)
            if heading:
                component_dir = "/".join(heading.group("dir").split("/")[:2])
                component = components.get(component_dir)
                if component is None:
                    current = None
                    continue
                current = (heading.group("pkg"), component_dir)
                component.evidence = Evidence(
                    level="declared",
                    provenance=component.evidence.provenance
                    + [
                        Provenance(
                            extractor=EXTRACTOR,
                            source=rel,
                            line=lineno,
                            detail="MODULE MAP heading",
                        )
                    ],
                )
                component.meta["responsibility"] = heading.group("desc").strip()
                edges.append(
                    Edge(
                        id=edge_id(rule_id, component.id, "defines"),
                        type="defines",
                        source=rule_id,
                        target=component.id,
                        evidence=Evidence(
                            level="declared",
                            provenance=[
                                Provenance(
                                    extractor=EXTRACTOR,
                                    source=rel,
                                    line=lineno,
                                    detail="MODULE MAP heading",
                                )
                            ],
                        ),
                    )
                )
                continue
            row = _ROW_RE.match(line)
            if row is None or current is None:
                continue
            responsibility = row.group("resp").strip()
            if responsibility in ("Responsibility", "") or set(responsibility) == {"-"}:
                continue
            pkg, component_dir = current
            for module_rel in _MODULE_TOKEN_RE.findall(row.group("modules")):
                module_id = f"module:{_dotted(pkg, module_rel)}"
                provenance = Provenance(
                    extractor=EXTRACTOR, source=rel, line=lineno, detail="MODULE MAP row"
                )
                nodes.append(
                    Node(
                        id=module_id,
                        kind="module",
                        label=module_id.removeprefix("module:"),
                        component=Path(component_dir).name,
                        evidence=Evidence(level="declared", provenance=[provenance]),
                        meta={"responsibility": responsibility},
                    )
                )
                edges.append(
                    Edge(
                        id=edge_id(rule_id, module_id, "defines"),
                        type="defines",
                        source=rule_id,
                        target=module_id,
                        evidence=Evidence(level="declared", provenance=[provenance]),
                    )
                )
    return Fragment(nodes=[*components.values(), *nodes], edges=edges), inputs
