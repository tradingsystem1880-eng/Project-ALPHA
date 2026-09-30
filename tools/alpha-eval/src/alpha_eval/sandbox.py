"""SUT isolation: an answer-key-free workspace, per-trial data sandboxes, integrity evidence.

Isolation layers (none alone is sufficient; each is recorded per trial):
1. Workspace: `git archive HEAD` minus tools/alpha-eval into a directory with no `.git` (no history,
   no answer keys, no `.env`, no `data/`), with its own `.venv` from `uv sync --locked`.
2. Data: per-trial ALPHA_DATA_DIR/ALPHA_BULK_DATA_DIR sandbox on the SUT process and MCP server.
3. Permissions: explicit tool list, allow-list, dontAsk mode, strict MCP config.
4. Evidence: before/after fingerprints of the owner's data/control and git status, and a canary
   string that only exists in hidden truth files — if it appears in a trajectory, the SUT read them.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpha_eval.platform import repo_root

EXCLUDED_FROM_WORKSPACE = (
    "tools/alpha-eval",
    "docs/audit",
    "docs/superpowers/plans",
    "tests/holdout_seed",
    "tests/holdout",
    ".codex",
    ".claude",
    ".mcp.json",
    "data",
    ".env",
    "scripts/schemas/codex_judge.json",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root()), *args], capture_output=True, text=True, check=True
    ).stdout


def head_sha() -> str:
    return _git("rev-parse", "HEAD").strip()


def prepare_workspace(dest: Path, ref: str = "HEAD") -> dict[str, Any]:
    """Export `ref` without the benchmark, copy project Claude settings, install its venv."""
    if dest.exists():
        marker = dest / ".alpha-eval-workspace.json"
        if marker.exists():
            info: dict[str, Any] = json.loads(marker.read_text(encoding="utf-8"))
            if info.get("ref_sha") == _git("rev-parse", ref).strip() and info.get(
                "excluded"
            ) == list(EXCLUDED_FROM_WORKSPACE):
                return info
        raise FileExistsError(f"Workspace mismatch; preserve existing export: {dest}")
    dest.mkdir(parents=True)
    with tempfile.NamedTemporaryFile(suffix=".tar") as tmp:
        subprocess.run(
            ["git", "-C", str(repo_root()), "archive", "--format=tar", "-o", tmp.name, ref],
            check=True,
        )
        with tarfile.open(tmp.name) as tar:
            members = [
                m
                for m in tar.getmembers()
                if not any(
                    m.name == ex or m.name.startswith(ex + "/") for ex in EXCLUDED_FROM_WORKSPACE
                )
            ]
            tar.extractall(dest, members=members, filter="data")
    subprocess.run(["uv", "sync", "--locked", "-q"], cwd=dest, check=True)
    info = {
        "ref": ref,
        "ref_sha": _git("rev-parse", ref).strip(),
        "excluded": list(EXCLUDED_FROM_WORKSPACE),
        "skills_sha256": tree_hash(dest / ".agents" / "skills"),
        "claude_md_sha256": file_hash(dest / "CLAUDE.md"),
        "mcp_server_sha256": file_hash(
            dest / "apps" / "alpha-mcp" / "src" / "alpha_mcp" / "server.py"
        ),
        "uv_lock_sha256": file_hash(dest / "uv.lock"),
    }
    (dest / ".alpha-eval-workspace.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return ""
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def owner_state_fingerprint() -> dict[str, str]:
    """Fingerprint of owner state the SUT must never touch."""
    control = repo_root() / "data" / "control"
    return {
        "data_control": tree_hash(control),
        "git_status": hashlib.sha256(_git("status", "--porcelain").encode()).hexdigest(),
    }


def owner_state_unchanged(integrity: dict[str, Any]) -> bool:
    """Owner data/control must be byte-identical across the trial.

    The repo's git status is recorded but not judged: the SUT has no git access and works in a
    separate workspace, while the operator may legitimately edit the repo during a long run.
    """
    before, after = integrity.get("owner_state_before"), integrity.get("owner_state_after")
    if before and after:
        return bool(before.get("data_control") == after.get("data_control"))
    return bool(integrity.get("owner_state_unchanged", True))


def trial_tag(scenario_id: str, sut: str, trial: int) -> str:
    """Neutral directory name: sandbox paths appear in tool output, so they must not leak the
    scenario id (which names the planted flaw)."""
    return hashlib.sha256(f"{scenario_id}|{sut}|{trial}".encode()).hexdigest()[:12]


@dataclass(frozen=True)
class TrialPaths:
    root: Path  # everything for this trial lives here (outside the workspace)
    sandbox: Path  # ALPHA_DATA_DIR
    truth: Path  # hidden truth JSON (never inside sandbox/workspace)
    trajectory: Path
    raw: Path  # raw SUT event stream

    @classmethod
    def create(
        cls, base: Path, scenario_id: str, sut: str, trial: int, *, retry: bool = False
    ) -> TrialPaths:
        root = base / "trials" / trial_tag(scenario_id, sut, trial)
        if retry and root.exists():
            attempts = root / "attempts"
            attempts.mkdir(exist_ok=True)
            for n in range(1, 10000):
                candidate = attempts / f"{n:04}"
                try:
                    candidate.mkdir()
                    root = candidate
                    break
                except FileExistsError:
                    continue
            else:
                raise RuntimeError("attempt limit reached")
        else:
            root.mkdir(parents=True, exist_ok=False)
        (root / "hidden").mkdir()
        (root / "sb").mkdir()
        return cls(
            root=root,
            sandbox=root / "sb",
            truth=root / "hidden" / "truth.json",
            trajectory=root / "trajectory.jsonl",
            raw=root / "raw.jsonl",
        )


def mcp_config(workspace: Path, sandbox: Path) -> dict[str, Any]:
    return {
        "mcpServers": {
            "alpha": {
                "command": str(workspace / ".venv" / "bin" / "alpha-mcp"),
                "args": [],
                "env": {
                    "ALPHA_DATA_DIR": str(sandbox),
                    "ALPHA_BULK_DATA_DIR": str(sandbox / "bulk"),
                    "PATH": f"{workspace / '.venv' / 'bin'}:/usr/bin:/bin",
                },
            }
        }
    }


SUT_TOOLS = "Bash,Read,Grep,Glob,Skill,Task,TodoWrite"


def claude_permissions(workspace: Path, sandbox: Path) -> tuple[list[str], list[str]]:
    allow = [
        "mcp__alpha",
        "Bash(uv run alpha:*)",
        "Bash(alpha:*)",
        f"Read(/{workspace}/**)",
        f"Read(/{sandbox}/**)",
        f"Grep(/{workspace}/**)",
        f"Glob(/{workspace}/**)",
        "Skill",
        "Task",
        "TodoWrite",
    ]
    deny = [
        "Edit",
        "Write",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
        f"Read(/{repo_root()}/**)",
        "Bash(git:*)",
    ]
    return allow, deny
