"""Pick the tests `gate.py check` runs: research guards always, plus tests mapped from changes.

The mapping is a cheap text search, not an import graph: a changed test file selects itself, a
changed module selects the test files whose source imports it, and last run's failures run again.
CI still runs every test on the pull request; this only decides what is worth running locally.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ALWAYS = ("tests/bias_guards", "tests/oracles", "tests/acceptance")
MAX_MAPPED_TESTS = 400
LAST_FAILED = Path(".pytest_cache") / "v" / "cache" / "lastfailed"
_TEST_DEF = re.compile(r"^\s*(?:async\s+)?def test_", re.MULTILINE)


@dataclass(frozen=True)
class Selection:
    """What to run and why; ``changed`` is None when the comparison base was unavailable."""

    always: tuple[str, ...]
    mapped: tuple[str, ...]
    last_failed: tuple[str, ...]
    changed: tuple[str, ...] | None
    notes: tuple[str, ...]

    def pytest_paths(self) -> list[str]:
        return [*self.always, *self.mapped, *self.last_failed]


def module_name(path: str) -> str | None:
    """Dotted import name for a changed Python file, or None when tests cannot import it."""
    posix = PurePosixPath(path)
    if posix.suffix != ".py":
        return None
    parts = list(posix.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if "src" in parts and parts[0] in {"packages", "apps"}:
        dotted = parts[parts.index("src") + 1 :]
    elif parts[0] == "scripts" and len(parts) == 2:
        dotted = parts[1:]
    elif parts[0] == "tests" and not parts[-1].startswith("test_") and parts[-1] != "conftest":
        dotted = parts
    else:
        return None
    return ".".join(dotted) if dotted else None


def imports_module(text: str, module: str) -> bool:
    """Whether ``text`` imports ``module`` (``import a.b``, ``from a.b``, ``from a import b``)."""
    parent, _, leaf = module.rpartition(".")
    # A script is importable as a top-level module and through the ``scripts`` package.
    spellings = [module] if parent else [module, f"scripts.{module}"]
    for name in spellings:
        if re.search(rf"^\s*(?:import|from)\s+{re.escape(name)}\b", text, re.MULTILINE):
            return True
    pattern = rf"^\s*from\s+{re.escape(parent or 'scripts')}\s+import\s+(\([^)]*\)|[^\n]*)"
    return any(
        re.search(rf"\b{re.escape(leaf)}\b", match.group(1))
        for match in re.finditer(pattern, text, re.MULTILINE)
    )


def _test_files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in (root / "tests").rglob("test_*.py"))


def _is_test_file(path: str) -> bool:
    posix = PurePosixPath(path)
    return posix.parts[0] == "tests" and posix.name.startswith("test_") and posix.suffix == ".py"


def _count_tests(root: Path, files: list[str]) -> int:
    return sum(len(_TEST_DEF.findall((root / f).read_text(errors="replace"))) for f in files)


def _last_failed(root: Path) -> list[str]:
    """Tests pytest recorded as failing last time that still exist, as ``file::function`` ids.

    The recorded id of a parametrised case (``test_x[case]``) stops existing when the case is
    renamed, and pytest then refuses the whole run. So each id is cut back to its function and
    kept only while the file still defines a function of that name.
    """
    try:
        recorded = json.loads((root / LAST_FAILED).read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(recorded, dict):
        return []
    kept: set[str] = set()
    for node in recorded:
        file, _, rest = str(node).partition("::")
        function = rest.split("[", 1)[0]
        name = function.rsplit("::", 1)[-1]
        try:
            text = (root / file).read_text(errors="replace")
        except OSError:
            continue
        if name and re.search(rf"^\s*(?:async\s+)?def {re.escape(name)}\(", text, re.MULTILINE):
            kept.add(f"{file}::{function}")
    return sorted(kept)


def select(root: Path, changed: list[str] | None) -> Selection:
    """Map ``changed`` repository paths to test files; ``None`` means the base was unavailable."""
    notes: list[str] = []
    mapped: set[str] = set()
    modules: list[str] = []
    if changed is None:
        notes.append("comparison base unavailable: ran the research guards and last failures only")
    else:
        for path in changed:
            if _is_test_file(path):
                if (root / path).is_file():
                    mapped.add(path)
            elif PurePosixPath(path).name == "conftest.py":
                notes.append(f"{path} changed: shared fixtures are left to CI (or run --all)")
            elif (name := module_name(path)) is not None:
                modules.append(name)
    if modules:
        for test in _test_files(root):
            text = (root / test).read_text(errors="replace")
            if any(imports_module(text, name) for name in modules):
                mapped.add(test)
    always = set(ALWAYS)
    chosen = sorted(f for f in mapped if not f.startswith(tuple(f"{a}/" for a in always)))
    if _count_tests(root, chosen) > MAX_MAPPED_TESTS:
        stems = {name.rsplit(".", 1)[-1] for name in modules}
        direct = [f for f in chosen if f in (changed or [])]
        named = [f for f in chosen if any(stem in PurePosixPath(f).stem for stem in stems)]
        kept = sorted(set(direct) | set(named))
        notes.append(
            f"the change maps to {len(chosen)} test files (over {MAX_MAPPED_TESTS} tests); kept "
            f"{len(kept)} named after the changed files and left the rest to CI"
        )
        chosen = kept
    covered = (*chosen, *(f"{a}/" for a in always))
    failed = [node for node in _last_failed(root) if not node.startswith(covered)]
    return Selection(
        always=ALWAYS,
        mapped=tuple(chosen),
        last_failed=tuple(failed),
        changed=None if changed is None else tuple(changed),
        notes=tuple(notes),
    )
