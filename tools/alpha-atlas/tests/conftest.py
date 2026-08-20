"""Shared fixtures for the Atlas test suite."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    assert (REPO_ROOT / "CLAUDE.md").is_file(), f"not the ALPHA repo root: {REPO_ROOT}"
    return REPO_ROOT
