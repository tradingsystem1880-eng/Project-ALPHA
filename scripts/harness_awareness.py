"""Session brief, repo index and plan checks — imported lazily by gate.py and by claude_hooks."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import gate

BRIEF_FILE = "brief.json"
INDEX_FILE = "repo-index.json"
_PLAN_DONE_RE = re.compile(r"delivery state:\*{0,2}\s*(completed|delivered|done)", re.I)
_ADR_ID_RE = re.compile(r"^(\d{4})-")
_WATCHOUT_HEADING_RE = re.compile(r"^##+\s*watch-?outs", re.I)


def adr_files(root: Path) -> list[str]:
    """ADR filenames (``NNNN-*.md``) in docs/adr, sorted."""
    adr_dir = root / "docs" / "adr"
    if not adr_dir.is_dir():
        return []
    return sorted(p.name for p in adr_dir.glob("*.md") if _ADR_ID_RE.match(p.name))


_ADR_MENTION_RE = re.compile(r"ADRs?[ -](\d{4})(?:(?:\.\.|-|–)(\d{4}))?")


def referenced_adr_ids(text: str) -> set[int]:
    """ADR numbers a document mentions: ``ADR-0013``, ``ADRs 0013-0016``, ``ADR-0021..0026``."""
    ids: set[int] = set()
    for start, end in _ADR_MENTION_RE.findall(text):
        lo, hi = int(start), int(end or start)
        ids.update(range(lo, hi + 1))
    return ids


def adr_drift(root: Path) -> list[str]:
    """ADR ids that neither CLAUDE.md nor .claude/rules/*.md mention (awareness drift)."""
    haystack = ""
    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        haystack += claude_md.read_text(errors="replace")
    for rule in sorted((root / ".claude" / "rules").glob("*.md")):
        haystack += rule.read_text(errors="replace")
    mentioned = referenced_adr_ids(haystack)
    ids: list[str] = []
    for name in adr_files(root):
        match = _ADR_ID_RE.match(name)
        assert match is not None
        if int(match.group(1)) not in mentioned:
            ids.append(f"ADR-{match.group(1)}")
    return ids


def open_plan(root: Path) -> str | None:
    """The newest docs/superpowers/plans/*.md unless its header says Completed/Delivered/done.

    Only the newest plan is considered: older plans predate the delivery-state
    marker convention, so scanning further back would resurrect finished work.
    """
    plans = sorted((root / "docs" / "superpowers" / "plans").glob("*.md"), reverse=True)
    if not plans:
        return None
    head = "\n".join(plans[0].read_text(errors="replace").splitlines()[:12])
    return None if _PLAN_DONE_RE.search(head) else plans[0].name


def latest_retrospective_watchouts(root: Path) -> tuple[str | None, list[str]]:
    retros = sorted((root / "docs" / "operations" / "retrospectives").glob("*.md"), reverse=True)
    if not retros:
        return (None, [])
    lines: list[str] = []
    capturing = False
    for line in retros[0].read_text(errors="replace").splitlines():
        if _WATCHOUT_HEADING_RE.match(line):
            capturing = True
            continue
        if capturing and line.startswith("#"):
            break
        if capturing and line.strip():
            lines.append(line.strip())
    return (retros[0].name, lines)


def build_brief(root: Path) -> str:
    """Compute the awareness brief from the tree (uncached)."""
    branch = gate._git(root, "branch", "--show-current", check=False).strip() or "?"
    dirty = len(gate._git_lines(root, "status", "--porcelain"))
    stamp = {
        "full": "full (valid)",
        "fast": "fast (valid; full needed to commit)",
    }.get(gate.stamp_tier(root), "none/stale")
    lines = [
        "REPO BRIEF (generated from the tree by gate.py brief):",
        f"- branch {branch}, {dirty} dirty file(s), gate stamp {stamp}",
    ]
    commits = gate._git_lines(root, "log", "--oneline", "-5")
    if commits:
        lines.append("- recent commits: " + " | ".join(commits))
    plan = open_plan(root)
    lines.append(f"- open plan: docs/superpowers/plans/{plan}" if plan else "- open plan: none")
    retro, watchouts = latest_retrospective_watchouts(root)
    if retro:
        joined = "; ".join(watchouts) if watchouts else "(no watch-outs section)"
        lines.append(f"- last retrospective {retro}: {joined}")
    adrs = adr_files(root)
    latest = f" (latest {adrs[-1]})" if adrs else ""
    lines.append(f"- ADRs: {len(adrs)}{latest}")
    escapes = [
        e
        for e in gate.read_audit(
            root, since=(datetime.now(UTC) - timedelta(days=gate.DIGEST_DEFAULT_DAYS)).isoformat()
        )
        if str(e.get("event")) in gate.ESCAPE_EVENTS
    ]
    if escapes:
        note = (
            " (owner token unset — all self-serve)" if not gate.owner_token_configured(root) else ""
        )
        lines.append(
            f"- escapes: {len(escapes)} self-authorized in the last "
            f"{gate.DIGEST_DEFAULT_DAYS}d{note} — gate.py audit --digest"
        )
    else:
        lines.append(f"- escapes: none in the last {gate.DIGEST_DEFAULT_DAYS}d")
    drift = adr_drift(root)
    if drift:
        lines.append(
            f"- DRIFT: {', '.join(drift)} not referenced in CLAUDE.md/.claude/rules — fix the docs"
        )
    return "\n".join(lines)


def _brief_cache_key(root: Path) -> str:
    """Tree content plus the git facts the brief reports that the tree hash cannot see.

    ``gate.compute_tree_hash`` covers file bytes only — deliberately, so that committing does not
    invalidate a gate stamp. But the brief also reports HEAD and the dirty count, and a plain
    commit changes both while touching no byte on disk. Keyed on content alone the cache would
    keep serving a brief that claims uncommitted files and omits the commit just made.
    """
    head = gate._git(root, "rev-parse", "HEAD", check=False).strip() or "?"
    branch = gate._git(root, "branch", "--show-current", check=False).strip() or "?"
    return f"{gate.compute_tree_hash(root)}:{head}:{branch}"


def repo_brief(root: Path, *, refresh: bool = False) -> str:
    """The brief, cached at .claude/state/brief.json keyed by tree content and git position."""
    key = _brief_cache_key(root)
    cache_path = gate._state_dir(root) / BRIEF_FILE
    cached = gate.read_json(cache_path)
    if (
        not refresh
        and cached
        and cached.get("cache_key") == key
        and isinstance(cached.get("text"), str)
    ):
        return str(cached["text"])
    text = build_brief(root)
    gate.write_json_atomic(
        cache_path, {"cache_key": key, "generated_at": gate._now(), "text": text}
    )
    return text


def _public_symbols(path: Path) -> list[str]:
    """Top-level public defs/classes (or ``__all__`` when declared); [] on syntax errors."""
    try:
        tree = ast.parse(path.read_text(errors="replace"))
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                break
            return [str(v) for v in value] if isinstance(value, list | tuple) else []
    names: list[str] = []
    for node in tree.body:
        if isinstance(
            node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ) and not node.name.startswith("_"):
            names.append(node.name)
    return names


def build_index(root: Path, *, cli: bool = True) -> dict[str, Any]:
    """Repo index: packages -> modules -> public symbols, contracts, CLI tree, ADRs, figures."""
    packages: dict[str, dict[str, list[str]]] = {}
    for src in sorted([*root.glob("packages/*/src/*"), *root.glob("apps/*/src/*")]):
        if not src.is_dir() or not (src / "__init__.py").exists() or "_vendor" in src.parts:
            continue
        modules: dict[str, list[str]] = {}
        for py in sorted(src.rglob("*.py")):
            if "_vendor" in py.parts:
                continue
            modules[str(py.relative_to(src))] = _public_symbols(py)
        packages[src.name] = modules
    contracts: list[str] = []
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text())
        except tomllib.TOMLDecodeError:
            data = {}
        for contract in data.get("tool", {}).get("importlinter", {}).get("contracts", []):
            contracts.append(str(contract.get("name", "")))
    figures: list[str] = []
    catalog = root / "packages/alpha-research/src/alpha_research/figures/catalog.py"
    if catalog.exists():
        figures = re.findall(r'figure_id="([^"]+)"', catalog.read_text())
    server = root / "apps/alpha-mcp/src/alpha_mcp/server.py"
    mcp_tools = len(re.findall(r"@mcp\.tool", server.read_text())) if server.exists() else 0
    cli_commands: dict[str, Any]
    if not cli:
        cli_commands = {"unavailable": "cli=False"}
    else:
        proc = subprocess.run(
            ["uv", "run", "alpha", "info", "commands", "--json"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        try:
            cli_commands = json.loads(proc.stdout) if proc.returncode == 0 else {}
        except json.JSONDecodeError:
            cli_commands = {}
        if not cli_commands:
            cli_commands = {"unavailable": (proc.stderr or "alpha info commands failed")[-300:]}
    return {
        "tree_hash": gate.compute_tree_hash(root),
        "generated_at": gate._now(),
        "packages": packages,
        "import_linter_contracts": contracts,
        "cli_commands": cli_commands,
        "mcp_tool_count": mcp_tools,
        "figure_ids": figures,
        "adrs": adr_files(root),
    }


def write_index(root: Path, *, cli: bool = True) -> Path:
    path = gate._state_dir(root) / INDEX_FILE
    gate.write_json_atomic(path, build_index(root, cli=cli))
    return path


# ---- feature plans (W4): a machine-checked front block in docs/superpowers/plans -----

_PLAN_BLOCK_RE = re.compile(r"^```json[ \t]*\n(.*?)\n```", re.S | re.M)


def plan_front_block(text: str) -> dict[str, Any] | None:
    """The first fenced ```json block of a plan doc as a dict; None if absent/invalid JSON."""
    match = _PLAN_BLOCK_RE.search(text)
    if match is None:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def plan_check(path: Path) -> tuple[bool, str]:
    """Validate a plan doc's front block against ``FeaturePlan`` (pydantic required)."""
    from harness_models import FeaturePlan
    from pydantic import ValidationError

    try:
        text = path.read_text()
    except OSError as exc:
        return (False, f"cannot read {path}: {exc}")
    block = plan_front_block(text)
    if block is None:
        return (False, f"{path.name}: no fenced ```json front block (or it is not a JSON object)")
    try:
        plan = FeaturePlan.model_validate(block)
    except ValidationError as exc:
        return (False, f"{path.name}: FeaturePlan invalid:\n{exc}")
    done = sum(1 for s in plan.slices if s.status == "done")
    return (
        True,
        f"{path.name}: FeaturePlan ok — {len(plan.slices)} slice(s), {done} done; "
        f"tier impact {', '.join(plan.tier_impact)}; "
        f"{len(plan.assumptions)} assumption(s), {len(plan.pre_mortem)} pre-mortem item(s)",
    )


def active_plan_scope(root: Path) -> tuple[str | None, list[str]]:
    """(open plan name, declared file scope) read WITHOUT pydantic so hooks can use it.

    Scope = the plan's ``files`` plus every slice's ``files``; empty when the open
    plan has no front block, so the over-eager warn is only armed by explicit scope.
    """
    name = open_plan(root)
    if name is None:
        return (None, [])
    block = plan_front_block((root / "docs" / "superpowers" / "plans" / name).read_text())
    if block is None:
        return (name, [])
    scope: list[str] = []
    slice_files = [f for sl in block.get("slices", []) for f in _slice_files(sl)]
    for item in [*block.get("files", []), *slice_files]:
        if isinstance(item, str) and item not in scope:
            scope.append(item)
    return (name, scope)


def _slice_files(sl: Any) -> list[Any]:
    return list(sl.get("files", [])) if isinstance(sl, dict) else []


def in_plan_scope(rel: str, scope: list[str]) -> bool:
    """A path is in scope when it equals, globs to, or lives under a declared entry."""
    from fnmatch import fnmatch

    return any(rel == p or fnmatch(rel, p) or rel.startswith(p.rstrip("/") + "/") for p in scope)
