"""Shared fixtures/helpers for the Claude Code harness test suite.

The harness tests (test_claude_harness_*.py) each need a throwaway git repo
seeded the same way. Building it once per session and copying it per test
keeps the git subprocess cost out of the hot path.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.unit._harness_support import build_harness_repo


@pytest.fixture(scope="session")
def _harness_repo_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_harness_repo(tmp_path_factory.mktemp("harness-repo-template") / "repo")


@pytest.fixture()
def harness_repo(_harness_repo_template: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(_harness_repo_template, dest, symlinks=True)
    return dest


@pytest.fixture()
def repo(harness_repo: Path) -> Path:
    """Short alias every harness test module reads through."""
    return harness_repo
