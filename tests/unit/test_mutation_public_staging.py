"""Selected public CSS dependencies survive isolated mutation staging."""

from __future__ import annotations

import tomllib
from pathlib import Path

import harness_quant
import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "packages/alpha-research/src/alpha_research/data.py"
CSS = ("index.css", "theme.generated.css")


def test_selected_theme_fixtures_are_exact_and_nested_copy_is_configured(tmp_path: Path) -> None:
    staging = tmp_path / "staged"
    harness_quant.stage_mutation_tree(ROOT, [MODULE], staging)
    assert (staging / "tests/unit/test_theme_drift.py").is_file()
    for name in CSS:
        relative = Path("apps/alpha-web/frontend/src") / name
        assert (staging / relative).read_bytes() == (ROOT / relative).read_bytes()
    config = tomllib.loads((staging / "pyproject.toml").read_text())["tool"]["mutmut"]
    assert config["also_copy"] == ["packages", "apps"]
    assert config["pytest_add_cli_args_test_selection"] == ["tests"]
    assert config["only_mutate"] == ["src/alpha_research/data.py"]


def test_unselected_theme_does_not_expand_mutation_staging(tmp_path: Path) -> None:
    staging = tmp_path / "staged"
    harness_quant.stage_mutation_tree(
        ROOT, ["packages/alpha-core/src/alpha_core/types.py"], staging
    )
    config = tomllib.loads((staging / "pyproject.toml").read_text())["tool"]["mutmut"]
    assert not (staging / "tests/unit/test_theme_drift.py").exists()
    assert config["also_copy"] == ["packages"]
    assert not (staging / "apps").exists()


@pytest.mark.parametrize("missing", CSS)
def test_selected_theme_missing_fixture_fails_loudly(tmp_path: Path, missing: str) -> None:
    package = tmp_path / "packages/alpha-research/src/alpha_research"
    package.mkdir(parents=True)
    (package / "data.py").write_text("X = 1\n")
    tests = tmp_path / "tests/unit"
    tests.mkdir(parents=True)
    (tests / "test_theme_drift.py").write_text("import alpha_research\n")
    assets = tmp_path / "apps/alpha-web/frontend/src"
    assets.mkdir(parents=True)
    for name in CSS:
        if name != missing:
            (assets / name).write_text("exact fixture\n")
    with pytest.raises(FileNotFoundError, match=missing.replace(".", r"\.")):
        harness_quant.stage_mutation_tree(tmp_path, [MODULE], tmp_path / "staged")
