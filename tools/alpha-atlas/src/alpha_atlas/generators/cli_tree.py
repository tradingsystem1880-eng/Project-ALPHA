"""Extract the CLI surface from the committed command cache plus main.py wiring.

The cache (`architecture/atlas/cache/cli-commands.json`) is the canonicalized
output of `alpha info commands --json`, refreshed explicitly via
`python -m alpha_atlas.generate --refresh-cli`. It lives outside generated/
because it is an input: generation stays deterministic and offline, and the
CLI is never subprocessed during a normal build. Group→module `calls` edges
come from the `add_typer` registrations in main.py, with file:line provenance.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from alpha_atlas.core.model import Edge, Evidence, Fragment, Node, Provenance, edge_id
from alpha_atlas.generators._repo import record_input

EXTRACTOR = "cli_tree"

CACHE_REL = "architecture/atlas/cache/cli-commands.json"
MAIN_REL = "apps/alpha-cli/src/alpha_cli/main.py"


def _typer_registrations(source: str) -> list[tuple[str, str, int]]:
    """(group name, alpha_cli module, line) for each add_typer(alias, name=...) call."""
    tree = ast.parse(source)
    alias_to_module: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("alpha_cli."):
            for alias in node.names:
                alias_to_module[alias.asname or alias.name] = str(node.module)
    out: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_typer"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            module = alias_to_module.get(node.args[0].id)
            name = next(
                (
                    kw.value.value
                    for kw in node.keywords
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant)
                ),
                None,
            )
            if module and isinstance(name, str):
                out.append((name, module, node.lineno))
    return out


def extract(root: Path) -> tuple[Fragment, dict[str, str]]:
    inputs: dict[str, str] = {}
    cache: dict[str, Any] = json.loads(record_input(root, CACHE_REL, inputs).decode("utf-8"))
    commands: list[dict[str, Any]] = cache["commands"]
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: set[str] = set()
    for command in commands:
        command_id = str(command["id"])
        node_id = f"cli:alpha {command_id}"
        provenance = Provenance(
            extractor=EXTRACTOR, source=CACHE_REL, detail="cached `alpha info commands` leaf"
        )
        nodes.append(
            Node(
                id=node_id,
                kind="cli_command",
                label=f"alpha {command_id}",
                component="alpha-cli",
                evidence=Evidence(level="implemented", provenance=[provenance]),
                meta={
                    "args": [str(a["name"]) for a in command.get("args", [])],
                    "options": [str(o["flag"]) for o in command.get("options", [])],
                },
            )
        )
        tokens = command_id.split(" ")
        if len(tokens) > 1:
            groups.add(tokens[0])
            edges.append(
                Edge(
                    id=edge_id(node_id, f"cli:alpha {tokens[0]}", "part_of"),
                    type="part_of",
                    source=node_id,
                    target=f"cli:alpha {tokens[0]}",
                    evidence=Evidence(level="declared", provenance=[provenance]),
                )
            )
    leaf_ids = {n.id for n in nodes}
    for group in sorted(groups):
        group_id = f"cli:alpha {group}"
        if group_id in leaf_ids:
            continue  # a bare command that is also a group; the leaf node anchors both
        nodes.append(
            Node(
                id=group_id,
                kind="cli_command",
                label=f"alpha {group}",
                component="alpha-cli",
                evidence=Evidence(
                    level="implemented",
                    provenance=[
                        Provenance(
                            extractor=EXTRACTOR,
                            source=CACHE_REL,
                            detail="command group from cached leaves",
                        )
                    ],
                ),
                meta={"group": True},
            )
        )
    known_ids = {n.id for n in nodes}
    main_source = record_input(root, MAIN_REL, inputs).decode("utf-8")
    for group, module, lineno in _typer_registrations(main_source):
        group_id = f"cli:alpha {group}"
        if group_id not in known_ids:
            continue
        edges.append(
            Edge(
                id=edge_id(group_id, f"module:{module}", "calls"),
                type="calls",
                source=group_id,
                target=f"module:{module}",
                evidence=Evidence(
                    level="declared",
                    provenance=[
                        Provenance(
                            extractor=EXTRACTOR,
                            source=MAIN_REL,
                            line=lineno,
                            detail=f"app.add_typer(..., name={group!r})",
                        )
                    ],
                ),
            )
        )
    return Fragment(nodes=nodes, edges=edges), inputs
