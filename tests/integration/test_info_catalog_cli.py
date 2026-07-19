"""``alpha info``/``alpha data symbols`` catalogs — the CLI's machine-readable projections.

The workstation reads these to build its strategy picker + dynamic new-run form, so this locks the
shapes and (critically) that command defaults come from the real Typer signatures, not a duplicate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()


def test_info_bare_still_prints_settings() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "alpha-core" in result.stdout and "data_dir=" in result.stdout


def test_info_strategies_json() -> None:
    result = runner.invoke(app, ["info", "strategies", "--json"])
    assert result.exit_code == 0
    by_name = {s["name"]: s for s in json.loads(result.stdout)}
    assert {"ts_momentum", "ma_crossover", "breakout", "kronos"} <= set(by_name)
    fast = next(p for p in by_name["ma_crossover"]["params"] if p["name"] == "fast")
    assert fast["default"] == 21 and fast["type"] == "int"
    assert by_name["ts_momentum"]["params"] == []  # only first-class RunSpec flags
    assert by_name["ts_momentum"]["has_tier1_surrogate"] is True
    assert by_name["ts_momentum"]["supports_live_paper"] is True
    assert by_name["ma_crossover"]["supports_live_paper"] is True
    assert by_name["breakout"]["supports_live_paper"] is True
    assert by_name["kronos"]["has_tier1_surrogate"] is True  # replay surrogate off the signal cache
    assert by_name["kronos"]["supports_live_paper"] is False


def test_info_commands_json_defaults_from_signature() -> None:
    result = runner.invoke(app, ["info", "commands", "--json"])
    assert result.exit_code == 0
    catalog = {c["id"]: c for c in json.loads(result.stdout)}
    assert "backtest run" in catalog and "validate" in catalog
    opts = {o["name"]: o for o in catalog["backtest run"]["options"]}
    assert opts["lookback"]["default"] == 252  # from the Typer signature, not a duplicate table
    assert any(a["name"] == "symbol" for a in catalog["backtest run"]["args"])


def test_data_symbols_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY")
    result = runner.invoke(app, ["data", "symbols", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"symbols": ["SPY"]}
