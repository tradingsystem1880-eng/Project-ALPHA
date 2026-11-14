"""Guard product files an agent cannot hold in its head.

Files may have at most 1,500 lines and functions at most 150 lines. Today's offenders are capped
at their current size in ``.claude/code-size-baseline.json``, which only shrinks as oversized code
is split or shortened: every entry must equal the current size, and compared with the baseline on
``origin/main`` no entry may be added or raised. Tests are not measured. The rule:
docs/reference/invariants/engineering.md (Code size).
"""

import ast
import json
import subprocess
from functools import cache
from pathlib import Path
from typing import TypedDict, cast

import pytest

ROOT = Path(__file__).parents[2]
BASELINE_REL = ".claude/code-size-baseline.json"
BASELINE = ROOT / BASELINE_REL
MAIN_REF = "origin/main"
FILE_LIMIT = 1500
FUNCTION_LIMIT = 150
PRODUCT_ROOTS = {"packages", "apps", "workers", "tools", "scripts"}


class Baseline(TypedDict):
    files: dict[str, int]
    functions: dict[str, int]


def measure_source(source: str, filename: str = "<source>") -> tuple[int, dict[str, int]]:
    """Return the line count and qualified function sizes, including nested scopes.

    A second definition with the same qualified name (a property setter, an ``if``/``else``
    pair) is keyed ``name#2``, a third ``name#3``, in source order, so each is measured.
    """
    functions: dict[str, int] = {}

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = (*scope, node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.end_lineno is not None
                name = base = ".".join(scope)
                occurrence = 1
                while name in functions:
                    occurrence += 1
                    name = f"{base}#{occurrence}"
                functions[name] = node.end_lineno - node.lineno + 1
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(ast.parse(source, filename=filename), ())
    return len(source.splitlines()), functions


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True)


@cache
def measure_tree() -> tuple[dict[str, int], dict[str, int]]:
    """Measure tracked product Python files once per session."""
    listed = _git("ls-files", "-z", "--", "*.py")
    assert listed.returncode == 0, listed.stderr.decode(errors="replace")
    files: dict[str, int] = {}
    functions: dict[str, int] = {}
    for name in listed.stdout.decode("utf-8").split("\0"):
        if not name:
            continue
        path = Path(name)
        if (
            path.parts[0] not in PRODUCT_ROOTS
            or {"tests", "test"}.intersection(path.parts[:-1])
            or path.name == "conftest.py"
        ):
            continue
        lines, sizes = measure_source((ROOT / path).read_text(encoding="utf-8"), name)
        files[name] = lines
        functions.update({f"{name}::{key}": size for key, size in sizes.items()})
    return files, functions


@cache
def read_baseline() -> Baseline:
    return cast(Baseline, json.loads(BASELINE.read_text(encoding="utf-8")))


def _new_offenders(measured: dict[str, int], recorded: dict[str, int], limit: int) -> list[str]:
    return [
        f"{name} ({size} lines): split it below {limit:,} lines; "
        "the baseline never takes new entries"
        for name, size in sorted(measured.items())
        if size > limit and name not in recorded
    ]


def test_no_new_file_over_the_limit() -> None:
    files, _ = measure_tree()
    errors = _new_offenders(files, read_baseline()["files"], FILE_LIMIT)
    assert not errors, "\n".join(errors)


def test_no_new_function_over_the_limit() -> None:
    _, functions = measure_tree()
    errors = _new_offenders(functions, read_baseline()["functions"], FUNCTION_LIMIT)
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


def test_baseline_never_grows_against_main() -> None:
    """Editing the baseline to admit growth fails: no entry is added or raised since main."""
    base = _git("merge-base", "HEAD", MAIN_REF)
    assert base.returncode == 0, (
        f"cannot find the merge base with {MAIN_REF} (run `git fetch origin`): "
        + base.stderr.decode(errors="replace")
    )
    commit = base.stdout.decode().strip()
    listed = _git("ls-tree", commit, "--", BASELINE_REL)
    assert listed.returncode == 0, listed.stderr.decode(errors="replace")
    if not listed.stdout.strip():
        return  # main has no baseline yet: this change introduces it
    shown = _git("show", f"{commit}:{BASELINE_REL}")
    assert shown.returncode == 0, shown.stderr.decode(errors="replace")
    previous = cast(Baseline, json.loads(shown.stdout))
    errors = baseline_growth(previous, read_baseline())
    assert not errors, "\n".join(errors)


def baseline_growth(previous: Baseline, current: Baseline) -> list[str]:
    """Entries ``current`` adds to or raises above ``previous``."""
    errors = []
    pairs = ((previous["files"], current["files"]), (previous["functions"], current["functions"]))
    for before, after in pairs:
        for name, size in sorted(after.items()):
            if name not in before:
                errors.append(f"{name}: added to {BASELINE_REL}; split the code instead")
            elif size > before[name]:
                errors.append(f"{name}: raised from {before[name]} to {size} in {BASELINE_REL}")
    return errors


def test_baseline_growth_names_added_and_raised_entries() -> None:
    previous: Baseline = {"files": {"a.py": 1600}, "functions": {"a.py::f": 200}}
    current: Baseline = {"files": {"a.py": 1700, "b.py": 1501}, "functions": {"a.py::f": 190}}
    assert baseline_growth(previous, current) == [
        f"a.py: raised from 1600 to 1700 in {BASELINE_REL}",
        f"b.py: added to {BASELINE_REL}; split the code instead",
    ]


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


def test_measure_counts_each_same_name_definition() -> None:
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
    assert measure_source(source) == (
        15,
        {"Example.value": 3, "Example.value#2": 2, "choice": 2, "choice#2": 3},
    )


def test_measure_names_the_file_that_does_not_parse() -> None:
    with pytest.raises(SyntaxError) as raised:
        measure_source("def broken(:\n", "pkg/broken.py")
    assert raised.value.filename == "pkg/broken.py"
