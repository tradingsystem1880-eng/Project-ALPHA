"""Shared fixtures/helpers for the Claude Code harness test suite.

The harness tests (test_claude_harness_*.py) each need a throwaway git repo
seeded the same way. Building it once per session and copying it per test
keeps the git subprocess cost out of the hot path.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.unit._harness_support import git


@pytest.fixture(scope="session")
def _harness_repo_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("harness-repo-template") / "repo"
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text(".claude/state/\n")
    (root / "tracked.py").write_text("x = 1\n")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "chore: init")
    return root


@pytest.fixture()
def harness_repo(_harness_repo_template: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(_harness_repo_template, dest, symlinks=True)
    return dest


@pytest.fixture()
def repo(harness_repo: Path) -> Path:
    """Short alias every harness test module reads through."""
    return harness_repo
