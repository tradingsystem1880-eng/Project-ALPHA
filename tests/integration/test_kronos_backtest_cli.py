"""kronos_forecast through the real CLI + engine + gauntlet with a stub forecaster.

The registry's ``_KRONOS_FACTORY`` seam is monkeypatched (mirrors ``data_cmds._ADAPTERS``),
so no torch/weights are needed. NOTE: the monkeypatch does not survive spawn workers —
gauntlet runs here stay serial (``max_workers`` unset).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store
from tests.fixtures.forecast_fixtures import StubForecaster

runner = CliRunner()

_KRONOS_ARGS = [
    "--strategy",
    "kronos_forecast",
    "--param",
    "model=0",
    "--param",
    "context=10",
    "--param",
    "horizon=3",
    "--param",
    "deadband=0",
    "--vol-window",
    "5",
    "--rebalance-every",
    "1",
]


def _patch_factory(monkeypatch: pytest.MonkeyPatch, *, drift: float = 0.02) -> None:
    def factory(params: Any) -> StubForecaster:
        return StubForecaster(drift=drift)

    monkeypatch.setattr("alpha_cli._strategies._KRONOS_FACTORY", factory)


def test_backtest_run_via_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _patch_factory(monkeypatch)
    seed_store(tmp_path, symbol="SPY", n=80)
    r = runner.invoke(app, ["backtest", "run", "SPY", *_KRONOS_ARGS, "--account-type", "MARGIN"])
    assert r.exit_code == 0, r.output
    assert "Traceback" not in r.output
    assert "-> run " in r.output
    # pre-cutoff fixture dates (2020) -> the weight-leakage warning must fire and be recorded
    combined = r.output + (r.stderr or "")
    assert "UPPER BOUND" in combined
    run_id = r.output.split("-> run ")[1].split(":")[0]
    manifest = json.loads((tmp_path / "runs" / run_id / "manifest.json").read_text())
    assert manifest["leakage_warning"] is not None
    assert ["model", 0.0] in [list(p) for p in manifest["params"]["strategy_params"]]
    assert manifest["fills"] > 0


def test_validate_skips_tier1_and_runs_tier2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _patch_factory(monkeypatch)
    seed_store(tmp_path, symbol="SPY", n=120)
    r = runner.invoke(
        app,
        [
            "validate",
            "SPY",
            *_KRONOS_ARGS,
            "--account-type",
            "MARGIN",
            "--train-size",
            "15",
            "--test-size",
            "10",
            "--embargo",
            "0",
            "--tier2-paths",
            "4",
            "--n-resamples",
            "50",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "Traceback" not in r.output
    assert "null pct SKIPPED/" in r.output
    run_id = r.output.split("-> run ")[1].split(":")[0]
    manifest = json.loads((tmp_path / "runs" / run_id / "manifest.json").read_text())

    nulls = {n["tier"]: n for n in manifest["nulls"]}
    assert nulls["returns_level"]["skipped"] is True
    assert "no engine-free Tier-1 surrogate" in nulls["returns_level"]["reason"]
    assert nulls["returns_level"]["passed"] is False
    assert nulls["full_engine"]["skipped"] is False
    assert nulls["full_engine"]["n_paths"] == 4

    outcome = next(o for o in manifest["outcomes"] if o["name"] == "randomized_price_null")
    assert outcome["detail"].get("returns_level_skipped") == 1.0
    # the gate's verdict must equal the full-engine tier's (Tier-1 neither passes nor vetoes)
    assert outcome["passed"] == nulls["full_engine"]["passed"]
    assert manifest["leakage_warning"] is not None

    tearsheet = (tmp_path / "runs" / run_id / "tearsheet.html").read_text()
    assert "SKIPPED" in tearsheet
