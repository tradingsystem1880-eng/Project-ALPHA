"""Load and check docs/roadmap/capabilities.toml, the map of ALPHA's user-facing workflows.

The map is hand-written; this module enforces its schema and checks every claim it can check
against the repository: entry points exist, each ``proof_synthetic`` and ``proof_smoke`` test file
and test exists, and every listed document exists.

"Working" means run end to end: a capability is ``Working`` only with at least one ``proof_smoke``
node (a check under ``tests/smoke/`` that runs the installed programs) that is not skipped or
xfailed by design, and nothing in ``needs``. Every strict-xfail smoke check must be listed under
``[[known_defect]]``, and every listed defect must be such a check, so the status page shows them.

``uv run python scripts/capabilities.py`` prints ``ok`` or the first problem (exit 1).
``tests/unit/test_capabilities.py`` runs the same check on the committed tree.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import cast

ROOT = Path(__file__).parents[1]
MAP = Path("docs/roadmap/capabilities.toml")

STATES = ("Working", "Partial", "Demo only", "Shelved", "Not started")
RECOMMENDATIONS = ("KEEP", "SHELVE", "SHELVE (your call)", "DELETE", "YOUR CALL")
DECISIONS = ("undecided", "KEEP", "SHELVE", "DELETE")
INTERNAL_ONLY = "nothing to see yet — internal only"
SMOKE_DIR = "tests/smoke/"
# A Partial capability whose 'missing' ends with this has in-process tests but no smoke check.
NO_SMOKE_YET = "no end-to-end smoke check yet"

_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_CLI_MAIN = Path("apps/alpha-cli/src/alpha_cli/main.py")
_API_DIR = Path("apps/alpha-web/src/alpha_web/api")
_PREFIX = re.compile(r'router = APIRouter\(prefix="([^"]*)"')
_ROUTE = re.compile(r'@router\.(get|post|put|delete|patch)\(\s*"([^"]*)"')
_SCRIPT = re.compile(r'^(?P<name>[A-Za-z0-9_-]+)\s*=\s*"', re.M)

_CAPABILITY_KEYS = {
    "id": str,
    "name": str,
    "what": str,
    "see_it": list,
    "entry_points": list,
    "proof_synthetic": list,
    "real_data": str,
    "needs": list,
    "state": str,
}
_OPTIONAL_KEYS = {
    "codes": list,
    "proof_smoke": list,
    "real_data_needs": str,
    "missing": str,
    "triage": dict,
    "docs": list,
}
_DESIGNED_MARKS = frozenset({"skip", "skipif", "xfail"})


class CapabilityError(ValueError):
    """The capability map breaks its schema or makes a claim the repository does not support."""


@dataclass(frozen=True)
class Triage:
    card: str
    recommendation: str
    owner_decision: str

    @property
    def decided(self) -> bool:
        return self.owner_decision != "undecided"


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    codes: tuple[str, ...]
    what: str
    see_it: tuple[str, ...]
    entry_points: tuple[str, ...]
    proof_synthetic: tuple[str, ...]
    proof_smoke: tuple[str, ...]
    real_data: str
    real_data_needs: str
    needs: tuple[str, ...]
    state: str
    missing: str
    triage: Triage | None
    docs: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        """Plain name first, codes in brackets."""
        return f"{self.name} ({', '.join(self.codes)})" if self.codes else self.name

    @property
    def internal_only(self) -> bool:
        return self.see_it == (INTERNAL_ONLY,)


@dataclass(frozen=True)
class Decision:
    """A triage card that is not a workflow of its own."""

    name: str
    triage: Triage


@dataclass(frozen=True)
class KnownDefect:
    """A strict-xfail smoke check: a defect seen through the installed program, not yet fixed."""

    title: str
    node: str
    how_to_reproduce: str


@dataclass(frozen=True)
class CapabilityMap:
    capabilities: tuple[Capability, ...]
    decisions: tuple[Decision, ...]
    known_defects: tuple[KnownDefect, ...] = ()

    def triage_items(self) -> list[tuple[str, Triage]]:
        """Every triage card with the plain name it is shown under, in file order."""
        items = [(c.label, c.triage) for c in self.capabilities if c.triage is not None]
        return items + [(d.name, d.triage) for d in self.decisions]


def _strings(where: str, key: str, value: object, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise CapabilityError(f"{where}: '{key}' must be a list of non-empty strings")
    if not allow_empty and not value:
        raise CapabilityError(f"{where}: '{key}' must not be empty")
    return tuple(cast(list[str], value))


def _text(where: str, key: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CapabilityError(f"{where}: '{key}' must be a non-empty string")
    return value


def _table(where: str, raw: object, required: set[str]) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise CapabilityError(f"{where}: must be a table")
    table = cast(dict[str, object], raw)
    if set(table) != required:
        raise CapabilityError(f"{where}: keys must be exactly {sorted(required)}")
    return table


def _triage(where: str, raw: object) -> Triage:
    table = _table(where, raw, {"card", "recommendation", "owner_decision"})
    triage = Triage(
        card=_text(where, "card", table["card"]),
        recommendation=_text(where, "recommendation", table["recommendation"]),
        owner_decision=_text(where, "owner_decision", table["owner_decision"]),
    )
    if triage.recommendation not in RECOMMENDATIONS:
        raise CapabilityError(f"{where}: recommendation must be one of {RECOMMENDATIONS}")
    if triage.owner_decision not in DECISIONS:
        raise CapabilityError(f"{where}: owner_decision must be one of {DECISIONS}")
    return triage


def _capability(index: int, raw: object) -> Capability:
    where = f"capability #{index + 1}"
    if not isinstance(raw, dict):
        raise CapabilityError(f"{where}: must be a table")
    table = cast(dict[str, object], raw)
    if isinstance(table.get("id"), str):
        where = f"capability '{table['id']}'"
    unknown = set(table) - set(_CAPABILITY_KEYS) - set(_OPTIONAL_KEYS)
    missing_keys = set(_CAPABILITY_KEYS) - set(table)
    if unknown or missing_keys:
        raise CapabilityError(
            f"{where}: unknown keys {sorted(unknown)}, missing keys {sorted(missing_keys)}"
        )
    for key, kind in (_CAPABILITY_KEYS | _OPTIONAL_KEYS).items():
        if key in table and not isinstance(table[key], kind):
            raise CapabilityError(f"{where}: '{key}' must be a {kind.__name__}")
    cap = Capability(
        id=_text(where, "id", table["id"]),
        name=_text(where, "name", table["name"]),
        codes=_strings(where, "codes", table.get("codes", [])),
        what=_text(where, "what", table["what"]),
        see_it=_strings(where, "see_it", table["see_it"], allow_empty=False),
        entry_points=_strings(where, "entry_points", table["entry_points"]),
        proof_synthetic=_strings(where, "proof_synthetic", table["proof_synthetic"]),
        proof_smoke=_strings(where, "proof_smoke", table.get("proof_smoke", [])),
        real_data=_text(where, "real_data", table["real_data"]),
        real_data_needs=str(table.get("real_data_needs", "")),
        needs=_strings(where, "needs", table["needs"]),
        state=_text(where, "state", table["state"]),
        missing=str(table.get("missing", "")),
        triage=_triage(f"{where} triage", table["triage"]) if "triage" in table else None,
        docs=_strings(where, "docs", table.get("docs", [])),
    )
    if _ID.fullmatch(cap.id) is None:
        raise CapabilityError(f"{where}: id must be kebab-case")
    if cap.state not in STATES:
        raise CapabilityError(f"{where}: state must be one of {STATES}")
    if cap.state == "Working":
        if not cap.proof_smoke or cap.needs:
            raise CapabilityError(f"{where}: Working needs proof_smoke and no needs")
        if cap.missing:
            raise CapabilityError(f"{where}: a Working capability has nothing missing")
    elif not cap.missing.strip():
        raise CapabilityError(f"{where}: state {cap.state} must say what is 'missing'")
    if cap.missing.endswith(NO_SMOKE_YET) and cap.proof_smoke:
        raise CapabilityError(f"{where}: says '{NO_SMOKE_YET}' but lists proof_smoke")
    if INTERNAL_ONLY in cap.see_it and len(cap.see_it) != 1:
        raise CapabilityError(f"{where}: '{INTERNAL_ONLY}' must be the only see_it entry")
    return cap


def _cli_names(root: Path) -> set[str]:
    text = (root / _CLI_MAIN).read_text(encoding="utf-8")
    return set(re.findall(r'^\s*\("([a-z-]+)", "alpha_cli\.', text, re.M))


def _api_routes(root: Path) -> set[str]:
    routes: set[str] = set()
    for path in sorted((root / _API_DIR).glob("*.py")):
        text = path.read_text(encoding="utf-8")
        prefix = _PREFIX.search(text)
        if prefix is None:
            continue
        for method, route in _ROUTE.findall(text):
            routes.add(f"{method.upper()} {prefix.group(1)}{route}")
    return routes


def _console_scripts(root: Path) -> set[str]:
    names: set[str] = set()
    for path in sorted(root.glob("apps/*/pyproject.toml")):
        section = path.read_text(encoding="utf-8").partition("[project.scripts]")[2]
        names.update(_SCRIPT.findall(section.split("\n[", 1)[0]))
    return names


def _check_entry_point(root: Path, where: str, entry: str, known: dict[str, set[str]]) -> None:
    kind, sep, value = entry.partition(": ")
    if not sep or not value:
        raise CapabilityError(f"{where}: entry point {entry!r} must be '<kind>: <value>'")
    if kind == "cli":
        words = value.split()
        if len(words) < 2 or words[0] != "alpha" or words[1] not in known["cli"]:
            raise CapabilityError(f"{where}: {entry!r} is not a registered alpha command group")
    elif kind == "api":
        if value not in known["api"]:
            raise CapabilityError(f"{where}: {entry!r} is not a route in {_API_DIR}")
    elif kind == "script":
        if value not in known["script"]:
            raise CapabilityError(f"{where}: {entry!r} is not a declared console script")
    elif kind in ("panel", "code"):
        if not (root / value).is_file():
            raise CapabilityError(f"{where}: {entry!r} does not exist")
    else:
        raise CapabilityError(f"{where}: unknown entry point kind in {entry!r}")


def _check_proof(root: Path, where: str, node: str) -> None:
    path, sep, test = node.partition("::")
    if not sep or not test:
        raise CapabilityError(f"{where}: proof {node!r} must be '<file>::<test>'")
    if path.startswith("tests/holdout"):
        raise CapabilityError(f"{where}: proof {node!r} must not name a hidden test")
    file = root / path
    if not file.is_file():
        raise CapabilityError(f"{where}: proof file {path} does not exist")
    text = file.read_text(encoding="utf-8")
    if path.endswith(".py"):
        found = re.search(rf"^(async )?def {re.escape(test)}\(", text, re.M) is not None
    else:
        found = test in text
    if not found:
        raise CapabilityError(f"{where}: proof test {test!r} not found in {path}")


def _mark_name(expr: ast.expr) -> str | None:
    """``skip`` for ``pytest.mark.skip`` / ``pytest.mark.skip(...)``; None for anything else."""
    if isinstance(expr, ast.Call):
        expr = expr.func
    if (
        isinstance(expr, ast.Attribute)
        and isinstance(expr.value, ast.Attribute)
        and expr.value.attr == "mark"
    ):
        return expr.attr
    return None


def _is_strict(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Call) and any(
        kw.arg == "strict" and isinstance(kw.value, ast.Constant) and kw.value.value is True
        for kw in expr.keywords
    )


def _module_marks(module: ast.Module) -> list[ast.expr]:
    for stmt in module.body:
        if isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets
        ):
            value = stmt.value
            return list(value.elts) if isinstance(value, (ast.List, ast.Tuple)) else [value]
    return []


def _smoke_tests(root: Path, path: str) -> tuple[ast.Module, dict[str, ast.FunctionDef]]:
    module = ast.parse((root / path).read_text(encoding="utf-8"), filename=path)
    tests = {
        stmt.name: stmt
        for stmt in module.body
        if isinstance(stmt, ast.FunctionDef) and stmt.name.startswith("test_")
    }
    return module, tests


def _designed_outcome(module: ast.Module, func: ast.FunctionDef) -> str | None:
    """'xfail' or 'skip' when the test is xfailed or skipped by design, else None."""
    for expr in [*_module_marks(module), *func.decorator_list]:
        name = _mark_name(expr)
        if name in _DESIGNED_MARKS:
            return "xfail" if name == "xfail" else "skip"
    for stmt in func.body:
        call = stmt.value if isinstance(stmt, ast.Expr) else None
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "pytest"
            and call.func.attr in ("skip", "xfail")
        ):
            return call.func.attr
    return None


def _strict_xfail(func: ast.FunctionDef) -> bool:
    return any(_mark_name(e) == "xfail" and _is_strict(e) for e in func.decorator_list)


def _smoke_node(root: Path, where: str, node: str) -> tuple[ast.Module, ast.FunctionDef]:
    path, sep, test = node.partition("::")
    if not sep or not test or not path.startswith(SMOKE_DIR) or not path.endswith(".py"):
        raise CapabilityError(
            f"{where}: smoke node {node!r} must be '{SMOKE_DIR}<file>.py::<test>'"
        )
    if not (root / path).is_file():
        raise CapabilityError(f"{where}: smoke file {path} does not exist")
    module, tests = _smoke_tests(root, path)
    if test not in tests:
        raise CapabilityError(f"{where}: smoke test {test!r} not found in {path}")
    return module, tests[test]


def _check_smoke(root: Path, cap: Capability) -> None:
    where = f"capability '{cap.id}'"
    proven = [
        node
        for node in cap.proof_smoke
        if _designed_outcome(*_smoke_node(root, where, node)) is None
    ]
    if cap.state == "Working" and not proven:
        raise CapabilityError(
            f"{where}: Working needs a proof_smoke check that is not skipped or xfailed by design"
        )


def _known_defects(root: Path, raw: object) -> tuple[KnownDefect, ...]:
    if not isinstance(raw, list):
        raise CapabilityError(f"{MAP}: [[known_defect]] must be an array of tables")
    defects: list[KnownDefect] = []
    for i, item in enumerate(raw):
        where = f"known_defect #{i + 1}"
        table = _table(where, item, {"title", "node", "how_to_reproduce"})
        defect = KnownDefect(
            title=_text(where, "title", table["title"]),
            node=_text(where, "node", table["node"]),
            how_to_reproduce=_text(where, "how_to_reproduce", table["how_to_reproduce"]),
        )
        _, func = _smoke_node(root, f"known_defect '{defect.title}'", defect.node)
        if not _strict_xfail(func):
            raise CapabilityError(
                f"known_defect '{defect.title}': {defect.node} is not marked "
                "pytest.mark.xfail(strict=True) in its file"
            )
        defects.append(defect)
    listed = Counter(d.node for d in defects)
    if any(n > 1 for n in listed.values()):
        raise CapabilityError(f"{MAP}: a known_defect node is listed more than once")
    for path in sorted((root / SMOKE_DIR).glob("test_*.py")):
        rel = path.relative_to(root).as_posix()
        module, tests = _smoke_tests(root, rel)
        for name, func in tests.items():
            node = f"{rel}::{name}"
            if _designed_outcome(module, func) == "xfail" and node not in listed:
                raise CapabilityError(
                    f"{MAP}: xfail smoke check {node} is not listed as a [[known_defect]]"
                )
    return tuple(defects)


def load(root: Path = ROOT) -> CapabilityMap:
    """Parse and fully check the capability map against the repository at ``root``."""
    try:
        data = tomllib.loads((root / MAP).read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise CapabilityError(f"{MAP}: not valid TOML: {exc}") from exc
    allowed = {"capability", "decision", "known_defect"}
    if set(data) - allowed:
        raise CapabilityError(f"{MAP}: unknown top-level keys {sorted(set(data) - allowed)}")
    raw_caps = data.get("capability", [])
    if not isinstance(raw_caps, list) or not raw_caps:
        raise CapabilityError(f"{MAP}: needs at least one [[capability]]")
    caps = tuple(_capability(i, raw) for i, raw in enumerate(raw_caps))
    dupes = [cid for cid, n in Counter(c.id for c in caps).items() if n > 1]
    if dupes:
        raise CapabilityError(f"{MAP}: duplicate capability ids {sorted(dupes)}")

    decisions: list[Decision] = []
    for i, raw in enumerate(data.get("decision", [])):
        keys = {"card", "name", "recommendation", "owner_decision"}
        table = _table(f"decision #{i + 1}", raw, keys)
        name = _text(f"decision #{i + 1}", "name", table.pop("name"))
        decisions.append(Decision(name, _triage(f"decision '{name}'", table)))
    cards = [c.triage.card for c in caps if c.triage] + [d.triage.card for d in decisions]
    dup_cards = [card for card, n in Counter(cards).items() if n > 1]
    if dup_cards:
        raise CapabilityError(f"{MAP}: triage cards listed more than once: {sorted(dup_cards)}")

    known = {"cli": _cli_names(root), "api": _api_routes(root), "script": _console_scripts(root)}
    for cap in caps:
        where = f"capability '{cap.id}'"
        for entry in cap.entry_points:
            _check_entry_point(root, where, entry, known)
        for node in cap.proof_synthetic:
            _check_proof(root, where, node)
        _check_smoke(root, cap)
        for doc in cap.docs:
            if not doc.endswith(".md") or not (root / doc).is_file():
                raise CapabilityError(f"{where}: doc {doc!r} is not a Markdown file in the repo")
    defects = _known_defects(root, data.get("known_defect", []))

    return CapabilityMap(caps, tuple(decisions), defects)


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        load(ROOT)
    except CapabilityError as exc:
        print(f"capabilities: {exc}", file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
