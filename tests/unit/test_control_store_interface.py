"""Pin the ControlStore surface while its implementation is split.

Regenerate deliberately: uv run python tests/unit/test_control_store_interface.py --write
"""

import argparse
import ast
import inspect
import json
from functools import cache
from pathlib import Path
from typing import TypedDict, cast

from alpha_cli import control_store

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests/fixtures/control_store_interface.json"
PRODUCT_ROOTS = ("apps", "packages", "workers", "tools", "scripts")
PATCHED_MODULE_ATTRIBUTES = [
    "_SCHEMA_V2",
    "_SCHEMA_V5",
    "_execute_static_sql_script",
    "_logical_database_fingerprint",
    "_verified_v1_backup",
    "time",
]
DELIBERATE_CHANGE = "An interface change during the split must be deliberate."


class InterfaceSnapshot(TypedDict):
    public_methods: dict[str, str]
    all: list[str]
    module_names_imported_elsewhere: list[str]
    patched_module_attributes: list[str]


def imported_names(tree: ast.AST) -> set[str]:
    """Collect direct imports and attribute uses of module import aliases."""
    names: set[str] = set()
    module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level:
            continue
        if node.module == "alpha_cli.control_store":
            names.update(alias.name for alias in node.names)
        elif node.module == "alpha_cli":
            module_aliases.update(
                alias.asname or alias.name for alias in node.names if alias.name == "control_store"
            )
    names.update(
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in module_aliases
    )
    return names


@cache
def interface_snapshot() -> InterfaceSnapshot:
    """Read the current interface without changing the golden."""
    methods: dict[str, str] = {}
    for name, member in sorted(vars(control_store.ControlStore).items()):
        if name.startswith("_"):
            continue
        if isinstance(member, property):
            methods[name] = "property"
        else:
            if isinstance(member, (staticmethod, classmethod)):
                member = member.__func__
            methods[name] = str(inspect.signature(member))

    names: set[str] = set()
    for directory in PRODUCT_ROOTS:
        for parent, directories, files in (ROOT / directory).walk():
            directories[:] = sorted(
                name
                for name in directories
                if name not in {"tests", "node_modules"} and not name.startswith(".")
            )
            for filename in sorted(files):
                if not filename.endswith(".py") or filename.startswith("test_"):
                    continue
                path = parent / filename
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                names.update(imported_names(tree))
    return {
        "public_methods": methods,
        "all": sorted(control_store.__all__),
        "module_names_imported_elsewhere": sorted(names),
        "patched_module_attributes": sorted(PATCHED_MODULE_ATTRIBUTES),
    }


def name_changes(label: str, before: set[str], after: set[str]) -> list[str]:
    """Describe additions and removals by name."""
    changes = [f"{label}: added {name}" for name in sorted(after - before)]
    changes.extend(f"{label}: removed {name}" for name in sorted(before - after))
    return changes


def test_control_store_interface_matches_golden() -> None:
    assert GOLDEN.is_file(), f"Missing interface golden: {GOLDEN}. {DELIBERATE_CHANGE}"
    expected = cast(InterfaceSnapshot, json.loads(GOLDEN.read_text(encoding="utf-8")))
    actual = interface_snapshot()
    changes = name_changes("snapshot fields", set(expected), set(actual))
    before = expected["public_methods"]
    after = actual["public_methods"]
    changes.extend(name_changes("public_methods", set(before), set(after)))
    changes.extend(
        f"public_methods: changed signature {name}: {before[name]} -> {after[name]}"
        for name in sorted(before.keys() & after.keys())
        if before[name] != after[name]
    )
    for label in ("all", "module_names_imported_elsewhere", "patched_module_attributes"):
        changes.extend(name_changes(label, set(expected[label]), set(actual[label])))
    assert actual == expected, "\n".join([*changes, DELIBERATE_CHANGE])


def test_imported_module_names_still_exist() -> None:
    missing = [
        name
        for name in interface_snapshot()["module_names_imported_elsewhere"]
        if not hasattr(control_store, name)
    ]
    assert not missing, f"Imported module attributes removed: {missing}. {DELIBERATE_CHANGE}"


def test_patched_module_attributes_are_still_read_here() -> None:
    assert control_store.__file__ is not None
    source = Path(control_store.__file__)
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    loads = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    missing = [name for name in PATCHED_MODULE_ATTRIBUTES if not hasattr(control_store, name)]
    unread = sorted(set(PATCHED_MODULE_ATTRIBUTES) - loads)
    assert not missing and not unread, (
        f"Patched module attributes removed: {missing}; no longer read here: {unread}. "
        f"{DELIBERATE_CHANGE}"
    )


def write_golden() -> None:
    """Explicitly regenerate the interface golden; tests never call this helper."""
    GOLDEN.write_text(
        json.dumps(interface_snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", required=True)
    parser.parse_args()
    write_golden()
