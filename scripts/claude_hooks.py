"""Claude Code hook entrypoints for the Project ALPHA harness.

Stdlib-only hooks wired in .claude/settings.json, all dispatching through
``main(<name>)`` with the hook payload on stdin:

    post-edit           PostToolUse (Edit|Write|MultiEdit) record every edit + per-file lint
    post-bash           PostToolUse (Bash)          record shell writes as edits
    post-tool-failure   PostToolUseFailure          record failures for the Stop brief
    pre-edit-guard      PreToolUse  (Edit|Write)    control-plane ack; hidden holdout deny
    pre-read-guard      PreToolUse  (Read)          hidden holdout deny (author never sees it)
    pre-bash-guard      PreToolUse  (Bash)          commit/push gate, destructive verbs, writes
    pre-mcp-guard       PreToolUse  (mcp__alpha|codex) owner-authority verbs deny; codex log
    tool-log            PostToolUse (Agent|Skill)   audit subagent/skill dispatch
    subagent-stop       SubagentStop                JSON-only agents must emit valid schema
    task-completed      TaskCompleted               tests named in the task must pass
    config-change       ConfigChange                audited; ack/owner required
    instructions-loaded InstructionsLoaded          awareness telemetry
    stop-guard          Stop                        fast stamp + quant attestation; budget
    session-start       SessionStart                doctor + brief + Karpathy block
    prompt-context      UserPromptSubmit            per-turn situational brief
    pre-compact         PreCompact                  compaction guidance
    post-compact        PostCompact                 re-inject brief + Karpathy + obligations

Exit 2 blocks (stderr is fed back to Claude); every block message names its
escape hatch. ``ALPHA_HARNESS_DISABLE=1`` bypasses everything. The repo root
is derived from the payload cwd via git (worktree-correct), never from
``$CLAUDE_PROJECT_DIR`` which resolves to the main checkout in worktrees.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import gate

COMMIT_RE = re.compile(
    r"^(feat|fix|test|build|chore|docs|refactor|ci|style|data)"
    r"(\([a-z0-9_.\-/]+\))?(!)?: \S.*"
)
# Docs waiver: docs/**, *.md, .agents/skills/**/*.md. `.claude/**` and `.codex/**`
# are CONTROL PLANE and never waived (audit finding A1).
_NEVER_WAIVED_PREFIXES = (".claude/", ".codex/")
_SOURCE_PREFIXES = ("packages/", "apps/", "tests/", "scripts/")
_FRONTEND_PREFIX = "apps/alpha-web/frontend/src/"
STOP_BLOCK_BUDGET = 3
SUBAGENT_BLOCK_BUDGET = 2
CONFIG_ACK_WINDOW_SECONDS = 600
_SCRATCH_PREFIXES = ("/private/tmp/claude-", "/tmp/claude-", "/tmp/")

# JSON-only subagents and the harness_models schema their last message must satisfy.
JSON_AGENT_SCHEMAS = {
    "independent-reviewer": "ReviewVerdict",
    "quant-verifier": "QuantVerificationReport",
    "invariants-auditor": "InvariantFindings",
    "docs-drift-checker": "DriftFindings",
    "red-team-code": "Counterexamples",
    "codex-liaison": "CodexReview|CodexResearch",  # either, per the request kind
}
# Sandboxed subagents: every Bash segment must start with one of these token prefixes.
# Tokens match exactly, except a path-like last token (contains "/") matches by startswith so
# files under it are allowed. Hook payloads carry `agent_type` inside a subagent; the main
# session (no agent_type) is unaffected.
_GIT_READ_ONLY = tuple(
    ("git", sub)
    for sub in ("diff", "log", "show", "status", "grep", "blame", "ls-files", "rev-parse")
)


def _py(*args: str) -> tuple[tuple[str, ...], ...]:
    """Both launcher spellings of a python invocation."""
    return (("python3", *args), ("uv", "run", "python", *args))


_PY_INLINE = _py("-c")
_READ_ONLY_TOOLS = (
    ("grep",),
    ("rg",),
    ("ls",),
    ("cat",),
    ("head",),
    ("tail",),
    ("wc",),
    ("find",),
    ("uv", "run", "pytest"),
    *_PY_INLINE,
    *(
        p
        for sub in ("audit", "check", "brief", "index", "semgrep", "raise-cov")
        for p in _py("scripts/gate.py", sub)
    ),
)
_NUMERIC_TOOLS = (("uv", "run", "pytest", "tests/oracles"), *_PY_INLINE)
AGENT_BASH_ALLOW: dict[str, tuple[tuple[str, ...], ...]] = {
    "quant-verifier": (*_NUMERIC_TOOLS, *_py("scripts/codex_bridge.py", "research")),
    "numerical-verifier": _NUMERIC_TOOLS,
    "codex-liaison": _py("scripts/codex_bridge.py"),
    "independent-reviewer": (*_GIT_READ_ONLY, *_READ_ONLY_TOOLS),
    "invariants-auditor": (*_GIT_READ_ONLY, *_READ_ONLY_TOOLS),
    "docs-drift-checker": (*_GIT_READ_ONLY, *_READ_ONLY_TOOLS),
    "red-team-code": (*_GIT_READ_ONLY, *_READ_ONLY_TOOLS),
    "retrospective": (*_GIT_READ_ONLY, *_READ_ONLY_TOOLS),
}
# MCP tool-name fragments that are owner authority; denied by name, defense in depth.
_MCP_OWNER_VERBS = re.compile(
    r"(approve|reject|decide|override_research_gate|reveal_holdout|research_decision)"
)

KARPATHY_BLOCK = """KARPATHY GUIDELINES (always on — .agents/skills/karpathy-guidelines):
1. Think Before Coding — Don't assume. Don't hide confusion. Surface tradeoffs.
   State assumptions explicitly; present competing interpretations instead of
   picking silently; say so when a simpler approach exists; stop and ask when unclear.
2. Simplicity First — Minimum code that solves the problem. Nothing speculative.
   No unrequested features, abstractions for single-use code, configurability, or
   error handling for impossible scenarios. 200 lines that could be 50? Rewrite.
3. Surgical Changes — Touch only what you must. Clean up only your own mess.
   No "improving" adjacent code/comments/formatting; match existing style; remove
   only orphans YOUR change created. Every changed line traces to the request.
4. Goal-Driven Execution — Define success criteria. Loop until verified.
   "Add validation" -> "write tests for invalid inputs, make them pass"; multi-step
   work states `step -> verify: check`; UNVERIFIED: is the only honest substitute
   for a check you could not run — never "should work"."""

HookResult = tuple[int, str]
LintRunner = Callable[[Path], str | None]


# ---------------------------------------------------------------------------
# command parsing


def _split_top_level(command: str) -> list[str]:
    """Split on unquoted &&, ||, ;, |, & and newlines — quoted operators stay put."""
    chunks: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    i = 0
    while i < len(command):
        ch = command[i]
        if escaped:
            current.append(ch)
            escaped = False
        elif ch == "\\" and quote != "'":
            current.append(ch)
            escaped = True
        elif quote is not None:
            current.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            current.append(ch)
        elif ch in ";|\n&":
            chunks.append("".join(current))
            current = []
            if command.startswith(("&&", "||"), i):
                i += 1
        else:
            current.append(ch)
        i += 1
    chunks.append("".join(current))
    return chunks


def extract_commands(command: str) -> list[list[str]]:
    """Split a shell command into per-command token lists (quote-aware)."""
    segments: list[list[str]] = []
    for chunk in _split_top_level(command):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            tokens = shlex.split(chunk)
        except ValueError:
            tokens = chunk.split()
        if tokens:
            segments.append(tokens)
    return segments


_GIT_GLOBAL_OPTS_WITH_ARG = ("-C", "-c", "--git-dir", "--work-tree", "--namespace")


def _git_subcommand(tokens: list[str]) -> str | None:
    """The git SUBCOMMAND of a token list, or None if this is not a git call."""
    if not tokens or Path(tokens[0]).name != "git":
        return None
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in _GIT_GLOBAL_OPTS_WITH_ARG:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token
    return None


def _is_git_commit(tokens: list[str]) -> bool:
    """True iff the git SUBCOMMAND is commit (never 'commit' as an argument)."""
    return _git_subcommand(tokens) == "commit"


def contains_git_commit(command: str) -> bool:
    return any(_is_git_commit(tokens) for tokens in extract_commands(command))


_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?\n(.*?)\n\1", re.DOTALL)


def _unwrap_heredoc(message: str) -> str:
    """`-m "$(cat <<'EOF' ... EOF)"` → the heredoc body (first line judged)."""
    if message.lstrip().startswith("$(") and "<<" in message:
        found = _HEREDOC_RE.search(message)
        if found:
            return found.group(2)
    return message


def commit_message_of(command: str) -> str | None:
    """The commit subject, or None when undeterminable (-F/--file, no -m)."""
    for tokens in extract_commands(command):
        if not _is_git_commit(tokens):
            continue
        for i, token in enumerate(tokens):
            if token in ("-m", "--message") and i + 1 < len(tokens):
                return _unwrap_heredoc(tokens[i + 1])
            if token.startswith("--message="):
                return _unwrap_heredoc(token.split("=", 1)[1])
            if re.fullmatch(r"-[a-zA-Z]*m", token) and i + 1 < len(tokens):
                return _unwrap_heredoc(tokens[i + 1])  # -am / -qm / -sm
            if token.startswith("-m") and len(token) > 2 and not token.startswith("--"):
                return _unwrap_heredoc(token[2:])
    return None


def is_docs_path(path: str) -> bool:
    if path.startswith(_NEVER_WAIVED_PREFIXES):
        return False
    return path.startswith("docs/") or path.endswith(".md")


def docs_only(paths: list[str]) -> bool:
    if not paths:
        return False
    return all(is_docs_path(p) for p in paths)


def _has_short_flag(tokens: list[str], letter: str) -> bool:
    return any(re.fullmatch(r"-[a-zA-Z]+", t) and letter in t[1:] for t in tokens)


def destructive_reason(tokens: list[str], root: Path, cwd: Path) -> str | None:
    """Commands the agent must not run (audit A3/A4); the owner runs them by hand."""
    if not tokens:
        return None
    sub = _git_subcommand(tokens)
    if sub == "commit":
        if "--amend" in tokens:
            return "git commit --amend rewrites history"
        if "--no-verify" in tokens or _has_short_flag(tokens[1:], "n"):
            return "git commit --no-verify skips repository hooks"
        return None
    if sub == "reset" and "--hard" in tokens:
        return "git reset --hard discards working changes"
    if sub in ("checkout", "restore"):
        rest = [t for t in tokens[tokens.index(sub) + 1 :] if not t.startswith("-")]
        if rest and rest[0] == "." or ("--" in tokens and rest == ["."]):
            return f"git {sub} . discards all working changes"
        return None
    if sub == "clean" and any(_has_short_flag([t], "f") or t == "--force" for t in tokens):
        return "git clean -f deletes untracked files"
    if sub == "stash" and any(t in ("drop", "clear") for t in tokens):
        return "git stash drop/clear destroys stashed work"
    if sub == "push" and any(t in ("--force", "-f", "--force-with-lease") for t in tokens):
        return "force push"
    name = Path(tokens[0]).name
    if name == "rm" and (_has_short_flag(tokens, "r") or _has_short_flag(tokens, "R")):
        targets = [t for t in tokens[1:] if not t.startswith("-")]
        for target in targets:
            resolved = (cwd / target).resolve() if not target.startswith("/") else Path(target)
            if not str(resolved).startswith(_SCRATCH_PREFIXES):
                return f"recursive rm outside the scratchpad ({target})"
        return None
    if name == "chmod" and any("x" in t and not t.startswith("-") for t in tokens[1:2]):
        for target in tokens[2:]:
            rel = _rel_path_from(root, cwd, target)
            if rel and gate.protected_reason(rel):
                return f"chmod on control-plane file {rel}"
    return None


def _rel_path_from(root: Path, cwd: Path, target: str) -> str | None:
    if target.startswith("-") or not target:
        return None
    try:
        path = Path(target) if target.startswith("/") else cwd / target
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return None


_PY_OPEN_WRITE_RE = re.compile(r"""open\(\s*['"]([^'"]+)['"]\s*,\s*['"][wax]""")
_PATHLIB_WRITE_RE = re.compile(r"""Path\(\s*['"]([^'"]+)['"]\s*\)\.write_(?:text|bytes)""")


def bash_write_targets(command: str, root: Path, cwd: Path) -> list[str]:
    """Repo-relative files a shell command writes (audit A5).

    Detects redirection, ``tee``, ``sed -i``, ``mv``/``cp`` destinations,
    ``ruff format``/``--fix``, and inline Python ``open(..., 'w')`` /
    ``Path(...).write_*``. Heuristic by design: it records what it can see so
    the Stop guard and attestations know the file changed; it never claims to
    be exhaustive.
    """
    targets: set[str] = set()

    def add(raw: str) -> None:
        if raw in ("/dev/null", "&1", "&2") or raw.startswith("&"):
            return
        rel = _rel_path_from(root, cwd, raw)
        if rel is not None:
            targets.add(rel)

    for tokens in extract_commands(command):
        name = Path(tokens[0]).name
        for i, token in enumerate(tokens):
            stripped = token.lstrip("012")
            if stripped in (">", ">>", "&>") and i + 1 < len(tokens):
                add(tokens[i + 1])
            elif re.match(r"^[012]?>{1,2}\S", token):
                add(re.sub(r"^[012]?>{1,2}", "", token))
        args = [t for t in tokens[1:] if not t.startswith("-")]
        if name == "tee":
            for arg in args:
                add(arg)
        elif name == "sed" and any(t.startswith("-i") for t in tokens):
            sed_args = [a for a in args if a]  # drop the empty `-i ''` suffix
            for arg in sed_args[1:] if "-e" not in tokens else sed_args:
                add(arg)
        elif name in ("mv", "cp") and len(args) >= 2:
            add(args[-1])
        elif "ruff" in tokens:
            if "format" in tokens and "--check" not in tokens:
                for arg in tokens[tokens.index("format") + 1 :]:
                    if not arg.startswith("-"):
                        add(arg)
            elif "--fix" in tokens:
                for arg in args:
                    if arg not in ("run", "ruff", "check"):
                        add(arg)
    for match in _PY_OPEN_WRITE_RE.finditer(command):
        add(match.group(1))
    for match in _PATHLIB_WRITE_RE.finditer(command):
        add(match.group(1))
    return sorted(targets)


# ---------------------------------------------------------------------------
# session state


def _session_file(root: Path, session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")
    return root / gate.STATE_DIR / f"session-{safe}.json"


_SESSION_DEFAULTS: dict[str, Any] = {
    "edited_files": [],
    "bash_writes": [],
    "failures": [],
    "instructions_loaded": [],
    "stop_blocks_used": 0,
    "stop_budget_exhausted": False,
    "codex_calls": 0,
    "over_eager": [],
}


def load_session(root: Path, session_id: str) -> dict[str, Any]:
    state = gate.read_json(_session_file(root, session_id)) or {"session_id": session_id}
    for key, default in _SESSION_DEFAULTS.items():
        state.setdefault(key, json.loads(json.dumps(default)))
    return state


def _save_session(root: Path, state: dict[str, Any]) -> None:
    (root / gate.STATE_DIR).mkdir(parents=True, exist_ok=True)
    gate.write_json_atomic(_session_file(root, str(state["session_id"])), state)


def record_edit(root: Path, session_id: str, rel_path: str, *, via_bash: bool = False) -> None:
    state = load_session(root, session_id)
    if rel_path not in state["edited_files"]:
        state["edited_files"].append(rel_path)
    if via_bash and rel_path not in state["bash_writes"]:
        state["bash_writes"].append(rel_path)
    if _over_eager(root, rel_path) and rel_path not in state["over_eager"]:
        # W4 scope declaration: warn-only, audited; the retrospective counts them.
        state["over_eager"].append(rel_path)
        gate.append_audit(root, "over_eager_edit", rel_path, session_id)
    _save_session(root, state)


def _over_eager(root: Path, rel_path: str) -> bool:
    """A source edit outside the open plan's declared ``files`` scope (if it declares one)."""
    if not _is_source_edit(rel_path):
        return False
    _, scope = gate.active_plan_scope(root)
    return bool(scope) and not gate.in_plan_scope(rel_path, scope)


def _record_stop_block(root: Path, session_id: str) -> int:
    state = load_session(root, session_id)
    state["stop_blocks_used"] = int(state.get("stop_blocks_used", 0)) + 1
    _save_session(root, state)
    return int(state["stop_blocks_used"])


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# helpers


def _rel_path(root: Path, file_path: str) -> str | None:
    try:
        return Path(file_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _payload_cwd(payload: dict[str, Any], root: Path) -> Path:
    raw = payload.get("cwd")
    return Path(str(raw)) if raw else root


def _tool_input_text(tool_input: dict[str, Any]) -> str:
    """All string values in tool_input, flattened — robust to Edit/Write schema drift."""
    parts: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(tool_input)
    return "\n".join(parts)


def _staged_paths(root: Path, use_working: bool) -> list[str]:
    paths = gate._git_lines(root, "diff", "--cached", "--name-only")
    if use_working:
        paths.extend(p for p in gate._git_lines(root, "diff", "--name-only") if p not in paths)
    return paths


def _staged_line_count(root: Path, use_working: bool) -> int:
    total = 0
    for cached in [True, False] if use_working else [True]:
        args = ["diff", "--numstat", "--cached"] if cached else ["diff", "--numstat"]
        for line in gate._git_lines(root, *args):
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            if is_docs_path(fields[2]):
                continue
            for count in fields[:2]:
                if count.isdigit():
                    total += int(count)
    return total


def _is_lintable_python(rel: str) -> bool:
    return rel.endswith(".py") and rel.startswith(_SOURCE_PREFIXES)


def _is_source_edit(rel: str) -> bool:
    """Counts toward "source edits" at Stop: anything not under the docs waiver."""
    return not is_docs_path(rel)


def _default_lint(root: Path) -> LintRunner:
    def run(path: Path) -> str | None:
        rel = path.relative_to(root).as_posix()
        if rel.endswith((".ts", ".tsx")) and rel.startswith(_FRONTEND_PREFIX):
            frontend = root / "apps" / "alpha-web" / "frontend"
            if not (frontend / "node_modules").is_dir():
                return None  # graceful skip: frontend toolchain not installed
            result = subprocess.run(
                ["npx", "eslint", "--no-warn-ignored", str(path)],
                capture_output=True,
                text=True,
                check=False,
                cwd=frontend,
                timeout=60,
            )
            return None if result.returncode == 0 else (result.stdout + result.stderr).strip()
        ruff = root / ".venv" / "bin" / "ruff"
        if not ruff.is_file():
            return None  # graceful skip: venv not synced yet
        for args in (["check"], ["format", "--check"]):
            result = subprocess.run(
                [str(ruff), *args, str(path)],
                capture_output=True,
                text=True,
                check=False,
                cwd=root,
                timeout=60,
            )
            if result.returncode != 0:
                return (result.stdout + result.stderr).strip()
        return None

    return run


def _venv_python(root: Path) -> Path | None:
    candidate = root / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else None


def validate_against_schema(root: Path, schema: str, text: str) -> str | None:
    """Validate JSON text against a harness_models schema in the project venv.

    Returns None on success, an error string on failure, and None (skip) when
    the venv is unavailable — hooks are stdlib-only and must fail open there.
    """
    python = _venv_python(root)
    if python is None:
        return None
    body = text.strip()
    if "```" in body:
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", body, re.DOTALL)
        if fenced:
            body = fenced.group(1)
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return "no JSON object found in the final message"
    body = body[start : end + 1]
    code = (
        "import json,sys; from harness_models import "
        f"{schema} as M; M.model_validate(json.loads(sys.stdin.read()))"
    )
    result = subprocess.run(
        [str(python), "-c", code],
        input=body,
        capture_output=True,
        text=True,
        cwd=root / "scripts",
        check=False,
        timeout=60,
    )
    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout).strip()[-1500:]


# ---------------------------------------------------------------------------
# hooks: PostToolUse


def hook_post_edit(
    payload: dict[str, Any], root: Path, *, run_lint: LintRunner | None = None
) -> HookResult:
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path", ""))
    rel = _rel_path(root, file_path) if file_path else None
    if rel is None:
        return (0, "")
    record_edit(root, str(payload.get("session_id", "")), rel)  # A13: every edit counts
    lintable = _is_lintable_python(rel) or (
        rel.endswith((".ts", ".tsx")) and rel.startswith(_FRONTEND_PREFIX)
    )
    if not lintable:
        return (0, "")
    lint = run_lint or _default_lint(root)
    try:
        failure = lint(root / rel)
    except (OSError, subprocess.SubprocessError):
        return (0, "")  # lint tooling failure must never block editing
    if failure:
        return (2, f"Lint failed for {rel} — fix before continuing:\n{failure[-3000:]}")
    return (0, "")


def hook_post_bash(payload: dict[str, Any], root: Path) -> HookResult:
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command", ""))
    targets = bash_write_targets(command, root, _payload_cwd(payload, root))
    session_id = str(payload.get("session_id", ""))
    for rel in targets:
        record_edit(root, session_id, rel, via_bash=True)
    return (0, "")


def hook_post_tool_failure(payload: dict[str, Any], root: Path) -> HookResult:
    session_id = str(payload.get("session_id", ""))
    state = load_session(root, session_id)
    state["failures"].append(
        {
            "tool": str(payload.get("tool_name", "")),
            "error": str(payload.get("error", ""))[:300],
            "ts": _now(),
        }
    )
    state["failures"] = state["failures"][-50:]
    _save_session(root, state)
    return (0, "")


def hook_tool_log(payload: dict[str, Any], root: Path) -> HookResult:
    tool_input = payload.get("tool_input") or {}
    tool = str(payload.get("tool_name", ""))
    what = str(tool_input.get("subagent_type") or tool_input.get("skill") or "")
    desc = str(tool_input.get("description") or tool_input.get("args") or "")[:120]
    gate.append_audit(
        root, "dispatch", f"{tool}:{what} {desc}".strip(), str(payload.get("session_id", ""))
    )
    return (0, "")


# ---------------------------------------------------------------------------
# hooks: PreToolUse


# git subcommands that may name tests/holdout/ without rendering file content
_GIT_HOLDOUT_SAFE = frozenset(
    {"mv", "add", "rm", "status", "ls-files", "commit", "restore", "checkout", "reset"}
)


def _holdout_block(rel: str, verb: str) -> HookResult:
    return (
        2,
        f"BLOCKED: {rel} is a HIDDEN HOLDOUT test (tests/holdout/). The authoring "
        f"agent may not {verb} it — the full gate and CI run it, and the "
        "independent-reviewer reads its results. Owner access: export "
        f"{gate.OWNER_TOKEN_ENV}.",
    )


def hook_pre_edit_guard(payload: dict[str, Any], root: Path) -> HookResult:
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path", ""))
    rel = _rel_path(root, file_path) if file_path else None
    if rel is None:
        return (0, "")
    if gate.is_hidden_holdout(rel) and not gate.owner_present(root):
        return _holdout_block(rel, "edit")
    reason = gate.protected_reason(rel, _tool_input_text(tool_input))
    if reason is None:
        return (0, "")
    if gate.owner_present(root):
        gate.append_audit(root, "protected_edit_owner", rel, authorized_by="owner")
        return (0, "")
    if gate.consume_ack(root, path=rel) is not None:
        return (0, "")
    return (
        2,
        f"BLOCKED: {reason}. Control-plane files need a one-shot governance ack:\n"
        f'  uv run python scripts/gate.py ack --reason "<why this change is needed>"'
        f" [--path {rel}]\n"
        "(the ack is appended to the audit journal for owner review), then retry the edit.",
    )


def hook_pre_read_guard(payload: dict[str, Any], root: Path) -> HookResult:
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path", ""))
    rel = _rel_path(root, file_path) if file_path else None
    if rel is None or not gate.is_hidden_holdout(rel):
        return (0, "")
    if gate.owner_present(root) or payload.get("agent_type") == "independent-reviewer":
        return (0, "")
    return _holdout_block(rel, "read")


def _push_present(command: str) -> bool:
    return any(_git_subcommand(t) == "push" for t in extract_commands(command))


def _prefix_matches(tokens: list[str], prefix: tuple[str, ...]) -> bool:
    if len(tokens) < len(prefix):
        return False
    head, last = prefix[:-1], prefix[-1]
    tail_ok = tokens[len(head)].startswith(last) if "/" in last else tokens[len(head)] == last
    return tokens[: len(head)] == list(head) and tail_ok


def agent_bash_violation(agent_type: str, command: str, segments: list[list[str]]) -> str | None:
    """Reason a sandboxed subagent may not run `command`, or None when every segment is allowed."""
    allowed = AGENT_BASH_ALLOW.get(agent_type)
    if allowed is None:
        return None
    if any(marker in command for marker in (">", "$(", "`")):
        return "redirections and command substitution are not allowed in a sandboxed agent"
    for tokens in segments:
        if not any(_prefix_matches(tokens, prefix) for prefix in allowed):
            return f"`{' '.join(tokens[:4])}` is outside the {agent_type} sandbox"
    return None


def hook_pre_bash_guard(payload: dict[str, Any], root: Path) -> HookResult:
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command", ""))
    cwd = _payload_cwd(payload, root)
    segments = extract_commands(command)

    agent_type = str(payload.get("agent_type", ""))
    violation = agent_bash_violation(agent_type, command, segments)
    if violation:
        allowed_list = ", ".join(" ".join(p) for p in AGENT_BASH_ALLOW[agent_type])
        return (2, f"BLOCKED: {violation}. Allowed prefixes: {allowed_list}")

    for tokens in segments:
        reason = destructive_reason(tokens, root, cwd)
        if reason:
            return (
                2,
                f"BLOCKED: {reason}. Destructive/side-channel commands are not run by the "
                "agent; the owner runs them by hand (ALPHA_HARNESS_DISABLE=1 is the audited "
                "emergency bypass).",
            )
        if not any(t in ("pytest", "git", "gate.py") or t.endswith("gate.py") for t in tokens):
            for token in tokens:
                rel = _rel_path_from(root, cwd, token)
                if rel and gate.is_hidden_holdout(rel) and not gate.owner_present(root):
                    return _holdout_block(rel, "read or modify via Bash")
        elif "git" in tokens and not gate.owner_present(root):
            # git may move/stage/commit holdout files but never print their content
            # (show/diff/log -p/blame/grep/cat-file all render bytes the author must not see)
            sub = next((t for t in tokens[tokens.index("git") + 1 :] if not t.startswith("-")), "")
            if sub not in _GIT_HOLDOUT_SAFE and any(
                "tests/holdout/" in t or t.endswith("tests/holdout") for t in tokens
            ):
                return _holdout_block("tests/holdout/", f"read via `git {sub}`")

    # A5: shell writes into control-plane / holdout paths follow the Edit policy.
    for rel in bash_write_targets(command, root, cwd):
        if gate.is_hidden_holdout(rel) and not gate.owner_present(root):
            return _holdout_block(rel, "write via Bash")
        reason = gate.protected_reason(rel)
        if reason and not gate.owner_present(root) and gate.consume_ack(root, path=rel) is None:
            return (
                2,
                f"BLOCKED: shell write to {rel} — {reason}. Arm an ack first:\n"
                f'  uv run python scripts/gate.py ack --reason "..." --path {rel}',
            )

    is_commit = contains_git_commit(command)
    is_push = _push_present(command)
    if not is_commit and not is_push:
        return (0, "")
    if gate.consume_override(root) is not None:
        return (0, "")

    if is_push and not is_commit:
        if gate.stamp_is_valid(root, "full"):
            return (0, "")
        return (
            2,
            "BLOCKED: git push requires a full-tier gate stamp for the current tree "
            "(the pushed head must have passed the gate). Run\n"
            "  uv run python scripts/gate.py full\n"
            "Emergency escape (loudly audited):\n"
            '  uv run python scripts/gate.py override --reason "..."',
        )

    tokens = next(t for t in segments if _is_git_commit(t))
    use_working = any(t in ("-a", "--all") or _has_short_flag([t], "a") for t in tokens[1:])
    paths = _staged_paths(root, use_working)
    waived = docs_only(paths)

    if paths and not waived and not gate.stamp_is_valid(root, "full"):
        return (
            2,
            "BLOCKED: no full-tier gate stamp for the current tree. Run\n"
            "  uv run python scripts/gate.py full\n"
            "and commit only when it passes. Emergency escape (loudly audited):\n"
            '  uv run python scripts/gate.py override --reason "..."',
        )

    message = commit_message_of(command)
    if message is None:
        gate.append_audit(
            root, "msg_undeterminable", command[:200], str(payload.get("session_id", ""))
        )
    elif not COMMIT_RE.match(message):
        return (
            2,
            f"BLOCKED: commit message {message!r} is not a conventional commit "
            "(feat|fix|test|build|chore|docs|refactor|ci|style|data, optional (scope), "
            "then ': <summary>').",
        )

    if paths and not waived:
        changed = _staged_line_count(root, use_working)
        if changed > 1000:
            return (
                2,
                f"BLOCKED: {changed} changed non-docs lines in one commit (>1000). "
                "Split this into smaller, reviewable commits. Emergency escape:\n"
                '  uv run python scripts/gate.py override --reason "..."',
            )

    risk_paths = [p for p in paths if gate.matches_risk(p)]
    if risk_paths and not gate.review_verdict_valid(root):
        listed = ", ".join(risk_paths[:5])
        return (
            2,
            f"BLOCKED: risk-tier paths staged ({listed}) with no APPROVE review "
            "verdict bound to the current risk-tier diff. Run /review-gate (independent "
            "reviewer subagent) first. Emergency escape (loudly audited):\n"
            '  uv run python scripts/gate.py override --reason "..."',
        )
    return (0, "")


def hook_pre_mcp_guard(payload: dict[str, Any], root: Path) -> HookResult:
    tool = str(payload.get("tool_name", ""))
    session_id = str(payload.get("session_id", ""))
    if tool.startswith("mcp__codex__"):
        state = load_session(root, session_id)
        state["codex_calls"] = int(state.get("codex_calls", 0)) + 1
        _save_session(root, state)
        gate.append_audit(root, "codex_call", f"mcp:{tool}", session_id)
        return (0, "")
    if _MCP_OWNER_VERBS.search(tool):
        return (
            2,
            f"BLOCKED: {tool} is an owner-authority operation (research approve/reject/decide, "
            "research-gate override, holdout reveal). These are trusted-local CLI actions the "
            "owner runs by hand; no agent path may invoke them.",
        )
    return (0, "")


# ---------------------------------------------------------------------------
# hooks: SubagentStop / TaskCompleted / ConfigChange / InstructionsLoaded


def hook_subagent_stop(payload: dict[str, Any], root: Path) -> HookResult:
    if payload.get("stop_hook_active"):
        return (0, "")
    agent_type = str(payload.get("agent_type", ""))
    schema = JSON_AGENT_SCHEMAS.get(agent_type)
    if schema is None:
        return (0, "")
    session_id = str(payload.get("session_id", ""))
    state = load_session(root, session_id)
    key = f"subagent_blocks:{payload.get('agent_id', agent_type)}"
    if int(state.get(key, 0)) >= SUBAGENT_BLOCK_BUDGET:
        return (0, "")
    message = str(payload.get("last_assistant_message", ""))
    errors: list[str] = []
    for name in schema.split("|"):
        problem = validate_against_schema(root, name, message)
        if problem is None:
            return (0, "")
        errors.append(problem)
    error = "; ".join(errors)
    state[key] = int(state.get(key, 0)) + 1
    _save_session(root, state)
    return (
        2,
        f"Your final message must be ONLY a JSON object valid against harness_models."
        f"{schema} (no prose, no code fences). Validation error:\n{error}",
    )


_TEST_REF_RE = re.compile(r"(tests/[\w./\-]+\.py(?:::[\w\[\]\-.]+)?)")


def hook_task_completed(payload: dict[str, Any], root: Path) -> HookResult:
    text = f"{payload.get('task_title', '')}\n{payload.get('task_description', '')}"
    refs = sorted({m for m in _TEST_REF_RE.findall(text) if (root / m.split("::")[0]).is_file()})
    if not refs:
        return (0, "")
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", *refs],
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
        timeout=110,
    )
    if result.returncode == 0:
        return (0, "")
    tail = (result.stdout + result.stderr).strip()[-2500:]
    return (
        2,
        "BLOCKED: this task names tests that currently FAIL — a task is complete when its "
        f"tests pass, not when it is declared done. ({' '.join(refs)})\n{tail}",
    )


def hook_config_change(payload: dict[str, Any], root: Path) -> HookResult:
    source = str(payload.get("config_source", ""))
    path = str(payload.get("config_path", ""))
    session_id = str(payload.get("session_id", ""))
    if gate.owner_present(root):
        gate.append_audit(
            root, "config_change", f"{source} {path}", session_id, authorized_by="owner"
        )
        return (0, "")
    cutoff = datetime.now(UTC).timestamp() - CONFIG_ACK_WINDOW_SECONDS
    recent_ack = False
    for event in gate.read_audit(root, kind="ack_consumed"):
        try:
            when = datetime.fromisoformat(str(event.get("ts"))).timestamp()
        except ValueError:
            continue
        if when >= cutoff:
            recent_ack = True
            break
    if source == "policy_settings" or recent_ack:
        gate.append_audit(
            root, "config_change", f"{source} {path}", session_id, authorized_by="ack"
        )
        return (0, "")
    gate.append_audit(root, "config_change_unacked", f"{source} {path}", session_id)
    return (
        2,
        f"BLOCKED: {source} changed ({path or 'unknown path'}) with no governance ack in the "
        f"last {CONFIG_ACK_WINDOW_SECONDS // 60} minutes and no owner token. Arm one with\n"
        '  uv run python scripts/gate.py ack --reason "..."\n'
        "and re-apply the change through Edit/Write (which consumes it).",
    )


def hook_instructions_loaded(payload: dict[str, Any], root: Path) -> HookResult:
    rel = _rel_path(root, str(payload.get("file_path", ""))) or str(payload.get("file_path", ""))
    if not rel:
        return (0, "")
    session_id = str(payload.get("session_id", ""))
    state = load_session(root, session_id)
    entry = f"{payload.get('load_reason', '?')}:{rel}"
    if entry not in state["instructions_loaded"]:
        state["instructions_loaded"].append(entry)
        state["instructions_loaded"] = state["instructions_loaded"][-100:]
        _save_session(root, state)
    return (0, "")


# ---------------------------------------------------------------------------
# hooks: Stop / SessionStart / UserPromptSubmit / compaction


def hook_stop_guard(payload: dict[str, Any], root: Path) -> HookResult:
    if payload.get("stop_hook_active"):
        return (0, "")
    session_id = str(payload.get("session_id", ""))
    state = load_session(root, session_id)
    edited = [p for p in state.get("edited_files", []) if isinstance(p, str)]
    source_edits = [p for p in edited if _is_source_edit(p)]
    if not source_edits:
        return (0, "")
    if int(state.get("stop_blocks_used", 0)) >= STOP_BLOCK_BUDGET:
        if not state.get("stop_budget_exhausted"):
            state["stop_budget_exhausted"] = True
            _save_session(root, state)
            gate.append_audit(
                root,
                "stop_budget_exhausted",
                f"{STOP_BLOCK_BUDGET} blocks used; stop allowed with unverified edits",
                session_id,
            )
        return (
            0,
            f"WARNING: stop-guard block budget exhausted ({STOP_BLOCK_BUDGET}); allowing stop "
            "with UNVERIFIED edits. Audited; the statusline stays red until the next passing gate.",
        )
    if not gate.stamp_is_valid(root, "fast"):
        _record_stop_block(root, session_id)
        return (
            2,
            "Source files were edited this session but there is no fast-tier gate "
            "stamp for the current tree. Run\n"
            "  uv run python scripts/gate.py fast\n"
            "(or /gate-fast) and fix any failures before finishing.",
        )
    quant_edits = [p for p in source_edits if gate.matches_quant(p)]
    if quant_edits and not gate.quant_attestation_valid(root):
        _record_stop_block(root, session_id)
        listed = ", ".join(quant_edits[:5])
        return (
            2,
            f"Quant-tier statistical sources were edited ({listed}) with no PASS "
            "quant verification attestation for the current quant diff. Run "
            "/verify-quant (quant-verifier subagent checks the math against primary "
            "literature, then `gate.py attest --kind quant`).",
        )
    return (0, "")


def _harness_brief() -> list[str]:
    return [
        "PROJECT ALPHA HARNESS (mechanical enforcement is active):",
        "- Commits require a passing `uv run python scripts/gate.py full` stamp for the",
        "  exact current tree; stopping after source edits requires a `fast` stamp.",
        "- Quant/statistical edits (alpha_validation, alpha_research, dsr/pbo/bootstrap/...)",
        "  additionally require /verify-quant (academic source verification) before Stop.",
        "- Risk-tier paths (quant + alpha_backtest + gauntlet/optim/seeds/identity/",
        "  surrogate/synth/runner) require /review-gate APPROVE before commit.",
        "- Control-plane files (gate, hooks, settings, agents, commands, rules, bias guards,",
        "  holdout/oracle tests, CI, CLAUDE.md, importlinter/coverage/mypy config) need",
        "  `gate.py ack --reason` per edit; shell writes (sed -i, >, tee) count as edits.",
        "- Never: git commit --amend/--no-verify, reset --hard, clean -f, stash drop,",
        "  rm -rf outside the scratchpad, force push, owner-authority MCP/CLI verbs.",
        "- Commands: /gate /gate-fast /verify-quant /review-gate /adversarial-review",
        "  /plan-feature /implement /harness-doctor /codex-review. Conventional commits enforced.",
        "WORKING CONTRACT (planning & simplicity):",
        "- Smallest diff that satisfies the request; no speculative abstractions;",
        "  every changed line must trace to the task.",
        "- Skip formal plans for trivial tasks; never a 1-step plan; multi-file",
        "  features go through /plan-feature -> docs/superpowers/plans/ -> /implement.",
        "- Delegate exploration to the navigator subagent to keep this context lean;",
        "  use test-architect before implementing, invariants-auditor for risky areas.",
        "- TDD: failing test -> minimal code -> green -> small conventional commit.",
        "- Report results honestly: failing tests are reported as failing, verbatim;",
        "  a check you could not run is `UNVERIFIED:`, never 'should work'.",
    ]


def _owner_warning(root: Path) -> list[str]:
    if gate.owner_token_configured(root):
        return []
    return [
        "OWNER TOKEN NOT CONFIGURED: override/ack escape hatches are agent self-serve and",
        "audited as such. Owner: run `uv run python scripts/gate.py owner-init` once, then",
        f"export {gate.OWNER_TOKEN_ENV} in your shell to authorize escapes.",
    ]


def _obligations(root: Path, state: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    edited = [p for p in state.get("edited_files", []) if isinstance(p, str)]
    quant = [p for p in edited if gate.matches_quant(p)]
    risk = [p for p in edited if gate.matches_risk(p)]
    if quant and not gate.quant_attestation_valid(root):
        lines.append(f"OWED: /verify-quant for {', '.join(quant[:5])}")
    if risk and not gate.review_verdict_valid(root):
        lines.append(f"OWED before commit: /review-gate for {', '.join(risk[:5])}")
    if any(_is_source_edit(p) for p in edited) and not gate.stamp_is_valid(root, "fast"):
        lines.append("OWED before stop: gate.py fast (source edits this session, stamp stale)")
    failures = state.get("failures", [])
    if failures:
        lines.append(f"{len(failures)} tool failure(s) recorded this session (see retrospective)")
    if state.get("stop_budget_exhausted"):
        lines.append("STOP BUDGET EXHAUSTED earlier this session — work left unverified")
    over_eager = state.get("over_eager", [])
    if over_eager:
        lines.append(
            f"SCOPE WARNING: {len(over_eager)} edit(s) outside the open plan's declared files "
            f"({', '.join(over_eager[:5])}) — justify in the plan or revert"
        )
    return lines


def hook_session_start(payload: dict[str, Any], root: Path) -> HookResult:
    code, report = gate.doctor(root)
    lines: list[str] = []
    if code != 0:
        failing = ", ".join(c["name"] for c in report["checks"] if not c["ok"])
        lines.append(f"HARNESS DOCTOR FAILING ({failing}) — run /harness-doctor to repair.")
    lines += _harness_brief()
    lines += _owner_warning(root)
    lines.append(KARPATHY_BLOCK)
    lines.append(_repo_brief_or_reason(root))
    return (0, "\n".join(lines))


def _repo_brief_or_reason(root: Path) -> str:
    """The generated repo brief; awareness must never crash a context hook."""
    try:
        return gate.repo_brief(root)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return f"REPO BRIEF unavailable: {exc!r} (run `gate.py brief --refresh`)"


def hook_post_compact(payload: dict[str, Any], root: Path) -> HookResult:
    state = load_session(root, str(payload.get("session_id", "")))
    lines = ["POST-COMPACTION REINJECTION (context was summarized; these do not survive it):"]
    lines += _harness_brief()
    lines += _owner_warning(root)
    lines.append(KARPATHY_BLOCK)
    lines.append(_repo_brief_or_reason(root))
    edited = [p for p in state.get("edited_files", []) if isinstance(p, str)]
    if edited:
        lines.append("Files edited this session: " + ", ".join(edited[:30]))
    lines += _obligations(root, state)
    return (0, "\n".join(lines))


def hook_prompt_context(payload: dict[str, Any], root: Path) -> HookResult:
    branch = gate._git(root, "branch", "--show-current", check=False).strip()
    dirty = len(gate._git_lines(root, "status", "--porcelain"))
    if gate.stamp_is_valid(root, "full"):
        stamp = "full (valid for current tree)"
    elif gate.stamp_is_valid(root, "fast"):
        stamp = "fast (valid for current tree; full needed to commit)"
    else:
        stamp = "none/stale — gate required before commit or stop-after-edits"
    state = load_session(root, str(payload.get("session_id", "")))
    obligations = _obligations(root, state)
    flags: list[str] = []
    if not gate.owner_token_configured(root):
        flags.append("owner-token:UNSET")
    if state.get("stop_budget_exhausted"):
        flags.append("stop-budget:EXHAUSTED")
    brief = [
        f"[harness] branch={branch or '?'} dirty_files={dirty}"
        + (f" flags={','.join(flags)}" if flags else ""),
        f"[harness] gate stamp: {stamp}",
        f"[harness] {'; '.join(obligations) if obligations else 'no outstanding obligations'}",
        "[harness] karpathy: think→simplify→surgical→goal-verify; unverifiable ⇒ say UNVERIFIED:",
    ]
    return (0, "\n".join(brief))


def hook_pre_compact(payload: dict[str, Any], root: Path) -> HookResult:
    return (
        0,
        "Compaction guidance — preserve verbatim: (1) the current plan and its "
        "per-step status; (2) failing tests and their exact error output; (3) the "
        "list of files edited this session; (4) any un-attested quant/risk-tier "
        "edits and which attestations (/verify-quant, /review-gate) are still owed; "
        "(5) the next concrete action.",
    )


# ---------------------------------------------------------------------------
# dispatch

_HOOKS: dict[str, Callable[[dict[str, Any], Path], HookResult]] = {
    "post-edit": hook_post_edit,
    "post-bash": hook_post_bash,
    "post-tool-failure": hook_post_tool_failure,
    "pre-edit-guard": hook_pre_edit_guard,
    "pre-read-guard": hook_pre_read_guard,
    "pre-bash-guard": hook_pre_bash_guard,
    "pre-mcp-guard": hook_pre_mcp_guard,
    "tool-log": hook_tool_log,
    "subagent-stop": hook_subagent_stop,
    "task-completed": hook_task_completed,
    "config-change": hook_config_change,
    "instructions-loaded": hook_instructions_loaded,
    "stop-guard": hook_stop_guard,
    "session-start": hook_session_start,
    "prompt-context": hook_prompt_context,
    "pre-compact": hook_pre_compact,
    "post-compact": hook_post_compact,
}


def main(argv: list[str]) -> int:
    if os.environ.get("ALPHA_HARNESS_DISABLE") == "1":
        return 0
    if len(argv) != 1 or argv[0] not in _HOOKS:
        print(f"usage: claude_hooks.py {{{'|'.join(_HOOKS)}}}", file=sys.stderr)
        return 1
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    try:
        root = gate.repo_root(Path(str(payload.get("cwd") or Path.cwd())))
    except (subprocess.CalledProcessError, OSError):
        return 0  # not in a git repo: never block
    try:
        code, message = _HOOKS[argv[0]](payload, root)
    except Exception as exc:  # noqa: BLE001 - a crashing hook must fail open, loudly
        print(f"[harness] hook {argv[0]} crashed (failing open): {exc!r}", file=sys.stderr)
        return 0
    if message:
        print(message, file=sys.stderr if code == 2 else sys.stdout)
    if code == 2:
        detail = message.splitlines()[0][:200]
        try:
            gate.append_audit(
                root, f"blocked_{argv[0]}", detail, str(payload.get("session_id", ""))
            )
        except Exception as exc:  # noqa: BLE001 - the block stands even if the journal fails
            print(f"[harness] audit append failed (block stands): {exc!r}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
