"""Structural guard: a research read of bars or dividends is cut at the held-back boundary.

`_runner.load_bars` and `load_dividends` read everything stored when `as_of` is None, and
`ParquetStore.read_bars` takes no cut-off at all. So the cut lives only in each caller. This test
scans `apps/alpha-cli/src` and enforces the cut positively. Every call to `load_bars`,
`load_dividends` or `.read_bars(` must pass an `as_of` that provably comes from the reserve:

- `reserve.CUTOFF` (or `CUTOFF` imported from `alpha_cli.spine.reserve`);
- `held.as_of` or `held.as_of_for(...)`, where `held` is assigned in the same function from
  `reserve.hold(...)`, `reserve.hold_many(...)` or a helper in HOLD_HELPERS;
- `min(..., <a cut value>)`, or a call to a helper in CUT_HELPERS;
- a local name whose every assignment in the function is such a value;
- a parameter of a module-level function whose every caller in the package passes such a value
  (followed through helpers, at most MAX_STEPS steps). A helper that is also used as a value
  (passed, stored) or has no caller is not proven.

Any other read is listed in ALLOWED with one reason. `exempt:` means forward use, a display, a
check of stored bytes or cut by other means the scan cannot prove. `open:` is a known leak; the
reason names the change that fixes it, and that change removes the entry. A read not proven and
not listed fails. An entry that matches no unproven read fails too: a stale list is a lie.

A second rule: `read_parquet` / `scan_parquet` on a bars store file (a `._bars_path(...)` path or a
`bars/` path) happens only where PARQUET_ALLOWED says, so a read cannot bypass the loaders.

What the guard cannot see: a call from outside `apps/alpha-cli/src` (tests, other apps) to a
helper here; a read through another reader (`PointInTimeSource(...).as_of`, `PointInTimeReader`,
`load_archive_bars`, `load_chart_dataset`, the crypto bulk artifacts under `bulk_root`); a cut
value that is right by name but wrong at run time (a Hold built for another symbol); and bars
that reach code as a frame or a stored result rather than through a loader.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "apps" / "alpha-cli" / "src" / "alpha_cli"
LOADERS = frozenset({"load_bars", "load_dividends"})
STORE_READER = "read_bars"
RUNNER = "alpha_cli._runner"
RESERVE = "alpha_cli.spine.reserve"
HOLDS = frozenset({"hold", "hold_many"})
PARQUET = frozenset({"read_parquet", "scan_parquet"})
MAX_STEPS = 6

# (file under alpha_cli/, function) whose return value is a cut-off no later than the boundary.
CUT_HELPERS: dict[tuple[str, str], str] = {
    ("monte_carlo_cmds.py", "_source_as_of"): "min(the source run's cut-off, reserve.CUTOFF)",
}
# (file under alpha_cli/, function) that returns a `reserve.Hold`.
HOLD_HELPERS: dict[tuple[str, str], str] = {
    ("backtest_cmds.py", "_run_hold"): "returns reserve.hold(...) or _archive_bars.hold_archive",
}

# (file under alpha_cli/, enclosing function) -> reason. `exempt:` or `open:` comes first.
# fmt: off
ALLOWED: dict[tuple[str, str], str] = {
    ("_data_health.py", "_stock_peers"): "exempt: data health checks every stored bar by design",
    ("_data_health.py", "compute_report"): "exempt: data health checks every stored bar by design",
    ("_ibkr_paper.py", "load_ibkr_warmup"): "exempt: forward paper use reads the newest bars",
    ("_paper.py", "load_paper_warmup"): "exempt: forward paper use reads the newest bars",
    ("daily_scheduler.py", "execute_cycle"): "exempt: the daily scheduler is forward paper use",
    ("follow_source.py", "latest_bar_hashes"): "exempt: follow is forward use (follow separation)",
    ("follow_source.py", "forward_bars"): "exempt: follow is forward use; as_of is now",
    ("follow_source.py", "forward_dividends"): "exempt: follow is forward use; as_of is now",
    ("market_overview_cmds.py", "build_market_overview"): "exempt: a display of the newest bars",
    ("nightly_refresh.py", "_bars"): "exempt: reads only the stored time span to plan a refresh",
    ("chart_cmds.py", "overlays"): "exempt: alpha chart is a display (label only)",
    ("data_cmds.py", "candles"): "exempt: alpha data candles is a display (label only)",
    ("assistant_context.py", "assemble_context"): "exempt: the assistant context (label only)",
    ("assistant_context.py", "_run_sources"): "exempt: the assistant context, to a run's last bar",
    ("forecast_cmds.py", "run"): "exempt: forecast run is forward use (reserved-period.md)",
    ("backtest_cmds.py", "holdout"): "exempt: the revealed holdout itself (reserved-period.md)",
    ("scan_cmds.py", "run_scan"): "exempt: research callers use hold_many; forward=True is alerts",
    ("_hypothesis_scan.py", "equity_panel"): "exempt: cut by hand to reserve.CUTOFF past the day",
    ("rdagent_rule_family.py", "_load"): "exempt: STUDY_AS_OF 2023-12-31, then ReservedDataError",
    ("toolbox/inputs.py", "load_run"): "exempt: a stored run's own cut-off and last bar",
    ("toolbox/inputs.py", "comparison"): "exempt: a benchmark up to the stored run's last bar",
    ("context_derived_cmds.py", "_bars_and_calendar"): "exempt: attach_context(cutoff=CUTOFF)",
    ("_native_rule_projection.py", "_snapshot"): "exempt: checks a synthetic snapshot's own rows",
    ("_native_daily_rule_projection.py", "chart_snapshot"): "exempt: checks a frozen chart query",
    ("comparison_acquisition_evidence.py", "_replay"): "exempt: verifies stored bytes; no research",
    ("comparison_acquisition_evidence.py", "_result"): "exempt: verifies stored bytes; no research",
}
# (file under alpha_cli/, enclosing function) that reads a bars store file with polars.
PARQUET_ALLOWED: dict[tuple[str, str], str] = {
    ("spine/reserve.py", "held_back_count"): "exempt: counts stamps from the reserved day on",
    ("spine/reserve.py", "hold"): "exempt: counts stamps from the reserved day on",
    ("toolbox/run_months.py", "bar_dates"): "exempt: reads stamps up to the run's last bar",
    ("investigation_comparisons.py", "_series"): "exempt: schema and row count; prices via PIT",
}
# fmt: on


@dataclass
class Module:
    """One source file: its tree and the names it binds to loaders, the reserve and modules."""

    rel: str
    dotted: str
    tree: ast.Module
    modules: dict[str, str] = field(default_factory=dict)  # local alias -> dotted module
    imported: dict[str, tuple[str, str]] = field(default_factory=dict)  # name -> (module, name)
    functions: dict[str, ast.FunctionDef] = field(default_factory=dict)  # module level only
    loaders: set[str] = field(default_factory=set)

    @classmethod
    def parse(cls, rel: str, source: str, known: frozenset[str] = frozenset()) -> Module:
        mod = cls(rel, _dotted(rel), ast.parse(source))
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("alpha_cli"):
                for alias in node.names:
                    local, home = alias.asname or alias.name, node.module or ""
                    mod.imported[local] = (home, alias.name)
                    if f"{home}.{alias.name}" in known | {RUNNER, RESERVE}:
                        mod.modules[local] = f"{home}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("alpha_cli.") and alias.asname:
                        mod.modules[alias.asname] = alias.name
        mod.functions = {n.name: n for n in mod.tree.body if isinstance(n, ast.FunctionDef)}
        mod.loaders = {k for k, (m, n) in mod.imported.items() if m == RUNNER and n in LOADERS}
        for node in ast.walk(mod.tree):  # a seam such as `_load_bars = _runner.load_bars`
            if isinstance(node, ast.Assign) and _names_loader(node.value, mod.loaders):
                mod.loaders.update(t.id for t in node.targets if isinstance(t, ast.Name))
        return mod

    def target(self, func: ast.expr) -> tuple[str, str] | None:
        """The (module, function) a called or named expression refers to, inside the package."""
        if isinstance(func, ast.Name):
            if func.id in self.imported:
                return self.imported[func.id]
            return (self.dotted, func.id) if func.id in self.functions else None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            home = self.modules.get(func.value.id)
            return (home, func.attr) if home else None
        return None

    def is_reserve(self, node: ast.expr, names: frozenset[str]) -> bool:
        """`reserve.<name>`, or `<name>` imported from the reserve module."""
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return self.modules.get(node.value.id) == RESERVE and node.attr in names
        return isinstance(node, ast.Name) and self.imported.get(node.id, ("", ""))[0] == RESERVE \
            and self.imported[node.id][1] in names  # fmt: skip


Caller = tuple[Module, ast.FunctionDef | None, ast.Call]


def _dotted(rel: str) -> str:
    return "alpha_cli." + rel.removesuffix(".py").removesuffix("/__init__").replace("/", ".")


def _names_loader(node: ast.expr, loaders: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in loaders
    return isinstance(node, ast.Attribute) and node.attr in LOADERS


Scoped = tuple[ast.AST, ast.FunctionDef | None, str]


def _scoped(tree: ast.AST) -> Iterator[Scoped]:
    """Every node with its innermost enclosing function and its dotted scope name."""

    def walk(node: ast.AST, fn: ast.FunctionDef | None, scope: str) -> Iterator[Scoped]:
        for child in ast.iter_child_nodes(node):
            inner, where = fn, scope
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                where = f"{scope}.{child.name}" if scope else child.name
                inner = child if isinstance(child, ast.FunctionDef) else None
            yield child, inner, where
            yield from walk(child, inner, where)

    return walk(tree, None, "")


def _starred(call: ast.Call) -> bool:
    return any(isinstance(a, ast.Starred) for a in call.args) or any(
        k.arg is None for k in call.keywords
    )


def _assigned(fn: ast.FunctionDef, name: str) -> list[ast.expr] | None:
    """Every value assigned to ``name`` in ``fn``; None when one is not a plain assignment."""
    values: list[ast.expr] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    values.append(node.value)
                elif any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(t)):
                    return None  # unpacked: the value cannot be traced
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name and node.value is not None:
                values.append(node.value)
        elif isinstance(node, ast.AugAssign | ast.For | ast.With | ast.NamedExpr):
            bound = node.target if not isinstance(node, ast.With) else node
            if any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(bound)):
                return None
    return values


def _param(fn: ast.FunctionDef, name: str) -> tuple[int | None, ast.expr | None] | None:
    """(position or None for keyword-only, default) of a named parameter; None if it is not one."""
    args = fn.args
    positional = [*args.posonlyargs, *args.args]
    for i, a in enumerate(positional):
        if a.arg == name:
            j = i - (len(positional) - len(args.defaults))
            return i, args.defaults[j] if j >= 0 else None
    for a, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        if a.arg == name:
            return None, default
    return None


class Package:
    """Every module of the package, its calls by target, and the cut-provenance check."""

    def __init__(self, sources: dict[str, str]) -> None:
        self.sources = sources
        self.known = frozenset(_dotted(rel) for rel in sources)
        self.parsed: dict[str, Module] = {}
        self.uses: dict[tuple[str, str], tuple[list[Caller], bool]] = {}
        self.cut_helpers = {(_dotted(f), n) for f, n in CUT_HELPERS}
        self.hold_helpers = {(_dotted(f), n) for f, n in HOLD_HELPERS}

    def module(self, rel: str) -> Module:
        if rel not in self.parsed:  # parsed on demand: only files that name what is looked for
            self.parsed[rel] = Module.parse(rel, self.sources[rel], self.known)
        return self.parsed[rel]

    def naming(self, *words: str) -> list[Module]:
        return [self.module(r) for r, src in self.sources.items() if any(w in src for w in words)]

    def callers(self, key: tuple[str, str]) -> tuple[list[Caller], bool]:
        """Every call of ``key`` in the package, and whether it is also used as a value."""
        if key not in self.uses:
            calls, as_value = [], False
            for mod in self.naming(key[1]):
                heads: set[int] = set()
                for node, fn, _ in _scoped(mod.tree):
                    if isinstance(node, ast.Call):
                        heads.add(id(node.func))
                        if mod.target(node.func) == key:
                            calls.append((mod, fn, node))
                    elif isinstance(node, ast.Name | ast.Attribute) and id(node) not in heads:
                        loaded = isinstance(node.ctx, ast.Load)
                        as_value = as_value or (loaded and mod.target(node) == key)
            self.uses[key] = calls, as_value
        return self.uses[key]

    def is_hold(self, mod: Module, fn: ast.FunctionDef, name: str) -> bool:
        values = _assigned(fn, name)
        return bool(values) and all(self.makes_hold(mod, v) for v in values or [])

    def makes_hold(self, mod: Module, value: ast.expr) -> bool:
        """A call of `reserve.hold`, `hold_many` or a hold helper; `a if c else b` of two."""
        if isinstance(value, ast.IfExp):
            return self.makes_hold(mod, value.body) and self.makes_hold(mod, value.orelse)
        return isinstance(value, ast.Call) and (
            mod.is_reserve(value.func, HOLDS) or mod.target(value.func) in self.hold_helpers
        )

    def is_cut(self, expr: ast.expr, mod: Module, fn: ast.FunctionDef | None, steps: int) -> bool:
        if steps > MAX_STEPS:
            return False
        if mod.is_reserve(expr, frozenset({"CUTOFF"})):
            return True
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and fn:
            return expr.attr == "as_of" and self.is_hold(mod, fn, expr.value.id)
        if isinstance(expr, ast.Call) and not _starred(expr):
            head = expr.func
            if (
                isinstance(head, ast.Attribute)
                and isinstance(head.value, ast.Name)
                and fn is not None
                and head.attr == "as_of_for"
                and self.is_hold(mod, fn, head.value.id)
            ):
                return True
            if isinstance(head, ast.Name) and head.id == "min" and len(expr.args) > 1:
                return any(self.is_cut(a, mod, fn, steps + 1) for a in expr.args)
            return mod.target(head) in self.cut_helpers
        if isinstance(expr, ast.Name) and fn is not None:
            values, param = _assigned(fn, expr.id), _param(fn, expr.id)
            if values is None or (not values and param is None):
                return False
            if param is not None and not self.param_is_cut(mod, fn, expr.id, steps + 1):
                return False
            return all(self.is_cut(v, mod, fn, steps + 1) for v in values)
        return False

    def param_is_cut(self, mod: Module, fn: ast.FunctionDef, name: str, steps: int) -> bool:
        """Every caller in the package passes a cut value (or the default is one)."""
        spot = _param(fn, name)
        callers, as_value = self.callers((mod.dotted, fn.name))
        if mod.functions.get(fn.name) is not fn or spot is None or as_value:
            return False
        position, default = spot
        if not callers:
            return False
        for caller, outer, call in callers:
            if _starred(call):
                return False
            given = next((k.value for k in call.keywords if k.arg == name), None)
            if given is None and position is not None and position < len(call.args):
                given = call.args[position]
            if given is None:
                if default is None or not self.is_cut(default, mod, None, steps):
                    return False
            elif not self.is_cut(given, caller, outer, steps):
                return False
        return True

    def unproven_reads(self) -> list[tuple[str, str, int, str]]:
        """Every (file, function, line, loader) whose cut-off the scan cannot prove."""
        found = []
        for mod in self.naming(*LOADERS, STORE_READER):
            heads: set[int] = set()
            for node, fn, where in _scoped(mod.tree):
                if isinstance(node, ast.Assign) and _names_loader(node.value, mod.loaders):
                    heads.add(id(node.value))  # a seam declaration, not a read
                if isinstance(node, ast.Call):
                    heads.add(id(node.func))
                    name = _loader_name(node.func, mod.loaders)
                    if name and not self._call_is_cut(node, name, mod, fn):
                        found.append((mod.rel, where or "<module>", node.lineno, name))
                elif isinstance(node, ast.Name | ast.Attribute) and id(node) not in heads:
                    name = _loader_name(node, mod.loaders) if isinstance(node.ctx, ast.Load) else ""
                    if name:
                        found.append((mod.rel, where or "<module>", node.lineno, f"{name} value"))
        return found

    def _call_is_cut(
        self, call: ast.Call, name: str, mod: Module, fn: ast.FunctionDef | None
    ) -> bool:
        if name == STORE_READER or _starred(call):
            return False  # `read_bars` takes no cut-off; `**kwargs` may hide one
        given = next((k.value for k in call.keywords if k.arg == "as_of"), None)
        return given is not None and self.is_cut(given, mod, fn, 0)

    def bars_file_reads(self) -> list[tuple[str, str, int]]:
        """Every polars read of a bars store file: (file, function, line)."""
        found = []
        for mod in self.naming("_bars_path", "bars/"):
            for node, fn, where in _scoped(mod.tree):
                if (
                    isinstance(node, ast.Call)
                    and _attr_or_name(node.func) in PARQUET
                    and node.args
                    and _names_bars_file(node.args[0], fn)
                ):
                    found.append((mod.rel, where or "<module>", node.lineno))
        return found


def _attr_or_name(node: ast.expr) -> str:
    return node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "")


def _loader_name(node: ast.expr, loaders: set[str]) -> str:
    if isinstance(node, ast.Name) and node.id in loaders:
        return node.id
    if isinstance(node, ast.Attribute) and node.attr in {*LOADERS, STORE_READER}:
        return node.attr
    return ""


def _names_bars_file(node: ast.expr, fn: ast.FunctionDef | None, depth: int = 0) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and _attr_or_name(sub.func) == "_bars_path":
            return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and "bars/" in sub.value:
            return True
        if isinstance(sub, ast.Name) and fn is not None and depth < 3:
            values = _assigned(fn, sub.id) or []
            if any(_names_bars_file(v, fn, depth + 1) for v in values):
                return True
    return False


@cache
def package() -> Package:
    files = sorted(CLI.rglob("*.py"))
    return Package({p.relative_to(CLI).as_posix(): p.read_text(encoding="utf-8") for p in files})


@cache
def unproven() -> list[tuple[str, str, int, str]]:
    return package().unproven_reads()


def _keys(
    rows: list[tuple[str, str, int, str]] | list[tuple[str, str, int]],
) -> set[tuple[str, str]]:
    return {(row[0], row[1]) for row in rows}


def test_every_unproven_read_is_listed_with_a_reason() -> None:
    rows = unproven()
    new = sorted(r for r in rows if (r[0], r[1]) not in ALLOWED)
    assert not new, f"a bars or dividends read is not cut by the reserve; cut it or list it: {new}"


def test_no_listed_entry_is_stale() -> None:
    stale = sorted(set(ALLOWED) - _keys(unproven()))
    assert not stale, f"these entries match no unproven read any more; remove them: {stale}"


def test_every_entry_has_a_kind_and_a_reason() -> None:
    entries = {**ALLOWED, **PARQUET_ALLOWED}
    bad = [k for k, why in entries.items() if not why.startswith(("exempt: ", "open: "))]
    assert not bad, f"each reason starts with 'exempt: ' or 'open: ': {bad}"


def test_every_listed_helper_exists_and_names_the_reserve() -> None:
    for rel, name in [*CUT_HELPERS, *HOLD_HELPERS]:
        mod = package().module(rel)
        assert name in mod.functions, (rel, name)
        assert "reserve." in ast.unparse(mod.functions[name]), (rel, name)


def test_bars_store_files_are_read_with_polars_only_where_listed() -> None:
    found = _keys(package().bars_file_reads())
    assert found <= set(PARQUET_ALLOWED), sorted(found - set(PARQUET_ALLOWED))
    assert set(PARQUET_ALLOWED) <= found, sorted(set(PARQUET_ALLOWED) - found)


def _unproven(*lines: str) -> int:
    rows = Package({"case.py": "\n".join(lines)}).unproven_reads()
    return sum(row[0] == "case.py" for row in rows)


RUN = "from alpha_cli._runner import load_bars"
RES = "from alpha_cli.spine import reserve"
FAILS: dict[str, tuple[str, ...]] = {
    "a bare call": (RUN, "def f(s, d):", "    load_bars(s, data_dir=d)"),
    "as_of=None": (RUN, "def f(s, d):", "    load_bars(s, data_dir=d, as_of=None)"),
    "an uncalled helper": (RUN, "def f(s, d, as_of):", "    load_bars(s, data_dir=d, as_of=as_of)"),
    "as_of=user_value": (
        RUN, "def f(s, d, a):", "    load_bars(s, data_dir=d, as_of=a)",
        "def cmd(s, d, user):", "    f(s, d, user)",
    ),
    "an alias import": (
        "from alpha_cli._runner import load_bars as lb", "def f(s, d):", "    lb(s, data_dir=d)",
    ),
    "a module alias": (
        "from alpha_cli import _runner as r", "def f(s, d):", "    r.load_dividends(s, data_dir=d)",
    ),
    "**kwargs": (
        "import alpha_cli._runner as r", "def f(s, d, kw):", "    r.load_bars(s, data_dir=d, **kw)",
    ),
    "a loader passed as a value": (RUN, "def f(xs):", "    return map(load_bars, xs)"),
    "read_bars takes no cut-off": ("def f(store, s):", "    store.read_bars(s)"),
    "a seam": (
        "from alpha_cli import _runner", "seam = _runner.load_bars",
        "def f(s, d):", "    seam(s, data_dir=d)",
    ),
    "one assignment is not cut": (
        RUN, RES, "def f(s, d, user):", "    cut = reserve.CUTOFF", "    if user:",
        "        cut = user", "    load_bars(s, data_dir=d, as_of=cut)",
    ),
    "an attribute of a non-hold": (
        RUN, RES, "def f(s, d, user):", "    held = reserve.hold(s, data_dir=d)",
        "    load_bars(s, data_dir=d, as_of=user.as_of)",
    ),
    "a hold or None": (
        RUN, RES, "def f(s, d, fwd):", "    held = None if fwd else reserve.hold(s, data_dir=d)",
        "    load_bars(s, data_dir=d, as_of=held.as_of)",
    ),
    "a helper also used as a value": (
        RUN, RES, "def f(s, d, a):", "    load_bars(s, data_dir=d, as_of=a)",
        "def g(s, d):", "    f(s, d, reserve.CUTOFF)", "h = f",
    ),
}  # fmt: skip
PROVES: dict[str, tuple[str, ...]] = {
    "CUTOFF": (RUN, RES, "def f(s, d):", "    load_bars(s, data_dir=d, as_of=reserve.CUTOFF)"),
    "an imported CUTOFF": (
        RUN, "from alpha_cli.spine.reserve import CUTOFF as C",
        "def f(s, d):", "    load_bars(s, data_dir=d, as_of=C)",
    ),
    "held.as_of": (
        RUN, RES, "def f(s, d, u):", "    held = reserve.hold(s, data_dir=d, as_of=u)",
        "    load_bars(s, data_dir=d, as_of=held.as_of)",
    ),
    "held.as_of_for": (
        RUN, RES, "def f(ss, d):", "    held = reserve.hold_many(ss, d)",
        "    load_bars(ss[0], data_dir=d, as_of=held.as_of_for(ss[0]))",
    ),
    "min": (
        RUN, RES, "def f(s, d, u):", "    load_bars(s, data_dir=d, as_of=min(u, reserve.CUTOFF))",
    ),
    "a helper's parameter": (
        RUN, RES, "def f(s, d, *, a):", "    load_bars(s, data_dir=d, as_of=a)",
        "def g(s, d):", "    held = reserve.hold(s, data_dir=d)", "    f(s, d, a=held.as_of)",
    ),
    "a cut default": (
        RUN, RES, "def f(s, d, a=reserve.CUTOFF):", "    load_bars(s, data_dir=d, as_of=a)",
        "def g(s, d):", "    f(s, d)",
    ),
    "a hold from either branch": (
        RUN, RES, "def f(ss, d, one):",
        "    held = reserve.hold(ss[0], data_dir=d) if one else reserve.hold_many(ss, d)",
        "    load_bars(ss[0], data_dir=d, as_of=held.as_of)",
    ),
    "a seam declaration": ("from alpha_cli import _runner", "seam = _runner.load_bars"),
    "another function": ("def f(other, s):", "    other.load_things(s)"),
}  # fmt: skip


def test_the_scan_fails_every_uncut_shape() -> None:
    for what, lines in FAILS.items():
        assert _unproven(*lines) == 1, what


def test_the_scan_proves_every_cut_shape() -> None:
    for what, lines in PROVES.items():
        assert _unproven(*lines) == 0, what


def test_the_scan_follows_a_helper_into_another_module() -> None:
    helper = f"{RUN}\ndef leg(s, d, as_of):\n    return load_bars(s, data_dir=d, as_of=as_of)\n"
    cut = f"{RES}\nfrom alpha_cli.helper import leg\ndef cmd(s, d):\n"
    cut += "    held = reserve.hold(s, data_dir=d)\n    leg(s, d, held.as_of)\n"
    leak = "from alpha_cli import helper\ndef cmd(s, d, user):\n    helper.leg(s, d, user)\n"
    for caller, expected in ((cut, 0), (leak, 1)):
        rows = Package({"helper.py": helper, "cmd.py": caller}).unproven_reads()
        assert len(rows) == expected, caller


def test_the_bars_file_rule_sees_a_store_path() -> None:
    source = (
        "import polars as pl\ndef f(store, s, snap):\n    path = store._bars_path(s)\n"
        "    pl.read_parquet(path)\n    pl.scan_parquet(snap / f'bars/{s}.parquet')\n"
        "    pl.read_parquet(snap / 'result.parquet')\n"
    )
    assert len(Package({"case.py": source}).bars_file_reads()) == 2
