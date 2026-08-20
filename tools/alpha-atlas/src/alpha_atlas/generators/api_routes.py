"""Extract the web API surface: openapi operations anchored to their routers.

Every operation in the committed openapi.json becomes a route node carrying
its governance classification. The router modules are AST-scanned for
`@router.<verb>("<path>")` decorators (prefix + path joined), which supplies
the implemented anchor (file:line) and a `serves` edge to the router module.
The web layer's CLI invocation is request-dynamic, so no static route→CLI
claim is made — the honest static truth is route → router module.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from alpha_atlas.core.model import Edge, Evidence, Fragment, Node, Provenance, edge_id
from alpha_atlas.generators._repo import record_input

EXTRACTOR = "api_routes"

OPENAPI_REL = "apps/alpha-web/frontend/openapi.json"
CLASSIFICATION_REL = "docs/governance/openapi-operation-classification.json"
ROUTERS_DIR = "apps/alpha-web/src/alpha_web/api"

_HTTP_METHODS = ("get", "post", "put", "delete")


def _router_prefix(tree: ast.Module) -> str:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "APIRouter"
        ):
            for kw in node.keywords:
                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                    return str(kw.value.value)
    return ""


def _router_anchors(source: str) -> dict[tuple[str, str], tuple[str, int]]:
    """(METHOD, full path) -> (function name, line) for one router module."""
    tree = ast.parse(source)
    prefix = _router_prefix(tree)
    anchors: dict[tuple[str, str], tuple[str, int]] = {}
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in func.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in _HTTP_METHODS
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            ):
                path = prefix + str(decorator.args[0].value)
                path = re.sub(r"\{(\w+):[^}]*\}", r"{\1}", path)  # `{symbol:path}` -> `{symbol}`
                anchors[(decorator.func.attr.upper(), path)] = (func.name, func.lineno)
    return anchors


def extract(root: Path) -> tuple[Fragment, dict[str, str]]:
    inputs: dict[str, str] = {}
    spec = json.loads(record_input(root, OPENAPI_REL, inputs).decode("utf-8"))
    classification = json.loads(record_input(root, CLASSIFICATION_REL, inputs).decode("utf-8"))
    modes = {
        (op["method"], op["path"]): (op["mode"], op.get("reason", ""))
        for op in classification["operations"]
    }

    anchors: dict[tuple[str, str], tuple[str, str, int]] = {}
    for path in sorted((root / ROUTERS_DIR).glob("*.py")):
        rel = str(path.relative_to(root))
        source = record_input(root, rel, inputs).decode("utf-8")
        for key, (func_name, line) in _router_anchors(source).items():
            anchors[key] = (rel, func_name, line)

    nodes: list[Node] = []
    edges: list[Edge] = []
    for spec_path, methods in spec["paths"].items():
        for method in methods:
            if method not in _HTTP_METHODS:
                continue
            verb = method.upper()
            node_id = f"route:{verb} {spec_path}"
            operation: dict[str, Any] = methods[method]
            meta: dict[str, Any] = {"operation_id": operation.get("operationId", "")}
            mode = modes.get((verb, spec_path))
            if mode is not None:
                meta["classification"] = mode[0]
                meta["classification_reason"] = mode[1]
            provenance = [
                Provenance(
                    extractor=EXTRACTOR,
                    source=OPENAPI_REL,
                    detail=f"openapi operation {verb} {spec_path}",
                )
            ]
            anchor = anchors.get((verb, spec_path))
            if anchor is not None:
                rel, func_name, line = anchor
                meta["verified_anchors"] = [{"path": rel, "symbol": func_name, "line": line}]
                provenance.append(
                    Provenance(
                        extractor=EXTRACTOR,
                        source=rel,
                        line=line,
                        detail=f"@router.{verb.lower()} handler {func_name}",
                    )
                )
                module = f"module:alpha_web.api.{Path(rel).stem}"
                edges.append(
                    Edge(
                        id=edge_id(node_id, module, "serves"),
                        type="serves",
                        source=node_id,
                        target=module,
                        evidence=Evidence(level="declared", provenance=[provenance[-1]]),
                    )
                )
            nodes.append(
                Node(
                    id=node_id,
                    kind="api_route",
                    label=f"{verb} {spec_path}",
                    component="alpha-web",
                    evidence=Evidence(
                        level="implemented" if anchor is not None else "declared",
                        provenance=provenance,
                    ),
                    meta=meta,
                )
            )
    return Fragment(nodes=nodes, edges=edges), inputs
