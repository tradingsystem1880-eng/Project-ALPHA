"""Scan the SPA: client.ts method→route joins, screens, panels, calls edges.

This is deliberately guarded regex, not a TypeScript compiler: every `/api/...`
literal extracted from client.ts MUST join an openapi path (orphans fail
generation, listed by name) and the method count has a hard floor, so silent
under-extraction cannot masquerade as coverage. Escalation to a ts-morph
script is documented in the design doc, not built.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from alpha_atlas.core.model import AtlasError, Edge, Evidence, Fragment, Node, Provenance, edge_id
from alpha_atlas.generators._repo import record_input
from alpha_atlas.generators.api_routes import OPENAPI_REL

EXTRACTOR = "frontend_scan"

CLIENT_REL = "apps/alpha-web/frontend/src/api/client.ts"
SCREENS_REL = "apps/alpha-web/frontend/src/shell/screens.tsx"
_FRONTEND_SRC = "apps/alpha-web/frontend/src"

_METHOD_FLOOR = 100

# a method entry inside `export const api = { ... }` — `name: (...)` or shorthand `async name(...)`
_ENTRY_RE = re.compile(r"^  (?:async )?(\w+)\s*[:(]", re.MULTILINE)
_URL_RE = re.compile(r"[`']((?:/api|/)[^`'\n]*)[`']")
_API_USE_RE = re.compile(r"\bapi\s*\.\s*(\w+)\s*\(")


def _normalize(url: str) -> str:
    """Client URL -> comparable shape: `/${x}` is a path param, bare `${x}` a query suffix."""
    url = url.split("?", 1)[0]
    url = re.sub(r"/\$\{[^}]*\}", "/{}", url)
    url = re.sub(r"\$\{[^}]*\}", "", url)
    return url.rstrip("/") or "/"


def join_client_methods(root: Path) -> dict[str, tuple[str, str]]:
    """api method name -> (HTTP verb, openapi path). Orphans and thin scans fail loud."""
    client = (root / CLIENT_REL).read_text(encoding="utf-8")
    spec = json.loads((root / OPENAPI_REL).read_text(encoding="utf-8"))
    by_normalized: dict[str, str] = {}
    for spec_path in spec["paths"]:
        normalized = re.sub(r"\{[^}]*\}", "{}", spec_path).rstrip("/") or "/"
        if normalized in by_normalized:
            raise AtlasError(f"openapi paths collide after normalization: {spec_path}")
        by_normalized[normalized] = spec_path

    start = client.index("export const api = {")
    end = client.index("\n}", start)
    body = client[start:end]
    entries = list(_ENTRY_RE.finditer(body))
    methods: dict[str, tuple[str, str]] = {}
    orphans: list[str] = []
    for i, entry in enumerate(entries):
        segment = body[entry.start() : entries[i + 1].start() if i + 1 < len(entries) else None]
        urls = [u for u in _URL_RE.findall(segment) if u.startswith("/api")]
        if not urls:
            continue
        verb = "GET"
        if "postJSON" in segment or "method: 'POST'" in segment:
            verb = "POST"
        if "method: 'DELETE'" in segment:
            verb = "DELETE"
        spec_path = by_normalized.get(_normalize(urls[0]))
        if spec_path is None:
            orphans.append(f"{entry.group(1)}: {urls[0]}")
            continue
        methods[entry.group(1)] = (verb, spec_path)
    if orphans:
        raise AtlasError(
            "client.ts paths with no openapi match (fix the scan or the client): "
            + "; ".join(sorted(orphans))
        )
    if len(methods) < _METHOD_FLOOR:
        raise AtlasError(
            f"client.ts scan found only {len(methods)} methods (< {_METHOD_FLOOR}); "
            "the regex extraction has silently degraded"
        )
    return methods


def _screens(source: str) -> list[tuple[str, str, list[str]]]:
    """(screen id, label, [component names]) parsed from the SCREENS literal."""
    start = source.index("export const SCREENS")
    body = source[start:].split("\n]", 1)[0]
    screens: list[tuple[str, str, list[str]]] = []
    current: tuple[str, str, list[str]] | None = None
    for match in re.finditer(r"id: '(\w+)'|label: '([^']+)'|component: (\w+)", body):
        screen_id, label, component = match.groups()
        if screen_id:
            current = (screen_id, "", [])
            screens.append(current)
        elif label and current and not current[1]:
            screens[-1] = current = (current[0], label, current[2])
        elif component and current and component not in current[2]:
            current[2].append(component)
    return screens


def extract(root: Path) -> tuple[Fragment, dict[str, str]]:
    inputs: dict[str, str] = {}
    record_input(root, CLIENT_REL, inputs)
    record_input(root, OPENAPI_REL, inputs)
    methods = join_client_methods(root)
    screens_source = record_input(root, SCREENS_REL, inputs).decode("utf-8")

    nodes: list[Node] = []
    edges: list[Edge] = []
    panel_files: dict[str, str] = {}
    for screen_id, label, component_names in _screens(screens_source):
        node_id = f"screen:{screen_id}"
        provenance = Provenance(
            extractor=EXTRACTOR, source=SCREENS_REL, detail=f"SCREENS entry {screen_id!r}"
        )
        nodes.append(
            Node(
                id=node_id,
                kind="screen",
                label=screen_id,
                component="alpha-web",
                evidence=Evidence(level="implemented", provenance=[provenance]),
                meta={"label": label},
            )
        )
        for component_name in component_names:
            panel_id = f"panel:{component_name}"
            if component_name not in panel_files:
                candidates = (
                    f"{_FRONTEND_SRC}/panels/{component_name}.tsx",
                    f"{_FRONTEND_SRC}/shell/{component_name}.tsx",
                )
                found = next((c for c in candidates if (root / c).is_file()), None)
                panel_files[component_name] = found or ""
                meta: dict[str, object] = {}
                if found:
                    record_input(root, found, inputs)
                    meta["verified_anchors"] = [
                        {"path": found, "symbol": component_name, "line": 1}
                    ]
                nodes.append(
                    Node(
                        id=panel_id,
                        kind="panel",
                        label=component_name,
                        path=found,
                        component="alpha-web",
                        evidence=Evidence(
                            level="implemented" if found else "declared",
                            provenance=[
                                Provenance(
                                    extractor=EXTRACTOR,
                                    source=found or SCREENS_REL,
                                    detail="screen pane component",
                                )
                            ],
                        ),
                        meta=meta,
                    )
                )
            edges.append(
                Edge(
                    id=edge_id(panel_id, node_id, "part_of"),
                    type="part_of",
                    source=panel_id,
                    target=node_id,
                    evidence=Evidence(level="declared", provenance=[provenance]),
                )
            )

    for component_name, rel in sorted(panel_files.items()):
        if not rel:
            continue
        source = (root / rel).read_text(encoding="utf-8")
        unmatched: list[str] = []
        for used in sorted(set(_API_USE_RE.findall(source))):
            entry = methods.get(used)
            if entry is None:
                unmatched.append(used)
                continue
            verb, spec_path = entry
            edges.append(
                Edge(
                    id=edge_id(f"panel:{component_name}", f"route:{verb} {spec_path}", "calls"),
                    type="calls",
                    source=f"panel:{component_name}",
                    target=f"route:{verb} {spec_path}",
                    evidence=Evidence(
                        level="declared",
                        provenance=[
                            Provenance(
                                extractor=EXTRACTOR,
                                source=rel,
                                detail=f"api.{used}(...)",
                            )
                        ],
                    ),
                )
            )
        if unmatched:
            raise AtlasError(
                f"{rel} uses api methods the client scan did not resolve: " + ", ".join(unmatched)
            )
    return Fragment(nodes=nodes, edges=edges), inputs
