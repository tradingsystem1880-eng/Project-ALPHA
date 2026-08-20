"""Shared fixtures for the Atlas test suite."""

from pathlib import Path

import pytest

from alpha_atlas.core.paths import find_repo_root


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return find_repo_root(Path(__file__).resolve())
