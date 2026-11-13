#!/usr/bin/env python3
"""Hand a written plan or brief to Codex to build, then verify the result outside the sandbox.

    python3 scripts/handoff.py build  (--task docs/work/<task>/ | --brief FILE) [--class C]
                [--base REF] [--worktree DIR] [--check CMD]... [--fix-rounds N] [--no-sync]
    python3 scripts/handoff.py verify (--task ... | --brief FILE) --worktree DIR --built-by WHO
    python3 scripts/handoff.py review [--base REF] [--task DIR] [--built-by auto|codex|claude]
    python3 scripts/handoff.py status
    python3 scripts/handoff.py clean  [--base REF] [--discard] [--dry-run]

The rules it applies live in ``docs/reference/model-routing.md``. The orchestrating session runs
it OUTSIDE any sandbox: it prepares a git worktree (``uv sync --locked`` is the network step Codex
cannot do), runs ``codex exec`` there with the workspace-write sandbox, never-prompting approvals,
the user config ignored and a scrubbed environment, then checks the diff against policy (no
commits, no forbidden paths, scope) and runs ``gate.py check`` and the plan's checks itself. A
failed check is fed back to Codex (``codex exec resume``) for at most ``--fix-rounds`` rounds.
It never reports success unless its own verification passed. Codex's text is data: it is
sanitized before being printed. Every run writes a JSON build record and prints a summary of at
most 40 lines.

``verify`` runs the same policy and checks on a worktree a Claude builder changed (the fallback
route) and records it. ``review`` names the reviewer the routing rules require for a diff and, for
a Claude-built change, runs the Codex bridge review. ``status`` and ``clean`` look after the
worktrees this tool created, and nothing else.

Exit status: 0 passed; 1 internal error; 2 invalid input; 3 policy violation; 4 verification
failed with the fix budget spent; 10 Codex unavailable; 11 Codex usage limit; 12 Codex timed out;
13 Codex failed. 10-13 carry a ``fallback`` naming the Claude builder for the same prompt.
Stdlib only.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import fnmatch
import json
import os
import re
import signal
import subprocess
import sys
import time
import tomllib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codex_bridge  # sibling module: sanitize, probe, review
import gate  # sibling module: codex_probe, matches_quant
from harness_awareness import plan_front_block

SCHEMA_VERSION = 1
HOME_ENV = "ALPHA_HANDOFF_HOME"
RECORD_NAME = "03-build.json"
TASK_PLAN = "02-plan.md"
SUMMARY_MAX_LINES = 40
TAIL_CHARS = 4000
DEFAULT_BASE = "origin/main"
DEFAULT_FIX_ROUNDS = 2
DEFAULT_SCOPE_TOLERANCE = 2
GATE_TIMEOUT = 1800.0
CHECK_TIMEOUT = 900.0
SYNC_TIMEOUT = 900.0
CLASS_ORDER = ("small", "standard", "hard")
BRIEF_HEADINGS = ("Task", "Decision already made", "Files", "Do not touch", "Checks", "Report")


@dataclass(frozen=True)
class Profile:
    """How one task class is built: Codex model, reasoning effort, time caps, Claude fallback."""

    model: str
    effort: str
    timeout: float
    fix_timeout: float
    claude_fallback: str


# The mapping is set from calibration evidence (docs/reference/model-routing.md, "Task classes").
PROFILES: dict[str, Profile] = {
    "small": Profile("gpt-6.1-sol", "medium", 900.0, 600.0, "sonnet"),
    "standard": Profile("gpt-6.1-sol", "high", 1800.0, 900.0, "opus"),
    "hard": Profile("gpt-6-astra", "high", 3600.0, 1200.0, "opus"),
}

EXIT = {
    "passed": 0,
    "internal_error": 1,
    "invalid_input": 2,
    "policy_violation": 3,
    "verification_failed": 4,
    "codex_unavailable": 10,
    "codex_limit": 11,
    "codex_timeout": 12,
    "codex_failed": 13,
}
FALLBACK_VERDICTS = frozenset({"codex_unavailable", "codex_limit", "codex_timeout", "codex_failed"})

# Paths no builder may change, whatever the plan says.
NEVER_PATHS = (
    "tests/holdout/",
    ".git/",
    "scripts/codex_bridge.py",
    "scripts/claude_hooks.py",
    ".claude/settings.json",
    ".claude/settings.local.json",
)
_SECRET_FILE = re.compile(r"(^|/)(\.env(\.[^/]*)?|auth\.json|[^/]*\.pem|id_[a-z0-9]+|\.netrc)$")
# Paths a builder may change only when the plan lists them in ``files`` AND declares the tier.
GUARDED: tuple[tuple[str, str, str], ...] = (
    ("packages/alpha-research/src/", "quant", "hash-bound source bytes (quant tier)"),
    ("packages/alpha-validation/src/", "quant", "hash-bound source bytes (quant tier)"),
    ("apps/alpha-cli/src/alpha_cli/research_intake.py", "quant", "research implementation hash"),
    ("apps/alpha-cli/src/alpha_cli/research_runtime.py", "quant", "research implementation hash"),
    (
        "apps/alpha-cli/src/alpha_cli/research_crypto_data.py",
        "quant",
        "research implementation hash",
    ),
    (
        "apps/alpha-cli/src/alpha_cli/research_crypto_runtime.py",
        "quant",
        "research implementation hash",
    ),
    ("uv.lock", "protected", "research implementation hash; needs the network"),
    ("tests/oracles/", "quant", "protected test (oracles)"),
    ("tests/bias_guards/", "bias", "protected test (bias guards)"),
    ("tests/acceptance/", "protected", "visible acceptance tests"),
    ("CLAUDE.md", "protected", "protected file"),
    ("AGENTS.md", "protected", "protected file"),
    (".claude/", "protected", "protected file"),
    (".codex/", "protected", "protected file"),
    (".github/", "protected", "protected file"),
    (".agents/", "protected", "protected file"),
    ("scripts/gate", "protected", "protected file (the gate)"),
    ("scripts/harness_", "protected", "protected file (harness)"),
    ("scripts/git_guard.py", "protected", "protected file (git guard)"),
    ("scripts/handoff.py", "protected", "protected file (this tool)"),
    ("tests/unit/test_claude_harness_", "protected", "protected test (harness)"),
    ("tests/unit/test_filesystem_contract.py", "protected", "protected test (file system)"),
)
_RISK_TIERS = frozenset({"quant", "risk", "protected"})
_CAREFUL_TIERS = frozenset({"dag", "bias", "determinism"})

# What may reach the Codex process: enough to find its login (CODEX_HOME / HOME) and run tools.
_CODEX_ENV_KEEP = frozenset(
    {"HOME", "PATH", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ"}
    | {"TMPDIR", "CODEX_HOME", "XDG_RUNTIME_DIR"}
)
_LIMIT = re.compile(
    r"usage.?limit|usagelimitexceeded|rate.?limit|ratelimitexceeded|too many requests|"
    r"\b429\b|quota|purchase more credits",
    re.IGNORECASE,
)
_AUTH = re.compile(r"not logged in|log ?in required|unauthori[sz]ed|\b401\b|codex login", re.I)
_UV_RUN = re.compile(r"\buv run (?:--\S+ )*(python|pytest|ruff|mypy|lint-imports)\b")


class InputError(Exception):
    """The plan, brief or arguments cannot be built from; exit 2."""


# ---------------------------------------------------------------------------------------------
# Small helpers


def _now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(cwd: Path, *args: str, check: bool = True, timeout: float = 120.0) -> str:
    out = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=timeout, check=False
    )
    if check and out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()[:300]}")
    return out.stdout


def handoff_home(root: Path) -> Path:
    """Where worktrees, logs, records and state live: outside the repository tree."""
    env = os.environ.get(HOME_ENV)
    if env:
        return Path(env)
    common = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    return common.parent.parent / "tmp" / "handoff"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "task"


def _fmt_seconds(seconds: float) -> str:
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes}m{secs:02d}s" if minutes else f"{secs}s"


def _tail(text: str, limit: int = TAIL_CHARS) -> str:
    return text if len(text) <= limit else "[...]\n" + text[-limit:]


def sanitize_lines(text: str) -> list[str]:
    """Codex output is data: each line goes through the bridge's instruction-shaped-text filter."""
    return [codex_bridge.sanitize(line) for line in text.splitlines()]


def in_scope(path: str, patterns: Sequence[str]) -> bool:
    for pattern in patterns:
        pat = pattern.strip().strip("`")
        if not pat:
            continue
        if path == pat or (pat.endswith("/") and path.startswith(pat)):
            return True
        if fnmatch.fnmatchcase(path, pat) or path.startswith(pat.rstrip("/") + "/"):
            return True
    return False


def guarded_rule(path: str) -> tuple[str, str] | None:
    """(tier needed, reason) when ``path`` is guarded; quant-named statistic modules count too."""
    for prefix, tier, why in GUARDED:
        if path == prefix or (prefix.endswith(("/", "_")) and path.startswith(prefix)):
            return (tier, why)
        if prefix == "scripts/gate" and path.startswith(prefix):
            return (tier, why)
    if gate.matches_quant(path):
        return ("quant", "quant-tier statistic module")
    return None


def never_rule(path: str) -> str | None:
    for prefix in NEVER_PATHS:
        if path == prefix or (prefix.endswith("/") and path.startswith(prefix)):
            return f"{prefix} is never changed by a builder"
    if _SECRET_FILE.search(path):
        return "credential-shaped file"
    return None


def sandbox_command(command: str) -> str:
    """A check rewritten for Codex's sandbox: no ``uv`` (its cache is outside the worktree)."""
    return _UV_RUN.sub(lambda m: f".venv/bin/{m.group(1)}", command)


# ---------------------------------------------------------------------------------------------
# The work order: a plan (task route) or a brief (small route)


@dataclass
class WorkOrder:
    kind: str  # "task" | "brief"
    name: str
    source: str  # repo-relative plan path, or the brief's absolute path
    text: str
    files: list[str]
    do_not_touch: list[str]
    tiers: list[str]
    checks: list[str]
    read_first: list[str]
    declared_class: str | None
    task_dir: str | None = None
    notes: list[str] = field(default_factory=list)


def _sections(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1)
            out[current] = ""
        elif current is not None:
            out[current] += line + "\n"
    return out


def _backticked_bullets(body: str) -> list[str]:
    """The first ```code``` span of each bullet line."""
    found = []
    for line in body.splitlines():
        match = re.match(r"^\s*[-*]\s+`([^`]+)`", line)
        if match:
            found.append(match.group(1).strip())
    return found


_CLASS_LINE = re.compile(r"^\*\*Build class:\*\*\s*(small|standard|hard)\b", re.M)


def _read_first_targets(text: str, doc_dir: Path, root: Path) -> list[str]:
    body = _sections(text).get("Read first", "")
    rows = []
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in ("Read", "") or set(cells[0]) <= {"-"}:
            continue
        link = re.search(r"\]\(([^)\s]+)\)", cells[0])
        target = link.group(1) if link else cells[0].strip("`")
        path, _, anchor = target.partition("#")
        resolved = (doc_dir / path).resolve()
        try:
            rel = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = path
        section = cells[1] if cells[1] not in ("—", "-", "") else "whole file"
        rows.append(f"`{rel}` — {section}" + (f" (#{anchor})" if anchor else "") + f"; {cells[2]}")
    return rows


def plan_check(plan: Path) -> tuple[bool, str]:
    """``gate.py plan-check`` in a child process (it needs pydantic; this tool is stdlib-only)."""
    out = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "gate.py"), "plan-check", str(plan)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return (out.returncode == 0, (out.stdout + out.stderr).strip())


def load_task(root: Path, task: str) -> WorkOrder:
    task_dir = Path(task)
    if task_dir.is_absolute():
        try:
            task_dir = task_dir.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise InputError(f"{task} is not inside {root}") from exc
    rel = task_dir.as_posix().rstrip("/")
    plan = root / rel / TASK_PLAN
    if not plan.is_file():
        raise InputError(
            f"{rel}/{TASK_PLAN} is not in the build tree; commit the approved plan to the base "
            "ref (or pass the worktree that has it) before building"
        )
    ok, message = plan_check(plan)
    if not ok:
        raise InputError(f"plan-check failed: {message[-600:]}")
    text = plan.read_text(encoding="utf-8")
    block = plan_front_block(text) or {}
    slices = [s for s in block.get("slices", []) if isinstance(s, dict)]
    files = [str(f) for f in block.get("files", [])]
    for item in slices:
        files += [str(f) for f in item.get("files", []) if str(f) not in files]
    if not files:
        raise InputError(f"{rel}/{TASK_PLAN} lists no files in scope (FeaturePlan 'files')")
    checks = [str(s["verify"]) for s in slices if s.get("status") != "done" and s.get("verify")]
    declared = _CLASS_LINE.search(text)
    return WorkOrder(
        kind="task",
        name=Path(rel).name,
        source=f"{rel}/{TASK_PLAN}",
        text=text,
        files=files,
        do_not_touch=[],
        tiers=[str(t) for t in block.get("tier_impact", []) if t != "none"],
        checks=checks,
        read_first=_read_first_targets(text, plan.parent, root),
        declared_class=declared.group(1) if declared else None,
        task_dir=rel,
    )


def load_brief(root: Path, brief: Path) -> WorkOrder:
    try:
        text = brief.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read brief {brief}: {exc}") from exc
    sections = _sections(text)
    missing = [h for h in BRIEF_HEADINGS if h not in sections]
    if missing:
        raise InputError(f"brief {brief.name} lacks headings: {', '.join(missing)}")
    files = _backticked_bullets(sections["Files"])
    if not files:
        raise InputError(f"brief {brief.name}: '## Files' lists no `path` bullets")
    checks = _backticked_bullets(sections["Checks"])
    if not checks:
        raise InputError(f"brief {brief.name}: '## Checks' lists no `command` bullets")
    declared = _CLASS_LINE.search(text)
    return WorkOrder(
        kind="brief",
        name=_slug(brief.name.removesuffix(".md").removesuffix(".brief")),
        source=str(brief.resolve()),
        text=text,
        files=files,
        do_not_touch=_backticked_bullets(sections["Do not touch"]),
        tiers=[],
        checks=checks,
        read_first=_read_first_targets(text, root, root),
        declared_class=declared.group(1) if declared else None,
    )


def classify(order: WorkOrder) -> tuple[str, str]:
    """The class the objective criteria give (routing file, "Task classes"), and why."""
    tiers = set(order.tiers)
    guarded = sorted({rule[0] for f in order.files if (rule := guarded_rule(f))})
    if tiers & _RISK_TIERS or set(guarded) & _RISK_TIERS:
        return ("hard", f"tier {', '.join(sorted((tiers | set(guarded)) & _RISK_TIERS))}")
    if len(order.files) > 8:
        return ("hard", f"{len(order.files)} files in scope (> 8)")
    if tiers & _CAREFUL_TIERS:
        return ("standard", f"tier {', '.join(sorted(tiers & _CAREFUL_TIERS))}")
    if len(order.files) > 3:
        return ("standard", f"{len(order.files)} files in scope (> 3)")
    return ("small", f"{len(order.files)} file(s) in scope, no risk tier")


def effective_class(order: WorkOrder, requested: str | None) -> tuple[str, str]:
    """Never below the objective class: a request or a plan line may only raise it."""
    computed, why = classify(order)
    chosen = computed
    for candidate in (order.declared_class, requested):
        if candidate and CLASS_ORDER.index(candidate) > CLASS_ORDER.index(chosen):
            chosen = candidate
    if requested and CLASS_ORDER.index(requested) < CLASS_ORDER.index(computed):
        why += f"; requested {requested} ignored (below the objective class)"
    if chosen != computed:
        why += f"; raised to {chosen} by the plan or --class"
    return (chosen, why)


def workspace_contexts(root: Path, files: Sequence[str]) -> list[str]:
    found: list[str] = []
    for item in files:
        plain = re.split(r"[*?\[]", item, maxsplit=1)[0].rstrip("/")
        path = Path(plain)
        for parent in [path, *path.parents]:
            if parent == Path("."):
                break
            candidate = parent / "CONTEXT.md"
            if (root / candidate).is_file():
                if candidate.as_posix() not in found:
                    found.append(candidate.as_posix())
                break
    return found


# ---------------------------------------------------------------------------------------------
# The prompt


def _forbidden_lines(order: WorkOrder) -> list[str]:
    lines = [f"- `{p}` (never)" for p in NEVER_PATHS]
    for prefix, tier, why in GUARDED:
        allowed = tier in order.tiers and any(
            f == prefix or f.startswith(prefix) for f in order.files
        )
        if not allowed:
            lines.append(f"- `{prefix}` ({why})")
    lines.append("- any quant-named statistic module (dsr, pbo, bootstrap, cpcv, ...) not in Files")
    lines += [f"- `{p}` (this task's Do not touch)" for p in order.do_not_touch]
    return lines


def compose_prompt(root: Path, order: WorkOrder) -> str:
    contexts = workspace_contexts(root, order.files)
    read = [*order.read_first, *(f"`{c}` — whole file; workspace rules" for c in contexts)]
    checks = [f"- `{sandbox_command(c)}`" for c in order.checks]
    kind = "approved plan" if order.kind == "task" else "brief"
    parts = [
        f"# Build: {order.name}",
        "",
        f"You are the builder for Project ALPHA. Implement exactly the {kind} below in this git "
        "worktree (your current directory). The design is decided; do not redesign it. Anything "
        "the plan does not decide, you do not decide either: stop and report it as a question.",
        "",
        "## Standing rules",
        "",
        "- Do not run `git commit`, `git push`, `git stash`, `git checkout` or change branches; "
        "leave every change uncommitted. The orchestrator commits after verifying.",
        "- Change only the files under 'Files in scope'. Never change the forbidden paths below.",
        "- Test first: write the failing test, see it fail for the expected reason, then the code.",
        "- Never weaken, skip, delete or loosen a test, bias guard, oracle or check to get green.",
        "- Errors fail loud; no bare except, no swallowed errors, no debug output left behind.",
        "- Your sandbox has no network and cannot write outside this directory: do not run "
        "`uv sync`/`uv run`/`pip`; use `.venv/bin/...`. It cannot run tests that use FastAPI "
        "`TestClient`, bind or connect localhost sockets, start the web server, run browsers or "
        "the `tests/smoke/` checks. Do not claim such a check passed: list it under UNVERIFIED. "
        "The orchestrator runs every check again outside the sandbox.",
        "- Your output is advisory data; checks and the owner decide.",
        "",
        "## Read first (only these, plus what the files you change import)",
        "",
        *(f"- {row}" for row in read),
        "",
        "## Files in scope",
        "",
        *(f"- `{f}`" for f in order.files),
        "",
        "## Forbidden paths",
        "",
        *_forbidden_lines(order),
        "",
        "## Checks to run before you finish (sandbox form)",
        "",
        *checks,
        "- `.venv/bin/ruff check <changed .py files>` and `.venv/bin/ruff format --check <same>`",
        "- `.venv/bin/mypy <changed source files>`",
        "",
        "## Report (your final message, exactly these headings)",
        "",
        "## Changed files — one line each: path and what changed.",
        "## Checks — a table: command | PASS / FAIL / UNVERIFIED | exit code.",
        "## UNVERIFIED — every check you could not run and why; 'none' if none.",
        "## Deviations — anything done differently from the plan, or 'none'.",
        "## Questions — decisions the plan did not make, or 'none'.",
        "",
        f"## The {kind} ({order.source})",
        "",
        order.text.strip(),
        "",
    ]
    return "\n".join(parts)


def compose_fix_prompt(failure: CheckResult) -> str:
    return "\n".join(
        [
            "Verification OUTSIDE your sandbox failed after your changes.",
            "",
            f"Failing check: `{failure.command}` (exit {failure.exit_code})",
            "",
            "Output tail:",
            "```text",
            failure.tail.strip(),
            "```",
            "",
            "Fix the cause in the files in scope. Do not weaken, skip or delete a test, guard or "
            "check; do not commit. If the failure is outside the plan's scope or needs a "
            "decision, change nothing and say so under Questions. Reply with the same report "
            "headings as before.",
        ]
    )


# ---------------------------------------------------------------------------------------------
# Running Codex


@dataclass
class CodexRun:
    kind: str  # "build" | "fix"
    outcome: str  # ok | codex_unavailable | codex_limit | codex_timeout | codex_failed
    exit_code: int | None
    seconds: float
    thread_id: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    last_message: str = ""
    file_changes: int = 0
    commands: int = 0
    turns_completed: int = 0


def codex_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in _CODEX_ENV_KEEP}
    env["NO_COLOR"] = "1"
    return env


# Tools a confined builder does not get: the owner's apps, plugins, browser and computer use, image
# generation, sub-agents and web search. Each name is in `codex features list` (0.167.0); a name a
# later CLI drops makes the run fail visibly (codex_failed), never silently widen.
CODEX_DISABLED_FEATURES = (
    "apps",
    "plugins",
    "remote_plugin",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "image_generation",
    "multi_agent",
)


def project_mcp_servers(worktree: Path) -> list[str]:
    """MCP server names a trusted project layer (``.codex/config.toml``) would start."""
    try:
        data = tomllib.loads((worktree / ".codex" / "config.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    servers = data.get("mcp_servers")
    return sorted(str(k) for k in servers) if isinstance(servers, dict) else []


def codex_args(profile: Profile, worktree: Path, last: Path, resume: str | None) -> list[str]:
    confine: list[str] = ["-c", 'web_search="disabled"']
    for feature in CODEX_DISABLED_FEATURES:
        confine += ["--disable", feature]
    for name in project_mcp_servers(worktree):
        # MCP servers run outside the sandbox; neutralise each (a bare enabled=false is invalid).
        confine += ["-c", f'mcp_servers.{name}={{command="true", enabled=false}}']
    common = [
        *confine,
        "--ignore-user-config",
        "--json",
        "-m",
        profile.model,
        "-c",
        f'model_reasoning_effort="{profile.effort}"',
        "-c",
        'approval_policy="never"',
        "-c",
        'shell_environment_policy.inherit="core"',
        "-o",
        str(last),
    ]
    if resume:
        # `exec resume` has no -s/-C: the sandbox is set by config and the directory by cwd.
        return ["codex", "exec", "resume", *common, "-c", 'sandbox_mode="workspace-write"', resume]
    return [
        "codex",
        "exec",
        *common,
        "-s",
        "workspace-write",
        "-C",
        str(worktree),
        "--color",
        "never",
    ]


def _parse_events(path: Path, run: CodexRun) -> None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "thread.started" and isinstance(event.get("thread_id"), str):
            run.thread_id = event["thread_id"]
        elif kind == "turn.completed":
            run.turns_completed += 1
            usage = event.get("usage")
            for key, value in (usage if isinstance(usage, dict) else {}).items():
                if isinstance(value, int):
                    run.usage[key] = run.usage.get(key, 0) + value
        elif kind == "error":
            run.errors.append(str(event.get("message", "")))
        elif kind == "turn.failed":
            error = event.get("error")
            run.errors.append(str(error.get("message", "")) if isinstance(error, dict) else "")
            run.errors.append("turn.failed")
        elif kind == "item.completed" and isinstance(event.get("item"), dict):
            item_type = event["item"].get("type")
            run.file_changes += item_type == "file_change"
            run.commands += item_type == "command_execution"


def _stop(proc: subprocess.Popen[str]) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, sig)
        try:
            proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue


def run_codex(
    kind: str,
    profile: Profile,
    worktree: Path,
    prompt: str,
    log_dir: Path,
    timeout: float,
    resume: str | None = None,
) -> CodexRun:
    index = len(list(log_dir.glob("*.events.jsonl")))
    tag = f"{index:02d}-{kind}"
    events, stderr, last = (log_dir / f"{tag}.{s}" for s in ("events.jsonl", "stderr.txt", "md"))
    cmd = [*codex_args(profile, worktree, last, resume), "-"]
    start = time.monotonic()
    timed_out = False
    try:
        with events.open("w") as out, stderr.open("w") as err:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                cwd=worktree,
                env=codex_env(),
                text=True,
                start_new_session=True,
            )
            try:
                proc.communicate(prompt, timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _stop(proc)
    except OSError as exc:
        return CodexRun(kind, "codex_unavailable", None, 0.0, errors=[f"cannot start codex: {exc}"])
    run = CodexRun(kind, "ok", proc.returncode, time.monotonic() - start)
    _parse_events(events, run)
    with contextlib.suppress(OSError):
        run.last_message = last.read_text(encoding="utf-8", errors="replace")
    err_text = stderr.read_text(encoding="utf-8", errors="replace")[-2000:]
    signals = "\n".join(run.errors) + ("\n" + err_text if proc.returncode else "")
    if timed_out:
        run.outcome = "codex_timeout"
        run.errors.append(f"exceeded the {int(timeout)}s cap")
    elif proc.returncode == 0 and "turn.failed" not in run.errors and run.turns_completed:
        run.outcome = "ok"
    elif _LIMIT.search(signals):
        run.outcome = "codex_limit"
    elif _AUTH.search(signals):
        run.outcome = "codex_unavailable"
    else:
        run.outcome = "codex_failed"
        if not run.errors:
            run.errors.append(f"exit {proc.returncode}: {err_text.strip()[-300:]}")
    return run


# ---------------------------------------------------------------------------------------------
# Verification outside the sandbox


@dataclass
class CheckResult:
    name: str
    command: str
    exit_code: int
    seconds: float
    round: int
    tail: str = ""

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


def run_check(name: str, command: str, cwd: Path, timeout: float, round_no: int) -> CheckResult:
    """``bash -c command`` in ``cwd``; on timeout the whole process group is stopped (exit 124)."""
    start = time.monotonic()
    proc = subprocess.Popen(
        ["bash", "-c", command],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        text, _ = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        _stop(proc)
        text, code = f"[timed out after {int(timeout)}s]", 124
    return CheckResult(name, command, code, time.monotonic() - start, round_no, _tail(text or ""))


def changed_paths(worktree: Path, base_sha: str) -> list[tuple[str, str]]:
    """(status, path) of every change against the base: commits, worktree edits, untracked."""
    merge_base = _git(worktree, "merge-base", base_sha, "HEAD").strip()
    found: dict[str, str] = {}
    for line in _git(worktree, "diff", "--name-status", "--no-renames", merge_base).splitlines():
        status, _, path = line.partition("\t")
        if path:
            found[path] = status[:1]
    others = _git(worktree, "ls-files", "--others", "--exclude-standard", "-z")
    for path in filter(None, others.split("\0")):
        found.setdefault(path, "A")
    return sorted((status, path) for path, status in found.items())


_IGNORED_NOISE = (".venv/", "node_modules/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/")


def ignored_paths(worktree: Path) -> set[str]:
    """Git-ignored paths (directories collapsed): a builder's write there never shows in a diff."""
    out = _git(worktree, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory")
    return {p for p in out.splitlines() if p and not _noise(p)}


def _noise(path: str) -> bool:
    return path.startswith(_IGNORED_NOISE) or "__pycache__/" in path or path.endswith(".pyc")


def new_ignored_files(worktree: Path, before: set[str]) -> list[str]:
    """Ignored files created since ``before`` was taken, new directories expanded to files."""
    found: list[str] = []
    for entry in sorted(ignored_paths(worktree) - before):
        if not entry.endswith("/"):
            found.append(entry)
            continue
        listed = _git(worktree, "ls-files", "--others", "--ignored", "--exclude-standard", entry)
        found += [p for p in listed.splitlines() if p and not p.startswith(_IGNORED_NOISE)] or [
            entry
        ]
    return found


def policy_problems(
    order: WorkOrder,
    paths: Sequence[tuple[str, str]],
    tolerance: int,
    ignore: Sequence[str],
) -> tuple[list[str], list[str]]:
    """(violations, outside-scope paths within tolerance)."""
    problems, extras = [], []
    for _, path in paths:
        if path in ignore:
            continue
        never = never_rule(path)
        if never:
            problems.append(f"{path}: {never}")
            continue
        if in_scope(path, order.do_not_touch):
            problems.append(f"{path}: listed under Do not touch")
            continue
        rule = guarded_rule(path)
        if rule and not (in_scope(path, order.files) and rule[0] in order.tiers):
            problems.append(f"{path}: {rule[1]}; needs the path in files and tier {rule[0]}")
            continue
        if not in_scope(path, order.files):
            extras.append(path)
    if len(extras) > tolerance:
        problems.append(
            f"{len(extras)} files outside the declared scope (tolerance {tolerance}): "
            + ", ".join(extras[:8])
        )
    return problems, extras


# ---------------------------------------------------------------------------------------------
# State, locks and records


@contextlib.contextmanager
def _flock(path: Path, *, blocking: bool = True) -> Iterator[TextIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        fcntl.flock(handle.fileno(), flags)
        yield handle
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _state_path(home: Path) -> Path:
    return home / "state.json"


def read_state(home: Path) -> dict[str, Any]:
    data = gate.read_json(_state_path(home)) or {}
    builds = data.get("builds")
    return {"builds": builds if isinstance(builds, dict) else {}}


def update_state(home: Path, run_id: str, **fields: Any) -> None:
    with _flock(home / "state.lock"):
        state = read_state(home)
        state["builds"].setdefault(run_id, {}).update(fields)
        tmp = _state_path(home).with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
        tmp.replace(_state_path(home))


def worktree_lock(home: Path, worktree: Path) -> Path:
    """The lock a build holds on its worktree for its whole run (clean takes it too)."""
    return home / "locks" / f"{_slug(str(worktree))}.lock"


def _pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass
class Build:
    run_id: str
    order: WorkOrder
    cls: str
    class_reason: str
    profile: Profile
    base: str
    base_sha: str
    worktree: Path
    branch: str
    log_dir: Path
    built_by: dict[str, str]
    started_at: str = field(default_factory=_now)
    start: float = field(default_factory=time.monotonic)
    runs: list[CodexRun] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    policy: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)
    files: list[tuple[str, str]] = field(default_factory=list)
    diffstat: str = ""
    verdict: str = "internal_error"
    fallback: dict[str, str] | None = None
    notes: list[str] = field(default_factory=list)
    start_head: str = ""
    ignored_at_start: set[str] = field(default_factory=set)
    previous: list[dict[str, Any]] = field(default_factory=list)

    def record_path_in_tree(self) -> Path | None:
        if self.order.task_dir is None:
            return None
        return self.worktree / self.order.task_dir / RECORD_NAME

    def record(self) -> dict[str, Any]:
        tokens: dict[str, int] = {}
        for run in self.runs:
            for key, value in run.usage.items():
                tokens[key] = tokens.get(key, 0) + value
        last = self.runs[-1].last_message if self.runs else ""
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "work_order": {"kind": self.order.kind, "name": self.order.name},
            "source": self.order.source,
            "class": self.cls,
            "class_reason": self.class_reason,
            "built_by": self.built_by,
            "base": self.base,
            "base_sha": self.base_sha,
            "worktree": str(self.worktree),
            "branch": self.branch,
            "started_at": self.started_at,
            "finished_at": _now(),
            "wall_seconds": round(time.monotonic() - self.start, 1),
            "tokens": tokens,
            "rounds": [
                {
                    "kind": r.kind,
                    "outcome": r.outcome,
                    "exit_code": r.exit_code,
                    "seconds": round(r.seconds, 1),
                    "thread_id": r.thread_id,
                    "usage": r.usage,
                    "errors": [codex_bridge.sanitize(e)[:300] for e in r.errors if e],
                    "file_changes": r.file_changes,
                    "commands": r.commands,
                }
                for r in self.runs
            ],
            "fix_rounds": sum(1 for r in self.runs if r.kind == "fix"),
            "files_changed": [{"status": s, "path": p} for s, p in self.files],
            "outside_scope": self.extras,
            "diffstat": self.diffstat,
            "policy_violations": self.policy,
            "checks": [
                {
                    "name": c.name,
                    "command": c.command,
                    "exit_code": c.exit_code,
                    "seconds": round(c.seconds, 1),
                    "passed": c.passed,
                    "round": c.round,
                }
                for c in self.checks
            ],
            "unverified": unverified_items(last),
            "verdict": self.verdict,
            "fallback": self.fallback,
            "notes": self.notes,
            "logs": str(self.log_dir),
            "previous_attempts": self.previous,
        }


def unverified_items(report: str) -> list[str]:
    """Lines under the builder's '## UNVERIFIED' heading, sanitized; [] for 'none'."""
    body = _sections(report).get("UNVERIFIED", "")
    lines = [ln.strip(" -*\t") for ln in sanitize_lines(body)]
    items = [ln for ln in lines if ln and ln.lower().rstrip(".") != "none"]
    return [item[:200] for item in items]


_ATTEMPT_KEYS = (
    "run_id",
    "built_by",
    "verdict",
    "fallback",
    "tokens",
    "wall_seconds",
    "fix_rounds",
)


def earlier_attempts(home: Path, worktree: Path, run_id: str) -> list[dict[str, Any]]:
    """The latest earlier record on this worktree, condensed, with its own earlier attempts."""
    for path in sorted((home / "records").glob("*.json"), reverse=True):
        data = gate.read_json(path) or {}
        if data.get("worktree") == str(worktree) and data.get("run_id") != run_id:
            prior = data.get("previous_attempts")
            older = prior if isinstance(prior, list) else []
            return [*older, {k: data.get(k) for k in _ATTEMPT_KEYS}]
    return []


def write_record(build: Build, home: Path) -> Path:
    build.previous = earlier_attempts(home, build.worktree, build.run_id)
    record = build.record()
    records = home / "records"
    records.mkdir(parents=True, exist_ok=True)
    path = records / f"{build.run_id}.json"
    body = json.dumps(record, indent=2, sort_keys=True) + "\n"
    path.write_text(body)
    in_tree = build.record_path_in_tree()
    if in_tree is not None and in_tree.parent.is_dir():
        in_tree.write_text(body)
        return in_tree
    return path


# ---------------------------------------------------------------------------------------------
# The summary


def summary(build: Build, record_path: Path) -> str:
    rec = build.record()
    tok = rec["tokens"]
    who = build.built_by
    lines = [
        f"handoff {build.run_id}: {build.verdict.upper()}",
        f"Built by: {who.get('tool')} {who.get('model', '')} effort {who.get('effort', '-')}"
        f" (class {build.cls}: {build.class_reason})",
        f"Worktree: {build.worktree} (branch {build.branch}; base {build.base} @ "
        f"{build.base_sha[:12]})",
        f"Time: {_fmt_seconds(rec['wall_seconds'])}; rounds: {len(build.runs)} codex "
        f"({rec['fix_rounds']} fix); tokens in {tok.get('input_tokens', 0):,} "
        f"(cached {tok.get('cached_input_tokens', 0):,}), out {tok.get('output_tokens', 0):,}",
    ]
    stat = [ln for ln in build.diffstat.splitlines() if ln.strip()]
    lines.append(f"Files changed: {len(build.files)}")
    lines += [f"  {ln.strip()}" for ln in stat[:10]]
    if len(stat) > 10:
        lines.append(f"  ... {len(stat) - 10} more")
    if build.extras:
        lines.append(f"Outside declared scope (within tolerance): {', '.join(build.extras[:5])}")
    lines.append("Checks (run outside the sandbox by this tool):")
    if not build.checks:
        lines.append("  none run")
    for check in build.checks[-8:]:
        mark = "PASS" if check.passed else f"FAIL({check.exit_code})"
        lines.append(
            f"  {mark:<9} {_fmt_seconds(check.seconds):>7}  r{check.round}  {check.command[:90]}"
        )
    lines.append("Policy: " + ("ok" if not build.policy else "VIOLATED"))
    lines += [f"  {p[:150]}" for p in build.policy[:4]]
    unverified = rec["unverified"]
    lines.append("Unverified (builder's report): " + ("none" if not unverified else ""))
    lines += [f"  {u[:150]}" for u in unverified[:5]]
    if build.fallback:
        lines.append(
            f"Fallback: {build.fallback['builder']} {build.fallback['model']} — "
            f"{build.fallback['reason'][:110]}"
        )
    lines.append(f"Next: {next_action(build)}")
    lines.append(f"Record: {record_path}")
    lines.append(f"Logs: {build.log_dir}")
    if len(lines) > SUMMARY_MAX_LINES:
        lines = [*lines[: SUMMARY_MAX_LINES - 1], "[summary truncated; see the record]"]
    return "\n".join(lines)


def next_action(build: Build) -> str:
    wt = build.worktree
    if build.verdict == "passed":
        return (
            f"review (`handoff.py review --base {build.base}` in {wt}), then commit on "
            f"{build.branch} and open the pull request"
        )
    if build.verdict == "policy_violation":
        return f"do not commit; inspect `git -C {wt} status`; discard: `handoff.py clean --discard`"
    if build.verdict == "verification_failed":
        return (
            "fix budget spent: read the failing check's log; fix by hand or re-run with "
            f"--worktree {wt}"
        )
    if build.fallback:
        return (
            f"give {build.log_dir / 'prompt.md'} to a Claude {build.fallback['model']} builder "
            f"in {wt}, then `handoff.py verify --worktree {wt} --built-by "
            f"claude:{build.fallback['model']}` with the same --task/--brief"
        )
    return "see the record"


# ---------------------------------------------------------------------------------------------
# build / verify


def _load_order(root: Path, args: argparse.Namespace) -> WorkOrder:
    if bool(args.task) == bool(args.brief):
        raise InputError("give exactly one of --task or --brief")
    return load_task(root, args.task) if args.task else load_brief(root, Path(args.brief))


def prepare_worktree(
    root: Path, home: Path, name: str, base_sha: str, given: str | None
) -> tuple[Path, str, bool]:
    if given:
        wt = Path(given).resolve()
        if not (wt / ".git").exists():
            raise InputError(f"{wt} is not a git worktree")
        branch = _git(wt, "rev-parse", "--abbrev-ref", "HEAD").strip()
        return wt, branch, False
    wt = home / "wt" / name
    branch = f"build/{name}"
    if wt.exists():
        raise InputError(f"{wt} exists; pass --worktree {wt} to build there again")
    if _git(root, "branch", "--list", branch).strip():
        raise InputError(f"branch {branch} exists; pass --worktree or delete it")
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "worktree", "add", "-q", "-b", branch, str(wt), base_sha, timeout=900.0)
    return wt, branch, True


def _verify_round(build: Build, args: argparse.Namespace, round_no: int, ignore: list[str]) -> bool:
    wt = build.worktree
    head_branch = _git(wt, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if head_branch != build.branch:
        build.policy.append(f"the worktree moved from branch {build.branch} to {head_branch}")
    if build.built_by.get("tool") == "codex":
        head = _git(wt, "rev-parse", "HEAD").strip()
        if head != build.start_head:
            build.policy.append("the builder committed (HEAD moved); Codex never commits")
    build.files = changed_paths(wt, build.base_sha)
    problems, build.extras = policy_problems(build.order, build.files, args.scope_tolerance, ignore)
    build.policy += problems
    for path in new_ignored_files(wt, build.ignored_at_start):
        # Ignored files never reach a commit; only the never rules (credentials, holdout) apply.
        rule = never_rule(path)
        if rule:
            build.policy.append(f"{path} (git-ignored): {rule}")
    merge_base = _git(wt, "merge-base", build.base_sha, "HEAD").strip()
    build.diffstat = _git(wt, "diff", "--stat=120", merge_base, check=False)
    if build.policy:
        return False
    if not build.files:
        build.notes.append("no files changed")
        return False
    commands = [("gate check", f"uv run python scripts/gate.py check --base {build.base}")]
    commands += [(f"check {i + 1}", c) for i, c in enumerate([*build.order.checks, *args.check])]
    ok = True
    for name, command in commands:
        timeout = GATE_TIMEOUT if name == "gate check" else CHECK_TIMEOUT
        result = run_check(name, command, wt, timeout, round_no)
        (build.log_dir / f"check-r{round_no}-{_slug(name)}.log").write_text(result.tail)
        build.checks.append(result)
        if not result.passed:
            ok = False
            break  # the first failure is what the fix round gets
    return ok


def cmd_build(args: argparse.Namespace, root: Path, *, codex: bool) -> int:
    home = handoff_home(root)
    try:
        order = _load_order(root if not args.worktree else Path(args.worktree), args)
    except InputError as exc:
        print(f"handoff: invalid input: {exc}", file=sys.stderr)
        return EXIT["invalid_input"]
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S-%f")
    run_id = f"{order.name}-{stamp}"
    try:
        base_sha = _git(root, "rev-parse", "--verify", f"{args.base}^{{commit}}").strip()
        wt, branch, created = prepare_worktree(root, home, order.name, base_sha, args.worktree)
        if order.kind == "task" and created:
            # Build, classify and check against the plan as the worktree has it.
            order = load_task(wt, order.source.rsplit("/", 1)[0])
    except (InputError, RuntimeError) as exc:
        print(f"handoff: invalid input: {exc}", file=sys.stderr)
        return EXIT["invalid_input"]
    cls, reason = effective_class(order, args.cls)
    profile = PROFILES[cls]
    log_dir = home / "logs" / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    if codex:
        built_by = {"tool": "codex", "model": profile.model, "effort": profile.effort}
    else:
        tool, _, model = str(args.built_by).partition(":")
        built_by = {"tool": tool or "claude", "model": model or "unknown", "effort": "-"}
    build = Build(
        run_id, order, cls, reason, profile, args.base, base_sha, wt, branch, log_dir, built_by
    )
    lock = worktree_lock(home, wt)
    try:
        with _flock(lock, blocking=False):
            update_state(
                home,
                run_id,
                worktree=str(wt),
                branch=branch,
                created_worktree=created,
                pid=os.getpid(),
                status="running",
                started_at=build.started_at,
                kind="build" if codex else "verify",
            )
            try:
                _run(build, args, root, codex=codex)
            finally:
                record_path = write_record(build, home)
                update_state(
                    home,
                    run_id,
                    status="finished",
                    verdict=build.verdict,
                    record=str(home / "records" / f"{run_id}.json"),
                    pid=None,
                    finished_at=_now(),
                )
    except BlockingIOError:
        print(f"handoff: a build is already running in {wt}", file=sys.stderr)
        return EXIT["invalid_input"]
    text = summary(build, record_path)
    (log_dir / "summary.txt").write_text(text + "\n")
    print(text)
    return EXIT.get(build.verdict, 1)


def _run(build: Build, args: argparse.Namespace, root: Path, *, codex: bool) -> None:
    wt = build.worktree
    prompt = compose_prompt(wt, build.order)
    (build.log_dir / "prompt.md").write_text(prompt)
    in_tree = build.record_path_in_tree()
    ignore = [in_tree.relative_to(wt).as_posix()] if in_tree else []
    build.start_head = _git(wt, "rev-parse", "HEAD").strip()
    build.ignored_at_start = ignored_paths(wt)
    if not codex:
        build.verdict = (
            "passed"
            if _verify_round(build, args, 0, ignore)
            else ("policy_violation" if build.policy else "verification_failed")
        )
        return
    ok, detail = gate.codex_probe()
    probe = codex_bridge.probe(build.profile.model) if ok else {"available": False}
    if not ok or not probe.get("available"):
        _fallback(build, "codex_unavailable", detail if not ok else str(probe.get("reason")))
        return
    if not args.no_sync:
        sync = run_check("uv sync", "uv sync --locked", wt, SYNC_TIMEOUT, 0)
        build.checks.append(sync)
        if not sync.passed:
            build.notes.append("uv sync --locked failed in the worktree; nothing was built")
            build.verdict = "internal_error"
            return
    run = run_codex("build", build.profile, wt, prompt, build.log_dir, build.profile.timeout)
    build.runs.append(run)
    if run.outcome != "ok":
        _fallback(build, run.outcome, "; ".join(e for e in run.errors if e)[:300])
        return
    for round_no in range(0, args.fix_rounds + 1):
        if _verify_round(build, args, round_no, ignore):
            build.verdict = "passed"
            return
        if build.policy:
            build.verdict = "policy_violation"
            return
        failed = [c for c in build.checks if c.round == round_no and not c.passed]
        if not failed or round_no == args.fix_rounds:
            build.verdict = "verification_failed"
            return
        fix = compose_fix_prompt(failed[-1])
        if run.thread_id:
            run = run_codex(
                "fix",
                build.profile,
                wt,
                fix,
                build.log_dir,
                build.profile.fix_timeout,
                resume=run.thread_id,
            )
        else:
            run = run_codex(
                "fix",
                build.profile,
                wt,
                prompt + "\n\n" + fix,
                build.log_dir,
                build.profile.fix_timeout,
            )
        build.runs.append(run)
        if run.outcome != "ok":
            _fallback(build, run.outcome, "; ".join(e for e in run.errors if e)[:300])
            return
    build.verdict = "verification_failed"


def _fallback(build: Build, verdict: str, reason: str) -> None:
    build.verdict = verdict
    build.fallback = {
        "builder": "claude",
        "model": build.profile.claude_fallback,
        "reason": f"{verdict}: {codex_bridge.sanitize(reason) or 'no detail'}",
        "prompt": str(build.log_dir / "prompt.md"),
    }


# ---------------------------------------------------------------------------------------------
# review


def _diff_against(root: Path, base: str) -> tuple[list[str], str]:
    merge_base = _git(root, "merge-base", base, "HEAD").strip()
    paths = [p for _, p in changed_paths(root, merge_base)]
    diff = _git(root, "diff", merge_base)
    for path in _git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if path:
            diff += _git(root, "diff", "--no-index", "/dev/null", path, check=False)
    return paths, diff


def review_route(
    paths: Sequence[str], tiers: Sequence[str], built_by: str, base: str = DEFAULT_BASE
) -> list[str]:
    """The reviewers the routing rules require (docs/reference/model-routing.md, Review)."""
    found = set(tiers)
    for path in paths:
        rule = guarded_rule(path)
        if rule:
            found.add(rule[0])
    steps = [f"machine: `uv run python scripts/gate.py check --base {base}`, then CI on the PR"]
    if "quant" in found:
        steps.append("agent `quant-verifier` (model opus): every formula against its source")
    if found & _RISK_TIERS or "bias" in found:
        steps.append("agent `reviewer` (model opus): risk, protected, bias or quant diff")
    elif built_by == "codex":
        steps.append(
            "agent `reviewer` with model sonnet (Agent tool `model: sonnet`): "
            "ordinary Codex-built diff"
        )
    if built_by != "codex":
        steps.append("Codex review via the bridge (below): the writer is never the only reviewer")
    return steps


def _built_by(root: Path, home: Path, branch: str) -> str:
    for record in sorted((home / "records").glob("*.json"), reverse=True):
        data = gate.read_json(record) or {}
        if data.get("branch") == branch and data.get("verdict") == "passed":
            built = data.get("built_by") or {}
            return str(built.get("tool", "claude"))
    return "claude"


def cmd_review(args: argparse.Namespace, root: Path) -> int:
    home = handoff_home(root)
    paths, diff = _diff_against(root, args.base)
    tiers: list[str] = []
    if args.task:
        try:
            tiers = load_task(root, args.task).tiers
        except InputError as exc:
            print(f"handoff: invalid input: {exc}", file=sys.stderr)
            return EXIT["invalid_input"]
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    built_by = args.built_by if args.built_by != "auto" else _built_by(root, home, branch)
    steps = review_route(paths, tiers, built_by, args.base)
    print(
        f"Diff vs {args.base}: {len(paths)} file(s); built by {built_by}; plan tiers: "
        f"{', '.join(tiers) or 'none given'}"
    )
    print("Required review (docs/reference/model-routing.md):")
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")
    if built_by == "codex" or args.no_codex:
        return 0
    model = codex_bridge.resolve_model(args.model)
    result = codex_bridge.review(root, diff=diff, model=model, effort=args.effort)
    out = home / "reviews"
    out.mkdir(parents=True, exist_ok=True)
    saved = out / f"{_slug(branch)}-{dt.datetime.now(dt.UTC):%Y%m%d-%H%M%S}.json"
    saved.write_text(json.dumps(result, indent=2, sort_keys=True))
    if not result.get("available"):
        print(
            f"Codex review unavailable ({result.get('unavailable_reason')}): use agent "
            "`reviewer` (model opus) instead."
        )
        return 0
    findings = result.get("findings", [])
    print(f"Codex review ({model}, effort {args.effort}): {len(findings)} finding(s); {saved}")
    for item in findings[:15]:
        where = f"{item['file']}:{item['line']}" if item.get("line") else item["file"]
        print(f"  [{item['severity']}] {where} — {str(item['summary'])[:200]}")
    print(f"Summary: {str(result.get('summary', ''))[:300]}")
    print("Dispose of each finding (fix, or reject with a reason) in 04-verify.md or the PR.")
    return 0


# ---------------------------------------------------------------------------------------------
# status / clean


def _limit_seen(home: Path) -> str:
    for record in sorted((home / "records").glob("*.json"), reverse=True):
        data = gate.read_json(record) or {}
        if data.get("verdict") == "codex_limit":
            return f"{data.get('finished_at')} in {data.get('run_id')}"
    return "none recorded"


def cmd_status(args: argparse.Namespace, root: Path) -> int:
    home = handoff_home(root)
    ok, detail = gate.codex_probe()
    print(f"Codex: {'available' if ok else 'UNAVAILABLE'} — {detail}")
    if ok:
        for cls in CLASS_ORDER:
            prof = PROFILES[cls]
            probe = codex_bridge.probe(prof.model)
            state = "ok" if probe.get("available") else str(probe.get("reason"))
            print(
                f"  {cls:<8} {prof.model} effort {prof.effort}, cap "
                f"{_fmt_seconds(prof.timeout)}: {state}"
            )
    print(
        f"  last usage limit hit: {_limit_seen(home)} (Codex shows no remaining-allowance "
        "figure to this tool)"
    )
    print(
        "Claude: limits are not visible here; on a Claude limit queue more for Codex "
        "(docs/reference/model-routing.md, Limits and fallback)."
    )
    builds = read_state(home)["builds"]
    running = {k: v for k, v in builds.items() if v.get("status") == "running"}
    print(f"In flight: {len(running)}")
    for run_id, entry in sorted(running.items()):
        alive = "alive" if _pid_alive(entry.get("pid")) else "DEAD (interrupted)"
        print(f"  {run_id}: {entry.get('worktree')} [{alive}]")
    finished = {k: v for k, v in builds.items() if v.get("status") == "finished"}
    print(f"Finished worktrees kept: {len(finished)} (`handoff.py clean` removes merged ones)")
    for run_id, entry in sorted(finished.items())[-10:]:
        exists = "" if Path(str(entry.get("worktree"))).exists() else " (gone)"
        print(f"  {run_id}: {entry.get('verdict')} {entry.get('worktree')}{exists}")
    return 0


def cmd_clean(args: argparse.Namespace, root: Path) -> int:
    home = handoff_home(root)
    with _flock(home / "state.lock"):
        builds = read_state(home)["builds"]
    removed = 0
    seen_worktrees: set[str] = set()
    for run_id, entry in sorted(builds.items()):
        wt = Path(str(entry.get("worktree")))
        if entry.get("status") != "finished" or not entry.get("created_worktree"):
            continue
        if str(wt) in seen_worktrees or any(
            e.get("status") == "running" and e.get("worktree") == str(wt) for e in builds.values()
        ):
            continue
        seen_worktrees.add(str(wt))
        branch = str(entry.get("branch"))
        if not wt.exists():
            action = "forget (worktree already gone)"
        else:
            dirty = bool(_git(wt, "status", "--porcelain", check=False).strip())
            merged = (
                subprocess.run(
                    ["git", "-C", str(root), "merge-base", "--is-ancestor", branch, args.base],
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            )
            if (dirty or not merged) and not args.discard:
                print(
                    f"keep   {run_id}: {'uncommitted changes' if dirty else 'branch not merged'}"
                    f" ({wt}); --discard removes it"
                )
                continue
            action = "remove" + (" (discarding)" if dirty or not merged else "")
        print(f"{action}: {run_id} {wt}")
        if args.dry_run:
            continue
        try:
            with _flock(worktree_lock(home, wt), blocking=False):
                if wt.exists():
                    force = ["--force"] if args.discard else []
                    _git(root, "worktree", "remove", *force, str(wt))
                if _git(root, "branch", "--list", branch).strip():
                    _git(root, "branch", "-D" if args.discard else "-d", branch, check=False)
        except BlockingIOError:
            print(f"keep   {run_id}: a build is running in {wt} now")
            continue
        removed += 1
        with _flock(home / "state.lock"):
            state = read_state(home)
            for key, value in list(state["builds"].items()):
                if value.get("worktree") == str(wt) and value.get("status") == "finished":
                    del state["builds"][key]
            _state_path(home).write_text(json.dumps(state, indent=2, sort_keys=True))
    print(f"cleaned {removed} worktree(s)" + (" (dry run)" if args.dry_run else ""))
    return 0


# ---------------------------------------------------------------------------------------------
# CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="handoff", description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", help="repository root (default: the one holding the cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--task", help="docs/work/<task>/ holding an approved 02-plan.md")
        p.add_argument("--brief", help="small-route brief file with the required headings")
        p.add_argument("--class", dest="cls", choices=CLASS_ORDER, help="raise the task class")
        p.add_argument("--base", default=DEFAULT_BASE)
        p.add_argument("--worktree", required=name == "verify")
        p.add_argument("--check", action="append", default=[], help="extra check command")
        p.add_argument("--scope-tolerance", type=int, default=DEFAULT_SCOPE_TOLERANCE)
        if name == "build":
            p.add_argument("--fix-rounds", type=int, default=DEFAULT_FIX_ROUNDS)
            p.add_argument("--no-sync", action="store_true", help="skip uv sync --locked")
        else:
            p.add_argument("--built-by", required=True, help="who built, e.g. claude:sonnet")
    r = sub.add_parser("review")
    r.add_argument("--base", default=DEFAULT_BASE)
    r.add_argument("--task", help="the task folder, to read its tier_impact")
    r.add_argument("--built-by", default="auto", choices=("auto", "codex", "claude"))
    r.add_argument("--no-codex", action="store_true", help="print the route only")
    r.add_argument("--model")
    r.add_argument("--effort", default=codex_bridge.DEFAULT_EFFORT)
    sub.add_parser("status")
    c = sub.add_parser("clean")
    c.add_argument("--base", default=DEFAULT_BASE)
    c.add_argument("--discard", action="store_true", help="also remove unmerged or dirty ones")
    c.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = Path(args.repo).resolve() if args.repo else gate.repo_root()
        if args.command == "build":
            return cmd_build(args, root, codex=True)
        if args.command == "verify":
            return cmd_build(args, root, codex=False)
        if args.command == "review":
            return cmd_review(args, root)
        if args.command == "status":
            return cmd_status(args, root)
        return cmd_clean(args, root)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"handoff: internal error: {exc}", file=sys.stderr)
        return EXIT["internal_error"]


if __name__ == "__main__":
    raise SystemExit(main())
