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
import ast
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
import tomllib
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
    "instructions-loaded",
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
        "scripts/harness_models.py",
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
    "scripts/harness_models.py",
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
# Repo awareness: generated brief + repo index (derived from the tree, never remembered)

BRIEF_FILE = "brief.json"
INDEX_FILE = "repo-index.json"
_PLAN_DONE_RE = re.compile(r"delivery state:\*{0,2}\s*(completed|delivered|done)", re.I)
_ADR_ID_RE = re.compile(r"^(\d{4})-")
_WATCHOUT_HEADING_RE = re.compile(r"^##+\s*watch-?outs", re.I)


def _git_lines(root: Path, *args: str) -> list[str]:
    return [line for line in _git(root, *args, check=False).splitlines() if line.strip()]


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
    branch = _git(root, "branch", "--show-current", check=False).strip() or "?"
    dirty = len(_git_lines(root, "status", "--porcelain"))
    stamp = {
        "full": "full (valid)",
        "fast": "fast (valid; full needed to commit)",
    }.get(stamp_tier(root), "none/stale")
    lines = [
        "REPO BRIEF (generated from the tree by gate.py brief):",
        f"- branch {branch}, {dirty} dirty file(s), gate stamp {stamp}",
    ]
    commits = _git_lines(root, "log", "--oneline", "-5")
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
        for e in read_audit(
            root, since=(datetime.now(UTC) - timedelta(days=DIGEST_DEFAULT_DAYS)).isoformat()
        )
        if str(e.get("event")) in ESCAPE_EVENTS
    ]
    if escapes:
        note = " (owner token unset — all self-serve)" if not owner_token_configured(root) else ""
        lines.append(
            f"- escapes: {len(escapes)} self-authorized in the last {DIGEST_DEFAULT_DAYS}d{note}"
            " — gate.py audit --digest"
        )
    else:
        lines.append(f"- escapes: none in the last {DIGEST_DEFAULT_DAYS}d")
    drift = adr_drift(root)
    if drift:
        lines.append(
            f"- DRIFT: {', '.join(drift)} not referenced in CLAUDE.md/.claude/rules — fix the docs"
        )
    return "\n".join(lines)


def _brief_cache_key(root: Path) -> str:
    """Tree content plus the git facts the brief reports that the tree hash cannot see.

    ``compute_tree_hash`` covers file bytes only — deliberately, so that committing does not
    invalidate a gate stamp. But the brief also reports HEAD and the dirty count, and a plain
    commit changes both while touching no byte on disk. Keyed on content alone the cache would
    keep serving a brief that claims uncommitted files and omits the commit just made.
    """
    head = _git(root, "rev-parse", "HEAD", check=False).strip() or "?"
    branch = _git(root, "branch", "--show-current", check=False).strip() or "?"
    return f"{compute_tree_hash(root)}:{head}:{branch}"


def repo_brief(root: Path, *, refresh: bool = False) -> str:
    """The brief, cached at .claude/state/brief.json keyed by tree content and git position."""
    key = _brief_cache_key(root)
    cache_path = _state_dir(root) / BRIEF_FILE
    cached = read_json(cache_path)
    if (
        not refresh
        and cached
        and cached.get("cache_key") == key
        and isinstance(cached.get("text"), str)
    ):
        return str(cached["text"])
    text = build_brief(root)
    write_json_atomic(cache_path, {"cache_key": key, "generated_at": _now(), "text": text})
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
        "tree_hash": compute_tree_hash(root),
        "generated_at": _now(),
        "packages": packages,
        "import_linter_contracts": contracts,
        "cli_commands": cli_commands,
        "mcp_tool_count": mcp_tools,
        "figure_ids": figures,
        "adrs": adr_files(root),
    }


def write_index(root: Path, *, cli: bool = True) -> Path:
    path = _state_dir(root) / INDEX_FILE
    write_json_atomic(path, build_index(root, cli=cli))
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


def _glob_rel(root: Path, globs: tuple[str, ...]) -> list[str]:
    """Repo-relative paths matching any of ``globs``, deduped and sorted."""
    return sorted({str(p.relative_to(root)) for pattern in globs for p in root.glob(pattern)})


# ---------------------------------------------------------------------------
# quant-rigor tooling (W5): mutation gate, semgrep, determinism double-run, raise-site coverage

SEMGREP_RULES = Path(".semgrep") / "alpha.yml"
MUTATION_BASELINE_FILE = Path(".claude") / "mutation-baseline.json"
MUTATION_MIN_KILL = 0.90
MUTATION_TOLERANCE = 0.005  # a mutant flipping on timing must not flap the verdict
_MUTATION_TEST_DIRS = ("unit", "oracles", "bias_guards")
_DETERMINISM_TEST_GLOBS = (
    "tests/**/test_*determinism*.py",
    "tests/**/test_*identity*.py",
    "tests/**/test_*golden*.py",
)
_DETERMINISM_ENVS = (
    {"PYTHONHASHSEED": "0", "TZ": "UTC", "OMP_NUM_THREADS": "1"},
    {"PYTHONHASHSEED": "31337", "TZ": "Pacific/Kiritimati", "OMP_NUM_THREADS": "1"},
)


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


def stage_mutation_tree(root: Path, modules: list[str], staging: Path) -> list[str]:
    """Copy each module's package + the tests that mention it into ``staging`` for mutmut.

    mutmut inserts only ``mutants/{.,src,source}`` into ``sys.path``, so the uv-workspace
    layout (``packages/<pkg>/src/<pkg>``) is flattened to ``src/<pkg>``. Test selection is
    textual on purpose (a test that never names the package cannot kill its mutants).
    """
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "src").mkdir(parents=True)
    only: list[str] = []
    packages: set[str] = set()
    for rel in modules:
        pkg_root, _, inner = rel.partition("/src/")
        pkg = inner.split("/")[0]
        packages.add(pkg)
        if not (staging / "src" / pkg).exists():
            shutil.copytree(
                root / pkg_root / "src" / pkg,
                staging / "src" / pkg,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            # tests that inspect source by repo-relative path (e.g. the figure renderer's
            # "never twinx" AST scan) need the workspace layout mirrored too (unmutated copy)
            shutil.copytree(
                root / pkg_root / "src" / pkg,
                staging / pkg_root / "src" / pkg,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        only.append(f"src/{inner}")
    tests_root = root / "tests"
    (staging / "tests").mkdir()
    for top in tests_root.glob("*.py"):
        shutil.copy2(top, staging / "tests" / top.name)
    if (tests_root / "fixtures").is_dir():
        shutil.copytree(tests_root / "fixtures", staging / "tests" / "fixtures")
    candidates: dict[Path, str] = {}
    for name in _MUTATION_TEST_DIRS:
        source_dir = tests_root / name
        if source_dir.is_dir():
            for path in sorted(source_dir.rglob("*.py")):
                candidates[path.relative_to(tests_root)] = path.read_text(errors="replace")
    keep: set[Path] = {
        rel_path
        for rel_path, text in candidates.items()
        if rel_path.name == "__init__.py"
        or "_reference" in rel_path.parts
        or any(
            re.search(rf"^\s*(from|import)\s+{re.escape(pkg)}\b", text, re.M) for pkg in packages
        )
    }
    # close over intra-``tests`` imports (``from tests.unit.x import helper``) so a kept test
    # never fails on a sibling module that the textual selection left behind
    frontier = list(keep)
    while frontier:
        text = candidates[frontier.pop()]
        for dotted in re.findall(r"^\s*from\s+tests\.([\w.]+)\s+import", text, re.M):
            sibling = Path(*dotted.split(".")).with_suffix(".py")
            if sibling in candidates and sibling not in keep:
                keep.add(sibling)
                frontier.append(sibling)
    for rel_path in sorted(keep):
        target = staging / "tests" / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tests_root / rel_path, target)
    markers: list[str] = []
    try:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text())
        markers = list(pyproject["tool"]["pytest"]["ini_options"].get("markers", []))
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        markers = []
    (staging / "pyproject.toml").write_text(
        "[tool.mutmut]\n"
        f"source_paths = {json.dumps([f'src/{pkg}' for pkg in sorted(packages)])}\n"
        f"only_mutate = {json.dumps(only)}\n"
        'also_copy = ["packages"]\n'
        'pytest_add_cli_args_test_selection = ["tests"]\n'
        f"pytest_add_cli_args = {json.dumps(_MUTATION_PYTEST_ARGS)}\n"
        "use_git_change_detection = false\n"
        "track_dependencies = false\n"
        "\n[tool.pytest.ini_options]\n"
        'addopts = "--strict-markers --import-mode=importlib"\n'
        'pythonpath = [".", "src"]\n'
        f"markers = {json.dumps(markers)}\n"
    )
    return only


_MUTATION_PYTEST_ARGS = ["-p", "no:cacheprovider", "-q", "-x"]


def staging_only_failures(output: str) -> list[str]:
    """pytest ``-rfE`` short-summary lines → deselect/ignore args for tests that fail in staging.

    A test that reads the repo by relative path (a stylesheet, a docs file, ``.claude/``) fails
    in the flattened mutation tree through no fault of the module under test; excluding it is
    conservative (fewer killers) and is recorded in the report, never silent.
    """
    args: list[str] = []
    for line in output.splitlines():
        if line.startswith("FAILED "):
            args += ["--deselect", line[len("FAILED ") :].split(" - ", 1)[0].strip()]
        elif line.startswith("ERROR "):
            args += ["--ignore", line[len("ERROR ") :].split(" - ", 1)[0].split("::", 1)[0]]
    return args


def mutation_kill_rate(stats: dict[str, Any]) -> float:
    denominator = int(stats.get("total", 0)) - int(stats.get("skipped", 0))
    return int(stats.get("killed", 0)) / denominator if denominator > 0 else 0.0


def mutation_required(module: str, baseline: dict[str, float]) -> float:
    """Kill-rate floor: 0.90, or the recorded (lower) baseline so a legacy module cannot regress."""
    recorded = baseline.get(module)
    return MUTATION_MIN_KILL if recorded is None else min(MUTATION_MIN_KILL, float(recorded))


def mutate(
    root: Path,
    modules: list[str] | None = None,
    *,
    runner: EnvRunner | None = None,
    timeout: float = 1800.0,
) -> tuple[int, dict[str, Any]]:
    """Mutation-test each quant module in isolation; block on a kill-rate below its floor.

    Tooling absence (no ``uvx``/network for mutmut, staged clean-run failure) is reported as
    ``unavailable:<reason>`` and never blocks — but it is printed and audited, never silent.
    """
    run = runner or _env_runner
    targets = quant_source_modules(root) if modules is None else quant_source_modules(root, modules)
    baseline_raw = read_json(root / MUTATION_BASELINE_FILE) or {}
    baseline = {k: float(v) for k, v in baseline_raw.get("kill_rates", {}).items()}
    report: dict[str, Any] = {"modules": {}, "min_kill": MUTATION_MIN_KILL}
    blocking = False
    for rel in targets:
        staging = _state_dir(root) / "mutation" / Path(rel).stem
        stage_mutation_tree(root, [rel], staging)
        entry: dict[str, Any] = {}
        # staged clean run: exclude tests that fail only because of the flattened layout
        preflight = ["uv", "run", "--project", str(root), "pytest", "-q", "-rfE"]
        preflight += ["-p", "no:cacheprovider", "--continue-on-collection-errors", "tests"]
        pre_ok, pre_seconds, pre_out = run(preflight, cwd=staging, timeout=timeout)
        excluded = [] if pre_ok else staging_only_failures(pre_out)
        if excluded:
            entry["excluded_tests"] = sorted({t.split("[", 1)[0] for t in excluded[1::2]})
            pyproject_path = staging / "pyproject.toml"
            pyproject_path.write_text(
                pyproject_path.read_text().replace(
                    json.dumps(_MUTATION_PYTEST_ARGS),
                    json.dumps([*_MUTATION_PYTEST_ARGS, *excluded]),
                )
            )
        mutmut = ["uv", "run", "--project", str(root), "--with", "mutmut", "mutmut"]
        ok, seconds, output = run([*mutmut, "run"], cwd=staging, timeout=timeout)
        entry["seconds"] = round(seconds + pre_seconds, 1)
        stats_path = staging / "mutants" / "mutmut-cicd-stats.json"
        if ok:
            run([*mutmut, "export-cicd-stats"], cwd=staging, timeout=120)
        stats = read_json(stats_path) if ok else None
        if stats is None:
            entry["status"] = f"unavailable:{output[-300:] or 'mutmut produced no stats'}"
        else:
            rate = mutation_kill_rate(stats)
            required = mutation_required(rel, baseline)
            entry.update(
                {
                    "killed": stats.get("killed"),
                    "survived": stats.get("survived"),
                    "total": stats.get("total"),
                    # module-scope mutants (constants, catalog data) that mutmut's function
                    # tracer cannot attribute to a test; counted as NOT killed (conservative)
                    "no_tests": stats.get("no_tests"),
                    "timeout": stats.get("timeout"),
                    "kill_rate": round(rate, 4),
                    "required": round(required, 4),
                }
            )
            if rate + MUTATION_TOLERANCE < required:
                entry["status"] = "fail"
                blocking = True
            else:
                entry["status"] = "pass"
        report["modules"][rel] = entry
        append_audit(root, "mutation_gate", f"module={rel} status={entry['status']}")
        shutil.rmtree(staging, ignore_errors=True)
    return (1 if blocking else 0), report


def write_mutation_baseline(root: Path, report: dict[str, Any], *, reason: str, by: str) -> None:
    current = read_json(root / MUTATION_BASELINE_FILE) or {}
    rates = dict(current.get("kill_rates", {}))
    for rel, entry in report.get("modules", {}).items():
        if "kill_rate" in entry:
            rates[rel] = entry["kill_rate"]
    write_json_atomic(
        root / MUTATION_BASELINE_FILE,
        {"schema_version": 1, "kill_rates": dict(sorted(rates.items()))},
    )
    append_audit(root, "mutation_baseline_written", f"by={by} reason={reason!r}")


_SEMGREP_BASE = (
    "uvx",
    "semgrep",
    "--config",
    str(SEMGREP_RULES),
    "--metrics=off",
    "--quiet",
    "--error",
)


def semgrep_command(root: Path, paths: list[str]) -> list[str]:
    """``uvx semgrep`` over the given python paths (empty list ⇒ nothing to scan ⇒ ``[]``)."""
    targets = sorted(p for p in paths if p.endswith(".py") and (root / p).is_file())
    return [*_SEMGREP_BASE, *targets] if targets else []


def semgrep(root: Path, *, changed_only: bool) -> int:
    if changed_only:
        paths = scoped_changed_paths(root, lambda p: p.endswith(".py"))
        cmd = semgrep_command(root, paths)
    else:
        cmd = [*_SEMGREP_BASE, "packages", "apps", "scripts", "tests"]
    if not cmd:
        print("[semgrep] no python changes to scan")
        return 0
    ok, seconds, output = _env_runner(cmd, cwd=root, timeout=600)
    if ok:
        print(f"[semgrep] ok ({seconds:.1f}s)")
        return 0
    if "command not found" in output or "No such file" in output or "OSError" in output:
        print(f"[semgrep] unavailable: {output[-200:]}", file=sys.stderr)
        append_audit(root, "semgrep_unavailable", output[-200:])
        return 0
    print(output[-4000:], file=sys.stderr)
    return 1


def raise_sites(path: Path) -> list[int]:
    """Line numbers of every ``raise`` statement in a module (the fail-loud surface)."""
    tree = ast.parse(path.read_text(errors="replace"))
    return sorted(node.lineno for node in ast.walk(tree) if isinstance(node, ast.Raise))


def uncovered_raise_sites(root: Path, coverage_json: Path, modules: list[str]) -> list[str]:
    data = read_json(coverage_json) or {}
    files = data.get("files", {})
    out: list[str] = []
    for rel in modules:
        entry = files.get(rel) or files.get(str(root / rel)) or {}
        missing = set(entry.get("missing_lines", []))
        out.extend(f"{rel}:{ln}" for ln in raise_sites(root / rel) if ln in missing)
    return out


def raise_cov(root: Path) -> tuple[list[str], int]:
    """Run the quant test tiers with branch coverage; list ``raise`` lines no test reached."""
    modules = all_quant_source_modules(root)
    cov_json = _state_dir(root) / "raise-cov.json"
    cov_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "uv", "run", "pytest", "-q", "-p", "no:cacheprovider",
        "-m", "not network and not slow_oracle",
        "--cov=alpha_validation", "--cov=alpha_research", "--cov-branch",
        f"--cov-report=json:{cov_json}", "--cov-fail-under=0",
        "tests/unit", "tests/oracles", "tests/bias_guards",
    ]  # fmt: skip
    ok, _, output = _env_runner(cmd, cwd=root, timeout=3600)
    if not ok:
        print(output[-4000:], file=sys.stderr)
        return (["<test run failed>"], 0)
    total = sum(len(raise_sites(root / rel)) for rel in modules)
    return uncovered_raise_sites(root, cov_json, modules), total


def determinism(root: Path, *, runner: EnvRunner | None = None) -> tuple[bool, str]:
    """Run the byte-stability / identity / golden tests twice in fresh processes.

    Each pass perturbs ``PYTHONHASHSEED``, ``TZ`` and pins ``OMP_NUM_THREADS=1``; the tests
    themselves compare artifacts against committed goldens, so two green passes under different
    process environments is the cross-process determinism evidence.
    """
    run = runner or _env_runner
    files = _glob_rel(root, _DETERMINISM_TEST_GLOBS)
    if not files:
        return (False, "no determinism tests found")
    for i, overrides in enumerate(_DETERMINISM_ENVS, start=1):
        env = {**os.environ, **overrides}
        ok, seconds, output = run(
            ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", *files],
            cwd=root,
            env=env,
            timeout=3600,
        )
        if not ok:
            return (False, f"pass {i} failed under {overrides}: {output[-1500:]}")
    return (True, f"2 passes green over {len(files)} file(s) under perturbed env")


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
        print(repo_brief(root, refresh=args.refresh))
        return 0
    if args.command == "plan-check":
        ok, message = plan_check(Path(args.plan))
        print(message, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    if args.command == "index":
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
        return semgrep(root, changed_only=args.changed)
    if args.command == "determinism":
        ok, detail = determinism(root)
        print(f"[determinism] {'ok' if ok else 'FAIL'} {detail}")
        return 0 if ok else 1
    if args.command == "raise-cov":
        uncovered, total = raise_cov(root)
        for site in uncovered:
            print(f"[raise-cov] uncovered {site}")
        print(f"[raise-cov] {len(uncovered)} of {total} raise sites in quant modules unreached")
        return 1 if (args.fail and uncovered) else 0
    return 2  # pragma: no cover - argparse enforces choices


if __name__ == "__main__":
    raise SystemExit(main())
