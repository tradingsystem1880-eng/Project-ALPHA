"""Claude Code harness gate runner for Project ALPHA.

One source of truth for: the tree-hash stamp protocol, the three path tiers
(quant / risk / protected control plane), attestation artifacts, one-shot
override/ack tokens, the append-only audit journal, and the harness doctor.

Top level is stdlib-only so hook shims can import it before ``uv sync`` has
ever run; pydantic validation (scripts/harness_models.py) is imported lazily
inside write paths and degrades to a loud error if unavailable.

CLI:
    python3 scripts/gate.py fast|full          # run the tiered gate, stamp on success
    python3 scripts/gate.py check --tier fast  # exit 0 iff a valid stamp covers the tier
    python3 scripts/gate.py attest --kind quant|review   # JSON report on stdin
    python3 scripts/gate.py override --reason "..."      # one-shot commit-gate override
    python3 scripts/gate.py ack --reason "..."           # one-shot control-plane edit ack
    python3 scripts/gate.py doctor             # verify the harness wiring itself
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_DIR = Path(".claude") / "state"
STAMP_FILE = "gate-stamp.json"
AUDIT_FILE = "harness-audit.jsonl"
OVERRIDE_FILE = "commit-override.json"
ACK_FILE = "governance-ack.json"
QUANT_ATTESTATION_FILE = "quant-attestation.json"
REVIEW_VERDICT_FILE = "review-verdict.json"

TIER_RANK = {"fast": 1, "full": 2}

# claude_hooks.py subcommands; doctor verifies every one is wired in settings.json.
HOOK_NAMES = (
    "post-edit",
    "pre-edit-guard",
    "pre-bash-guard",
    "stop-guard",
    "session-start",
    "prompt-context",
    "pre-compact",
)

_QUANT_NAME_RE = re.compile(
    r"(dsr|psr|pbo|deflated|bootstrap|reality_check|spa|montecarlo|"
    r"walkforward|cpcv|multiple_testing|overfitting)"
)
_RISK_CLI_FILES = frozenset(
    f"apps/alpha-cli/src/alpha_cli/{name}.py"
    for name in ("_gauntlet", "_optim", "_seeds", "_identity", "_surrogate", "_synth", "_runner")
)
_PYPROJECT_GUARDED = ("[tool.importlinter]", "fail_under", "strict")

Runner = Callable[[list[str]], tuple[bool, float, str]]


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


def _untracked_paths(root: Path) -> list[str]:
    status = _git(root, "status", "--porcelain=v2", "-z", "--untracked-files=all")
    untracked: list[str] = []
    for entry in status.split("\0"):
        if entry.startswith("? "):
            untracked.append(entry[2:])
    return untracked


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


def scoped_diff_hash(root: Path, matcher: Callable[[str], bool]) -> str:
    """sha256 of the working diff restricted to paths accepted by ``matcher``.

    Binds quant attestations to the quant-scope diff only, so out-of-scope
    edits (docs, unrelated code) do not invalidate an attestation while any
    in-scope change does.
    """
    hasher = hashlib.sha256()
    changed = _git(root, "status", "--porcelain=v2", "-z", "--untracked-files=all")
    scoped_tracked: list[str] = []
    for entry in changed.split("\0"):
        if not entry:
            continue
        path = entry.split(" ")[-1] if not entry.startswith("? ") else entry[2:]
        if matcher(path):
            if entry.startswith("? "):
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


def matches_quant(path: str) -> bool:
    """Statistical source code requiring academic verification before Stop."""
    posix = path.replace("\\", "/")
    if posix.startswith(("packages/alpha-validation/src/", "packages/alpha-research/src/")):
        return posix.endswith(".py")
    if posix.startswith("packages/") and "/src/" in posix and posix.endswith(".py"):
        return bool(_QUANT_NAME_RE.search(posix.rsplit("/", 1)[-1]))
    return False


def matches_risk(path: str) -> bool:
    """Risk-tier paths requiring an independent APPROVE review before commit."""
    posix = path.replace("\\", "/")
    if matches_quant(posix):
        return True
    if posix.startswith("packages/alpha-backtest/src/") and posix.endswith(".py"):
        return True
    return posix in _RISK_CLI_FILES


def protected_reason(path: str, content: str = "") -> str | None:
    """Control-plane paths whose edits need a one-shot governance ack."""
    posix = path.replace("\\", "/")
    if posix in (
        "scripts/gate.py",
        "scripts/claude_hooks.py",
        "scripts/harness_models.py",
        ".claude/settings.json",
        ".github/workflows/ci.yml",
        "CLAUDE.md",
    ):
        return f"{posix} is harness/governance control plane"
    if posix.startswith((".claude/skills/", "tests/bias_guards/")):
        return f"{posix} is harness/governance control plane"
    if posix == "pyproject.toml":
        for marker in _PYPROJECT_GUARDED:
            if marker in content:
                return f"pyproject.toml edit touches guarded config ({marker!r})"
    return None


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


def append_audit(root: Path, event: str, detail: str, session_id: str = "") -> None:
    line = {
        "ts": _now(),
        "session_id": session_id or os.environ.get("CLAUDE_SESSION_ID", ""),
        "event": event,
        "detail": detail,
        "tree_hash": compute_tree_hash(root),
    }
    journal = _state_dir(root) / AUDIT_FILE
    with journal.open("a") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")


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


def stamp_is_valid(root: Path, tier: str) -> bool:
    stamp = read_json(_state_dir(root) / STAMP_FILE)
    if stamp is None:
        return False
    have = TIER_RANK.get(str(stamp.get("tier")), 0)
    if have < TIER_RANK[tier]:
        return False
    return stamp.get("tree_hash") == compute_tree_hash(root)


# ---------------------------------------------------------------------------
# attestations


def attest(root: Path, kind: str, payload_text: str) -> int:
    """Validate an agent-produced report and persist it bound to current state."""
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

    if kind == "quant":
        try:
            report = QuantVerificationReport.model_validate(payload)
        except ValueError as exc:
            print(f"attest rejected: {exc}", file=sys.stderr)
            return 1
        if report.overall != "PASS":
            print("attest rejected: overall must be PASS to attest", file=sys.stderr)
            return 1
        artifact = QuantAttestation(
            created_at=_now(),
            bound_quant_diff_hash=scoped_diff_hash(root, matches_quant),
            report=report,
        )
        write_json_atomic(_state_dir(root) / QUANT_ATTESTATION_FILE, artifact.model_dump())
        append_audit(root, "quant_attested", f"claims={len(report.claims)}")
        return 0

    if kind == "review":
        try:
            verdict = ReviewVerdict.model_validate(payload)
        except ValueError as exc:
            print(f"attest rejected: {exc}", file=sys.stderr)
            return 1
        if verdict.verdict != "APPROVE":
            print("attest rejected: verdict must be APPROVE to attest", file=sys.stderr)
            return 1
        if verdict.reviewed_tree_hash != compute_tree_hash(root):
            print(
                "attest rejected: reviewed_tree_hash is stale — the tree changed "
                "since review; re-run /review-gate",
                file=sys.stderr,
            )
            return 1
        review_artifact = ReviewAttestation(created_at=_now(), verdict=verdict)
        write_json_atomic(_state_dir(root) / REVIEW_VERDICT_FILE, review_artifact.model_dump())
        append_audit(root, "review_attested", f"findings={len(verdict.findings)}")
        return 0

    print(f"attest rejected: unknown kind {kind!r}", file=sys.stderr)
    return 2


def quant_attestation_valid(root: Path) -> bool:
    artifact = read_json(_state_dir(root) / QUANT_ATTESTATION_FILE)
    if artifact is None:
        return False
    return artifact.get("bound_quant_diff_hash") == scoped_diff_hash(root, matches_quant)


def review_verdict_valid(root: Path) -> bool:
    artifact = read_json(_state_dir(root) / REVIEW_VERDICT_FILE)
    if artifact is None:
        return False
    verdict = artifact.get("verdict")
    if not isinstance(verdict, dict) or verdict.get("verdict") != "APPROVE":
        return False
    return verdict.get("reviewed_tree_hash") == compute_tree_hash(root)


# ---------------------------------------------------------------------------
# one-shot tokens


def _write_token(root: Path, filename: str, event: str, reason: str) -> None:
    from harness_models import OnceToken

    token = OnceToken(created_at=_now(), reason=reason)
    write_json_atomic(_state_dir(root) / filename, token.model_dump())
    append_audit(root, event, reason)


def write_override(root: Path, *, reason: str) -> None:
    _write_token(root, OVERRIDE_FILE, "override_written", reason)


def write_ack(root: Path, *, reason: str) -> None:
    _write_token(root, ACK_FILE, "ack_written", reason)


def _consume(root: Path, filename: str, event: str) -> dict[str, Any] | None:
    path = _state_dir(root) / filename
    token = read_json(path)
    if token is None:
        return None
    path.unlink(missing_ok=True)
    append_audit(root, event, str(token.get("reason", "")))
    return token


def consume_override(root: Path) -> dict[str, Any] | None:
    return _consume(root, OVERRIDE_FILE, "override_consumed")


def consume_ack(root: Path) -> dict[str, Any] | None:
    return _consume(root, ACK_FILE, "ack_consumed")


# ---------------------------------------------------------------------------
# gate execution


def _default_runner(cmd: list[str]) -> tuple[bool, float, str]:
    started = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
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


def gate_steps(tier: str) -> list[tuple[str, list[str]]]:
    fast: list[tuple[str, list[str]]] = [
        ("ruff check", ["uv", "run", "ruff", "check", "."]),
        ("ruff format", ["uv", "run", "ruff", "format", "--check", "."]),
        ("import contracts", ["uv", "run", "lint-imports"]),
        ("mypy", ["uv", "run", "mypy", "packages", "apps", "tests"]),
        ("mypy harness", ["uv", "run", "mypy", "scripts/gate.py", "scripts/claude_hooks.py"]),
    ]
    if tier == "fast":
        return fast
    return [
        ("uv lock", ["uv", "lock", "--check"]),
        ("uv sync", ["uv", "sync", "--locked"]),
        *fast,
        (
            "pytest + coverage",
            ["uv", "run", "pytest", "-q", "-m", "not network", "--cov"],
        ),
        (
            "openapi freshness",
            ["uv", "run", "python", "scripts/generate_web_openapi.py", "--check"],
        ),
        ("build wheels", ["uv", "build", "--all-packages"]),
        ("wheel smoke", ["bash", "-c", _WHEEL_SMOKE_SH]),
    ]


def run_gate(root: Path, tier: str, *, runner: Runner | None = None) -> int:
    """Run the tiered gate; stamp only on full success. Mirrors CI's check job."""
    run = runner or _default_runner
    clear_stamp(root)
    started = time.monotonic()
    steps: list[tuple[str, float, bool]] = []
    for name, cmd in gate_steps(tier):
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


def doctor(root: Path) -> tuple[int, dict[str, Any]]:
    checks: list[tuple[str, bool, str]] = []

    settings_path = root / ".claude" / "settings.json"
    settings = read_json(settings_path)
    checks.append(("settings.json parses", settings is not None, str(settings_path)))

    wired = json.dumps(settings.get("hooks", {})) if settings else ""
    for name in HOOK_NAMES:
        checks.append((f"hook wired: {name}", name in wired, "settings.json hooks block"))

    for rel in ("scripts/gate.py", "scripts/claude_hooks.py", "scripts/harness_models.py"):
        checks.append((f"file present: {rel}", (root / rel).is_file(), rel))

    statusline = root / ".claude" / "statusline.py"
    checks.append(("statusline present", statusline.is_file(), str(statusline)))

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gate", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fast")
    sub.add_parser("full")
    check = sub.add_parser("check")
    check.add_argument("--tier", choices=("fast", "full"), default="fast")
    attest_p = sub.add_parser("attest")
    attest_p.add_argument("--kind", choices=("quant", "review"), required=True)
    override_p = sub.add_parser("override")
    override_p.add_argument("--reason", required=True)
    ack_p = sub.add_parser("ack")
    ack_p.add_argument("--reason", required=True)
    sub.add_parser("doctor")
    args = parser.parse_args(argv)

    root = repo_root()
    if args.command in ("attest", "override", "ack"):
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
    if args.command == "override":
        write_override(root, reason=args.reason)
        print("one-shot commit override armed (loudly audited).")
        return 0
    if args.command == "ack":
        write_ack(root, reason=args.reason)
        print("one-shot governance ack armed (loudly audited).")
        return 0
    if args.command == "doctor":
        code, report = doctor(root)
        for check_row in report["checks"]:
            marker = "ok " if check_row["ok"] else "FAIL"
            print(f"[doctor] {marker} {check_row['name']} — {check_row['detail']}")
        return code
    return 2  # pragma: no cover - argparse enforces choices


if __name__ == "__main__":
    raise SystemExit(main())
