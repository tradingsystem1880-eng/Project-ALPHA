"""Guard product files an agent cannot hold in its head.

Files may have at most 1,500 lines and functions at most 150 lines. Today's offenders are capped
at their current size in ``.claude/code-size-baseline.json``, which only shrinks as oversized code
is split or shortened. Tests are not measured. The rule: docs/reference/invariants/engineering.md
(Code size).
"""

import ast
import json
import subprocess
from functools import cache
from pathlib import Path
from typing import TypedDict, cast

ROOT = Path(__file__).parents[2]
BASELINE_REL = ".claude/code-size-baseline.json"
BASELINE = ROOT / BASELINE_REL
FILE_LIMIT = 1500
FUNCTION_LIMIT = 150
PRODUCT_ROOTS = {"packages", "apps", "workers", "tools", "scripts"}


class Baseline(TypedDict):
    files: dict[str, int]
    functions: dict[str, int]


def measure_source(source: str) -> tuple[int, dict[str, int]]:
    """Return line counts and qualified function sizes, including nested scopes."""
    functions: dict[str, int] = {}

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = (*scope, node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.end_lineno is not None
                name = ".".join(scope)
                size = node.end_lineno - node.lineno + 1
                functions[name] = max(functions.get(name, 0), size)
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(ast.parse(source), ())
    return len(source.splitlines()), functions


@cache
def measure_tree() -> tuple[dict[str, int], dict[str, int]]:
    """Measure tracked product Python files once per session."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    files: dict[str, int] = {}
    functions: dict[str, int] = {}
    for name in tracked.split("\0"):
        if not name:
            continue
        path = Path(name)
        if (
            path.parts[0] not in PRODUCT_ROOTS
            or {"tests", "test"}.intersection(path.parts[:-1])
            or path.name == "conftest.py"
        ):
            continue
        lines, sizes = measure_source((ROOT / path).read_text(encoding="utf-8"))
        files[name] = lines
        functions.update({f"{name}::{key}": size for key, size in sizes.items()})
    return files, functions


@cache
def read_baseline() -> Baseline:
    return cast(Baseline, json.loads(BASELINE.read_text(encoding="utf-8")))


def test_product_files_stay_within_size_limits() -> None:
    files, _ = measure_tree()
    baseline = read_baseline()["files"]
    errors = []
    for name, lines in sorted(files.items()):
        if lines <= FILE_LIMIT:
            continue
        if name not in baseline:
            errors.append(
                f"{name} ({lines} lines): split it below 1,500 lines; "
                "the baseline never takes new entries"
            )
        elif lines > baseline[name]:
            errors.append(f"{name} ({lines} lines): it may not grow past {baseline[name]}")
    assert not errors, "\n".join(errors)


def test_product_functions_stay_within_size_limits() -> None:
    _, functions = measure_tree()
    baseline = read_baseline()["functions"]
    errors = []
    for name, lines in sorted(functions.items()):
        if lines <= FUNCTION_LIMIT:
            continue
        if name not in baseline:
            errors.append(
                f"{name} ({lines} lines): split it below 150 lines; "
                "the baseline never takes new entries"
            )
        elif lines > baseline[name]:
            errors.append(f"{name} ({lines} lines): it may not grow past {baseline[name]}")
    assert not errors, "\n".join(errors)


def test_baseline_entries_are_exact() -> None:
    files, functions = measure_tree()
    baseline = read_baseline()
    errors = []
    for recorded, measured, limit in (
        (baseline["files"], files, FILE_LIMIT),
        (baseline["functions"], functions, FUNCTION_LIMIT),
    ):
        for name, previous in sorted(recorded.items()):
            current = measured.get(name)
            if current is None or current <= limit:
                errors.append(f"{name}: remove the entry from {BASELINE_REL}")
            elif current < previous:
                errors.append(f"{name}: lower the entry to {current} in {BASELINE_REL}")
            elif current > previous:
                errors.append(f"{name} ({current} lines): it may not grow past {previous}")
    assert not errors, "\n".join(errors)


def test_measure_nested_function() -> None:
    source = "def outer():\n    def inner():\n        pass\n    return inner\n"
    assert measure_source(source) == (4, {"outer": 4, "outer.inner": 2})


def test_measure_method() -> None:
    source = "class Example:\n    def method(self):\n        pass\n"
    assert measure_source(source) == (3, {"Example.method": 2})


def test_measure_async_function() -> None:
    source = "async def fetch():\n    return 1\n"
    assert measure_source(source) == (2, {"fetch": 2})


def test_measure_excludes_decorators() -> None:
    source = "@decorate\n@another(\n    1,\n)\ndef decorated():\n    pass\n"
    assert measure_source(source) == (6, {"decorated": 2})


def test_measure_duplicate_key_takes_larger_size() -> None:
    source = (
        "class Example:\n"
        "    @property\n"
        "    def value(self):\n"
        "        result = 1\n"
        "        return result\n"
        "    @value.setter\n"
        "    def value(self, new):\n"
        "        pass\n"
        "if condition:\n"
        "    def choice():\n"
        "        pass\n"
        "else:\n"
        "    def choice():\n"
        "        result = 1\n"
        "        return result\n"
    )
    assert measure_source(source) == (15, {"Example.value": 3, "choice": 3})
