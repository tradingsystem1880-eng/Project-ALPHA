"""The research kernel has no network, persistence, credential, or dynamic-code edge."""

from __future__ import annotations

import ast
from pathlib import Path


def test_research_kernel_imports_no_side_effectful_runtime() -> None:
    package = Path(__file__).parents[2] / "packages" / "alpha-research" / "src" / "alpha_research"
    forbidden = {
        "ctypes",
        "http",
        "httpx",
        "marshal",
        "pickle",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }

    found: set[str] = set()
    for source_path in package.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".", 1)[0])

    assert found.isdisjoint(forbidden), found & forbidden
