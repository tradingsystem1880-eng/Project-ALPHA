"""Mechanical checks for the empty alpha-study package seam."""

from __future__ import annotations

import inspect
import tomllib
from pathlib import Path

import alpha_study

ROOT = Path(__file__).parents[3]


def test_empty_package_exports_version_without_runtime_composition() -> None:
    source = inspect.getsource(alpha_study)

    assert alpha_study.__version__ == "1.0.0"
    assert "alpha_cli" not in source
    assert "alpha_mcp" not in source
    assert "alpha_web" not in source
    assert "alpha_strategies" not in source
    assert "alpha_backtest" not in source
    assert "alpha_validation" not in source


def test_package_metadata_declares_only_approved_composition_inputs() -> None:
    metadata = tomllib.loads((ROOT / "packages" / "alpha-study" / "pyproject.toml").read_text())

    assert metadata["project"]["name"] == "alpha-study"
    assert metadata["project"]["version"] == "1.0.0"
    assert set(metadata["project"]["dependencies"]) == {
        "alpha-core",
        "alpha-data",
        "alpha-patterns",
        "alpha-research",
    }
