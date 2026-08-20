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
