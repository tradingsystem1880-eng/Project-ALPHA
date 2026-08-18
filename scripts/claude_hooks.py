"""Claude Code hook entrypoints for the Project ALPHA harness.

Seven stdlib-only hooks wired in .claude/settings.json, all dispatching
through ``main(<name>)`` with the hook payload on stdin:

    post-edit        PostToolUse (Edit|Write)  per-file lint feedback + session tracking
    pre-edit-guard   PreToolUse  (Edit|Write)  control-plane edits need a governance ack
    pre-bash-guard   PreToolUse  (Bash)        commit gate: stamp, message, size, four-eyes
    stop-guard       Stop                      fast stamp + quant attestation before stopping
    session-start    SessionStart              doctor + working contract injection
    prompt-context   UserPromptSubmit          per-turn situational brief
    pre-compact      PreCompact                compaction guidance

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
from pathlib import Path
from typing import Any

import gate

COMMIT_RE = re.compile(
    r"^(feat|fix|test|build|chore|docs|refactor|ci|style|data)"
    r"(\([a-z0-9_.\-/]+\))?(!)?: \S.*"
)
_DOCS_PREFIXES = ("docs/", ".claude/", ".agents/", ".codex/")
_SOURCE_PREFIXES = ("packages/", "apps/", "tests/", "scripts/")
_FRONTEND_PREFIX = "apps/alpha-web/frontend/src/"

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


def _is_git_commit(tokens: list[str]) -> bool:
    """True iff the git SUBCOMMAND is commit (never 'commit' as an argument)."""
    if not tokens or Path(tokens[0]).name != "git":
        return False
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in _GIT_GLOBAL_OPTS_WITH_ARG:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token == "commit"
    return False


def contains_git_commit(command: str) -> bool:
    return any(_is_git_commit(tokens) for tokens in extract_commands(command))


def commit_message_of(command: str) -> str | None:
    for tokens in extract_commands(command):
        if not _is_git_commit(tokens):
            continue
        for i, token in enumerate(tokens):
            if token in ("-m", "--message") and i + 1 < len(tokens):
                return tokens[i + 1]
            if token.startswith("--message="):
                return token.split("=", 1)[1]
            if token.startswith("-m") and len(token) > 2:
                return token[2:]
    return None


def docs_only(paths: list[str]) -> bool:
    if not paths:
        return False
    return all(p.endswith(".md") or p.startswith(_DOCS_PREFIXES) for p in paths)


# ---------------------------------------------------------------------------
# session state


def _session_file(root: Path, session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")
    return root / gate.STATE_DIR / f"session-{safe}.json"


def load_session(root: Path, session_id: str) -> dict[str, Any]:
    state = gate.read_json(_session_file(root, session_id))
    if state is None:
        state = {"session_id": session_id, "edited_files": [], "stop_blocks_used": 0}
    return state


def _save_session(root: Path, state: dict[str, Any]) -> None:
    (root / gate.STATE_DIR).mkdir(parents=True, exist_ok=True)
    gate.write_json_atomic(_session_file(root, str(state["session_id"])), state)


def record_edit(root: Path, session_id: str, rel_path: str) -> None:
    state = load_session(root, session_id)
    if rel_path not in state["edited_files"]:
        state["edited_files"].append(rel_path)
    _save_session(root, state)


def _record_stop_block(root: Path, session_id: str) -> int:
    state = load_session(root, session_id)
    state["stop_blocks_used"] = int(state.get("stop_blocks_used", 0)) + 1
    _save_session(root, state)
    return int(state["stop_blocks_used"])


# ---------------------------------------------------------------------------
# helpers


def _rel_path(root: Path, file_path: str) -> str | None:
    try:
        return Path(file_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


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
    out = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    paths = [p for p in out if p]
    if use_working:
        working = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.splitlines()
        paths.extend(p for p in working if p and p not in paths)
    return paths


def _staged_line_count(root: Path, use_working: bool) -> int:
    total = 0
    for cached in [True, False] if use_working else [True]:
        cmd = ["git", "-C", str(root), "diff", "--numstat"]
        if cached:
            cmd.append("--cached")
        for line in subprocess.run(
            cmd, capture_output=True, text=True, check=False
        ).stdout.splitlines():
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            path = fields[2]
            if path.endswith(".md") or path.startswith(_DOCS_PREFIXES):
                continue
            for count in fields[:2]:
                if count.isdigit():
                    total += int(count)
    return total


def _is_lintable_python(rel: str) -> bool:
    return rel.endswith(".py") and rel.startswith(_SOURCE_PREFIXES)


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


# ---------------------------------------------------------------------------
# hooks


def hook_post_edit(
    payload: dict[str, Any], root: Path, *, run_lint: LintRunner | None = None
) -> HookResult:
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path", ""))
    rel = _rel_path(root, file_path) if file_path else None
    if rel is None:
        return (0, "")
    lintable = _is_lintable_python(rel) or (
        rel.endswith((".ts", ".tsx")) and rel.startswith(_FRONTEND_PREFIX)
    )
    if not lintable:
        return (0, "")
    record_edit(root, str(payload.get("session_id", "")), rel)
    lint = run_lint or _default_lint(root)
    try:
        failure = lint(root / rel)
    except (OSError, subprocess.SubprocessError):
        return (0, "")  # lint tooling failure must never block editing
    if failure:
        return (2, f"Lint failed for {rel} — fix before continuing:\n{failure[-3000:]}")
    return (0, "")


def hook_pre_edit_guard(payload: dict[str, Any], root: Path) -> HookResult:
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path", ""))
    rel = _rel_path(root, file_path) if file_path else None
    if rel is None:
        return (0, "")
    reason = gate.protected_reason(rel, _tool_input_text(tool_input))
    if reason is None:
        return (0, "")
    if gate.consume_ack(root) is not None:
        return (0, "")
    return (
        2,
        f"BLOCKED: {reason}. Control-plane files need a one-shot governance ack:\n"
        f'  uv run python scripts/gate.py ack --reason "<why this change is needed>"\n'
        "(the ack is appended to the audit journal for owner review), then retry the edit.",
    )


def hook_pre_bash_guard(payload: dict[str, Any], root: Path) -> HookResult:
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command", ""))
    if not contains_git_commit(command):
        return (0, "")
    if gate.consume_override(root) is not None:
        return (0, "")

    tokens = next(t for t in extract_commands(command) if _is_git_commit(t))
    use_working = any(t in ("-a", "--all") or t == "-am" for t in tokens)
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
    if message is not None and not COMMIT_RE.match(message):
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
            "verdict for the current tree. Run /review-gate (independent reviewer "
            "subagent) first. Emergency escape (loudly audited):\n"
            '  uv run python scripts/gate.py override --reason "..."',
        )
    return (0, "")


def hook_stop_guard(payload: dict[str, Any], root: Path) -> HookResult:
    if payload.get("stop_hook_active"):
        return (0, "")
    session_id = str(payload.get("session_id", ""))
    state = load_session(root, session_id)
    edited = [p for p in state.get("edited_files", []) if isinstance(p, str)]
    source_edits = [p for p in edited if _is_lintable_python(p) or p.startswith(_FRONTEND_PREFIX)]
    if not source_edits:
        return (0, "")
    if int(state.get("stop_blocks_used", 0)) >= 3:
        return (
            0,
            "WARNING: stop-guard block budget exhausted (3); allowing stop with "
            "unverified edits. Run the gate before relying on this work.",
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


def hook_session_start(payload: dict[str, Any], root: Path) -> HookResult:
    code, report = gate.doctor(root)
    lines = []
    if code != 0:
        failing = ", ".join(c["name"] for c in report["checks"] if not c["ok"])
        lines.append(f"HARNESS DOCTOR FAILING ({failing}) — run /harness-doctor to repair.")
    lines += [
        "PROJECT ALPHA HARNESS (mechanical enforcement is active):",
        "- Commits require a passing `uv run python scripts/gate.py full` stamp for the",
        "  exact current tree; stopping after source edits requires a `fast` stamp.",
        "- Quant/statistical edits (alpha_validation, alpha_research, dsr/pbo/bootstrap/...)",
        "  additionally require /verify-quant (academic source verification) before Stop.",
        "- Risk-tier paths (quant + alpha_backtest + gauntlet/optim/seeds/identity/",
        "  surrogate/synth/runner) require /review-gate APPROVE before commit.",
        "- Control-plane files (gate, hooks, settings, bias guards, CI, CLAUDE.md,",
        "  importlinter/coverage/mypy config) need `gate.py ack --reason` per edit.",
        "- Commands: /gate /gate-fast /verify-quant /review-gate /adversarial-review",
        "  /plan-feature /implement /harness-doctor. Conventional commits enforced.",
        "WORKING CONTRACT (planning & simplicity):",
        "- Smallest diff that satisfies the request; no speculative abstractions;",
        "  every changed line must trace to the task.",
        "- Skip formal plans for trivial tasks; never a 1-step plan; multi-file",
        "  features go through /plan-feature -> docs/superpowers/plans/ -> /implement.",
        "- Delegate exploration to the navigator subagent to keep this context lean;",
        "  use test-architect before implementing, invariants-auditor for risky areas.",
        "- TDD: failing test -> minimal code -> green -> small conventional commit.",
        "- Report results honestly: failing tests are reported as failing, verbatim.",
    ]
    return (0, "\n".join(lines))


def hook_prompt_context(payload: dict[str, Any], root: Path) -> HookResult:
    branch = subprocess.run(
        ["git", "-C", str(root), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    dirty = len(
        [
            line
            for line in subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.splitlines()
            if line.strip()
        ]
    )
    if gate.stamp_is_valid(root, "full"):
        stamp = "full (valid for current tree)"
    elif gate.stamp_is_valid(root, "fast"):
        stamp = "fast (valid for current tree; full needed to commit)"
    else:
        stamp = "none/stale — gate required before commit or stop-after-edits"
    obligations: list[str] = []
    if not gate.quant_attestation_valid(root):
        obligations.append("quant attestation: absent (needed only if quant paths change)")
    if not gate.review_verdict_valid(root):
        obligations.append("review verdict: absent (needed only if risk-tier paths staged)")
    brief = [
        f"[harness] branch={branch or '?'} dirty_files={dirty}",
        f"[harness] gate stamp: {stamp}",
        f"[harness] {'; '.join(obligations) if obligations else 'all attestations current'}",
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
    "pre-edit-guard": hook_pre_edit_guard,
    "pre-bash-guard": hook_pre_bash_guard,
    "stop-guard": hook_stop_guard,
    "session-start": hook_session_start,
    "prompt-context": hook_prompt_context,
    "pre-compact": hook_pre_compact,
}
_CONTEXT_HOOKS = frozenset({"session-start", "prompt-context", "pre-compact"})


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
    if code == 2 and argv[0] in ("pre-bash-guard", "pre-edit-guard", "stop-guard"):
        detail = message.splitlines()[0][:200]
        gate.append_audit(root, f"blocked_{argv[0]}", detail, str(payload.get("session_id", "")))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
