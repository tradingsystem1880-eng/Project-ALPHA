"""Supported lightweight seams shared by CLI, MCP, and web."""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from alpha_cli import RUN_DIRS
from alpha_cli.catalog import COMMAND_RUN_TYPES, known_strategies, strategy_params
from alpha_cli.run_store import find_run_dir, read_manifest, valid_run_id
from alpha_core import DataError


def test_catalog_is_canonical_and_exposes_exclusive_bounds() -> None:
    assert known_strategies() == [
        "breakout",
        "kronos",
        "ma_crossover",
        "mean_reversion",
        "ts_momentum",
    ]
    entry_z = next(p for p in strategy_params("mean_reversion") if p["name"] == "entry_z")
    assert entry_z["min"] == 0.0
    assert entry_z["min_exclusive"] is True
    assert COMMAND_RUN_TYPES["forecast eval"] == "forecast"


def test_run_store_validates_discovers_and_reads(tmp_path: Path) -> None:
    data_dir = tmp_path
    run_id = "0123456789abcdef"
    rdir = data_dir / "runs" / run_id
    rdir.mkdir(parents=True)
    (rdir / "manifest.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
    assert valid_run_id(run_id)
    assert not valid_run_id("../not-a-run")
    assert find_run_dir(data_dir, run_id) == rdir
    assert find_run_dir(data_dir, "../not-a-run") is None
    assert read_manifest(rdir) == {"run_id": run_id}
    (rdir / "manifest.json").write_text("{")
    with pytest.raises(DataError, match="corrupt"):
        read_manifest(rdir)


def test_surface_seams_do_not_import_heavy_numerical_stacks() -> None:
    code = (
        "import sys; import alpha_cli.catalog, alpha_cli.run_store; "
        "bad={'numpy','scipy','torch','nautilus_trader','alpha_validation'} & set(sys.modules); "
        "raise SystemExit(','.join(sorted(bad)) if bad else 0)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize(
    ("distribution", "module"),
    [
        ("alpha-core", "alpha_core"),
        ("alpha-data", "alpha_data"),
        ("alpha-strategies", "alpha_strategies"),
        ("alpha-backtest", "alpha_backtest"),
        ("alpha-validation", "alpha_validation"),
        ("alpha-forecast", "alpha_forecast"),
        ("alpha-options", "alpha_options"),
        ("alpha-screener", "alpha_screener"),
        ("alpha-cli", "alpha_cli"),
        ("alpha-mcp", "alpha_mcp"),
        ("alpha-web", "alpha_web"),
    ],
)
def test_versions_come_from_installed_metadata(distribution: str, module: str) -> None:
    imported = __import__(module)
    assert imported.__version__ == version(distribution) == "1.0.0"


def test_run_dirs_reexport_is_preserved() -> None:
    assert RUN_DIRS == ("runs", "portfolio", "cross_sectional", "optim", "propfirm", "forecast")
