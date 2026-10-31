"""Importable helpers shared by the Claude Code harness test suite.

conftest.py fixtures aren't importable, so the plain-function/constant half of
the shared harness test scaffolding lives here instead; conftest.py's
`harness_repo` fixture builds on top of `git`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_harness_repo(root: Path) -> Path:
    """Seed the disposable repository copied by harness tests."""
    root.mkdir()
    git(root, "-c", "maintenance.auto=false", "init", "--quiet")
    # Detached maintenance can remove Git files while the session template is copied.
    git(root, "config", "--local", "maintenance.auto", "false")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text(".claude/state/\n.alpha/state/\n")
    (root / "tracked.py").write_text("x = 1\n")
    (root / "README.md").write_text("# Fixture\n\nHarness test repository.\n")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "chore: init")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    return root


def pass_full_gate(repo: Path, monkeypatch: Any, *, with_readme: bool = True) -> None:
    """Stamp ``repo`` through the real full-gate path with every command succeeding."""
    import gate
    import gate_components

    monkeypatch.setattr(gate, "_env_runner", lambda *args, **kwargs: (True, 0.0, ""))
    assert gate_components.run_full(repo) == 0
    if with_readme:
        import json

        import readme_review

        scope = readme_review.context(repo)
        payload = {
            "reviewed_tree_hash": gate.compute_tree_hash(repo),
            "disposition": "updated" if "README.md" in scope["paths"] else "no_change",
            "rationale": "Synthetic fixture review: no new reader impact beyond test setup.",
        }
        assert gate.attest(repo, "readme", json.dumps(payload)) == 0


def git(cwd: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=check,
    )
    return result.stdout.strip()


def hook_payload(cwd: Path | str | None = None, **kwargs: Any) -> dict[str, Any]:
    """A synthetic hook payload; `cwd` is added only when a test needs it."""
    base: dict[str, Any] = {"session_id": "s1", "hook_event_name": "test"}
    if cwd is not None:
        base["cwd"] = str(cwd)
    base.update(kwargs)
    return base
