"""Computed source index shared by terminal orientation and optional Atlas rendering.

No generated graph, owner store, network, or tests directory is read here. Extraction errors
propagate: an unavailable source index must not be presented as an empty repository.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_atlas.core.model import Fragment
from alpha_atlas.generators import components, frontend_scan, python_modules


def computed_fragments(root: Path) -> list[tuple[Fragment, dict[str, str]]]:
    """The common source-only component, Python module, and document extraction pass."""
    return [components.extract(root), python_modules.extract(root), frontend_scan.extract(root)]


def developer_index(root: Path, *, component: str | None = None) -> dict[str, Any]:
    fragments = computed_fragments(root)
    nodes = [node for fragment, _ in fragments for node in fragment.nodes]
    packages = sorted(
        (node for node in nodes if node.kind == "component"), key=lambda node: node.id
    )
    modules = sorted(
        (node for node in nodes if node.kind == "module" and node.path), key=lambda node: node.id
    )
    result: dict[str, Any] = {
        "schema_version": 1,
        "authority": "none",
        "source": "current repository source; computed, not runtime evidence",
        "components": [
            {
                "id": node.label,
                "path": node.path,
                "modules": sum(module.component == node.label for module in modules),
            }
            for node in packages
        ],
        "module_count": len(modules),
        "documents": sorted(node.label for node in nodes if node.kind == "screen"),
        "commands": {
            "complete": "alpha info commands --all --json",
            "procedures": "alpha info procedures --json",
        },
    }
    if component is not None:
        if component not in {node.label for node in packages}:
            raise ValueError(f"unknown component: {component}")
        result["modules"] = [
            {"id": node.label, "path": node.path} for node in modules if node.component == component
        ]
    return result
