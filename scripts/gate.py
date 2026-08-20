"""Claude Code harness gate runner for Project ALPHA.

One source of truth for: the tree-hash stamp protocol, the three path tiers
(quant / risk / protected control plane), attestation artifacts, owner-token
authorization of escape hatches, one-shot override/ack tokens, the
hash-chained append-only audit journal, the harness weakening scanner, and
the harness doctor.

Top level is stdlib-only so hook shims can import it before ``uv sync`` has
ever run; pydantic validation (scripts/harness_models.py) is imported lazily
inside write paths and degrades to a loud error if unavailable.

CLI:
    python3 scripts/gate.py fast|full          # run the tiered gate, stamp on success
    python3 scripts/gate.py check --tier fast  # exit 0 iff a valid stamp covers the tier
    python3 scripts/gate.py attest --kind quant|review   # JSON report on stdin
    python3 scripts/gate.py override --reason "..."      # one-shot commit-gate override
    python3 scripts/gate.py ack --reason "..." [--path P] # one-shot control-plane edit ack
    python3 scripts/gate.py owner-init         # owner sets the escape-hatch token (interactive)
    python3 scripts/gate.py audit --digest     # escape logbook: who authorized what, last 7d
    python3 scripts/gate.py lint-harness       # weakening scanner vs .claude/harness-baseline.json
    python3 scripts/gate.py baseline --reason  # rewrite the baseline (owner/ack authorized)
    python3 scripts/gate.py audit [--json --since ISO --kind K --verify]  # journal reader
    python3 scripts/gate.py brief [--refresh]  # generated repo brief (cached by tree hash)
    python3 scripts/gate.py index [--no-cli]   # regenerate .claude/state/repo-index.json
    python3 scripts/gate.py plan-check PLAN.md # validate a plan's ```json FeaturePlan front block
    python3 scripts/gate.py doctor [--json]    # verify the harness wiring itself
    python3 scripts/gate.py mutate [MODULES|--all] [--json --write-baseline REASON]  # mutmut gate
    python3 scripts/gate.py semgrep [--changed] # .semgrep/alpha.yml banned constructs
    python3 scripts/gate.py determinism        # byte-stability tests twice under perturbed env
    python3 scripts/gate.py raise-cov [--fail] # `raise` lines in quant modules no test reached
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

STATE_DIR = Path(".claude") / "state"
STAMP_FILE = "gate-stamp.json"
AUDIT_FILE = "harness-audit.jsonl"
OVERRIDE_FILE = "commit-override.json"
ACK_FILE = "governance-ack.json"
QUANT_ATTESTATION_FILE = "quant-attestation.json"
REVIEW_VERDICT_FILE = "review-verdict.json"
AGENT_ACK_COUNT_FILE = "agent-ack-count.json"
OWNER_FILE = Path(".claude") / "owner.local.json"
BASELINE_FILE = Path(".claude") / "harness-baseline.json"
OWNER_TOKEN_ENV = "ALPHA_OWNER_TOKEN"
AGENT_ACK_LIMIT = 3

TIER_RANK = {"fast": 1, "full": 2}

# claude_hooks.py subcommands; doctor verifies every one is wired in settings.json.
HOOK_NAMES = (
    "post-edit",
    "post-bash",
    "post-tool-failure",
    "pre-edit-guard",
    "pre-read-guard",
    "pre-bash-guard",
    "pre-mcp-guard",
    "tool-log",
    "subagent-stop",
    "task-completed",
    "config-change",
    "stop-guard",
    "session-start",
    "prompt-context",
    "pre-compact",
    "post-compact",
)

_QUANT_NAME_RE = re.compile(
    r"(dsr|psr|pbo|deflated|bootstrap|reality_check|spa|montecarlo|"
    r"walkforward|cpcv|multiple_testing|overfitting)"
)
_RISK_CLI_FILES = frozenset(
    f"apps/alpha-cli/src/alpha_cli/{name}.py"
    for name in ("_gauntlet", "_optim", "_seeds", "_identity", "_surrogate", "_synth", "_runner")
)
_QUANT_SRC_PREFIXES = ("packages/alpha-validation/src/", "packages/alpha-research/src/")
_PYPROJECT_GUARDED = ("[tool.importlinter]", "fail_under", "strict", "addopts")
_PROTECTED_EXACT = frozenset(
    {
        "scripts/gate.py",
        "scripts/claude_hooks.py",
        "scripts/harness_awareness.py",
        "scripts/harness_models.py",
        "scripts/harness_quant.py",
        "scripts/codex_bridge.py",
        ".claude/settings.json",
        ".claude/statusline.py",
        ".claude/harness-baseline.json",
        ".claude/mutation-baseline.json",
        ".mcp.json",
        ".semgrep/alpha.yml",
        "CLAUDE.md",
        "AGENTS.md",
    }
)
_PROTECTED_PREFIXES = (
    ".claude/skills/",
    ".claude/agents/",
    ".claude/commands/",
    ".claude/rules/",
    ".codex/",
    ".github/workflows/",
    "tests/bias_guards/",
    "tests/holdout/",
    "tests/oracles/",
    "tests/unit/test_claude_harness_",
    "tests/unit/test_claude_md_relocation",
    "tests/unit/test_repo_awareness_drift",
)
# Edits an agent may ack for itself even when the owner token is configured.
_AGENT_ACKABLE_PREFIXES = (".claude/agents/", ".claude/commands/", ".claude/rules/")
HIDDEN_HOLDOUT_PREFIX = "tests/holdout/"

Runner = Callable[[list[str]], tuple[bool, float, str]]
EnvRunner = Callable[..., tuple[bool, float, str]]


# ---------------------------------------------------------------------------
# git plumbing


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _git_lines(root: Path, *args: str) -> list[str]:
    return [line for line in _git(root, *args, check=False).splitlines() if line.strip()]


def repo_root(start: Path | None = None) -> Path:
    """Resolve the enclosing repository root (worktree-correct) from cwd."""
    where = start or Path.cwd()
    out = subprocess.run(
        ["git", "-C", str(where), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def _status_entries(root: Path) -> list[tuple[str, bool]]:
    """``(path, untracked)`` for every changed or untracked working-tree entry."""
    status = _git(root, "status", "--porcelain=v2", "-z", "--untracked-files=all")
    entries: list[tuple[str, bool]] = []
    for entry in status.split("\0"):
        if not entry:
            continue
        untracked = entry.startswith("? ")
        entries.append((entry[2:] if untracked else entry.split(" ")[-1], untracked))
    return entries


def compute_tree_hash(root: Path) -> str:
    """Content hash of the working tree (tracked + untracked, gitignore-respected).

    Built by staging everything into a THROWAWAY git index and asking git for
    the resulting tree object id — the real index, HEAD, and working tree are
    never touched. Because the hash covers file content only, a pure
    ``git commit`` (which changes no bytes on disk) never invalidates a stamp,
    while any content edit — tracked, staged, or untracked — does.
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        subprocess.run(
            ["git", "-C", str(root), "add", "-A"],
            capture_output=True,
            check=True,
            env=env,
        )
        tree = subprocess.run(
            ["git", "-C", str(root), "write-tree"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        ).stdout.strip()
    return hashlib.sha256(tree.encode()).hexdigest()


def scoped_changed_paths(root: Path, matcher: Callable[[str], bool]) -> list[str]:
    """Working-tree paths (tracked-changed or untracked) accepted by ``matcher``."""
    return sorted({path for path, _ in _status_entries(root) if matcher(path)})


def scoped_diff_hash(root: Path, matcher: Callable[[str], bool]) -> str:
    """sha256 of the working diff restricted to paths accepted by ``matcher``.

    Binds attestations to the in-scope diff only, so out-of-scope edits (docs,
    unrelated code) do not invalidate an attestation while any in-scope change
    does.
    """
    hasher = hashlib.sha256()
    scoped_tracked: list[str] = []
    for path, untracked in _status_entries(root):
        if not matcher(path):
            continue
        if untracked:
            hasher.update(path.encode())
            hasher.update(b"\0")
            try:
                hasher.update((root / path).read_bytes())
            except OSError:
                hasher.update(b"<unreadable>")
            hasher.update(b"\0")
        else:
            scoped_tracked.append(path)
    head = _git(root, "rev-parse", "HEAD", check=False).strip()
    if head and scoped_tracked:
        diff = subprocess.run(
            ["git", "-C", str(root), "diff", "HEAD", "--no-ext-diff", "--binary", "--"]
            + sorted(scoped_tracked),
            capture_output=True,
            check=True,
        )
        hasher.update(diff.stdout)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# path tiers


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def matches_quant(path: str) -> bool:
    """Statistical source code requiring academic verification before Stop."""
    posix = _posix(path)
    if posix.startswith(_QUANT_SRC_PREFIXES):
        return posix.endswith(".py")
    if posix.startswith("packages/") and "/src/" in posix and posix.endswith(".py"):
        return bool(_QUANT_NAME_RE.search(posix.rsplit("/", 1)[-1]))
    return False


def matches_risk(path: str) -> bool:
    """Risk-tier paths requiring an independent APPROVE review before commit."""
    posix = _posix(path)
    if matches_quant(posix):
        return True
    if posix.startswith("packages/alpha-backtest/src/") and posix.endswith(".py"):
        return True
    return posix in _RISK_CLI_FILES


def protected_reason(path: str, content: str = "") -> str | None:
    """Control-plane paths whose edits need a governance ack (or the owner token)."""
    posix = _posix(path)
    if posix in _PROTECTED_EXACT or posix.startswith(_PROTECTED_PREFIXES):
        return f"{posix} is harness/governance control plane"
    if posix == "pyproject.toml":
        for marker in _PYPROJECT_GUARDED:
            if marker in content:
                return f"pyproject.toml edit touches guarded config ({marker!r})"
    return None


def agent_ackable(path: str) -> bool:
    """Low-risk control-plane text an agent may ack for itself (bounded per session)."""
    return _posix(path).startswith(_AGENT_ACKABLE_PREFIXES)


def is_hidden_holdout(path: str) -> bool:
    return _posix(path).startswith(HIDDEN_HOLDOUT_PREFIX)


# ---------------------------------------------------------------------------
# state files, audit journal


def _state_dir(root: Path) -> Path:
    directory = root / STATE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def first_json_object(text: str) -> str | None:
    """The outermost ``{...}`` slice of ``text`` (fenced or not), or ``None``."""
    body = text.strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    return body[start : end + 1]


def write_json_atomic(path: Path, obj: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _last_audit_line(journal: Path) -> bytes:
    try:
        with journal.open("rb") as fh:
            last = b""
            for raw in fh:
                if raw.strip():
                    last = raw.rstrip(b"\n")
            return last
    except OSError:
        return b""


def append_audit(
    root: Path,
    event: str,
    detail: str,
    session_id: str = "",
    *,
    authorized_by: str = "",
    path: str | None = None,
) -> None:
    """Append one hash-chained event; ``prev_hash`` binds each line to its predecessor."""
    journal = _state_dir(root) / AUDIT_FILE
    tree_hash = compute_tree_hash(root)
    # Hooks fire concurrently (e.g. ConfigChange alongside an ack consumption); the
    # read-last + append pair must be atomic or two lines share one parent.
    with journal.open("a") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            prev = _last_audit_line(journal)
            line = {
                "ts": _now(),
                "session_id": session_id or os.environ.get("CLAUDE_SESSION_ID", ""),
                "event": event,
                "detail": detail,
                "tree_hash": tree_hash,
                "prev_hash": hashlib.sha256(prev).hexdigest() if prev else "",
                "authorized_by": authorized_by,
            }
            if path:
                line["path"] = path
            fh.write(json.dumps(line, sort_keys=True) + "\n")
            fh.flush()
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def read_audit(
    root: Path, *, since: str | None = None, kind: str | None = None
) -> list[dict[str, Any]]:
    journal = _state_dir(root) / AUDIT_FILE
    events: list[dict[str, Any]] = []
    try:
        lines = journal.read_text().splitlines()
    except OSError:
        return events
    for raw in lines:
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        if since and str(item.get("ts", "")) < since:
            continue
        if kind and str(item.get("event", "")) != kind:
            continue
        events.append(item)
    return events


AUDIT_FORK_WINDOW_SECONDS = 5


def _audit_ts(item: dict[str, Any]) -> float | None:
    try:
        return datetime.fromisoformat(str(item.get("ts"))).timestamp()
    except ValueError:
        return None


def verify_audit_chain(root: Path) -> tuple[bool, str]:
    """Recompute the hash chain; a truncated/rewritten line breaks it loudly.

    Two hooks that fired concurrently before ``append_audit`` took its file lock
    could both bind to the same parent (a *fork*: line N+1's ``prev_hash`` equals
    line N's, and both were written within ``AUDIT_FORK_WINDOW_SECONDS``). Such a
    pair is reported as a fork and the chain resumes from the later sibling; it is
    not treated as tampering. Limitation (documented): deleting exactly one sibling
    of a fork is undetectable by this check.
    """
    journal = _state_dir(root) / AUDIT_FILE
    try:
        raw_lines = [ln for ln in journal.read_bytes().split(b"\n") if ln.strip()]
    except OSError:
        return (True, "no journal")
    prev = b""
    prev_item: dict[str, Any] = {}
    forks = 0
    for index, raw in enumerate(raw_lines):
        try:
            item = json.loads(raw)
        except ValueError:
            return (False, f"line {index + 1}: not JSON")
        expected = hashlib.sha256(prev).hexdigest() if prev else ""
        recorded = item.get("prev_hash")
        # Lines written before the chain existed carry no prev_hash; the chain
        # starts at the first line that records one.
        if recorded is not None and recorded != expected:
            sibling = recorded == prev_item.get("prev_hash")
            t_prev, t_cur = _audit_ts(prev_item), _audit_ts(item)
            close = t_prev is not None and t_cur is not None
            close = close and abs(t_cur - t_prev) <= AUDIT_FORK_WINDOW_SECONDS  # type: ignore[operator]
            if not (sibling and close):
                return (
                    False,
                    f"line {index + 1}: prev_hash mismatch (journal edited or truncated)",
                )
            forks += 1
        prev, prev_item = raw, item
    suffix = f", {forks} concurrent-append fork(s) tolerated" if forks else ""
    return (True, f"{len(raw_lines)} events, chain intact{suffix}")


ESCAPE_EVENTS = ("ack_written", "override_written", "baseline_written")
BLOCK_PREFIX = "blocked_"
DIGEST_DEFAULT_DAYS = 7


def audit_digest(root: Path, *, since: str | None = None, days: int = DIGEST_DEFAULT_DAYS) -> str:
    """One screen of who authorized what, from the hash-chained journal.

    Counts and paths only — never file contents. Acks are rolled up *by path*
    because a single sweep legitimately arms dozens of them, and the question
    worth answering is which files kept needing an escape, not how many times.
    """
    if since is None:
        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    events = read_audit(root, since=since)
    escapes = [e for e in events if str(e.get("event")) in ESCAPE_EVENTS]
    blocks = [e for e in events if str(e.get("event", "")).startswith(BLOCK_PREFIX)]
    lines = [
        f"[digest] harness audit since {since}",
        "",
        f"  self-authorized escapes  {len(escapes)}",
    ]
    by_event: dict[str, list[dict[str, Any]]] = {}
    for item in escapes:
        by_event.setdefault(str(item.get("event")), []).append(item)
    for event in ESCAPE_EVENTS:
        group = by_event.get(event, [])
        if not group:
            continue
        agent = sum(1 for e in group if str(e.get("authorized_by", "")).startswith("agent"))
        lines.append(f"    {event:<18} {len(group):>4}   ({agent} agent self-serve)")
        paths: dict[str, int] = {}
        for item in group:
            recorded = str(item.get("path") or "")
            if recorded:
                paths[recorded] = paths.get(recorded, 0) + 1
        # Paths were only recorded from the logbook onwards, so an older window
        # legitimately has none. Say that once instead of printing a placeholder
        # row per event kind.
        for path, count in sorted(paths.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"      {path:<48} {count:>4}")
        if not paths:
            lines.append("      (no paths recorded in this window)")
    if not escapes:
        lines.append("    (none)")
    lines += ["", f"  blocks the harness enforced  {len(blocks)}"]
    kinds: dict[str, int] = {}
    for item in blocks:
        kinds[str(item.get("event"))] = kinds.get(str(item.get("event")), 0) + 1
    for kind, count in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"    {kind:<28} {count:>4}")
    if not blocks:
        lines.append("    (none)")
    other = {
        "config changes": "config_change",
        "codex calls": "codex_call",
        "gate failures": "gate_failed",
    }
    lines.append("")
    for label, kind in other.items():
        lines.append(f"  {label:<28} {sum(1 for e in events if e.get('event') == kind):>4}")
    # A token that was written but never consumed is still armed on disk: it
    # fires on the next matching action, days later, with nobody expecting it.
    # The journal shows it was *written*, never that it is still loaded.
    live = [
        (label, token)
        for filename, label in ((OVERRIDE_FILE, "commit override"), (ACK_FILE, "governance ack"))
        if (token := read_json(_state_dir(root) / filename)) is not None
    ]
    if live:
        lines += ["", "  LIVE — armed, not yet used (fires on the next matching action)"]
        for label, token in live:
            lines.append(f"    {label:<18} {token.get('path') or 'any file'}")
            lines.append(f"      armed {token.get('created_at', '?')} — {token.get('reason', '')}")
    ok, detail = verify_audit_chain(root)
    lines += ["", f"  chain: {'ok' if ok else 'FAIL'} — {detail}"]
    if not owner_token_configured(root):
        lines.append("  owner token: NOT configured — every escape above was agent self-serve")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# owner token


def owner_token_configured(root: Path) -> bool:
    data = read_json(root / OWNER_FILE)
    return bool(data and isinstance(data.get("ownerTokenHash"), str))


def owner_present(root: Path) -> bool:
    """True iff ``ALPHA_OWNER_TOKEN`` in the environment matches the configured hash."""
    data = read_json(root / OWNER_FILE)
    if not data:
        return False
    token = os.environ.get(OWNER_TOKEN_ENV, "")
    if not token:
        return False
    return hashlib.sha256(token.encode()).hexdigest() == data.get("ownerTokenHash")


def owner_init(root: Path, token: str) -> None:
    if len(token) < 12:
        raise ValueError("owner token must be at least 12 characters")
    (root / OWNER_FILE).parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        root / OWNER_FILE,
        {"ownerTokenHash": hashlib.sha256(token.encode()).hexdigest(), "created_at": _now()},
    )
    append_audit(root, "owner_token_configured", "escape hatches now require the owner token")


def authorize_escape(root: Path, *, kind: str, path: str | None = None) -> tuple[bool, str]:
    """Decide who may arm an escape hatch (override/ack/baseline).

    Owner token configured  -> the env token must match, except an agent may
    ack up to AGENT_ACK_LIMIT low-risk text edits per session.
    Owner token unconfigured -> self-serve, audited as ``agent`` and flagged
    loudly everywhere (statusline, brief, doctor) until the owner runs owner-init.
    """
    if owner_present(root):
        return (True, "owner")
    if not owner_token_configured(root):
        return (True, "agent (owner token not configured)")
    if kind == "ack" and path and agent_ackable(path):
        counter = _state_dir(root) / AGENT_ACK_COUNT_FILE
        session = os.environ.get("CLAUDE_SESSION_ID", "unknown")
        data = read_json(counter) or {}
        used = int(data.get(session, 0))
        if used < AGENT_ACK_LIMIT:
            data[session] = used + 1
            write_json_atomic(counter, data)
            return (True, f"agent (low-risk ack {used + 1}/{AGENT_ACK_LIMIT})")
        return (False, f"agent low-risk ack budget exhausted ({AGENT_ACK_LIMIT}/session)")
    return (
        False,
        f"{kind} requires the owner: export {OWNER_TOKEN_ENV}=<token> in the owner's shell "
        "(configured via `gate.py owner-init`); the agent cannot authorize its own bypass",
    )


# ---------------------------------------------------------------------------
# stamps


def write_stamp(
    root: Path, tier: str, *, steps: list[tuple[str, float, bool]], duration: float
) -> None:
    from harness_models import GateStamp, GateStep

    stamp = GateStamp(
        tier=tier,
        created_at=_now(),
        head=_git(root, "rev-parse", "HEAD", check=False).strip() or "EMPTY",
        tree_hash=compute_tree_hash(root),
        duration_seconds=duration,
        steps=[GateStep(name=name, seconds=seconds, ok=ok) for name, seconds, ok in steps],
    )
    write_json_atomic(_state_dir(root) / STAMP_FILE, stamp.model_dump())
    append_audit(root, "stamp_written", f"tier={tier} duration={duration:.1f}s")


def clear_stamp(root: Path) -> None:
    (_state_dir(root) / STAMP_FILE).unlink(missing_ok=True)


def stamp_state(root: Path) -> tuple[str, bool]:
    """``(tier, fresh-for-current-tree)``; tier is ``"none"`` when no stamp exists."""
    stamp = read_json(_state_dir(root) / STAMP_FILE)
    if stamp is None:
        return ("none", False)
    return (str(stamp.get("tier")), stamp.get("tree_hash") == compute_tree_hash(root))


def stamp_tier(root: Path) -> str:
    """Highest tier the stamp satisfies for the current tree; ``"none"`` if absent or stale."""
    have, fresh = stamp_state(root)
    return have if fresh and have in TIER_RANK else "none"


def stamp_is_valid(root: Path, tier: str) -> bool:
    return TIER_RANK.get(stamp_tier(root), 0) >= TIER_RANK[tier]


def stamp_age_seconds(root: Path) -> float | None:
    stamp = read_json(_state_dir(root) / STAMP_FILE)
    if stamp is None:
        return None
    try:
        created = datetime.fromisoformat(str(stamp.get("created_at")))
    except ValueError:
        return None
    return (datetime.now(UTC) - created).total_seconds()


# ---------------------------------------------------------------------------
# attestations


def attest(root: Path, kind: str, payload_text: str) -> int:
    """Validate an agent-produced report and persist it bound to the in-scope diff."""
    try:
        payload = json.loads(payload_text)
    except ValueError as exc:
        print(f"attest rejected: not valid JSON ({exc})", file=sys.stderr)
        return 1
    try:
        from harness_models import (
            QuantAttestation,
            QuantVerificationReport,
            ReviewAttestation,
            ReviewVerdict,
        )
    except ImportError as exc:  # pragma: no cover - requires broken env
        print(f"attest unavailable: pydantic models not importable ({exc})", file=sys.stderr)
        return 1

    # per-kind spec: (model, PASS-field, required value, tier label, matcher, state file, event)
    model: type[QuantVerificationReport] | type[ReviewVerdict]
    if kind == "quant":
        model, field, want = QuantVerificationReport, "overall", "PASS"
        label, matcher, state_file, event = (
            "quant-tier", matches_quant, QUANT_ATTESTATION_FILE, "quant_attested",
        )  # fmt: skip
    elif kind == "review":
        model, field, want = ReviewVerdict, "verdict", "APPROVE"
        label, matcher, state_file, event = (
            "risk-tier", matches_risk, REVIEW_VERDICT_FILE, "review_attested",
        )  # fmt: skip
    else:
        print(f"attest rejected: unknown kind {kind!r}", file=sys.stderr)
        return 2

    try:
        report = model.model_validate(payload)
    except ValueError as exc:
        print(f"attest rejected: {exc}", file=sys.stderr)
        return 1
    if getattr(report, field) != want:
        print(f"attest rejected: {field} must be {want} to attest", file=sys.stderr)
        return 1
    if isinstance(report, ReviewVerdict) and report.reviewed_diff_hash != scoped_diff_hash(
        root, matches_risk
    ):
        print(
            "attest rejected: reviewed_diff_hash is stale — a risk-tier file changed "
            "since review; re-run /review-gate",
            file=sys.stderr,
        )
        return 1
    missing = sorted(set(scoped_changed_paths(root, matcher)) - set(report.files_reviewed))
    if missing:
        print(
            f"attest rejected: {label} files changed but absent from files_reviewed: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    artifact: QuantAttestation | ReviewAttestation
    if isinstance(report, QuantVerificationReport):
        artifact = QuantAttestation(
            created_at=_now(),
            bound_quant_diff_hash=scoped_diff_hash(root, matches_quant),
            report=report,
        )
        detail = f"claims={len(report.claims)}"
    else:
        artifact = ReviewAttestation(created_at=_now(), verdict=report)
        detail = f"findings={len(report.findings)}"
    write_json_atomic(_state_dir(root) / state_file, artifact.model_dump())
    append_audit(root, event, detail)
    return 0


def quant_attestation_valid(root: Path) -> bool:
    artifact = read_json(_state_dir(root) / QUANT_ATTESTATION_FILE) or {}
    return artifact.get("bound_quant_diff_hash") == scoped_diff_hash(root, matches_quant)


def review_verdict_valid(root: Path) -> bool:
    verdict = (read_json(_state_dir(root) / REVIEW_VERDICT_FILE) or {}).get("verdict")
    if not isinstance(verdict, dict) or verdict.get("verdict") != "APPROVE":
        return False
    return verdict.get("reviewed_diff_hash") == scoped_diff_hash(root, matches_risk)


# ---------------------------------------------------------------------------
# one-shot tokens


def _write_token(
    root: Path,
    filename: str,
    event: str,
    reason: str,
    *,
    authorized_by: str,
    path: str | None = None,
) -> None:
    from harness_models import OnceToken

    token = OnceToken(created_at=_now(), reason=reason, authorized_by=authorized_by, path=path)
    write_json_atomic(_state_dir(root) / filename, token.model_dump())
    append_audit(root, event, reason, authorized_by=authorized_by, path=path)


def write_override(root: Path, *, reason: str, authorized_by: str = "agent") -> None:
    _write_token(root, OVERRIDE_FILE, "override_written", reason, authorized_by=authorized_by)


def write_ack(
    root: Path, *, reason: str, authorized_by: str = "agent", path: str | None = None
) -> None:
    _write_token(root, ACK_FILE, "ack_written", reason, authorized_by=authorized_by, path=path)


def _consume(root: Path, filename: str, event: str) -> dict[str, Any] | None:
    path = _state_dir(root) / filename
    token = read_json(path)
    if token is None:
        return None
    path.unlink(missing_ok=True)
    append_audit(
        root,
        event,
        str(token.get("reason", "")),
        authorized_by=str(token.get("authorized_by", "")),
        path=str(token.get("path") or "") or None,
    )
    return token


def disarm_token(root: Path, kind: str) -> dict[str, Any] | None:
    """Drop an armed token without using it, recorded as dropped rather than spent.

    Deleting the state file by hand also disarms it, but leaves the journal claiming the
    token is still live — the one thing the digest cannot then get right.
    """
    filename = OVERRIDE_FILE if kind == "override" else ACK_FILE
    return _consume(root, filename, f"{kind}_disarmed")


def consume_override(root: Path) -> dict[str, Any] | None:
    return _consume(root, OVERRIDE_FILE, "override_consumed")


def consume_ack(root: Path, *, path: str | None = None) -> dict[str, Any] | None:
    """Consume the pending ack; a path-bound ack only clears an edit of that path."""
    token = read_json(_state_dir(root) / ACK_FILE)
    if token is None:
        return None
    bound = token.get("path")
    if bound and path and bound != path:
        return None
    return _consume(root, ACK_FILE, "ack_consumed")


# ---------------------------------------------------------------------------
# weakening scanner


def harness_metrics(root: Path) -> dict[str, Any]:
    """Current guardrail counts; compared against .claude/harness-baseline.json."""
    settings = read_json(root / ".claude" / "settings.json") or {}
    permissions = settings.get("permissions") or {}
    deny = sorted(str(rule) for rule in permissions.get("deny") or [])
    hook_events = sorted(str(k) for k in (settings.get("hooks") or {}))
    pyproject = (root / "pyproject.toml").read_text() if (root / "pyproject.toml").is_file() else ""
    fail_under = 0
    match = re.search(r"^fail_under\s*=\s*(\d+)", pyproject, re.MULTILINE)
    if match:
        fail_under = int(match.group(1))
    contracts = len(re.findall(r"^\[\[tool\.importlinter\.contracts\]\]", pyproject, re.MULTILINE))
    strict_markers = "--strict-markers" in pyproject
    bias_dir = root / "tests" / "bias_guards"
    bias_tests = len(list(bias_dir.glob("test_*.py"))) if bias_dir.is_dir() else 0
    suppressions = 0
    for base in ("packages/alpha-validation/src", "packages/alpha-research/src"):
        directory = root / base
        if not directory.is_dir():
            continue
        for file in directory.rglob("*.py"):
            text = file.read_text(errors="replace")
            suppressions += text.count("# noqa") + text.count("# type: ignore")
    return {
        "schema_version": 1,
        "deny_rules": deny,
        "hook_events": hook_events,
        "coverage_fail_under": fail_under,
        "importlinter_contracts": contracts,
        "bias_guard_tests": bias_tests,
        "strict_markers": strict_markers,
        "quant_suppressions": suppressions,
    }


def lint_harness(root: Path) -> list[str]:
    """Return regressions of the current tree against the committed baseline."""
    baseline = read_json(root / BASELINE_FILE)
    if baseline is None:
        return [f"{BASELINE_FILE} missing — run `gate.py baseline --reason ...`"]
    current = harness_metrics(root)
    problems: list[str] = []
    for rule in set(baseline.get("deny_rules", [])) - set(current["deny_rules"]):
        problems.append(f"deny rule removed: {rule}")
    for event in set(baseline.get("hook_events", [])) - set(current["hook_events"]):
        problems.append(f"hook event unwired: {event}")
    if current["coverage_fail_under"] < int(baseline.get("coverage_fail_under", 0)):
        problems.append(
            f"coverage fail_under lowered: {baseline.get('coverage_fail_under')} -> "
            f"{current['coverage_fail_under']}"
        )
    if current["importlinter_contracts"] < int(baseline.get("importlinter_contracts", 0)):
        problems.append("import-linter contract deleted")
    if current["bias_guard_tests"] < int(baseline.get("bias_guard_tests", 0)):
        problems.append("bias-guard test file deleted")
    if baseline.get("strict_markers") and not current["strict_markers"]:
        problems.append("--strict-markers disabled")
    if current["quant_suppressions"] > int(baseline.get("quant_suppressions", 0)):
        problems.append(
            f"quant-module suppressions grew: {baseline.get('quant_suppressions')} -> "
            f"{current['quant_suppressions']} (# noqa / # type: ignore)"
        )
    ci = root / ".github" / "workflows" / "ci.yml"
    if ci.is_file():
        text = ci.read_text()
        if re.search(r"pytest[^\n]*(--maxfail|\s-x\b)", text):
            problems.append("CI pytest uses -x/--maxfail (hides later failures)")
    return problems


def write_baseline(root: Path, *, reason: str, authorized_by: str) -> None:
    from harness_models import HarnessBaseline

    baseline = HarnessBaseline.model_validate(harness_metrics(root))
    write_json_atomic(root / BASELINE_FILE, baseline.model_dump())
    append_audit(root, "baseline_written", reason, authorized_by=authorized_by)


# ---------------------------------------------------------------------------
# gate execution


def _env_runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
    """The one subprocess wrapper: (ok, seconds, combined output); never raises."""
    started = time.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (False, time.monotonic() - started, f"{type(exc).__name__}: {exc}")
    output = (result.stdout + result.stderr).strip()
    return (result.returncode == 0, time.monotonic() - started, output)


# Mirrors CI's "Import built wheels" step byte-for-byte (13 wheels incl. alpha_patterns).
_WHEEL_SMOKE_SH = (
    "uv pip install --python .venv/bin/python --reinstall --no-deps dist/*.whl && "
    ".venv/bin/python -c 'import alpha_core, alpha_data, alpha_strategies, alpha_backtest, "
    "alpha_validation, alpha_forecast, alpha_options, alpha_screener, alpha_research, "
    "alpha_patterns, alpha_cli, alpha_mcp, alpha_web; "
    'assert all(m.__version__ == "1.0.0" for m in (alpha_core, alpha_data, alpha_strategies, '
    "alpha_backtest, alpha_validation, alpha_forecast, alpha_options, alpha_screener, "
    "alpha_research, alpha_patterns, alpha_cli, alpha_mcp, alpha_web))'"
)

HARNESS_SCRIPTS = (
    "scripts/gate.py",
    "scripts/claude_hooks.py",
    "scripts/harness_awareness.py",
    "scripts/harness_models.py",
    "scripts/harness_quant.py",
    "scripts/codex_bridge.py",
    ".claude/statusline.py",
)


def gate_steps(tier: str, root: Path | None = None) -> list[tuple[str, list[str]]]:
    base = root or Path.cwd()
    harness_files = [rel for rel in HARNESS_SCRIPTS if (base / rel).is_file()]
    fast: list[tuple[str, list[str]]] = [
        ("ruff check", ["uv", "run", "ruff", "check", "."]),
        ("ruff format", ["uv", "run", "ruff", "format", "--check", "."]),
        ("import contracts", ["uv", "run", "lint-imports"]),
        ("mypy", ["uv", "run", "mypy", "packages", "apps", "tests"]),
        ("mypy harness", ["uv", "run", "mypy", *harness_files]),
        ("harness lint", [sys.executable, "scripts/gate.py", "lint-harness"]),
    ]
    if (base / SEMGREP_RULES).is_file():
        fast.append(("semgrep", [sys.executable, "scripts/gate.py", "semgrep", "--changed"]))
    if tier == "fast":
        return fast
    full = [
        ("uv lock", ["uv", "lock", "--check"]),
        ("uv sync", ["uv", "sync", "--locked"]),
        *fast,
        (
            "pytest + coverage",
            ["uv", "run", "pytest", "-q", "-m", "not network and not slow_oracle", "--cov"],
        ),
        (
            "openapi freshness",
            ["uv", "run", "python", "scripts/generate_web_openapi.py", "--check"],
        ),
        ("build wheels", ["uv", "build", "--all-packages"]),
        ("wheel smoke", ["bash", "-c", _WHEEL_SMOKE_SH]),
    ]
    # On-touch of quant-tier SOURCE (not tests): the slow known-truth oracles and the mutation
    # gate join the full gate, so a statistical edit cannot be stamped on fast tests alone.
    if root is not None and quant_source_modules(root):
        full.append(("slow oracles", ["uv", "run", "pytest", "-q", "-m", "slow_oracle"]))
        full.append(("mutation gate", [sys.executable, "scripts/gate.py", "mutate"]))
    return full


def run_gate(root: Path, tier: str, *, runner: Runner | None = None) -> int:
    """Run the tiered gate; stamp only on full success. Mirrors CI's check job."""
    run = runner or _env_runner
    clear_stamp(root)
    started = time.monotonic()
    steps: list[tuple[str, float, bool]] = []
    for name, cmd in gate_steps(tier, root):
        ok, seconds, output = run(cmd)
        steps.append((name, seconds, ok))
        marker = "PASS" if ok else "FAIL"
        print(f"[gate:{tier}] {name}: {marker} ({seconds:.1f}s)")
        if not ok:
            if output:
                print(output[-4000:], file=sys.stderr)
            append_audit(root, "gate_failed", f"tier={tier} step={name}")
            print(f"[gate:{tier}] FAILED at {name!r}; no stamp written.", file=sys.stderr)
            return 1
    write_stamp(root, tier, steps=steps, duration=time.monotonic() - started)
    print(f"[gate:{tier}] PASS — stamp written for current tree.")
    return 0


# ---------------------------------------------------------------------------
# doctor


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fields: dict[str, str] = {}
    key = ""
    for line in parts[1].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            key = key.strip()
            fields[key] = value.strip()
        elif key and line.lstrip().startswith("- "):  # YAML block list → inline "[a, b]"
            item = line.lstrip()[2:].strip()
            inner = fields[key].strip("[]")
            fields[key] = f"[{inner}, {item}]" if inner else f"[{item}]"
    return fields


def _bracket_list(value: str) -> list[str]:
    """A frontmatter inline list (``[a, b]``) as items, brackets and quotes stripped."""
    return [item.strip().strip("\"'") for item in value.strip("[]").split(",") if item.strip()]


def codex_probe() -> tuple[bool, str]:
    """Is the Codex CLI installed and logged in? Never calls the model."""
    binary = shutil.which("codex")
    if binary is None:
        return (False, "codex CLI not on PATH (second-model review unavailable; gates unaffected)")
    try:
        status = subprocess.run(
            ["codex", "login", "status"], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (False, f"codex login status failed: {exc!r}")
    text = (status.stdout + status.stderr).strip()
    if "logged in" in text.lower() and "not logged" not in text.lower():
        return (True, f"{binary}: {text.splitlines()[0][:80]}")
    return (False, f"codex present but not logged in: {text[:80]}")


def doctor(root: Path) -> tuple[int, dict[str, Any]]:
    checks: list[tuple[str, bool, str]] = []

    settings_path = root / ".claude" / "settings.json"
    settings = read_json(settings_path)
    checks.append(("settings.json parses", settings is not None, str(settings_path)))

    wired = json.dumps(settings.get("hooks", {})) if settings else ""
    for name in HOOK_NAMES:
        checks.append((f"hook wired: {name}", name in wired, "settings.json hooks block"))

    for rel in HARNESS_SCRIPTS:
        checks.append((f"file present: {rel}", (root / rel).is_file(), rel))

    try:
        probe = _state_dir(root) / ".doctor-probe"
        probe.write_text("ok")
        probe.unlink()
        checks.append(("state dir writable", True, str(_state_dir(root))))
    except OSError as exc:
        checks.append(("state dir writable", False, str(exc)))

    skills_dir = root / ".claude" / "skills"
    if skills_dir.is_dir():
        for stub in sorted(skills_dir.iterdir()):
            if not stub.is_dir():
                continue
            canonical = root / ".agents" / "skills" / stub.name / "SKILL.md"
            checks.append(
                (
                    f"skill stub has canonical: {stub.name}",
                    canonical.is_file(),
                    str(canonical),
                )
            )

    agents_dir = root / ".claude" / "agents"
    if agents_dir.is_dir():
        for agent in sorted(agents_dir.glob("*.md")):
            fields = _frontmatter(agent.read_text())
            ok = bool(fields.get("name")) and bool(fields.get("description"))
            skills = _bracket_list(fields.get("skills", ""))
            missing = [s for s in skills if not (skills_dir / s).is_dir()]
            checks.append(
                (
                    f"agent frontmatter valid: {agent.stem}",
                    ok and not missing,
                    "missing skills: " + ", ".join(missing) if missing else "name+description",
                )
            )

    rules_dir = root / ".claude" / "rules"
    if rules_dir.is_dir():
        for rule in sorted(rules_dir.glob("*.md")):
            fields = _frontmatter(rule.read_text())
            paths_field = fields.get("paths", "")
            unmatched = [g for g in _bracket_list(paths_field) if not any(root.glob(g))]
            checks.append(
                (
                    f"rule paths resolve: {rule.stem}",
                    not unmatched,
                    "unmatched: " + ", ".join(unmatched)
                    if unmatched
                    else (paths_field or "unscoped"),
                )
            )

    baseline_ok = (root / BASELINE_FILE).is_file()
    checks.append(("harness baseline present", baseline_ok, str(BASELINE_FILE)))
    if baseline_ok:
        problems = lint_harness(root)
        checks.append(
            ("harness not weakened", not problems, "; ".join(problems) or "no regressions")
        )

    ok_chain, chain_detail = verify_audit_chain(root)
    checks.append(("audit chain intact", ok_chain, chain_detail))

    checks.append(
        (
            "owner token configured",
            True,
            "yes"
            if owner_token_configured(root)
            else "WARN: not configured — escape hatches are agent self-serve; run owner-init",
        )
    )

    codex_ok, codex_detail = codex_probe()
    checks.append(("codex second model", True, ("available: " if codex_ok else "") + codex_detail))

    age = stamp_age_seconds(root)
    checks.append(
        (
            "gate stamp",
            True,
            "none"
            if age is None
            else f"{age / 3600:.1f}h old, {'valid' if stamp_is_valid(root, 'fast') else 'stale'}",
        )
    )

    report = {
        "created_at": _now(),
        "checks": [{"name": name, "ok": ok, "detail": detail} for name, ok, detail in checks],
        "ok": all(ok for _, ok, _ in checks),
    }
    try:
        from harness_models import DoctorReport

        DoctorReport.model_validate(report)
    except ImportError:
        pass  # doctor must still run pre-`uv sync`; validation is best-effort here
    return (0 if report["ok"] else 1, report)


# ---------------------------------------------------------------------------
# quant-tier module selection (W5); the sweeps themselves live in scripts/harness_quant.py

SEMGREP_RULES = Path(".semgrep") / "alpha.yml"


def quant_source_modules(root: Path, paths: list[str] | None = None) -> list[str]:
    """Quant-tier SOURCE modules (default: those changed in the working tree). Tests excluded."""
    candidates = paths if paths is not None else scoped_changed_paths(root, matches_quant)
    return sorted(
        p
        for p in candidates
        if matches_quant(p)
        and "/src/" in p
        and not p.rsplit("/", 1)[-1].startswith("__")
        and (root / p).is_file()
    )


def all_quant_source_modules(root: Path) -> list[str]:
    files = [
        str(p.relative_to(root)).replace(os.sep, "/")
        for prefix in _QUANT_SRC_PREFIXES
        for p in sorted((root / prefix).rglob("*.py"))
        if (root / prefix).is_dir()
    ]
    return quant_source_modules(root, files)


# ---------------------------------------------------------------------------
# CLI


def _reexec_with_pydantic(root: Path) -> None:
    """Re-exec under the project venv when pydantic is unavailable.

    Write paths (attest/override/ack) validate artifacts with pydantic, but the
    hooks' block messages must work even when invoked as plain ``python3``.
    """
    try:
        import pydantic  # noqa: F401

        return
    except ImportError:
        pass
    venv_python = root / ".venv" / "bin" / "python"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), *sys.argv])
    raise SystemExit(
        "pydantic unavailable and no project venv found — run via: "
        "uv run python scripts/gate.py ..."
    )


def _clear_token(root: Path, kind: str) -> int:
    dropped = disarm_token(root, kind)
    if dropped is None:
        print(f"no {kind} was armed; nothing to clear.")
        return 0
    print(f"armed {kind} dropped without being used (recorded in the journal).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The full CLI parser (built apart from ``main`` so every subcommand is testable)."""
    parser = argparse.ArgumentParser(prog="gate", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fast")
    sub.add_parser("full")
    check = sub.add_parser("check")
    check.add_argument("--tier", choices=("fast", "full"), default="fast")
    attest_p = sub.add_parser("attest")
    attest_p.add_argument("--kind", choices=("quant", "review"), required=True)
    _CLEAR_HELP = "drop an armed token without using it (recorded in the journal)"
    override_p = sub.add_parser("override")
    override_p.add_argument("--reason")
    override_p.add_argument("--clear", action="store_true", help=_CLEAR_HELP)
    ack_p = sub.add_parser("ack")
    ack_p.add_argument("--reason")
    ack_p.add_argument("--path", default=None)
    ack_p.add_argument("--clear", action="store_true", help=_CLEAR_HELP)
    owner_p = sub.add_parser("owner-init")
    owner_p.add_argument("--token", default=None, help="omit to be prompted (never echoed)")
    sub.add_parser("lint-harness")
    baseline_p = sub.add_parser("baseline")
    baseline_p.add_argument("--reason", required=True)
    audit_p = sub.add_parser("audit")
    audit_p.add_argument("--json", action="store_true")
    audit_p.add_argument("--since", default=None)
    audit_p.add_argument("--kind", default=None)
    audit_p.add_argument("--verify", action="store_true")
    audit_p.add_argument(
        "--digest",
        action="store_true",
        help=f"rolled-up escape/block summary (default {DIGEST_DEFAULT_DAYS}d)",
    )
    brief_p = sub.add_parser("brief")
    brief_p.add_argument("--refresh", action="store_true")
    plan_p = sub.add_parser("plan-check")
    plan_p.add_argument("plan", help="docs/superpowers/plans/<doc>.md with a ```json front block")
    index_p = sub.add_parser("index")
    index_p.add_argument("--no-cli", action="store_true")
    doctor_p = sub.add_parser("doctor")
    doctor_p.add_argument("--json", action="store_true")
    mutate_p = sub.add_parser("mutate")
    mutate_p.add_argument("modules", nargs="*", help="quant modules (default: changed in tree)")
    mutate_p.add_argument("--all", action="store_true", help="every quant-tier source module")
    mutate_p.add_argument("--json", action="store_true")
    mutate_p.add_argument("--write-baseline", default=None, metavar="REASON")
    mutate_p.add_argument("--timeout", type=float, default=1800.0, help="seconds per module")
    semgrep_p = sub.add_parser("semgrep")
    semgrep_p.add_argument("--changed", action="store_true", help="only changed .py files")
    sub.add_parser("determinism")
    raise_p = sub.add_parser("raise-cov")
    raise_p.add_argument("--fail", action="store_true", help="exit 1 on any uncovered raise")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    root = repo_root()
    if args.command in ("attest", "override", "ack", "baseline", "plan-check"):
        _reexec_with_pydantic(root)
    if args.command in ("fast", "full"):
        return run_gate(root, args.command)
    if args.command == "check":
        if stamp_is_valid(root, args.tier):
            print(f"stamp valid for tier {args.tier}")
            return 0
        print(f"no valid {args.tier} stamp for current tree — run gate.py {args.tier}")
        return 1
    if args.command == "attest":
        return attest(root, args.kind, sys.stdin.read())
    if args.command in ("override", "ack") and args.clear:
        return _clear_token(root, args.command)
    if args.command in ("override", "ack") and not args.reason:
        print(
            f"{args.command} needs --reason (or --clear to drop an armed one)",
            file=sys.stderr,
        )
        return 2
    if args.command == "override":
        allowed, who = authorize_escape(root, kind="override")
        if not allowed:
            print(f"override refused: {who}", file=sys.stderr)
            return 1
        write_override(root, reason=args.reason, authorized_by=who)
        print(f"one-shot commit override armed by {who} (loudly audited).")
        return 0
    if args.command == "ack":
        allowed, who = authorize_escape(root, kind="ack", path=args.path)
        if not allowed:
            print(f"ack refused: {who}", file=sys.stderr)
            return 1
        write_ack(root, reason=args.reason, authorized_by=who, path=args.path)
        print(f"one-shot governance ack armed by {who} (loudly audited).")
        return 0
    if args.command == "owner-init":
        token = args.token
        if token is None:
            import getpass

            token = getpass.getpass("owner token (min 12 chars, never stored in clear): ")
        try:
            owner_init(root, token)
        except ValueError as exc:
            print(f"owner-init refused: {exc}", file=sys.stderr)
            return 1
        print(f"owner token hash written to {OWNER_FILE}; export {OWNER_TOKEN_ENV} to authorize.")
        return 0
    if args.command == "lint-harness":
        problems = lint_harness(root)
        for problem in problems:
            print(f"[harness-lint] FAIL {problem}", file=sys.stderr)
        if not problems:
            print("[harness-lint] ok — no guardrail regressions vs baseline")
        return 1 if problems else 0
    if args.command == "baseline":
        allowed, who = authorize_escape(root, kind="baseline")
        if not allowed and consume_ack(root, path=str(BASELINE_FILE)) is None:
            print(f"baseline refused: {who}", file=sys.stderr)
            return 1
        write_baseline(root, reason=args.reason, authorized_by=who if allowed else "ack")
        print(f"harness baseline rewritten at {BASELINE_FILE} (loudly audited).")
        return 0
    if args.command == "audit":
        if args.digest:
            print(audit_digest(root, since=args.since))
            return 0
        if args.verify:
            ok, detail = verify_audit_chain(root)
            print(f"[audit] {'ok' if ok else 'FAIL'} {detail}")
            return 0 if ok else 1
        events = read_audit(root, since=args.since, kind=args.kind)
        if args.json:
            print(json.dumps(events, indent=2, sort_keys=True))
        else:
            for item in events:
                print(f"{item.get('ts')} {item.get('event')} {item.get('detail')}")
        return 0
    if args.command == "brief":
        from harness_awareness import repo_brief

        print(repo_brief(root, refresh=args.refresh))
        return 0
    if args.command == "plan-check":
        from harness_awareness import plan_check

        ok, message = plan_check(Path(args.plan))
        print(message, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    if args.command == "index":
        from harness_awareness import write_index

        path = write_index(root, cli=not args.no_cli)
        print(f"repo index written to {path.relative_to(root)}")
        return 0
    if args.command == "doctor":
        code, report = doctor(root)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
            return code
        for check_row in report["checks"]:
            marker = "ok " if check_row["ok"] else "FAIL"
            print(f"[doctor] {marker} {check_row['name']} — {check_row['detail']}")
        return code
    if args.command == "mutate":
        from harness_quant import MUTATION_BASELINE_FILE, mutate, write_mutation_baseline

        modules = all_quant_source_modules(root) if args.all else (args.modules or None)
        code, report = mutate(root, modules, timeout=args.timeout)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            for rel, entry in report["modules"].items():
                print(f"[mutate] {entry['status']:<8} {rel} {entry}")
            if not report["modules"]:
                print("[mutate] no quant-tier source modules to mutate")
        if args.write_baseline is not None:
            allowed, who = authorize_escape(root, kind="baseline")
            if not allowed and consume_ack(root, path=str(MUTATION_BASELINE_FILE)) is None:
                print(f"mutation baseline refused: {who}", file=sys.stderr)
                return 1
            write_mutation_baseline(
                root, report, reason=args.write_baseline, by=who if allowed else "ack"
            )
            print(f"mutation baseline written at {MUTATION_BASELINE_FILE} (loudly audited).")
        return code
    if args.command == "semgrep":
        from harness_quant import semgrep

        return semgrep(root, changed_only=args.changed)
    if args.command == "determinism":
        from harness_quant import determinism

        ok, detail = determinism(root)
        print(f"[determinism] {'ok' if ok else 'FAIL'} {detail}")
        return 0 if ok else 1
    if args.command == "raise-cov":
        from harness_quant import raise_cov

        uncovered, total = raise_cov(root)
        for site in uncovered:
            print(f"[raise-cov] uncovered {site}")
        print(f"[raise-cov] {len(uncovered)} of {total} raise sites in quant modules unreached")
        return 1 if (args.fail and uncovered) else 0
    return 2  # pragma: no cover - argparse enforces choices


if __name__ == "__main__":
    raise SystemExit(main())
