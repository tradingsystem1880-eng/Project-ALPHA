"""Extract the pinned MCP tool surface and its argv-literal bridges to the CLI.

Tools are the `@mcp.tool()` functions in alpha_mcp/server.py (governance-pinned
at 62). Action tools build an argv list of leading string literals before
subprocessing the CLI; the longest prefix of those literals that names a known
CLI node becomes a `calls` edge. Tools without an argv literal (in-process
read/projection tools) honestly get no edge.
"""

from __future__ import annotations

import ast
from pathlib import Path

from alpha_atlas.core.model import Edge, Evidence, Fragment, Node, Provenance, edge_id
from alpha_atlas.generators._repo import record_input

EXTRACTOR = "mcp_tools"

SERVER_REL = "apps/alpha-mcp/src/alpha_mcp/server.py"


def _is_tool(func: ast.FunctionDef) -> bool:
    return any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool"
        for d in func.decorator_list
    )


def _leading_literals(value: ast.expr) -> list[str]:
    if not isinstance(value, ast.List):
        return []
    out: list[str] = []
    for element in value.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            out.append(element.value)
        else:
            break
    return out


def _argv_tokens(func: ast.FunctionDef) -> list[str]:
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "args" for t in node.targets
        ):
            tokens = _leading_literals(node.value)
            if tokens:
                return tokens
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run_alpha"
            and node.args
        ):
            tokens = _leading_literals(node.args[0])
            if tokens:
                return tokens
    return []


def extract(root: Path, *, cli_ids: set[str]) -> tuple[Fragment, dict[str, str]]:
    inputs: dict[str, str] = {}
    source = record_input(root, SERVER_REL, inputs).decode("utf-8")
    nodes: list[Node] = []
    edges: list[Edge] = []
    for func in ast.walk(ast.parse(source)):
        if not isinstance(func, ast.FunctionDef) or not _is_tool(func):
            continue
        tool_id = f"mcp:{func.name}"
        docstring = ast.get_docstring(func) or ""
        nodes.append(
            Node(
                id=tool_id,
                kind="mcp_tool",
                label=func.name,
                path=SERVER_REL,
                component="alpha-mcp",
                evidence=Evidence(
                    level="implemented",
                    provenance=[
                        Provenance(
                            extractor=EXTRACTOR,
                            source=SERVER_REL,
                            line=func.lineno,
                            detail="@mcp.tool() function",
                        )
                    ],
                ),
                meta={"doc": docstring.splitlines()[0] if docstring else ""},
            )
        )
        tokens = _argv_tokens(func)
        for k in range(len(tokens), 0, -1):
            target = f"cli:alpha {' '.join(tokens[:k])}"
            if target in cli_ids:
                edges.append(
                    Edge(
                        id=edge_id(tool_id, target, "calls"),
                        type="calls",
                        source=tool_id,
                        target=target,
                        evidence=Evidence(
                            level="declared",
                            provenance=[
                                Provenance(
                                    extractor=EXTRACTOR,
                                    source=SERVER_REL,
                                    line=func.lineno,
                                    detail=f"argv literal {tokens!r}",
                                )
                            ],
                        ),
                    )
                )
                break
    return Fragment(nodes=nodes, edges=edges), inputs
