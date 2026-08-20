"""Shared stdlib-only repository helpers for extractors."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path


def record_input(root: Path, rel: str, inputs: dict[str, str]) -> bytes:
    """Read a repository file and record its sha256 in the inputs manifest."""
    raw = (root / rel).read_bytes()
    inputs[rel] = hashlib.sha256(raw).hexdigest()
    return raw


_SRC_GLOBS = ("packages/*/src/*", "apps/*/src/*", "workers/*/src/*")


def source_roots(root: Path) -> dict[str, tuple[str, str]]:
    """Top-level package name -> (repo-relative src dir, component name)."""
    roots: dict[str, tuple[str, str]] = {}
    for glob in _SRC_GLOBS:
        for path in sorted(root.glob(glob)):
            if path.is_dir() and (path / "__init__.py").is_file():
                component = path.relative_to(root).parts[1]
                roots[path.name] = (str(path.relative_to(root)), component)
    return roots


def module_roots(root: Path) -> dict[str, str]:
    """Top-level importable package name -> repo-relative source directory."""
    return {pkg: src for pkg, (src, _) in source_roots(root).items()}


def module_to_path(root: Path, module: str, roots: dict[str, str]) -> str | None:
    """Resolve a dotted module name to its repo-relative file, or None if unknown."""
    top, _, rest = module.partition(".")
    base = roots.get(top)
    if base is None:
        return None
    if not rest:
        return f"{base}/__init__.py"
    stem = f"{base}/{rest.replace('.', '/')}"
    for candidate in (f"{stem}.py", f"{stem}/__init__.py"):
        if (root / candidate).is_file():
            return candidate
    return None


def symbol_line(source: str, symbol: str) -> int | None:
    """First definition line of a function/class/assignment named `symbol` (any nesting)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and node.name == symbol
        ):
            return node.lineno
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol:
                    return node.lineno
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == symbol
        ):
            return node.lineno
    return None
