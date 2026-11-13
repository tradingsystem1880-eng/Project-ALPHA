"""Repository orientation for the file system: components, module counts and routing documents.

Computed from the tree on every call (directory listings only; no file contents, owner stores,
network or tests are read). ``gate.py orient`` and ``fs.py orient`` both print this. An
unreadable tree raises: an unavailable index must not look like an empty repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

COMPONENT_GLOBS = ("packages/*", "apps/*", "workers/*")
# The small files an agent reads first; each routes to the rest.
ROUTING_DOCUMENTS = (
    "CLAUDE.md",
    "CONTEXT.md",
    "STATUS.md",
    "docs/roadmap/README.md",
    "workflow/CONTEXT.md",
)
DEFAULT_SIZE_CAP = 6_000


def _modules(root: Path, component_dir: Path) -> list[dict[str, str]]:
    """Every Python module under ``<component>/src/<package>/`` as dotted id and repo path."""
    rows: list[dict[str, str]] = []
    for package in sorted((component_dir / "src").glob("*")):
        if not package.is_dir() or not (package / "__init__.py").is_file():
            continue
        for path in sorted(package.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            parts = list(path.relative_to(package).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            rows.append(
                {"id": ".".join([package.name, *parts]), "path": path.relative_to(root).as_posix()}
            )
    return sorted(rows, key=lambda row: row["id"])


def orientation(root: Path, *, component: str | None = None) -> dict[str, Any]:
    """The bounded default summary, or one component's module list when ``component`` is set."""
    components: dict[str, tuple[str, list[dict[str, str]]]] = {}
    for glob in COMPONENT_GLOBS:
        for path in sorted(root.glob(glob)):
            if (path / "pyproject.toml").is_file():
                components[path.name] = (path.relative_to(root).as_posix(), _modules(root, path))
    result: dict[str, Any] = {
        "schema_version": 1,
        "authority": "none",
        "source": "current repository source; computed, not runtime evidence",
        "components": [
            {"id": name, "path": rel, "modules": len(modules)}
            for name, (rel, modules) in sorted(components.items())
        ],
        "module_count": sum(len(modules) for _, modules in components.values()),
        "documents": [rel for rel in ROUTING_DOCUMENTS if (root / rel).is_file()],
        "commands": {
            "complete": "alpha info commands --all --json",
            "procedures": "alpha info procedures --json",
            "search": 'uv run python scripts/fs.py search "QUERY"',
        },
    }
    if component is not None:
        if component not in components:
            raise ValueError(f"unknown component: {component}")
        result["modules"] = components[component][1]
    elif len(json.dumps(result).encode("utf-8")) > DEFAULT_SIZE_CAP:
        raise ValueError("orientation exceeds 6 KB; narrow the default summary")
    return result


def render_orientation(payload: dict[str, Any]) -> str:
    rows = ["Repository orientation (source index; authority: none)"]
    rows.extend(
        f"  {item['id']}: {item['path']} ({item['modules']} modules)"
        for item in payload["components"]
    )
    rows.append("Documents: " + ", ".join(payload["documents"]))
    rows.extend(payload["commands"].values())
    rows.extend(f"  {item['id']}: {item['path']}" for item in payload.get("modules", []))
    return "\n".join(rows)
